import os
import pickle
import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms
from sklearn.neighbors import NearestNeighbors
from scipy.ndimage import gaussian_filter

from model.feature_extractor import ResNet18FeatureExtractor

class PatchCoreDetector:
    """
    Industrial-grade lightweight PatchCore Anomaly Detector.
    Designed for real-time inference on Apple Silicon / CPU.
    """
    def __init__(self, device=None, coreset_ratio=0.1, max_memory_patches=2500, threshold=0.55):
        if device is None:
            if torch.backends.mps.is_available():
                self.device = torch.device('mps')
            elif torch.cuda.is_available():
                self.device = torch.device('cuda')
            else:
                self.device = torch.device('cpu')
        else:
            self.device = torch.device(device)
            
        print(f"[PatchCore] Using computation device: {self.device}")
        
        self.feature_extractor = ResNet18FeatureExtractor(device=self.device)
        self.coreset_ratio = coreset_ratio
        self.max_memory_patches = max_memory_patches
        self.threshold = threshold
        
        # Image preprocessing pipeline (Standard ImageNet normalization)
        self.transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225])
        ])
        
        self.memory_bank = None  # (M, D) numpy array
        self.nn_model = None     # NearestNeighbors search index
        self.patch_resolution = None
        self.min_dist = None
        self.max_dist = None

    def preprocess(self, img_bgr_or_rgb, input_size=(224, 224), is_bgr=True):
        """Preprocesses image from OpenCV (BGR or RGB) into normalized PyTorch tensor."""
        import cv2
        if is_bgr:
            img_rgb = cv2.cvtColor(img_bgr_or_rgb, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = img_bgr_or_rgb.copy()
            
        img_resized = cv2.resize(img_rgb, input_size, interpolation=cv2.INTER_AREA)
        tensor = self.transform(img_resized).unsqueeze(0)  # Shape: (1, 3, H, W)
        return tensor

    def _coreset_subsampling(self, features, target_size):
        """
        Greedy K-Center approximation for Coreset Selection.
        Ensures diverse and representative coverage of normal patch features.
        """
        N, D = features.shape
        if N <= target_size:
            return features
            
        # Select first point at random
        selected_indices = [np.random.randint(0, N)]
        
        # Min distances to current selected set
        min_distances = np.linalg.norm(features - features[selected_indices[0]], axis=1)
        
        # Iteratively pick points with maximum min-distance
        for _ in range(1, target_size):
            next_idx = np.argmax(min_distances)
            selected_indices.append(next_idx)
            
            # Update min distances with the new point
            dist_to_new = np.linalg.norm(features - features[next_idx], axis=1)
            min_distances = np.minimum(min_distances, dist_to_new)
            
        return features[selected_indices]

    def fit(self, normal_images, is_bgr=True):
        """
        Fits the PatchCore memory bank using normal sample images.
        normal_images: list of numpy arrays (e.g. from OpenCV or file paths)
        """
        if len(normal_images) == 0:
            raise ValueError("At least 1 normal image is required to train PatchCore!")
            
        print(f"[PatchCore] Extracting features from {len(normal_images)} normal samples...")
        patch_list = []
        
        for img in normal_images:
            tensor = self.preprocess(img, is_bgr=is_bgr)
            with torch.no_grad():
                patch_emb, self.patch_resolution = self.feature_extractor(tensor)
                # patch_emb: (1, Num_patches, D)
                patches_np = patch_emb.squeeze(0).cpu().numpy()
                patch_list.append(patches_np)
                
        all_patches = np.concatenate(patch_list, axis=0) # (Total_patches, D)
        total_p, feat_dim = all_patches.shape
        print(f"[PatchCore] Total normal patch vectors collected: {total_p} (dim: {feat_dim})")
        
        # Calculate target memory size
        target_size = min(self.max_memory_patches, max(200, int(total_p * self.coreset_ratio)))
        
        print(f"[PatchCore] Performing Coreset Subsampling to {target_size} landmark patches...")
        self.memory_bank = self._coreset_subsampling(all_patches, target_size)
        
        # Pre-convert memory bank to GPU tensor for high-speed tensor distance
        self.memory_bank_tensor = torch.from_numpy(self.memory_bank).to(self.device)

        # Rigorous Cross-Sample Baseline Calibration
        print("[PatchCore] Calibrating statistical baseline across normal samples on GPU...")
        sample_scores = []
        for img in normal_images:
            tensor = self.preprocess(img, is_bgr=is_bgr)
            with torch.no_grad():
                p_emb, _ = self.feature_extractor(tensor)
                p_gpu = p_emb.squeeze(0)
                # Compute distance on GPU
                d_gpu = torch.cdist(p_gpu, self.memory_bank_tensor).min(dim=1)[0]
                dists = d_gpu.cpu().numpy()
            top_k = max(1, int(len(dists) * 0.01))
            top_d = np.partition(dists.squeeze(), -top_k)[-top_k:]
            sample_scores.append(float(np.mean(top_d)))
            
        sample_scores = np.array(sample_scores)
        self.normal_mean = float(np.mean(sample_scores))
        self.normal_std = float(np.std(sample_scores))
        self.normal_max = float(np.max(sample_scores))
        
        # 3-Sigma Statistical Control Limit above normal population
        # With L2-normalized unit vectors, distances are bounded [0, 2]
        sigma_margin = max(self.normal_std * 3.0, self.normal_max * 0.18, 0.06)
        self.threshold_raw = float(self.normal_max + sigma_margin)
        
        print(f"[PatchCore] Normal Baseline -> Mean: {self.normal_mean:.4f}, Max: {self.normal_max:.4f}, Std: {self.normal_std:.4f}")
        print(f"[PatchCore] Baseline Calibrated Raw Threshold: {self.threshold_raw:.4f} (Bank: {self.memory_bank.shape[0]} patches)")
        return True

    def predict(self, img, is_bgr=True):
        """
        Evaluates an image for anomalies.
        Returns:
            anomaly_score: normalized float in [0.0, 1.0] (0.50 corresponds to decision threshold)
            raw_score: true Euclidean distance in patch feature space
            anomaly_map: 2D numpy array [0.0, 1.0] (H, W) corresponding to input image dimensions
            is_anomaly: boolean verdict based on threshold
        """
        if self.memory_bank is None:
            raise RuntimeError("Model is not trained yet! Please call fit() or load() first.")
            
        orig_h, orig_w = img.shape[:2]
        tensor = self.preprocess(img, is_bgr=is_bgr)
        
        with torch.no_grad():
            patch_emb, (hp, wp) = self.feature_extractor(tensor)
            patches_gpu = patch_emb.squeeze(0)
            
            # Ultra-fast GPU Tensor Distance (8ms on Apple Silicon MPS)
            if not hasattr(self, 'memory_bank_tensor') or self.memory_bank_tensor is None:
                self.memory_bank_tensor = torch.from_numpy(self.memory_bank).to(self.device)
                
            dists_gpu = torch.cdist(patches_gpu, self.memory_bank_tensor).min(dim=1)[0]
            distances = dists_gpu.cpu().numpy()
            
        # Spatial heatmap map
        dist_map = distances.reshape(hp, wp)
        
        # Image-level anomaly score: top 1% max distance
        top_k = max(1, int(len(distances) * 0.01))
        top_distances = np.partition(distances, -top_k)[-top_k:]
        raw_score = float(np.mean(top_distances))
        
        # Decoupled Objective Anomaly Score in [0.0, 1.0]:
        # At raw_score == threshold_raw, normalized_score is exactly 0.50 (50%)
        # Below baseline threshold: 0.00 ~ 0.49 (Normal spectrum)
        # Above baseline threshold: 0.50 ~ 1.00 (Defect spectrum)
        if self.threshold_raw > 1e-4:
            normalized_score = float(np.clip(raw_score / (self.threshold_raw * 2.0), 0.0, 1.0))
        else:
            normalized_score = 0.0
            
        # Decision boundary set by operator threshold slider (default 0.50)
        is_anomaly = normalized_score >= self.threshold
        
        # Smooth and upscale heatmap
        import cv2
        smoothed_map = gaussian_filter(dist_map, sigma=1.2)
        
        # Normalize heatmap: highlight regions exceeding normal baseline
        map_min = self.normal_mean
        map_max = max(self.threshold_raw * 1.15, float(smoothed_map.max()))
        norm_map = (smoothed_map - map_min) / max(1e-4, (map_max - map_min))
        norm_map = np.clip(norm_map, 0.0, 1.0)
            
        anomaly_map = cv2.resize(norm_map, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
        
        return {
            'anomaly_score': normalized_score,
            'raw_score': raw_score,
            'effective_threshold': self.threshold_raw,
            'threshold': self.threshold,
            'is_anomaly': is_anomaly,
            'anomaly_map': anomaly_map
        }

    def save(self, file_path):
        """Saves trained memory bank and parameters to disk."""
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        data = {
            'memory_bank': self.memory_bank,
            'patch_resolution': self.patch_resolution,
            'normal_mean': getattr(self, 'normal_mean', 0.25),
            'normal_std': getattr(self, 'normal_std', 0.04),
            'normal_max': getattr(self, 'normal_max', 0.35),
            'threshold_raw': getattr(self, 'threshold_raw', 0.45),
            'threshold': self.threshold
        }
        with open(file_path, 'wb') as f:
            pickle.dump(data, f)
        print(f"[PatchCore] Saved model successfully to {file_path}")

    def load(self, file_path):
        """Loads trained memory bank and parameters from disk."""
        if not os.path.exists(file_path):
            return False
        with open(file_path, 'rb') as f:
            data = pickle.load(f)
        self.memory_bank = data['memory_bank']
        self.patch_resolution = data['patch_resolution']
        self.normal_mean = data.get('normal_mean', 0.25)
        self.normal_std = data.get('normal_std', 0.04)
        self.normal_max = data.get('normal_max', 0.35)
        self.threshold_raw = data.get('threshold_raw', 0.45)
        self.threshold = data.get('threshold', self.threshold)
        
        # Rebuild GPU memory bank tensor
        self.memory_bank_tensor = torch.from_numpy(self.memory_bank).to(self.device)
        print(f"[PatchCore] Loaded model from {file_path} (Bank: {len(self.memory_bank)} patches on {self.device})")
        return True
