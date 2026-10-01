import cv2
import numpy as np

class ComponentDetector:
    """
    Industrial-grade Machine Vision Presence & Alignment Module.
    Works universally across all electronic components (LEDs, PCBs, ICs, connectors)
    by evaluating statistical gradient density and structural variance.
    """
    def __init__(self, min_std_dev=14.0, min_edge_density=0.005, min_dyn_range=30.0):
        self.min_std_dev = min_std_dev
        self.min_edge_density = min_edge_density
        self.min_dyn_range = min_dyn_range
        
        self.last_crop = None
        self.consecutive_stable_frames = 0
        self.inspected_current_part = False

    def check_presence(self, roi_bgr):
        """
        Analyzes the inspection zone to determine if a physical component is present.
        Returns:
            is_present: bool
            component_bbox: (x1, y1, x2, y2)
            isolated_crop: 224x224 normalized image for feature extraction
            status_text: descriptive industrial status
        """
        if roi_bgr is None or roi_bgr.size == 0:
            return False, None, None, "NO_IMAGE"

        H, W = roi_bgr.shape[:2]
        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        
        # 1. Statistical Luminance Variance
        std_dev = float(np.std(gray))
        
        # 2. Dynamic Contrast Range
        dyn_range = float(gray.max() - gray.min())
        
        # 3. High-Frequency Structural Gradient (Canny Edge Energy)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 35, 110)
        edge_density = float(np.count_nonzero(edges) / edges.size)

        # Decision Boundary:
        # Uniform backgrounds (empty conveyor, desk, ceiling) have near-zero variance
        is_present = (std_dev >= self.min_std_dev) and (edge_density >= self.min_edge_density) and (dyn_range >= self.min_dyn_range)

        if not is_present:
            self.inspected_current_part = False
            return False, None, None, "ZONE_CLEAR_STANDBY"

        # Locate component center of mass / bounding area within ROI
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) > 0:
            # Combine all significant contours to encompass the component
            all_pts = []
            for c in contours:
                if cv2.contourArea(c) > 50:
                    all_pts.append(c.reshape(-1, 2))
                    
            if len(all_pts) > 0:
                pts = np.vstack(all_pts)
                x, y, w, h = cv2.boundingRect(pts)
                # Apply balanced padding
                pad_x = int(w * 0.15)
                pad_y = int(h * 0.15)
                x1 = max(0, x - pad_x)
                y1 = max(0, y - pad_y)
                x2 = min(W, x + w + pad_x)
                y2 = min(H, y + h + pad_y)
                crop = roi_bgr[y1:y2, x1:x2]
            else:
                crop = roi_bgr
                x1, y1, x2, y2 = 0, 0, W, H
        else:
            crop = roi_bgr
            x1, y1, x2, y2 = 0, 0, W, H

        if crop.size == 0 or crop.shape[0] < 30 or crop.shape[1] < 30:
            crop = roi_bgr
            x1, y1, x2, y2 = 0, 0, W, H

        # Canonical standardized frame for PatchCore feature extraction:
        # Avoids erratic contour jitter and aspect-ratio warping
        canonical_inspection_frame = cv2.resize(roi_bgr, (224, 224), interpolation=cv2.INTER_AREA)
        return True, (x1, y1, x2, y2), canonical_inspection_frame, "PART_INSPECTING"

    def check_motion_stability(self, current_crop):
        """
        Ensures the component is stationary before recording an official inspection event.
        """
        if self.last_crop is None:
            self.last_crop = current_crop
            return False

        diff = cv2.absdiff(current_crop, self.last_crop)
        mse = np.mean(diff)
        self.last_crop = current_crop

        if mse < 14.0: # Stable threshold
            self.consecutive_stable_frames += 1
        else:
            self.consecutive_stable_frames = 0
            self.inspected_current_part = False

        return self.consecutive_stable_frames >= 4
