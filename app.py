import os
import base64
import threading
import json
import time
from datetime import datetime

import cv2
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_socketio import SocketIO, emit
from functools import wraps

from detection import DetectionEngine
from notifications import get_notification_manager
from firebase_utils import (
    verify_firebase_token,
    save_detection_to_firestore,
    get_detection_history,
    get_stats_summary,
)
from excel_export import export_detections_to_excel

# App Setup ───────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "firepro-secret-2024")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ─── Globals ─────────────────────────────────────────────────────────────────
engine = DetectionEngine()
stream_thread: threading.Thread | None = None
stream_active = False

# ─── Auth Decorator ──────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_uid" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ─── Routes ──────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if "admin_uid" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json()
    id_token = data.get("idToken")

    if not id_token:
        return jsonify({"error": "No token provided"}), 400

    uid, email, error = verify_firebase_token(id_token)
    if error:
        return jsonify({"error": error}), 401

    session["admin_uid"] = uid
    session["admin_email"] = email
    return jsonify({"success": True, "email": email})

@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", email=session.get("admin_email", "Admin"))

@app.route("/history")
@login_required
def history():
    return render_template("history.html", email=session.get("admin_email", "Admin"))

# ─── Settings API ────────────────────────────────────────────────────────────
@app.route("/api/settings", methods=["POST"])
@login_required
def update_settings():
    data = request.get_json()
    engine.update_settings(
        objects=data.get("objects", []),
        start_time=data.get("start_time"),
        end_time=data.get("end_time"),
        fire_conf=float(data.get("fire_conf", 0.4)),
        obj_conf=float(data.get("obj_conf", 0.4)),
        alert_cooldown=int(data.get("alert_cooldown", 5)),
    )
    return jsonify({"success": True})

@app.route("/api/settings", methods=["GET"])
@login_required
def get_settings():
    return jsonify(engine.get_settings())

# ─── Detection Control API ───────────────────────────────────────────────────
@app.route("/api/detection/start", methods=["POST"])
@login_required
def start_detection():
    global stream_thread, stream_active
    if stream_active:
        return jsonify({"error": "Detection already running"}), 400

    stream_active = True
    stream_thread = threading.Thread(target=_detection_loop, daemon=True)
    stream_thread.start()
    return jsonify({"success": True})

@app.route("/api/detection/stop", methods=["POST"])
@login_required
def stop_detection():
    global stream_active
    stream_active = False
    return jsonify({"success": True})

@app.route("/api/detection/status", methods=["GET"])
@login_required
def detection_status():
    return jsonify({
        "running": stream_active,
        "settings": engine.get_settings(),
    })

# ─── History & Export API ─────────────────────────────────────────────────────
@app.route("/api/history", methods=["GET"])
@login_required
def api_history():
    limit = int(request.args.get("limit", 100))
    label_filter = request.args.get("label", None)
    records = get_detection_history(limit=limit, label_filter=label_filter)
    return jsonify(records)

@app.route("/api/stats", methods=["GET"])
@login_required
def api_stats():
    stats = get_stats_summary()
    return jsonify(stats)

@app.route("/api/export/excel", methods=["GET"])
@login_required
def api_export_excel():
    records = get_detection_history(limit=10000)
    filepath = export_detections_to_excel(records)
    return send_file(filepath, as_attachment=True,
                     download_name=f"detections_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")

# ─── Notification Settings API ───────────────────────────────────────────────
@app.route("/api/notify/settings", methods=["GET"])
@login_required
def get_notify_settings():
    from notifications import NotifyConfig
    cfg = get_notification_manager().cfg
    return jsonify({
        "email_enabled":   cfg.EMAIL_ENABLED,
        "sender_email":    cfg.SENDER_EMAIL,
        "recipient_email": cfg.RECIPIENT_EMAIL,
        "notify_cooldown": cfg.NOTIFY_COOLDOWN,
    })

