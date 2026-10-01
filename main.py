#!/usr/bin/env python3
import os
import sys
import time
import cv2
import numpy as np

from model.patchcore import PatchCoreDetector
from utils.camera import CameraManager
from utils.visualizer import IndustrialDashboard
from utils.sound import SoundAlert
from utils.detector import ComponentDetector
from arduino.arduino_bridge import ArduinoBridge

def main():
    print("=" * 75)
    print("  AI SMART QA FACTORY // REAL-TIME COMPONENT ANOMALY INSPECTION  ")
    print("  Genuine PatchCore Deep Visual Inspection (ResNet-18 MPS/CPU)     ")
    print("=" * 75)
    
    import argparse
    parser = argparse.ArgumentParser(description="Standalone Industrial HUD Inspection")
    parser.add_argument("--camera", type=str, default=None, help="Camera index (0, 1) or IP stream URL (http://...)")
    args, _ = parser.parse_known_args()

    MODEL_PATH = "data/models/patchcore_led.pkl"
    NORMAL_DIR = "data/normal"
    TARGET_SAMPLES = 15
    THRESHOLD = 0.50
    CAMERA_SOURCE = args.camera or os.environ.get("CAMERA_SOURCE") or 0
    
    os.makedirs(NORMAL_DIR, exist_ok=True)
    os.makedirs("data/models", exist_ok=True)
    
    # Initialize components
    detector = PatchCoreDetector(threshold=THRESHOLD)
    comp_detector = ComponentDetector()
    dashboard = IndustrialDashboard(canvas_width=1340, canvas_height=740)
    sound = SoundAlert(enabled=True)
    arduino = ArduinoBridge()
    
    # Load model if available
    if os.path.exists(MODEL_PATH) and detector.load(MODEL_PATH):
        current_mode = "INSPECT"
        dashboard.add_log("Loaded trained PatchCore component model.")
    else:
        current_mode = "ENROLL"
        dashboard.add_log("Enrollment mode: align component in target zone.")

    # Camera
    cam = CameraManager(camera_id=CAMERA_SOURCE, target_width=1280, target_height=720, roi_size=280)
    cam.start()

    # Arduino
    manual_trigger_pending = False
    def on_arduino_trigger():
        nonlocal manual_trigger_pending
        manual_trigger_pending = True
        dashboard.add_log("Arduino IR Proximity Sensor Triggered!")
        
    arduino.on_trigger_callback = on_arduino_trigger
    arduino.connect()

    # Load normal samples
    captured_normal_images = []
    normal_files = sorted([os.path.join(NORMAL_DIR, f) for f in os.listdir(NORMAL_DIR) if f.endswith('.png')])
    for nf in normal_files:
        img = cv2.imread(nf)
        if img is not None:
            captured_normal_images.append(img)
            
    if len(captured_normal_images) > 0 and current_mode == "ENROLL":
        dashboard.add_log(f"Loaded {len(captured_normal_images)} saved normal samples.")

    auto_inspect = True
    window_name = "AI Smart QA System // Industrial Component Inspection"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1340, 740)

    prev_time = time.time()
    
    print("\n[Controls]")
    print("  [C]     : Capture Normal Sample (in Enroll mode)")
    print("  [T]     : Train PatchCore Memory Bank")
    print("  [R]     : Reset Samples & Statistics")
    print("  [S]     : Save Model to Disk")
    print("  [L]     : Load Saved Model from Disk")
    print("  [+/-]   : Increase / Decrease Anomaly Threshold")
    print("  [SPACE] : Trigger Inspection Snapshot")
    print("  [M]     : Toggle Auto-Debounce vs Manual Trigger Mode")
    print("  [Q/ESC] : Quit\n")

    try:
        while True:
            ret, raw_frame = cam.read_frame()
            if not ret or raw_frame is None:
                time.sleep(0.01)
                continue
                
            roi_crop = cam.extract_roi(raw_frame)
            is_present, comp_box, comp_crop, status_msg = comp_detector.check_presence(roi_crop)
            
            pred_result = None
            latency_ms = 0.0

            if current_mode == "INSPECT":
                if is_present and comp_crop is not None:
                    t0 = time.time()
                    res = detector.predict(comp_crop)
                    latency_ms = (time.time() - t0) * 1000
                    pred_result = res
                    
                    is_anomaly = res['is_anomaly']
                    is_stable = comp_detector.check_motion_stability(comp_crop)
                    
                    # Record official inspection event
                    record_event = False
                    if manual_trigger_pending:
                        record_event = True
                        manual_trigger_pending = False
                        dashboard.add_log(f"Manual Inspection: {'FAIL' if is_anomaly else 'PASS'} ({res['anomaly_score']:.2f})")
                    elif auto_inspect and is_stable and not comp_detector.inspected_current_part:
                        record_event = True
                        comp_detector.inspected_current_part = True
                        dashboard.add_log(f"Auto Inspection: {'FAIL' if is_anomaly else 'PASS'} ({res['anomaly_score']:.2f})")
                        
                    if record_event:
                        dashboard.record_verdict(is_anomaly)
                        if is_anomaly:
                            sound.play_fail()
                            arduino.send_verdict("FAIL")
                        else:
                            sound.play_pass()
                            arduino.send_verdict("PASS")
                else:
                    # No part in ROI
                    comp_detector.inspected_current_part = False

            curr_time = time.time()
            fps = 1.0 / max(1e-4, (curr_time - prev_time))
            prev_time = curr_time

            # Render HUD
            dashboard_img = dashboard.render(
                raw_cam_frame=raw_frame,
                roi_crop=comp_crop if is_present else roi_crop,
                mode=current_mode,
                sample_count=len(captured_normal_images),
                max_samples=TARGET_SAMPLES,
                pred_result=pred_result,
                threshold=detector.threshold,
                fps=fps,
                latency_ms=latency_ms
            )

            cv2.imshow(window_name, dashboard_img)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key == ord('c') or key == ord('C'):
                if is_present and comp_crop is not None:
                    captured_normal_images.append(comp_crop.copy())
                    idx = len(captured_normal_images)
                    cv2.imwrite(os.path.join(NORMAL_DIR, f"normal_sample_{idx:02d}.png"), comp_crop)
                    sound.play_capture()
                    dashboard.add_log(f"Captured clean component #{idx}")
                else:
                    dashboard.add_log("No component detected in ROI. Please align part.")
            elif key == ord('t') or key == ord('T'):
                if len(captured_normal_images) < 2:
                    dashboard.add_log("Need at least 2 samples to train!")
                else:
                    dashboard.add_log("Training PatchCore memory bank...")
                    cv2.imshow(window_name, dashboard_img)
                    cv2.waitKey(1)
                    
                    t_start = time.time()
                    detector.fit(captured_normal_images)
                    detector.save(MODEL_PATH)
                    current_mode = "INSPECT"
                    sound.play_pass()
                    dashboard.add_log(f"Trained in {time.time() - t_start:.2f}s! Active inspection started.")
            elif key == ord('r') or key == ord('R'):
                captured_normal_images = []
                current_mode = "ENROLL"
                dashboard.reset_stats()
                dashboard.add_log("Reset all samples and stats. Ready for enrollment.")
            elif key == ord('s') or key == ord('S'):
                detector.save(MODEL_PATH)
                dashboard.add_log("Model saved to disk.")
            elif key == ord('l') or key == ord('L'):
                if detector.load(MODEL_PATH):
                    current_mode = "INSPECT"
                    dashboard.add_log("Model loaded successfully.")
            elif key == ord('+') or key == ord('='):
                detector.threshold = min(0.90, round(detector.threshold + 0.05, 2))
                dashboard.add_log(f"Threshold: {detector.threshold:.2f}")
            elif key == ord('-') or key == ord('_'):
                detector.threshold = max(0.10, round(detector.threshold - 0.05, 2))
                dashboard.add_log(f"Threshold: {detector.threshold:.2f}")
            elif key == 32: # SPACE
                manual_trigger_pending = True
            elif key == ord('m') or key == ord('M'):
                auto_inspect = not auto_inspect
                mode_str = "Auto-Debounce" if auto_inspect else "Manual (Trigger Only)"
                dashboard.add_log(f"Mode: {mode_str}")

    except KeyboardInterrupt:
        pass
    finally:
        cam.release()
        arduino.close()
        cv2.destroyAllWindows()
        print("[System] Terminated.")

if __name__ == "__main__":
    main()
