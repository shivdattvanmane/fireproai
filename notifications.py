"""
🔔 Notification Manager
Sends Email (SMTP/Gmail) and WhatsApp (Twilio) alerts
with attached screenshot when a monitored object is detected.

Setup:
  Email  → any Gmail account with App Password enabled
  WhatsApp → Twilio account with WhatsApp Sandbox or approved number
"""

import os
import io
import time
import threading
import smtplib
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.image     import MIMEImage
from datetime             import datetime
from typing               import Optional

import cv2
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
#  NOTIFICATION CONFIG  ← fill these in or set as environment variables
# ─────────────────────────────────────────────────────────────────────────────
class NotifyConfig:
    # ── Email (Gmail SMTP) ────────────────────────────────────────────────────
    EMAIL_ENABLED      = True
    SMTP_HOST          = "smtp.gmail.com"
    SMTP_PORT          = 587
    SENDER_EMAIL       = os.environ.get("NOTIFY_EMAIL",    "shivdattvanmane@gmail.com")
    SENDER_PASSWORD    = os.environ.get("NOTIFY_PASSWORD", "jbvh khtv jxma hipk")   # Gmail App Password
    RECIPIENT_EMAIL    = os.environ.get("NOTIFY_RECIPIENT","shivdattvanmane@gmail.com")

    # ── Cooldown: don't re-notify same label within N seconds ─────────────────
    NOTIFY_COOLDOWN    = 60   # seconds

    # ── Screenshot quality ────────────────────────────────────────────────────
    SCREENSHOT_QUALITY = 80
    SCREENSHOT_WIDTH   = 640
    SCREENSHOT_HEIGHT  = 480