@app.route("/api/notify/settings", methods=["POST"])
@login_required
def update_notify_settings():
    data = request.get_json()
    mgr  = get_notification_manager()
    cfg  = mgr.cfg

    cfg.EMAIL_ENABLED   = bool(data.get("email_enabled",   cfg.EMAIL_ENABLED))
    cfg.SENDER_EMAIL    = data.get("sender_email",    cfg.SENDER_EMAIL)
    cfg.SENDER_PASSWORD = data.get("sender_password", cfg.SENDER_PASSWORD) if data.get("sender_password") else cfg.SENDER_PASSWORD
    cfg.RECIPIENT_EMAIL = data.get("recipient_email", cfg.RECIPIENT_EMAIL)
    cfg.NOTIFY_COOLDOWN = int(data.get("notify_cooldown", cfg.NOTIFY_COOLDOWN))

    return jsonify({"success": True})

@app.route("/api/notify/test", methods=["POST"])
@login_required
def test_notification():
    """Send a test notification immediately (bypasses cooldown)."""
    import numpy as np
    data    = request.get_json() or {}
    channel = data.get("channel", "both")   # email / whatsapp / both
    mgr     = get_notification_manager()

    # Create a dummy black frame with text for test
    frame   = np.zeros((480, 640, 3), dtype=np.uint8)
    import cv2 as _cv2
    _cv2.putText(frame, "FirePro AI — Test Alert", (60, 240),
                 _cv2.FONT_HERSHEY_DUPLEX, 1, (0, 100, 255), 2)

    # Temporarily bypass cooldown for test
    mgr._cooldowns.clear()

    orig_email = mgr.cfg.EMAIL_ENABLED
    mgr.cfg.EMAIL_ENABLED = True
    mgr.notify("TEST", 0.99, "HIGH", frame, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    mgr.cfg.EMAIL_ENABLED = orig_email

    return jsonify({"success": True, "message": f"Test notification queued ({channel})"})

# ─── Screenshot API ──────────────────────────────────────────────────────────
@app.route("/api/screenshot", methods=["POST"])
@login_required
def api_screenshot():
    if not stream_active:
        return jsonify({"error": "No active stream"}), 400
    engine.request_screenshot()
    return jsonify({"success": True})

# ─── Detection Pipeline — 3-Thread Architecture ──────────────────────────────
#
#  Thread 1 (camera)    → reads frames as fast as camera allows → _frame_queue
#  Thread 2 (yolo)      → runs YOLO on frames from queue        → _result_queue
#  Thread 3 (emitter)   → encodes JPEG + emits to browser       → Socket.IO
#
#  Result: camera NEVER waits for YOLO. Stream stays smooth even on slow CPU.
#
import queue as _queue

# ── Tuning constants (adjust to balance speed vs accuracy) ───────────────────
CAM_WIDTH      = 640    # camera capture width
CAM_HEIGHT     = 480    # camera capture height
JPEG_QUALITY   = 55     # 40-65 sweet spot (lower = faster, less data)
STREAM_FPS_CAP = 30     # max FPS sent to browser
YOLO_FPS       = 8      # how many times per second YOLO actually runs
                        # (camera still streams at full speed between runs)

# ── Shared queues between threads ─────────────────────────────────────────────
_frame_queue  = _queue.Queue(maxsize=2)   # camera  → YOLO    (max 2 frames buffered)
_result_queue = _queue.Queue(maxsize=2)   # YOLO    → emitter (max 2 results buffered)


# ── Thread 1: Camera Reader ───────────────────────────────────────────────────
def _camera_thread(cap):
    """Reads frames from webcam as fast as possible, drops old ones."""
    global stream_active
    while stream_active:
        ret, frame = cap.read()
        if not ret:
            stream_active = False
            break
        # Drop old frame if queue full — always keep freshest frame
        if _frame_queue.full():
            try: _frame_queue.get_nowait()
            except: pass
        try: _frame_queue.put_nowait(frame)
        except: pass


# ── Thread 2: YOLO Inference ──────────────────────────────────────────────────
def _yolo_thread():
    """Pulls frames from camera queue, runs YOLO, pushes results."""
    global stream_active
    last_yolo_time = 0.0
    min_yolo_gap   = 1.0 / YOLO_FPS   # enforce YOLO_FPS cap

    while stream_active:
        try:
            frame = _frame_queue.get(timeout=0.5)
        except _queue.Empty:
            continue

        now = time.time()
        elapsed = now - last_yolo_time

        if elapsed >= min_yolo_gap:
            # Run full detection
            result         = engine.process_frame(frame)
            last_yolo_time = time.time()

            # Handle alerts (email notification, Firestore, socket)
            for alert in result["alerts"]:
                socketio.emit("alert", alert)
                save_detection_to_firestore(alert)
                try:
                    get_notification_manager().notify(
                        label     = alert.get("label",    "unknown"),
                        conf      = alert.get("conf",     0.0),
                        severity  = alert.get("severity", "MEDIUM"),
                        frame     = frame,
                        timestamp = alert.get("timestamp"),
                    )
                except Exception as _ne:
                    print(f"[Notify] {_ne}")

            # Screenshot request
            if engine.screenshot_pending:
                name = f"screenshots/{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                cv2.imwrite(name, frame)
                socketio.emit("screenshot_saved", {"path": name})
                engine.screenshot_pending = False
        else:
            # Between YOLO runs: pass raw frame with last cached annotations
            result = {
                "annotated": frame,
                "alerts":    [],
                "stats":     engine._make_stats([]),
            }

        # Push to emit queue (drop old if full)
        if _result_queue.full():
            try: _result_queue.get_nowait()
            except: pass
        try: _result_queue.put_nowait((frame, result))
        except: pass


# ── Thread 3: Stream Emitter ──────────────────────────────────────────────────
def _emitter_thread():
    """Encodes frames as JPEG and emits to browser at capped FPS."""
    global stream_active
    last_emit  = 0.0
    min_gap    = 1.0 / STREAM_FPS_CAP

    while stream_active:
        try:
            frame, result = _result_queue.get(timeout=0.5)
        except _queue.Empty:
            continue

        # FPS cap
        now = time.time()
        if now - last_emit < min_gap:
            continue
        last_emit = now

        # Encode: resize → JPEG → base64
        display = result.get("annotated", frame)
        if display.shape[1] != CAM_WIDTH:
            display = cv2.resize(display, (CAM_WIDTH, CAM_HEIGHT),
                                 interpolation=cv2.INTER_LINEAR)
        _, buf = cv2.imencode(".jpg", display,
                              [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        b64 = base64.b64encode(buf).decode("utf-8")
        socketio.emit("frame", {"data": b64, "stats": result.get("stats", {})})


# ── Main controller ───────────────────────────────────────────────────────────
def _detection_loop():
    global stream_active

    # Open camera
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if os.name == "nt" else 0)
    if not cap.isOpened():
        socketio.emit("error", {"message": "Cannot open camera"})
        stream_active = False
        return

    # Camera hardware settings
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS,          30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)   # no stale frames

    # Drain queues from any previous session
    for q in (_frame_queue, _result_queue):
        while not q.empty():
            try: q.get_nowait()
            except: pass

    socketio.emit("stream_started", {})

    # Spawn the 3 pipeline threads
    t_cam     = threading.Thread(target=_camera_thread,  args=(cap,), daemon=True)
    t_yolo    = threading.Thread(target=_yolo_thread,              daemon=True)
    t_emitter = threading.Thread(target=_emitter_thread,           daemon=True)

    t_cam.start()
    t_yolo.start()
    t_emitter.start()

    # Wait until stream is stopped
    t_cam.join()
    t_yolo.join()
    t_emitter.join()

    cap.release()
    stream_active = False
    socketio.emit("stream_stopped", {})


# ─── SocketIO Events ─────────────────────────────────────────────────────────
@socketio.on("connect")
def on_connect():
    emit("connected", {"status": "ok"})

@socketio.on("disconnect")
def on_disconnect():
    pass

# ─── Entry Point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=False,          # ← must be False with SocketIO + YOLO
        use_reloader=False,   # ← stops Flask watching torch/ultralytics files
        log_output=True,
    )
