import time
import threading
from datetime import datetime, time as dtime
from typing import Optional

import cv2
import numpy as np

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

# ─── Label → colour map ───────────────────────────────────────────────────────
COLOUR_MAP = {
    "fire":    (0,   60,  255),   # red
    "smoke":   (80,  80,  200),   # purple-red
    "person":  (0,   200, 100),   # green
    "car":     (255, 180, 0),     # amber
    "default": (0,   200, 255),   # cyan
}

# Fire-related labels that trigger high-priority alert
HIGH_PRIORITY = {"fire", "smoke", "flame"}

# COCO classes that are considered security-relevant
SECURITY_CLASSES = {
    "person", "knife", "scissors", "gun",
    "cell phone", "backpack", "handbag",
    "car", "truck", "motorcycle",
}

# ─── Alert cooldown tracker ───────────────────────────────────────────────────
class CooldownTracker:
    def __init__(self, cooldown_seconds: int = 5):
        self._last: dict[str, float] = {}
        self.cooldown = cooldown_seconds
        self._lock = threading.Lock()

    def should_alert(self, label: str) -> bool:
        with self._lock:
            now = time.time()
            last = self._last.get(label, 0)
            if now - last >= self.cooldown:
                self._last[label] = now
                return True
            return False

    def reset(self):
        with self._lock:
            self._last.clear()


# ─── Zone definition (polygon ROI) ───────────────────────────────────────────
class DetectionZone:
    """Define a polygon zone; detections outside are ignored."""
    def __init__(self, points: list[tuple[int, int]] | None = None):
        self.points = points  # None = full frame

    def contains(self, cx: int, cy: int) -> bool:
        if self.points is None:
            return True
        pts = np.array(self.points, dtype=np.int32)
        return cv2.pointPolygonTest(pts, (cx, cy), False) >= 0

    def draw(self, frame):
        if self.points:
            pts = np.array(self.points, dtype=np.int32)
            cv2.polylines(frame, [pts], True, (255, 255, 0), 2)


