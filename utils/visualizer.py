import cv2
import numpy as np

class IndustrialDashboard:
    """
    Precision Machine Vision Inspection HUD for OpenCV.
    Designed according to commercial industrial instrumentation standards (Cognex / Keyence style).
    """
    def __init__(self, canvas_width=1340, canvas_height=740):
        self.w = canvas_width
        self.h = canvas_height
        self.cam_w = 720
        self.panel_w = self.w - self.cam_w
        
        # Industrial Palette (BGR)
        self.BG_APP = (20, 23, 28)           # Matte deep slate
        self.SURFACE = (30, 35, 43)          # Surface panel
        self.SURFACE_ELEV = (38, 44, 54)     # Elevated card
        self.BORDER_SUBTLE = (55, 64, 78)    # Border line
        self.BORDER_STRONG = (75, 86, 104)
        
        self.COLOR_BRAND = (235, 115, 37)    # Cobalt / Royal Blue
        self.COLOR_PASS = (80, 185, 16)      # Forest Emerald (PASS)
        self.COLOR_FAIL = (68, 68, 239)      # Signal Red (REJECT)
        self.COLOR_STANDBY = (130, 140, 155) # Slate Gray
        
        self.TEXT_PRIMARY = (245, 248, 250)
        self.TEXT_SECONDARY = (160, 172, 188)
        self.TEXT_MUTED = (105, 116, 134)
        
        # Inspection History
        self.total_inspections = 0
        self.pass_count = 0
        self.fail_count = 0
        self.history_logs = ["AOI Vision System initialized."]

    def add_log(self, text):
        self.history_logs.append(text)
        if len(self.history_logs) > 4:
            self.history_logs.pop(0)

    def record_verdict(self, is_anomaly):
        self.total_inspections += 1
        if is_anomaly:
            self.fail_count += 1
        else:
            self.pass_count += 1

    def reset_stats(self):
        self.total_inspections = 0
        self.pass_count = 0
        self.fail_count = 0
        self.add_log("Statistical Process Control data reset.")

    def draw_measurement_reticle(self, frame, roi_box, status_color):
        """Draws clean precision measurement crosshairs and bounding box."""
        x1, y1, x2, y2 = roi_box
        
        # Outer Bounding Box
        cv2.rectangle(frame, (x1, y1), (x2, y2), self.BORDER_SUBTLE, 1)
        
        # Corner brackets
        c_len = 16
        cv2.line(frame, (x1, y1), (x1 + c_len, y1), status_color, 2)
        cv2.line(frame, (x1, y1), (x1, y1 + c_len), status_color, 2)
        cv2.line(frame, (x2, y1), (x2 - c_len, y1), status_color, 2)
        cv2.line(frame, (x2, y1), (x2, y1 + c_len), status_color, 2)
        cv2.line(frame, (x1, y2), (x1 + c_len, y2), status_color, 2)
        cv2.line(frame, (x1, y2), (x1, y2 - c_len), status_color, 2)
        cv2.line(frame, (x2, y2), (x2 - c_len, y2), status_color, 2)
        cv2.line(frame, (x2, y2), (x2, y2 - c_len), status_color, 2)
        
        # Precision Metric Crosshair
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        cv2.line(frame, (cx - 12, cy), (cx + 12, cy), status_color, 1, cv2.LINE_AA)
        cv2.line(frame, (cx, cy - 12), (cx, cy + 12), status_color, 1, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), 4, status_color, 1, cv2.LINE_AA)
        
        # Subtle LED Dome Outline
        box_size = x2 - x1
        r = int(box_size * 0.22)
        cv2.circle(frame, (cx, cy - int(box_size * 0.08)), r, (90, 100, 115), 1, cv2.LINE_AA)
        
        # Header Label
        cv2.putText(frame, "TARGET ROI [280x280]", (x1 + 2, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.TEXT_MUTED, 1, cv2.LINE_AA)

    def render(self, raw_cam_frame, roi_crop, mode, sample_count, max_samples,
               pred_result=None, threshold=0.50, fps=0.0, latency_ms=0.0):
        dashboard = np.full((self.h, self.w, 3), self.BG_APP, dtype=np.uint8)
        
        # 1. Left Station: Camera Viewfinder
        cam_h, cam_w = raw_cam_frame.shape[:2]
        target_cam_h = self.h - 60
        target_cam_w = self.cam_w
        
        scale = min(target_cam_w / cam_w, target_cam_h / cam_h)
        nw, nh = int(cam_w * scale), int(cam_h * scale)
        scaled_cam = cv2.resize(raw_cam_frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
        
        pad_x = (self.cam_w - nw) // 2
        pad_y = (target_cam_h - nh) // 2
        dashboard[pad_y:pad_y + nh, pad_x:pad_x + nw] = scaled_cam
        
        # Scaled ROI
        from utils.camera import CameraManager
        orig_roi = CameraManager(roi_size=280).get_roi_box((cam_h, cam_w))
        sx1 = int(orig_roi[0] * scale) + pad_x
        sy1 = int(orig_roi[1] * scale) + pad_y
        sx2 = int(orig_roi[2] * scale) + pad_x
        sy2 = int(orig_roi[3] * scale) + pad_y
        scaled_roi_box = (sx1, sy1, sx2, sy2)
        
        status_color = self.COLOR_BRAND
        if mode == 'INSPECT' and pred_result is not None:
            status_color = self.COLOR_FAIL if pred_result['is_anomaly'] else self.COLOR_PASS
        elif mode == 'ENROLL':
            status_color = (30, 160, 245)
            
        self.draw_measurement_reticle(dashboard, scaled_roi_box, status_color)
        
        # Viewfinder Telemetry Bar (Top Left)
        cv2.rectangle(dashboard, (15, 15), (340, 46), self.SURFACE, -1)
        cv2.rectangle(dashboard, (15, 15), (340, 46), self.BORDER_SUBTLE, 1)
        badge_text = f"STATION 01 | MODE: {mode}"
        if mode == 'ENROLL': badge_text += f" [{sample_count}/{max_samples}]"
        cv2.putText(dashboard, badge_text, (26, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.44, self.TEXT_PRIMARY, 1, cv2.LINE_AA)
        
        # Telemetry Bar (Top Right)
        perf_text = f"{fps:.1f} FPS | {latency_ms:.1f} ms"
        cv2.putText(dashboard, perf_text, (self.cam_w - 150, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.42, self.TEXT_MUTED, 1, cv2.LINE_AA)
        
        # Bottom Command Strip
        bar_y1 = self.h - 50
        cv2.rectangle(dashboard, (10, bar_y1), (self.cam_w - 10, self.h - 10), self.SURFACE, -1)
        cv2.rectangle(dashboard, (10, bar_y1), (self.cam_w - 10, self.h - 10), self.BORDER_SUBTLE, 1)
        shortcuts = "[C] Sample Enroll  |  [T] Train Bank  |  [SPACE] Trigger  |  [R] Reset  |  [+/-] Threshold  |  [Q] Exit"
        cv2.putText(dashboard, shortcuts, (20, bar_y1 + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.TEXT_SECONDARY, 1, cv2.LINE_AA)
        
        # 2. Right Station: Defect Analysis & SPC
        px = self.cam_w + 10
        pw = self.panel_w - 20
        cv2.rectangle(dashboard, (px, 10), (px + pw, self.h - 10), self.SURFACE, -1)
        cv2.rectangle(dashboard, (px, 10), (px + pw, self.h - 10), self.BORDER_SUBTLE, 1)
        
        # Header
        cv2.putText(dashboard, "AUTOMATED OPTICAL INSPECTION // AOI-01", (px + 20, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.60, self.TEXT_PRIMARY, 1, cv2.LINE_AA)
        cv2.putText(dashboard, "PatchCore Unsupervised Anomaly Engine · ResNet-18 Backbone",
                    (px + 20, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.TEXT_MUTED, 1, cv2.LINE_AA)
        cv2.line(dashboard, (px + 20, 68), (px + pw - 20, 68), self.BORDER_SUBTLE, 1)
        
        # Dual Display (ROI vs Heatmap)
        view_y = 80
        view_size = 180
        
        # Left Box: Cropped ROI
        cv2.putText(dashboard, "1. COMPONENT ROI", (px + 20, view_y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.TEXT_MUTED, 1, cv2.LINE_AA)
        if roi_crop is not None and roi_crop.size > 0:
            roi_disp = cv2.resize(roi_crop, (view_size, view_size))
            dashboard[view_y + 24:view_y + 24 + view_size, px + 20:px + 20 + view_size] = roi_disp
            cv2.rectangle(dashboard, (px + 20, view_y + 24), (px + 20 + view_size, view_y + 24 + view_size), self.BORDER_SUBTLE, 1)
            
        # Right Box: Anomaly Heatmap
        cv2.putText(dashboard, "2. ANOMALY HEATMAP", (px + 300, view_y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.TEXT_MUTED, 1, cv2.LINE_AA)
                    
        if pred_result is not None and roi_crop is not None and roi_crop.size > 0:
            norm_map = pred_result['anomaly_map']
            # Resize heatmap to match roi_crop dimensions
            h_roi, w_roi = roi_crop.shape[:2]
            norm_map_resized = cv2.resize(norm_map, (w_roi, h_roi), interpolation=cv2.INTER_LINEAR)
            heatmap_raw = np.uint8(255 * norm_map_resized)
            heatmap_color = cv2.applyColorMap(heatmap_raw, cv2.COLORMAP_JET)
            blended = cv2.addWeighted(roi_crop, 0.55, heatmap_color, 0.45, 0)
            heat_disp = cv2.resize(blended, (view_size, view_size))
            
            dashboard[view_y + 24:view_y + 24 + view_size, px + 300:px + 300 + view_size] = heat_disp
            cv2.rectangle(dashboard, (px + 300, view_y + 24), (px + 300 + view_size, view_y + 24 + view_size), status_color, 1)
        else:
            cv2.rectangle(dashboard, (px + 300, view_y + 24), (px + 300 + view_size, view_y + 24 + view_size), self.BORDER_SUBTLE, 1)
            cv2.putText(dashboard, "[STANDBY]", (px + 350, view_y + 115),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.44, self.TEXT_MUTED, 1, cv2.LINE_AA)

        # Quantitative Anomaly Score Bar
        gauge_y = view_y + view_size + 42
        score = pred_result['anomaly_score'] if pred_result else 0.0
        
        cv2.putText(dashboard, f"ANOMALY SCORE: {score:.3f}   (CONTROL LIMIT: {threshold:.2f})",
                    (px + 20, gauge_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.TEXT_PRIMARY, 1, cv2.LINE_AA)
                    
        bar_x = px + 20
        bar_w = pw - 40
        bar_h = 16
        cv2.rectangle(dashboard, (bar_x, gauge_y + 8), (bar_x + bar_w, gauge_y + 8 + bar_h), self.BG_APP, -1)
        cv2.rectangle(dashboard, (bar_x, gauge_y + 8), (bar_x + bar_w, gauge_y + 8 + bar_h), self.BORDER_SUBTLE, 1)
        
        fill_w = int(bar_w * np.clip(score, 0.0, 1.0))
        if fill_w > 0:
            fill_col = self.COLOR_PASS if score < threshold else self.COLOR_FAIL
            cv2.rectangle(dashboard, (bar_x + 1, gauge_y + 9), (bar_x + fill_w, gauge_y + 7 + bar_h), fill_col, -1)
            
        th_pos = bar_x + int(bar_w * threshold)
        cv2.line(dashboard, (th_pos, gauge_y + 4), (th_pos, gauge_y + 12 + bar_h), (255, 255, 255), 2)
        cv2.putText(dashboard, "TH", (th_pos - 6, gauge_y + 24 + bar_h),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.TEXT_MUTED, 1, cv2.LINE_AA)
                    
        # Authoritative Industrial Annunciator Banner
        ann_y = gauge_y + bar_h + 38
        ann_h = 60
        
        if mode == 'ENROLL':
            cv2.rectangle(dashboard, (px + 20, ann_y), (px + pw - 20, ann_y + ann_h), self.SURFACE_ELEV, -1)
            cv2.rectangle(dashboard, (px + 20, ann_y), (px + pw - 20, ann_y + ann_h), (30, 160, 245), 1)
            cv2.putText(dashboard, f"SAMPLE ENROLLMENT [{sample_count}/{max_samples}]",
                        (px + 40, ann_y + 36), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (30, 160, 245), 2, cv2.LINE_AA)
        elif mode == 'INSPECT' and pred_result is not None:
            if pred_result['is_anomaly']:
                cv2.rectangle(dashboard, (px + 20, ann_y), (px + pw - 20, ann_y + ann_h), (25, 25, 60), -1)
                cv2.rectangle(dashboard, (px + 20, ann_y), (px + pw - 20, ann_y + ann_h), self.COLOR_FAIL, 1)
                cv2.putText(dashboard, "[ REJECT // DEFECT DETECTED ]", (px + 40, ann_y + 38),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.72, self.COLOR_FAIL, 2, cv2.LINE_AA)
            else:
                cv2.rectangle(dashboard, (px + 20, ann_y), (px + pw - 20, ann_y + ann_h), (20, 50, 30), -1)
                cv2.rectangle(dashboard, (px + 20, ann_y), (px + pw - 20, ann_y + ann_h), self.COLOR_PASS, 1)
                cv2.putText(dashboard, "[ PASS // QUALITY COMPLIANT ]", (px + 40, ann_y + 38),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.72, self.COLOR_PASS, 2, cv2.LINE_AA)
        else:
            cv2.rectangle(dashboard, (px + 20, ann_y), (px + pw - 20, ann_y + ann_h), self.BG_APP, -1)
            cv2.rectangle(dashboard, (px + 20, ann_y), (px + pw - 20, ann_y + ann_h), self.BORDER_SUBTLE, 1)
            cv2.putText(dashboard, "AWAITING COMPONENT // OPTICAL ZONE CLEAR", (px + 35, ann_y + 36),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, self.TEXT_MUTED, 1, cv2.LINE_AA)

        # Statistical Process Control (SPC) Grid
        spc_y = ann_y + ann_h + 20
        cv2.line(dashboard, (px + 20, spc_y), (px + pw - 20, spc_y), self.BORDER_SUBTLE, 1)
        
        col_w = (pw - 40) // 3
        # Total
        cv2.putText(dashboard, "TOTAL UNITS", (px + 30, spc_y + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.TEXT_MUTED, 1)
        cv2.putText(dashboard, str(self.total_inspections), (px + 30, spc_y + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.70, self.TEXT_PRIMARY, 2)
        
        # Pass (Yield)
        yield_rate = (self.pass_count / self.total_inspections * 100) if self.total_inspections > 0 else 0.0
        cv2.putText(dashboard, f"YIELD ({yield_rate:.1f}%)", (px + 30 + col_w, spc_y + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.COLOR_PASS, 1)
        cv2.putText(dashboard, str(self.pass_count), (px + 30 + col_w, spc_y + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.70, self.COLOR_PASS, 2)
        
        # Defect Rate
        def_rate = (self.fail_count / self.total_inspections * 100) if self.total_inspections > 0 else 0.0
        cv2.putText(dashboard, f"REJECT ({def_rate:.1f}%)", (px + 30 + col_w * 2, spc_y + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.COLOR_FAIL, 1)
        cv2.putText(dashboard, str(self.fail_count), (px + 30 + col_w * 2, spc_y + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.70, self.COLOR_FAIL, 2)
        
        # Event Audit Table
        audit_y = spc_y + 70
        cv2.line(dashboard, (px + 20, audit_y), (px + pw - 20, audit_y), self.BORDER_SUBTLE, 1)
        cv2.putText(dashboard, "AUDIT TRAIL LOG:", (px + 20, audit_y + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.TEXT_MUTED, 1)
        
        for idx, entry in enumerate(self.history_logs[-3:]):
            cv2.putText(dashboard, f"> {entry}", (px + 25, audit_y + 36 + idx * 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.TEXT_SECONDARY, 1, cv2.LINE_AA)
                        
        return dashboard
