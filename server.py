import os
import sys
import time
import asyncio
import threading
import cv2
import numpy as np
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from contextlib import asynccontextmanager


from model.patchcore import PatchCoreDetector
from utils.camera import CameraManager
from utils.sound import SoundAlert
from utils.detector import ComponentDetector
from arduino.arduino_bridge import ArduinoBridge

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vision_thread
    init_system()
    vision_thread = threading.Thread(target=vision_worker, daemon=True)
    vision_thread.start()
    yield
    if state.cam is not None:
        state.cam.release()

app = FastAPI(title="PUAD // PatchCore Unsupervised Anomaly Detection", version="2.5.0", lifespan=lifespan)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")
TEMPLATES_DIR = os.path.join(WEB_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs("data/normal", exist_ok=True)
os.makedirs("data/models", exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

class SystemState:
    def __init__(self):
        self.model_path = "data/models/patchcore_led.pkl"
        self.normal_dir = "data/normal"
        self.detector = PatchCoreDetector(threshold=0.50)
        self.comp_detector = ComponentDetector()
        self.cam = None
        self.arduino = ArduinoBridge()
        
        self.mode = "ENROLL"  # "ENROLL" or "INSPECT"
        self.auto_inspect = False
        self.manual_trigger_pending = False
        
        self.captured_samples = []
        self.total_tested = 0
        self.pass_count = 0
        self.fail_count = 0
        self.current_score = 0.0
        self.current_verdict = "WAITING"
        self.last_latency = 0.0
        self.current_fps = 0.0
        self.part_present = False
        self.is_paused = False
        self.logs = ["AI Machine Vision Server initialized. Ready."]
        
        # Frames
        self.latest_raw_frame = None
        self.latest_roi_frame = None
        self.latest_heatmap_frame = None
        self.pred_result = None
        
        # WebSocket clients
        self.connected_ws = set()

    def add_log(self, msg: str):
        self.logs.append(msg)
        if len(self.logs) > 6:
            self.logs.pop(0)

state = SystemState()

def init_system():
    # Connect camera
    try:
        state.cam = CameraManager(camera_id=None, target_width=1280, target_height=720, roi_size=280)
        state.cam.start()
        state.add_log("Industrial camera feed online.")
    except Exception as e:
        print(f"[Camera Error] {e}")
        state.add_log(f"Camera warning: {e}")

    # Arduino connection
    def on_ir_trigger():
        state.manual_trigger_pending = True
        state.add_log("Arduino IR Proximity Sensor Trigger received.")
        
    state.arduino.on_trigger_callback = on_ir_trigger
    state.arduino.connect()

    # Load real normal samples from disk
    normal_files = sorted([os.path.join(state.normal_dir, f) for f in os.listdir(state.normal_dir) if f.endswith('.png')])
    for nf in normal_files:
        img = cv2.imread(nf)
        if img is not None:
            state.captured_samples.append(img)

    # Set mode based on whether trained model & samples exist
    if os.path.exists(state.model_path) and len(state.captured_samples) >= 2:
        if state.detector.load(state.model_path):
            state.mode = "INSPECT"
            state.add_log(f"Inspection mode active with {len(state.captured_samples)} enrolled samples.")
    else:
        state.mode = "ENROLL"
        state.add_log("Enrollment mode: Align pristine component in target zone and press [C].")

def vision_worker():
    prev_t = time.time()
    
    while True:
        try:
            if state.is_paused:
                state.current_fps = 0.0
                if state.cam and state.cam.cap is not None:
                    try:
                        state.cam.release()
                        print("[Camera] Hardware successfully released for PAUSE mode.")
                    except Exception as e:
                        print(f"[Camera Release Error] {e}")
                time.sleep(0.12)
                continue

            if state.cam is None or getattr(state.cam, 'is_switching', False):
                time.sleep(0.05)
                continue

            # If unpaused and camera cap was released, safely re-open on this vision thread
            if state.cam.cap is None and not getattr(state.cam, 'is_switching', False):
                try:
                    state.cam.start()
                    print(f"[Camera] Hardware successfully re-opened on source '{state.cam.camera_id}'.")
                except Exception as e:
                    print(f"[Camera Restart Error] {e}")
                    time.sleep(0.5)
                    continue

            # 1. Acquire raw frame
            ret, raw = state.cam.read_frame()
            if not ret or raw is None:
                time.sleep(0.02)
                continue
                
            roi = state.cam.extract_roi(raw)
            state.latest_raw_frame = raw
            state.latest_roi_frame = roi

            # 2. Component Presence & Alignment Detection
            is_present, comp_box, comp_crop, presence_status = state.comp_detector.check_presence(roi)
            state.part_present = is_present

            # 3. Handle Inspection logic
            if state.mode == "INSPECT":
                inspect_target = comp_crop if (is_present and comp_crop is not None) else roi

                trigger_inspection = False
                if state.manual_trigger_pending:
                    trigger_inspection = True
                    state.manual_trigger_pending = False
                elif state.auto_inspect and is_present:
                    is_stable = state.comp_detector.check_motion_stability(inspect_target)
                    if is_stable and not state.comp_detector.inspected_current_part:
                        trigger_inspection = True
                        state.comp_detector.inspected_current_part = True

                if trigger_inspection:
                    t0 = time.time()
                    res = state.detector.predict(inspect_target)
                    state.last_latency = (time.time() - t0) * 1000
                    state.pred_result = res

                    # Generate Continuous / Inspected Heatmap
                    norm_map = res['anomaly_map']
                    heatmap_raw = np.uint8(255 * norm_map)
                    heatmap_color = cv2.applyColorMap(heatmap_raw, cv2.COLORMAP_JET)
                    state.latest_heatmap_frame = cv2.addWeighted(inspect_target, 0.55, heatmap_color, 0.45, 0)

                    state.current_score = res['anomaly_score']
                    is_anomaly = res['is_anomaly']
                    state.current_verdict = "FAIL" if is_anomaly else "PASS"

                    state.total_tested += 1
                    if is_anomaly:
                        state.fail_count += 1
                        state.arduino.send_verdict("FAIL")
                    else:
                        state.pass_count += 1
                        state.arduino.send_verdict("PASS")

                    state.add_log(f"검사 판정: {state.current_verdict} (이상치 점수: {(state.current_score*100):.1f}%)")
                elif not is_present:
                    # Empty inspection zone: Neutral standby display
                    state.current_score = 0.0
                    state.current_verdict = "WAITING"
                    state.latest_heatmap_frame = None
                    state.comp_detector.inspected_current_part = False
                elif state.current_verdict not in ["PASS", "FAIL"]:
                    # Part is present, awaiting Space key trigger
                    state.current_verdict = "READY"
                    state.current_score = 0.0

            elif state.mode == "ENROLL":
                state.current_verdict = "ENROLL"
                state.current_score = 0.0
                state.latest_heatmap_frame = None

            # Calculate FPS
            curr_t = time.time()
            state.current_fps = 1.0 / max(1e-4, (curr_t - prev_t))
            prev_t = curr_t
            
            time.sleep(0.015)
        except Exception as e:
            time.sleep(0.05)

vision_thread = None

# Video streaming generators
def generate_mjpeg_stream(stream_type="main"):
    while True:
        try:
            if state.is_paused:
                if stream_type == "main":
                    frame = np.full((720, 1280, 3), 14, dtype=np.uint8)
                    cv2.rectangle(frame, (240, 250), (1040, 470), (28, 33, 44), -1)
                    cv2.rectangle(frame, (240, 250), (1040, 470), (60, 60, 230), 2)
                    cv2.putText(frame, "PAUSED // OPTICAL SENSOR OFFLINE", (310, 325),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.85, (70, 70, 240), 2, cv2.LINE_AA)
                    cv2.putText(frame, "Inspection paused & camera turned off to save power.", (340, 370),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180, 180, 180), 1, cv2.LINE_AA)
                    cv2.putText(frame, "Click [카메라 켜기 / 검사 재개] on bottom-left to resume.", (330, 415),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 220, 255), 1, cv2.LINE_AA)
                elif stream_type == "roi":
                    frame = np.full((280, 280, 3), 14, dtype=np.uint8)
                    cv2.putText(frame, "CAMERA OFF", (42, 130),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (70, 70, 240), 2, cv2.LINE_AA)
                    cv2.putText(frame, "STANDBY", (78, 165),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.50, (140, 140, 140), 1, cv2.LINE_AA)
                elif stream_type == "heatmap":
                    frame = np.full((280, 280, 3), 14, dtype=np.uint8)
                    cv2.putText(frame, "HEATMAP OFF", (38, 130),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (70, 70, 240), 2, cv2.LINE_AA)
                    cv2.putText(frame, "STANDBY", (78, 165),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.50, (140, 140, 140), 1, cv2.LINE_AA)
                
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                time.sleep(0.15)
                continue

            if stream_type == "main":
                frame = state.latest_raw_frame
                if frame is None:
                    frame = np.full((720, 1280, 3), 20, dtype=np.uint8)
                else:
                    frame = frame.copy()
                    h, w = frame.shape[:2]
                    x1, y1, x2, y2 = state.cam.get_roi_box((h, w)) if state.cam else (w//2-140, h//2-140, w//2+140, h//2+140)
                    
                    # Industrial status color in BGR
                    # Standby: High-contrast Ice Cyan (255, 195, 30) | Normal: Optical Emerald (30, 225, 60) | Anomaly: Alert Red (30, 30, 255)
                    status_color = (255, 195, 30)
                    if state.mode == "INSPECT":
                        if not state.part_present:
                            status_color = (200, 180, 150) # Precision Standby Slate
                        elif state.current_verdict == "FAIL":
                            status_color = (30, 30, 255)   # Vivid Alert Red
                        else:
                            status_color = (30, 225, 60)   # Optical Emerald
                    
                    # 1. Bolder boundary frame (2px thickness, high visibility)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), status_color, 2, cv2.LINE_AA)
                    
                    # 2. Precision Corner Brackets (4px heavy thickness for high visibility)
                    c_len = max(24, min(42, (x2 - x1) // 5))
                    # Top-Left
                    cv2.line(frame, (x1, y1), (x1 + c_len, y1), status_color, 4, cv2.LINE_AA)
                    cv2.line(frame, (x1, y1), (x1, y1 + c_len), status_color, 4, cv2.LINE_AA)
                    # Top-Right
                    cv2.line(frame, (x2, y1), (x2 - c_len, y1), status_color, 4, cv2.LINE_AA)
                    cv2.line(frame, (x2, y1), (x2, y1 + c_len), status_color, 4, cv2.LINE_AA)
                    # Bottom-Left
                    cv2.line(frame, (x1, y2), (x1 + c_len, y2), status_color, 4, cv2.LINE_AA)
                    cv2.line(frame, (x1, y2), (x1, y2 - c_len), status_color, 4, cv2.LINE_AA)
                    # Bottom-Right
                    cv2.line(frame, (x2, y2), (x2 - c_len, y2), status_color, 4, cv2.LINE_AA)
                    cv2.line(frame, (x2, y2), (x2, y2 - c_len), status_color, 4, cv2.LINE_AA)
                    
                    # 3. Center reticle (2px thickness, 12px cross)
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    cv2.line(frame, (cx - 6, cy), (cx + 6, cy), status_color, 2, cv2.LINE_AA)
                    cv2.line(frame, (cx, cy - 6), (cx, cy + 6), status_color, 2, cv2.LINE_AA)
                                
            elif stream_type == "roi":
                frame = state.latest_roi_frame
                if frame is None:
                    frame = np.full((280, 280, 3), 20, dtype=np.uint8)
                else:
                    frame = frame.copy()
            elif stream_type == "heatmap":
                frame = state.latest_heatmap_frame
                if frame is None:
                    frame = np.full((280, 280, 3), 20, dtype=np.uint8)
                    if state.mode == "ENROLL":
                        msg = "ENROLL MODE [PRESS C]"
                        cv2.putText(frame, msg, (20, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (150, 150, 150), 2)
                    elif state.part_present:
                        msg = "READY [PRESS SPACE]"
                        cv2.putText(frame, msg, (15, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (150, 150, 150), 2)
                    else:
                        msg = "AWAITING PART..."
                        cv2.putText(frame, msg, (35, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (150, 150, 150), 2)
                    
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                continue
                
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.033)
        except Exception:
            time.sleep(0.05)

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(generate_mjpeg_stream("main"),
                             media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/roi_feed")
async def roi_feed():
    return StreamingResponse(generate_mjpeg_stream("roi"),
                             media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/heatmap_feed")
async def heatmap_feed():
    return StreamingResponse(generate_mjpeg_stream("heatmap"),
                             media_type="multipart/x-mixed-replace; boundary=frame")

# REST API endpoints
class ThresholdPayload(BaseModel):
    threshold: float

@app.post("/api/capture")
async def api_capture():
    if state.latest_roi_frame is not None:
        roi = state.latest_roi_frame.copy()
        # Save canonical 280x280 optical inspection window
        save_target = cv2.resize(roi, (280, 280), interpolation=cv2.INTER_AREA)
        state.captured_samples.append(save_target)
        idx = len(state.captured_samples)
        path = os.path.join(state.normal_dir, f"normal_sample_{idx:02d}.png")
        cv2.imwrite(path, save_target)
        state.add_log(f"Enrolled pristine normal sample #{idx}")
        return {"status": "ok", "samples_count": len(state.captured_samples)}
    return {"status": "error", "message": "No frame available"}

@app.post("/api/train")
async def api_train():
    if len(state.captured_samples) < 2:
        return {"status": "error", "message": "Need at least 2 normal samples to train!"}
    state.add_log(f"Compiling PatchCore memory bank from {len(state.captured_samples)} samples...")
    t0 = time.time()
    state.detector.fit(state.captured_samples)
    state.detector.save(state.model_path)
    dur = time.time() - t0
    state.mode = "INSPECT"
    state.add_log(f"Memory Bank trained in {dur:.2f}s! Active inspection started.")
    return {"status": "ok", "duration": dur}

@app.post("/api/reset")
async def api_reset():
    state.captured_samples = []
    # Clear directory
    for f in os.listdir(state.normal_dir):
        if f.endswith('.png'):
            try:
                os.remove(os.path.join(state.normal_dir, f))
            except Exception:
                pass
    if os.path.exists(state.model_path):
        try:
            os.remove(state.model_path)
        except Exception:
            pass
    state.detector.memory_bank = None
    state.mode = "ENROLL"
    state.total_tested = 0
    state.pass_count = 0
    state.fail_count = 0
    state.current_score = 0.0
    state.current_verdict = "WAITING"
    state.add_log("Reset all sample data. Ready for fresh Enrollment (Press C).")
    return {"status": "ok"}

@app.post("/api/threshold")
async def api_threshold(payload: ThresholdPayload):
    state.detector.threshold = round(float(np.clip(payload.threshold, 0.10, 0.90)), 2)
    state.detector.save(state.model_path)
    state.add_log(f"Threshold set to {state.detector.threshold:.2f} ({(state.detector.threshold*100):.1f}%)")
    return {"status": "ok", "threshold": state.detector.threshold}

@app.post("/api/trigger")
async def api_trigger():
    state.manual_trigger_pending = True
    return {"status": "ok"}

class RoiPayload(BaseModel):
    roi_size: Optional[int] = None
    offset_x: Optional[int] = None
    offset_y: Optional[int] = None

class CameraPayload(BaseModel):
    source: str

@app.post("/api/roi_size")
@app.post("/api/roi")
async def api_roi_adjust(payload: RoiPayload):
    if state.cam:
        if payload.roi_size is not None:
            state.cam.set_roi_size(payload.roi_size)
        if payload.offset_x is not None or payload.offset_y is not None:
            state.cam.set_roi_offset(payload.offset_x, payload.offset_y)

        if state.latest_raw_frame is not None:
            try:
                state.latest_roi_frame = state.cam.extract_roi(state.latest_raw_frame)
            except Exception:
                pass
        return {
            "status": "ok",
            "roi_size": state.cam.roi_size,
            "offset_x": getattr(state.cam, 'roi_offset_x', 0),
            "offset_y": getattr(state.cam, 'roi_offset_y', 0)
        }
    return {"status": "error", "message": "Camera not active"}

@app.post("/api/camera")
async def api_switch_camera(payload: CameraPayload):
    if state.cam:
        try:
            # If inspection was paused, resume automatically upon explicit camera selection
            if state.is_paused:
                state.is_paused = False
                state.add_log("Camera resumed on optical sensor switch.")

            # Run camera opening & handshake in background thread so event loop remains responsive
            await run_in_threadpool(state.cam.switch_camera, payload.source)
            state.add_log(f"Camera source changed to [{payload.source}]")
            return {
                "status": "ok",
                "source": str(state.cam.camera_id),
                "is_paused": state.is_paused
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "current": str(state.cam.camera_id),
                "is_paused": state.is_paused
            }
    return {"status": "error", "message": "Camera subsystem not initialized"}

@app.get("/api/cameras")
async def api_get_cameras():
    from utils.camera import CameraManager
    available = CameraManager.list_available_cameras(4)
    current = str(state.cam.camera_id) if state.cam else "0"
    return {"available": available, "current": current}

@app.post("/api/toggle_pause")
async def api_toggle_pause():
    state.is_paused = not state.is_paused
    if state.is_paused:
        state.current_fps = 0.0
        state.add_log("Camera turned OFF. Inspection PAUSED.")
    else:
        state.add_log("Camera turned ON. Inspection RESUMED.")
    return {"status": "ok", "is_paused": state.is_paused}

@app.post("/api/auto_inspect")
@app.post("/api/toggle_auto")
async def api_toggle_auto():
    state.auto_inspect = not state.auto_inspect
    mode_text = "Auto-Debounce" if state.auto_inspect else "Manual (Trigger Only)"
    state.add_log(f"Inspection Trigger Mode: {mode_text}")
    return {"status": "ok", "auto_inspect": state.auto_inspect}

@app.get("/api/status")
async def api_status():
    pass_rate = (state.pass_count / state.total_tested * 100) if state.total_tested > 0 else 0.0
    defect_rate = (state.fail_count / state.total_tested * 100) if state.total_tested > 0 else 0.0
    return {
        "mode": state.mode,
        "auto_inspect": state.auto_inspect,
        "part_present": state.part_present,
        "score": round(state.current_score, 3),
        "threshold": round(state.detector.threshold, 2),
        "verdict": state.current_verdict,
        "sample_count": len(state.captured_samples),
        "total_tested": state.total_tested,
        "pass_count": state.pass_count,
        "fail_count": state.fail_count,
        "pass_rate": round(pass_rate, 1),
        "defect_rate": round(defect_rate, 1),
        "fps": round(state.current_fps, 1),
        "latency_ms": round(state.last_latency, 1),
        "roi_size": state.cam.roi_size if state.cam else 280,
        "roi_offset_x": getattr(state.cam, 'roi_offset_x', 0) if state.cam else 0,
        "roi_offset_y": getattr(state.cam, 'roi_offset_y', 0) if state.cam else 0,
        "camera_id": str(state.cam.camera_id) if state.cam else "0",
        "arduino_connected": state.arduino.is_connected,
        "is_paused": state.is_paused,
        "logs": state.logs
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.connected_ws.add(websocket)
    try:
        while True:
            pass_rate = (state.pass_count / state.total_tested * 100) if state.total_tested > 0 else 0.0
            defect_rate = (state.fail_count / state.total_tested * 100) if state.total_tested > 0 else 0.0
            data = {
                "mode": state.mode,
                "auto_inspect": state.auto_inspect,
                "part_present": state.part_present,
                "score": round(state.current_score, 3),
                "threshold": round(state.detector.threshold, 2),
                "verdict": state.current_verdict,
                "sample_count": len(state.captured_samples),
                "total_tested": state.total_tested,
                "pass_count": state.pass_count,
                "fail_count": state.fail_count,
                "pass_rate": round(pass_rate, 1),
                "defect_rate": round(defect_rate, 1),
                "fps": round(state.current_fps, 1),
                "latency_ms": round(state.last_latency, 1),
                "roi_size": state.cam.roi_size if state.cam else 280,
                "roi_offset_x": getattr(state.cam, 'roi_offset_x', 0) if state.cam else 0,
                "roi_offset_y": getattr(state.cam, 'roi_offset_y', 0) if state.cam else 0,
                "camera_id": str(state.cam.camera_id) if state.cam else "0",
                "arduino_connected": state.arduino.is_connected,
                "is_paused": state.is_paused,
                "logs": state.logs
            }
            await websocket.send_json(data)
            await asyncio.sleep(0.08)
    except WebSocketDisconnect:
        state.connected_ws.remove(websocket)
    except Exception:
        if websocket in state.connected_ws:
            state.connected_ws.remove(websocket)

if __name__ == "__main__":
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser(description="AI Smart QA Vision Inspection Server")
    parser.add_argument("--camera", type=str, default=None, help="Camera index (0, 1) or IP stream URL (http://...)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    args = parser.parse_args()

    if args.camera is not None:
        os.environ["CAMERA_SOURCE"] = args.camera

    print("\n" + "=" * 70)
    print("  🚀 Starting Production AI Smart QA Vision Server...")
    print(f"  📷 Active Camera Source: {os.environ.get('CAMERA_SOURCE', 'Default Built-in (0)')}")
    print(f"  🌐 Access URL: http://localhost:{args.port}")
    print("=" * 70 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")
