"""
🔥 AI Smart Surveillance — Flask + SocketIO Web Server
"""

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
from firebase_utils import (
    verify_firebase_token,
    save_detection_to_firestore,
    get_detection_history,
    get_stats_summary,
)
from excel_export import export_detections_to_excel

# ─── App Setup ───────────────────────────────────────────────────────────────
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

# ─── Screenshot API ──────────────────────────────────────────────────────────
@app.route("/api/screenshot", methods=["POST"])
@login_required
def api_screenshot():
    if not stream_active:
        return jsonify({"error": "No active stream"}), 400
    engine.request_screenshot()
    return jsonify({"success": True})

# ─── Detection Loop (Background Thread) ──────────────────────────────────────
# ── Performance constants ─────────────────────────────────────────────────────
STREAM_WIDTH   = 640    # resize frame before encoding (lower = faster stream)
STREAM_HEIGHT  = 480
DETECT_EVERY   = 3      # run YOLO only every N frames  (1=every frame, 3=every 3rd)
JPEG_QUALITY   = 55     # JPEG compression 0-100        (lower = faster, smaller)
STREAM_FPS_CAP = 25     # max frames emitted per second to browser

def _detection_loop():
    global stream_active

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if os.name == "nt" else 0)
    if not cap.isOpened():
        socketio.emit("error", {"message": "Cannot open camera"})
        stream_active = False
        return

    # ── Camera hardware settings ──────────────────────────────────────────
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  STREAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, STREAM_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # keep buffer tiny → no stale frames

    socketio.emit("stream_started", {})

    frame_idx       = 0
    last_result     = None          # cached last detection result
    last_emit_time  = 0.0
    min_emit_gap    = 1.0 / STREAM_FPS_CAP

    while stream_active:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1

        # ── Run YOLO only every DETECT_EVERY frames ───────────────────────
        # All other frames reuse the last boxes (still looks smooth visually)
        if frame_idx % DETECT_EVERY == 0 or last_result is None:
            result      = engine.process_frame(frame)
            last_result = result

            # Emit alerts from detection frames only
            for alert in result["alerts"]:
                socketio.emit("alert", alert)
                save_detection_to_firestore(alert)
        else:
            # Re-use last stats — draw nothing new (frame still streams clean)
            result = last_result

        # ── Screenshot ────────────────────────────────────────────────────
        if engine.screenshot_pending:
            name = f"screenshots/{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            cv2.imwrite(name, frame)
            socketio.emit("screenshot_saved", {"path": name})
            engine.screenshot_pending = False

        # ── FPS cap: skip emit if too soon ────────────────────────────────
        now = time.time()
        if now - last_emit_time < min_emit_gap:
            continue
        last_emit_time = now

        # ── Resize → JPEG → Base64 ────────────────────────────────────────
        # Use last annotated frame from result (already has boxes drawn)
        display = result["annotated"]
        small   = cv2.resize(display, (STREAM_WIDTH, STREAM_HEIGHT),
                             interpolation=cv2.INTER_LINEAR)
        _, buf  = cv2.imencode(".jpg", small,
                               [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        b64 = base64.b64encode(buf).decode("utf-8")
        socketio.emit("frame", {"data": b64, "stats": result["stats"]})

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