# ─────────────────────────────────────────────────────────────────────────────
#  Notification Manager
# ─────────────────────────────────────────────────────────────────────────────
class NotificationManager:

    def __init__(self, config: NotifyConfig = None):
        self.cfg           = config or NotifyConfig()
        self._cooldowns:   dict[str, float] = {}
        self._lock         = threading.Lock()
        self._queue        = []
        self._worker_thread = threading.Thread(
            target=self._worker, daemon=True
        )
        self._worker_thread.start()
        print("✅ NotificationManager started")

    # ── Public API ────────────────────────────────────────────────────────────
    def notify(self, label: str, conf: float, severity: str,
               frame: np.ndarray, timestamp: str = None):
        """
        Queue a notification. Non-blocking — runs in background thread.
        Respects cooldown so same label doesn't spam.
        """
        if not self._should_notify(label):
            return

        # Mark cooldown immediately so parallel detections don't double-fire
        with self._lock:
            self._cooldowns[label] = time.time()

        ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Encode screenshot once, reuse for both channels
        screenshot_bytes = self._encode_screenshot(frame)

        # Push to background queue
        self._queue.append({
            "label":            label,
            "conf":             conf,
            "severity":         severity,
            "timestamp":        ts,
            "screenshot_bytes": screenshot_bytes,
        })

    # ── Cooldown check ─────────────────────────────────────────────────────
    def _should_notify(self, label: str) -> bool:
        with self._lock:
            last = self._cooldowns.get(label, 0)
            return (time.time() - last) >= self.cfg.NOTIFY_COOLDOWN

    def update_cooldown(self, seconds: int):
        self.cfg.NOTIFY_COOLDOWN = seconds

    # ── Background worker ──────────────────────────────────────────────────
    def _worker(self):
        while True:
            if self._queue:
                item = self._queue.pop(0)
                try:
                    self._send_all(item)
                except Exception as e:
                    print(f"[Notify] Worker error: {e}")
            else:
                time.sleep(0.2)

    def _send_all(self, item: dict):
        threads = []
        if self.cfg.EMAIL_ENABLED:
            t = threading.Thread(target=self._send_email, args=(item,), daemon=True)
            t.start(); threads.append(t)
        for t in threads:
            t.join(timeout=20)

    # ── Screenshot encode ──────────────────────────────────────────────────
    def _encode_screenshot(self, frame: np.ndarray) -> bytes:
        try:
            h, w = frame.shape[:2]
            if w != self.cfg.SCREENSHOT_WIDTH:
                frame = cv2.resize(
                    frame,
                    (self.cfg.SCREENSHOT_WIDTH, self.cfg.SCREENSHOT_HEIGHT),
                    interpolation=cv2.INTER_LINEAR
                )
            _, buf = cv2.imencode(
                ".jpg", frame,
                [cv2.IMWRITE_JPEG_QUALITY, self.cfg.SCREENSHOT_QUALITY]
            )
            return buf.tobytes()
        except Exception as e:
            print(f"[Notify] Screenshot encode error: {e}")
            return b""

    # ── EMAIL ──────────────────────────────────────────────────────────────
    def _send_email(self, item: dict):
        try:
            label     = item["label"].upper()
            conf      = int(item["conf"] * 100)
            severity  = item["severity"]
            ts        = item["timestamp"]
            img_bytes = item["screenshot_bytes"]

            sev_color = "#ff1744" if severity == "HIGH" else "#ff9800"
            sev_icon  = "🔴" if severity == "HIGH" else "🟡"

            msg = MIMEMultipart("related")
            msg["Subject"] = f"🔥 FirePro Alert: {label} Detected ({severity})"
            msg["From"]    = self.cfg.SENDER_EMAIL
            msg["To"]      = self.cfg.RECIPIENT_EMAIL

            html = f"""
            <html><body style="font-family:Arial,sans-serif;background:#0d0d1e;color:#e8e8f0;margin:0;padding:0">
              <div style="max-width:560px;margin:0 auto;background:#10101f;border:1px solid #1e1e3f;border-radius:4px;overflow:hidden">
                <div style="background:linear-gradient(90deg,#ff4500,#ff6b35);padding:16px 24px">
                  <h1 style="margin:0;font-size:20px;color:#fff">🔥 FirePro AI — Security Alert</h1>
                </div>
                <div style="padding:24px">
                  <div style="background:{sev_color}22;border:1px solid {sev_color}55;
                              border-radius:3px;padding:14px 18px;margin-bottom:20px">
                    <div style="font-size:22px;font-weight:bold;color:{sev_color}">
                      {sev_icon} {severity} ALERT — {label} DETECTED
                    </div>
                    <div style="font-size:13px;color:#aaa;margin-top:4px">{ts}</div>
                  </div>

                  <table style="width:100%;border-collapse:collapse;font-size:14px">
                    <tr style="border-bottom:1px solid #1e1e3f">
                      <td style="padding:10px 0;color:#888;width:140px">Object</td>
                      <td style="padding:10px 0;color:#e8e8f0;font-weight:bold">{label}</td>
                    </tr>
                    <tr style="border-bottom:1px solid #1e1e3f">
                      <td style="padding:10px 0;color:#888">Confidence</td>
                      <td style="padding:10px 0;color:#00d4ff">{conf}%</td>
                    </tr>
                    <tr style="border-bottom:1px solid #1e1e3f">
                      <td style="padding:10px 0;color:#888">Severity</td>
                      <td style="padding:10px 0;color:{sev_color}">{severity}</td>
                    </tr>
                    <tr>
                      <td style="padding:10px 0;color:#888">Time</td>
                      <td style="padding:10px 0;color:#e8e8f0">{ts}</td>
                    </tr>
                  </table>

                  {"<div style='margin-top:20px'><p style='color:#888;font-size:13px;margin-bottom:8px'>📷 Screenshot at time of detection:</p><img src='cid:screenshot' style='width:100%;border-radius:3px;border:1px solid #1e1e3f'></div>" if img_bytes else ""}

                  <div style="margin-top:24px;padding:12px;background:#0a0a18;
                              border-radius:3px;font-size:12px;color:#555;text-align:center">
                    FirePro AI Smart Surveillance System
                  </div>
                </div>
              </div>
            </body></html>
            """

            msg.attach(MIMEText(html, "html"))

            if img_bytes:
                img_part = MIMEImage(img_bytes, _subtype="jpeg")
                img_part.add_header("Content-ID", "<screenshot>")
                img_part.add_header(
                    "Content-Disposition", "inline",
                    filename=f"alert_{label}_{datetime.now().strftime('%H%M%S')}.jpg"
                )
                msg.attach(img_part)

            with smtplib.SMTP(self.cfg.SMTP_HOST, self.cfg.SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.login(self.cfg.SENDER_EMAIL, self.cfg.SENDER_PASSWORD)
                server.sendmail(
                    self.cfg.SENDER_EMAIL,
                    self.cfg.RECIPIENT_EMAIL,
                    msg.as_string()
                )

            print(f"✅ Email sent — {label} alert to {self.cfg.RECIPIENT_EMAIL}")

        except smtplib.SMTPAuthenticationError:
            print("❌ Email auth failed — check SENDER_EMAIL and SENDER_PASSWORD (use Gmail App Password)")
        except smtplib.SMTPException as e:
            print(f"❌ SMTP error: {e}")
        except Exception as e:
            print(f"❌ Email error: {e}")
            traceback.print_exc()

    # ── WHATSAPP via Twilio ────────────────────────────────────────────────
    def _send_whatsapp(self, item: dict):
        if not TWILIO_AVAILABLE:
            return
        try:
            label    = item["label"].upper()
            conf     = int(item["conf"] * 100)
            severity = item["severity"]
            ts       = item["timestamp"]
            icon     = "🔴" if severity == "HIGH" else "🟡"

            body = (
                f"{icon} *FirePro AI Alert*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎯 *Object:* {label}\n"
                f"📊 *Confidence:* {conf}%\n"
                f"⚠️ *Severity:* {severity}\n"
                f"🕐 *Time:* {ts}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"_FirePro AI Surveillance_"
            )

            client = TwilioClient(self.cfg.TWILIO_SID, self.cfg.TWILIO_TOKEN)

            # Save screenshot temporarily to send as media URL
            # Twilio requires a publicly accessible URL for media
            # Option A: save locally and use ngrok URL
            # Option B: upload to Firebase Storage (advanced)
            # Here we send text message — screenshot saved locally
            screenshot_path = None
            if item["screenshot_bytes"]:
                screenshot_path = f"alerts/wa_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                os.makedirs("alerts", exist_ok=True)
                with open(screenshot_path, "wb") as f:
                    f.write(item["screenshot_bytes"])

            # Send WhatsApp text message
            message = client.messages.create(
                body=body,
                from_=self.cfg.TWILIO_FROM,
                to=self.cfg.TWILIO_TO,
            )

            print(f"✅ WhatsApp sent — SID: {message.sid} | {label} alert")

            # Optionally also send screenshot as media if you have public URL
            # See README for ngrok setup to enable image sending
            if screenshot_path:
                print(f"   Screenshot saved: {screenshot_path}")

        except Exception as e:
            print(f"❌ WhatsApp error: {e}")
            if "authenticate" in str(e).lower():
                print("   Check TWILIO_SID and TWILIO_TOKEN")
            elif "not a valid" in str(e).lower():
                print("   Check TWILIO_FROM and TWILIO_TO format: whatsapp:+1234567890")


# ── Singleton instance used across the app ───────────────────────────────────
_manager: Optional[NotificationManager] = None

def get_notification_manager() -> NotificationManager:
    global _manager
    if _manager is None:
        _manager = NotificationManager()
    return _manager
