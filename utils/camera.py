import cv2
import platform
import threading

class CameraManager:
    """
    Webcam manager with auto-resolution setting, central ROI extraction,
    and crosshair/stencil overlay.
    """
    def __init__(self, camera_id=None, target_width=1280, target_height=720, roi_size=280):
        self._lock = threading.RLock()
        # Support environment variable override: CAMERA_SOURCE or CAMERA_ID
        import os
        env_cam = os.environ.get("CAMERA_SOURCE") or os.environ.get("CAMERA_ID")
        if env_cam is not None:
            camera_id = env_cam

        # Parse camera_id: defaults to 0 (Mac built-in camera) to avoid waking iPhone
        if camera_id is None:
            self.camera_id = 0
        else:
            try:
                self.camera_id = int(camera_id)
            except (ValueError, TypeError):
                self.camera_id = str(camera_id).strip()

        self.target_width = target_width
        self.target_height = target_height
        self.roi_size = roi_size
        self.cap = None

    def start(self):
        with self._lock:
            import time
            # If it's a network IP stream (e.g. DroidCam, IP Webcam HTTP stream)
            if isinstance(self.camera_id, str) and (self.camera_id.startswith("http://") or self.camera_id.startswith("https://") or self.camera_id.startswith("rtsp://")):
                print(f"[Camera] Connecting to Network IP Camera: {self.camera_id}...")
                self.cap = cv2.VideoCapture(self.camera_id)
            else:
                # Physical camera device index (0 = built-in, 1 = iPhone Continuity or external)
                if str(self.camera_id) == "1":
                    print("[Camera] User explicitly selected iPhone Camera (Device 1). Connecting via AVFoundation...")
                else:
                    print(f"[Camera] Connecting to Camera Device {self.camera_id}...")

                backend = cv2.CAP_AVFOUNDATION if platform.system() == 'Darwin' else cv2.CAP_ANY
                self.cap = cv2.VideoCapture(self.camera_id, backend)
                
                # Request desired resolution
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)
                
                if not self.cap.isOpened():
                    # Fallback to default backend
                    self.cap = cv2.VideoCapture(self.camera_id)
                
                # Give Continuity Camera handshake time only if iPhone is explicitly chosen
                if self.cap.isOpened() and str(self.camera_id) == "1":
                    time.sleep(0.4)
                    for _ in range(5):
                        ret, _ = self.cap.read()
                        if ret:
                            break
                        time.sleep(0.1)
                
            if not self.cap or not self.cap.isOpened():
                if self.camera_id != 0:
                    print(f"[Camera] Camera '{self.camera_id}' unavailable, falling back to 0...")
                    self.camera_id = 0
                    return self.start()
                raise RuntimeError(f"Could not open camera '{self.camera_id}'. Check connection, IP address, or permissions.")
                
            print(f"[Camera] Opened camera source '{self.camera_id}' successfully.")
            return True

    def read_frame(self):
        with self._lock:
            if self.cap is None or not self.cap.isOpened():
                return False, None
            return self.cap.read()

    def get_roi_box(self, frame_shape):
        """
        Calculates center ROI box (x1, y1, x2, y2) based on frame dimensions.
        """
        h, w = frame_shape[:2]
        size = min(self.roi_size, min(h, w) - 40)
        cx, cy = w // 2, h // 2
        x1 = cx - size // 2
        y1 = cy - size // 2
        x2 = x1 + size
        y2 = y1 + size
        return x1, y1, x2, y2

    def extract_roi(self, frame):
        """Returns the cropped ROI image."""
        x1, y1, x2, y2 = self.get_roi_box(frame.shape)
        return frame[y1:y2, x1:x2].copy()

    def release(self):
        with self._lock:
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None

    def switch_camera(self, new_camera_id):
        """Switches active camera to a new index or IP URL stream on the fly."""
        with self._lock:
            self.release()
            try:
                self.camera_id = int(new_camera_id)
            except (ValueError, TypeError):
                self.camera_id = str(new_camera_id).strip()
            return self.start()

    def set_roi_size(self, new_size):
        """Dynamically adjusts inspection zone ROI box dimension."""
        self.roi_size = max(100, min(640, int(new_size)))
        return self.roi_size

    @staticmethod
    def list_available_cameras(max_check=4):
        """Scans connected local video devices without waking up the iPhone."""
        available = [0]
        # On macOS, check if iPhone camera is paired passively via system profiler
        if platform.system() == 'Darwin':
            try:
                import subprocess
                res = subprocess.run(['system_profiler', 'SPCameraDataType'], capture_output=True, text=True, timeout=1.0)
                if 'iPhone' in res.stdout:
                    available.append(1)
            except Exception:
                pass
        return available