# ─── Main Detection Engine ────────────────────────────────────────────────────
class DetectionEngine:
    FIRE_MODEL_PATH = "E:/firepro/best.pt"
    OBJ_MODEL_PATH  = "E:/firepro/yolov8n.pt"
    POSE_MODEL_PATH = "E:/firepro/yolov8n-pose.pt"   # optional

    def __init__(self):
        self._lock = threading.Lock()

        # ── Models ──────────────────────────────────────────
        self.model_fire = None
        self.model_obj  = None
        self.model_pose = None

        if YOLO_AVAILABLE:
            try:
                self.model_fire = YOLO(self.FIRE_MODEL_PATH)
                print("✅ Fire model loaded")
            except Exception as e:
                print(f"⚠️  Fire model not found: {e}")

            try:
                self.model_obj = YOLO(self.OBJ_MODEL_PATH)
                print("✅ Object model loaded")
            except Exception as e:
                print(f"⚠️  Object model not found: {e}")

            try:
                self.model_pose = YOLO(self.POSE_MODEL_PATH)
                print("✅ Pose model loaded")
            except Exception as e:
                print(f"ℹ️  Pose model not loaded (optional): {e}")
        else:
            print("⚠️  Ultralytics not installed — running in demo mode")

        # ── Settings (thread-safe) ────────────────────────
        self._selected_objects:  list[str] = ["fire", "smoke", "person"]
        self._start_time: Optional[dtime] = None
        self._end_time:   Optional[dtime] = None
        self._fire_conf   = 0.40
        self._obj_conf    = 0.40
        self._cooldown    = CooldownTracker(5)
        self._zone        = DetectionZone()

        # ── Frame stats ───────────────────────────────────
        self._frame_count  = 0
        self._alert_count  = 0
        self._fps_tracker  = time.time()
        self._fps          = 0.0

        # ── Control flags ──────────────────────────────────
        self.screenshot_pending = False

        # ── GPU check ──────────────────────────────────────
        try:
            import torch
            self._gpu_available = torch.cuda.is_available()
            print("✅ GPU: " + torch.cuda.get_device_name(0) if self._gpu_available else "ℹ️  CPU mode")
        except Exception:
            self._gpu_available = False

    # ── Settings API ──────────────────────────────────────────────────────────
    def update_settings(self, objects, start_time, end_time,
                        fire_conf=0.4, obj_conf=0.4, alert_cooldown=5):
        with self._lock:
            self._selected_objects = [o.strip().lower() for o in objects]
            self._fire_conf = fire_conf
            self._obj_conf  = obj_conf
            self._cooldown  = CooldownTracker(alert_cooldown)

            try:
                # Empty string = clear schedule = always detect
                if start_time and str(start_time).strip():
                    h, m = map(int, str(start_time).strip().split(":"))
                    self._start_time = dtime(h, m)
                else:
                    self._start_time = None  # no schedule

                if end_time and str(end_time).strip():
                    h, m = map(int, str(end_time).strip().split(":"))
                    self._end_time = dtime(h, m)
                else:
                    self._end_time = None  # no schedule

            except Exception as e:
                print(f"Time parse error: {e}")
                self._start_time = None
                self._end_time   = None

    def get_settings(self) -> dict:
        with self._lock:
            return {
                "objects":       self._selected_objects,
                "start_time":    self._start_time.strftime("%H:%M") if self._start_time else None,
                "end_time":      self._end_time.strftime("%H:%M")   if self._end_time   else None,
                "fire_conf":     self._fire_conf,
                "obj_conf":      self._obj_conf,
                "alert_cooldown": self._cooldown.cooldown,
            }

    def set_zone(self, points: list[tuple[int, int]] | None):
        with self._lock:
            self._zone = DetectionZone(points)

    def request_screenshot(self):
        self.screenshot_pending = True

    # ── Time Guard ────────────────────────────────────────────────────────────
    def _is_time_valid(self) -> bool:
        # If either time is not set → no schedule → always detect
        if self._start_time is None or self._end_time is None:
            return True
        # If both are identical → no meaningful schedule → always detect
        if self._start_time == self._end_time:
            return True
        now = datetime.now().time()
        if self._start_time < self._end_time:
            # Normal range e.g. 08:00 → 18:00
            return self._start_time <= now <= self._end_time
        else:
            # Overnight range e.g. 20:00 → 06:00
            return now >= self._start_time or now <= self._end_time

    # ── Frame Processing ──────────────────────────────────────────────────────
    def process_frame(self, frame: np.ndarray) -> dict:
        """
        Returns:
          annotated  — BGR frame with boxes drawn
          alerts     — list of alert dicts for Firestore / Socket
          stats      — live counters
        """
        annotated = frame.copy()
        alerts: list[dict] = []
        detections: list[dict] = []

        self._frame_count += 1

        # FPS calculation
        now = time.time()
        elapsed = now - self._fps_tracker
        if elapsed >= 1.0:
            self._fps = self._frame_count / elapsed
            self._frame_count = 0
            self._fps_tracker = now

        # ── Snapshot ALL settings under lock once per frame ──────────────────
        # This is the KEY fix: detection thread reads a fresh copy of
        # selected_objects every frame, so UI changes apply immediately.
        # Previously it read self._selected_objects without the lock,
        # causing stale values even after Save Settings was clicked.
        with self._lock:
            selected_objects = set(self._selected_objects)  # e.g. {"fire","smoke"}
            fire_conf        = self._fire_conf
            obj_conf         = self._obj_conf
            zone             = self._zone

        print(f"[DEBUG] Active alert objects: {selected_objects}")  # remove after testing

        # Draw zone overlay
        zone.draw(annotated)

        if not self._is_time_valid():
            self._draw_schedule_overlay(annotated)
            return {
                "annotated": annotated,
                "alerts": [],
                "stats": self._make_stats(detections),
            }

        # ── Fire model ─────────────────────────────────────────────────────
        if self.model_fire:
            fire_results = self.model_fire(
                frame,
                conf=fire_conf,
                verbose=False,
                imgsz=320,      # smaller inference size → 2-3x faster than 640
                half=False,     # set True if you have an NVIDIA GPU
                device=0 if self._gpu_available else "cpu",
            )
            for box in fire_results[0].boxes:
                cls   = int(box.cls[0])
                label = self.model_fire.names[cls].lower()
                conf  = float(box.conf[0])
                x1,y1,x2,y2 = map(int, box.xyxy[0])
                cx, cy = (x1+x2)//2, (y1+y2)//2

                if not zone.contains(cx, cy):
                    continue

                colour = COLOUR_MAP.get("fire")
                self._draw_box(annotated, x1,y1,x2,y2, label, conf, colour, priority=True)
                d = self._make_detection(label, conf, x1,y1,x2,y2, "fire_model")
                detections.append(d)

                # Uses fresh snapshot — UI changes reflect on next frame
                if label in selected_objects and self._cooldown.should_alert(label):
                    alerts.append(self._make_alert(d, "HIGH" if label in HIGH_PRIORITY else "MEDIUM"))
                    self._alert_count += 1

        # ── Object model ───────────────────────────────────────────────────
        if self.model_obj:
            obj_results = self.model_obj(
                frame,
                conf=obj_conf,
                verbose=False,
                imgsz=320,
                half=False,
                device=0 if self._gpu_available else "cpu",
            )
            for box in obj_results[0].boxes:
                cls   = int(box.cls[0])
                label = self.model_obj.names[cls].lower()
                conf  = float(box.conf[0])
                x1,y1,x2,y2 = map(int, box.xyxy[0])
                cx, cy = (x1+x2)//2, (y1+y2)//2

                if not zone.contains(cx, cy):
                    continue

                colour = COLOUR_MAP.get(label, COLOUR_MAP["default"])
                self._draw_box(annotated, x1,y1,x2,y2, label, conf, colour)
                d = self._make_detection(label, conf, x1,y1,x2,y2, "object_model")
                detections.append(d)

                # Uses fresh snapshot — UI changes reflect on next frame
                if label in selected_objects and self._cooldown.should_alert(label):
                    alerts.append(self._make_alert(d, "MEDIUM"))
                    self._alert_count += 1

        # ── Pose model (person skeleton) ───────────────────────────────────
        if self.model_pose:
            pose_results = self.model_pose(
                frame, conf=obj_conf, verbose=False
            )
            if pose_results[0].keypoints is not None:
                kpts_all = pose_results[0].keypoints.xy
                for kpts in kpts_all:
                    self._draw_skeleton(annotated, kpts.cpu().numpy())

        # Timestamp & FPS watermark
        self._draw_hud(annotated)

        return {
            "annotated": annotated,
            "alerts":    alerts,
            "stats":     self._make_stats(detections),
        }

    # ── Drawing Helpers ───────────────────────────────────────────────────────
    def _draw_box(self, frame, x1,y1,x2,y2, label, conf, colour, priority=False):
        thickness = 3 if priority else 2
        cv2.rectangle(frame, (x1,y1), (x2,y2), colour, thickness)

        text = f"{label.upper()} {conf:.0%}"
        tw, th = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 0.55, 1)[0]
        cv2.rectangle(frame, (x1, y1-th-8), (x1+tw+4, y1), colour, -1)
        cv2.putText(frame, text, (x1+2, y1-5),
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, (255,255,255), 1)

        if priority:
            # Pulsing corner marks
            size = 12
            for (cx,cy) in [(x1,y1),(x2,y1),(x1,y2),(x2,y2)]:
                cv2.line(frame,(cx,cy),(cx+size if cx==x1 else cx-size,cy),colour,3)
                cv2.line(frame,(cx,cy),(cx,cy+size if cy==y1 else cy-size),colour,3)

    def _draw_skeleton(self, frame, kpts):
        SKELETON = [
            (5,6),(5,7),(7,9),(6,8),(8,10),
            (5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16)
        ]
        colour = (0, 255, 180)
        for i, (x,y) in enumerate(kpts):
            if x > 0 and y > 0:
                cv2.circle(frame,(int(x),int(y)),3,colour,-1)
        for a,b in SKELETON:
            if a < len(kpts) and b < len(kpts):
                xa,ya = kpts[a]; xb,yb = kpts[b]
                if xa > 0 and ya > 0 and xb > 0 and yb > 0:
                    cv2.line(frame,(int(xa),int(ya)),(int(xb),int(yb)),colour,1)

    def _draw_hud(self, frame):
        h, w = frame.shape[:2]
        ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        cv2.putText(frame, ts, (10, h-40),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, (200,200,200), 1)
        cv2.putText(frame, f"FPS: {self._fps:.1f}", (w-120, h-40),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, (200,200,200), 1)
        cv2.putText(frame, f"ALERTS: {self._alert_count}", (w-130, 25),
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, (0,60,255), 1)

    def _draw_schedule_overlay(self, frame):
        overlay = frame.copy()
        cv2.rectangle(overlay,(0,0),(frame.shape[1],frame.shape[0]),(0,0,0),-1)
        frame[:] = cv2.addWeighted(overlay, 0.55, frame, 0.45, 0)
        cv2.putText(frame,"⏸  OUTSIDE DETECTION SCHEDULE",
                    (30, frame.shape[0]//2),
                    cv2.FONT_HERSHEY_DUPLEX, 0.8, (100,100,100), 2)

    # ── Data Helpers ──────────────────────────────────────────────────────────
    @staticmethod
    def _make_detection(label, conf, x1,y1,x2,y2, source):
        return {
            "label":  label,
            "conf":   round(conf, 3),
            "bbox":   [x1,y1,x2,y2],
            "source": source,
        }

    @staticmethod
    def _make_alert(detection: dict, severity: str) -> dict:
        return {
            **detection,
            "severity":  severity,
            "timestamp": datetime.now().isoformat(),
            "date":      datetime.now().strftime("%Y-%m-%d"),
            "time":      datetime.now().strftime("%H:%M:%S"),
        }

    def _make_stats(self, detections: list) -> dict:
        labels = [d["label"] for d in detections]
        return {
            "fps":         round(self._fps, 1),
            "total_alerts": self._alert_count,
            "current_dets": len(detections),
            "labels":       list(set(labels)),
            "fire_active":  any(l in HIGH_PRIORITY for l in labels),
        }
