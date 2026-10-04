import cv2
import platform
import threading
import time

class CameraManager:
    """
    Industrial Webcam & Optical Sensor Manager with auto-resolution setting,
    central ROI extraction, and Apple Continuity Camera (iPhone) support.
    """
    def __init__(self, camera_id=None, target_width=1280, target_height=720, roi_size=280):
        self._lock = threading.RLock()
        self._is_switching = False

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
        self.roi_offset_x = 0
        self.roi_offset_y = 0
        self.cap = None

    @property
    def is_switching(self):
        return self._is_switching

    def is_opened(self):
        with self._lock:
            return self.cap is not None and self.cap.isOpened()

    def start(self):
        with self._lock:
            # If it's a network IP stream (e.g. DroidCam, IP Webcam HTTP stream)
            if isinstance(self.camera_id, str) and (self.camera_id.startswith("http://") or self.camera_id.startswith("https://") or self.camera_id.startswith("rtsp://")):
                print(f"[Camera] Connecting to Network IP Camera: {self.camera_id}...")
                self.cap = cv2.VideoCapture(self.camera_id)
            elif str(self.camera_id) == "1":
                # Explicit iPhone Continuity Camera (Device Index 1)
                print("[Camera] User explicitly selected iPhone Camera (Device 1). Connecting via AVFoundation...")
                backend = cv2.CAP_AVFOUNDATION if platform.system() == 'Darwin' else cv2.CAP_ANY
                self.cap = cv2.VideoCapture(1, backend)
                if not self.cap.isOpened():
                    self.cap = cv2.VideoCapture(1)

                if not self.cap.isOpened():
                    raise RuntimeError("iPhone 연속성 카메라(장치 1)를 열 수 없습니다. iPhone의 잠금을 해제하고, Bluetooth와 Wi-Fi가 켜져 있는지 확인해주세요.")

                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)

                # macOS Continuity Camera handshake requires 1.5 ~ 2.5 seconds
                # Poll up to 20 times (every 0.15s = up to 3.0 seconds) for first frame
                got_frame = False
                for attempt in range(20):
                    time.sleep(0.15)
                    ret, test_f = self.cap.read()
                    if ret and test_f is not None and test_f.size > 0:
                        got_frame = True
                        print(f"[Camera] iPhone Camera ready on attempt {attempt+1} ({test_f.shape[1]}x{test_f.shape[0]}).")
                        break

                if not got_frame:
                    self.release()
                    raise RuntimeError("iPhone 카메라 신호 대기 시간 초과. iPhone 잠금을 해제하고 화면을 켠 후 다시 선택해주세요. (USB 케이블 연결 시 즉시 연결됩니다)")
            else:
                # Standard physical camera index (0 = built-in webcam, 2 = external USB)
                print(f"[Camera] Connecting to Camera Device {self.camera_id}...")
                backend = cv2.CAP_AVFOUNDATION if platform.system() == 'Darwin' else cv2.CAP_ANY
                self.cap = cv2.VideoCapture(self.camera_id, backend)

                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)

                if not self.cap.isOpened():
                    self.cap = cv2.VideoCapture(self.camera_id)

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
            if self._is_switching or self.cap is None or not self.cap.isOpened():
                return False, None
            return self.cap.read()

    def get_roi_box(self, frame_shape):
        """
        Calculates inspection zone ROI box (x1, y1, x2, y2) based on frame dimensions,
        supporting screen-filling scale and 4-way (Left/Right/Up/Down) positional movement.
        """
        h, w = frame_shape[:2]
        size = min(self.roi_size, min(h, w))

        # Base center with X/Y directional offset
        cx = (w // 2) + self.roi_offset_x
        cy = (h // 2) + self.roi_offset_y

        half = size // 2
        x1 = cx - half
        y1 = cy - half
        x2 = x1 + size
        y2 = y1 + size

        # Soft clamp so box stays inside camera frame while allowing edge positioning
        if x1 < 0:
            shift = -x1
            x1 = 0
            x2 = min(w, x2 + shift)
        if y1 < 0:
            shift = -y1
            y1 = 0
            y2 = min(h, y2 + shift)
        if x2 > w:
            shift = x2 - w
            x2 = w
            x1 = max(0, x1 - shift)
        if y2 > h:
            shift = y2 - h
            y2 = h
            y1 = max(0, y1 - shift)

        x1 = max(0, int(x1))
        y1 = max(0, int(y1))
        x2 = min(w, max(x1 + 10, int(x2)))
        y2 = min(h, max(y1 + 10, int(y2)))
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
        """
        Safely switches active camera to a new index or IP URL stream on the fly.
        Thread-safe and guaranteed not to deadlock or leave cap in undefined state.
        """
        with self._lock:
            self._is_switching = True
            old_id = self.camera_id
            try:
                self.release()
                try:
                    self.camera_id = int(new_camera_id)
                except (ValueError, TypeError):
                    self.camera_id = str(new_camera_id).strip()
                self.start()
                return True
            except Exception as e:
                print(f"[Camera Switch Error] Failed to switch to '{new_camera_id}': {e}")
                # Revert safely to old camera or 0
                self.camera_id = old_id if old_id != new_camera_id else 0
                try:
                    self.start()
                except Exception:
                    pass
                raise e
            finally:
                self._is_switching = False

    def set_roi_size(self, new_size):
        """Dynamically adjusts inspection zone ROI dimension (up to full frame size)."""
        with self._lock:
            self.roi_size = max(80, min(1080, int(new_size)))
            return self.roi_size

    def set_roi_offset(self, offset_x=None, offset_y=None):
        """Dynamically adjusts 4-directional (Left/Right, Up/Down) center offset."""
        with self._lock:
            if offset_x is not None:
                self.roi_offset_x = max(-500, min(500, int(offset_x)))
            if offset_y is not None:
                self.roi_offset_y = max(-400, min(400, int(offset_y)))
            return self.roi_offset_x, self.roi_offset_y

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
