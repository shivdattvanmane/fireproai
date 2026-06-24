import cv2
import numpy as np
import os
import threading
import time
import webbrowser
import pyttsx3

from tkinter import *
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from pyzbar.pyzbar import decode
from ultralytics import YOLO
from datetime import datetime

# -------------------- PATHS --------------------
model_path1 = r"D:\obj_detect_proj\yolov8n-oiv7.pt"
model_path2 = r"D:\obj_detect_proj\yolov8n.pt"

# -------------------- LOAD MODELS --------------------
model1 = YOLO(model_path1)
model2 = YOLO(model_path2)

# -------------------- SETTINGS --------------------
danger_objects = {"knife", "gun", "fire", "weapon"}
last_alert_time = 0
alert_cooldown = 10

engine = pyttsx3.init()
engine.setProperty("rate", 150)

os.makedirs("detections", exist_ok=True)

# -------------------- VOICE --------------------
def speak(text):
    threading.Thread(target=lambda: engine.say(text) or engine.runAndWait(), daemon=True).start()

# -------------------- DETECTION --------------------
def detect_objects(frame):
    r1 = model1.predict(frame, conf=0.5, verbose=False)
    r2 = model2.predict(frame, conf=0.5, verbose=False)
    return r1, r2

# -------------------- DRAW BOX --------------------
def draw_boxes(frame, r1, r2):

    labels = set()

    for box in r1[0].boxes:
        cls = int(box.cls[0])
        name = model1.names[cls]
        labels.add(name)

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cv2.rectangle(frame, (x1,y1),(x2,y2),(0,0,255),2)
        cv2.putText(frame,name,(x1,y1-10),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,0,255),2)

    for box in r2[0].boxes:
        cls = int(box.cls[0])
        name = model2.names[cls]
        labels.add(name)

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cv2.rectangle(frame, (x1,y1),(x2,y2),(255,0,0),2)
        cv2.putText(frame,name,(x1,y1-30),cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,0,0),2)

    return frame, labels

# -------------------- QR SCAN --------------------
opened_links = set()

def scan_qr(frame):
    decoded = decode(frame)

    for obj in decoded:
        pts = np.array(obj.polygon, np.int32).reshape((-1,1,2))
        text = obj.data.decode("utf-8")

        cv2.polylines(frame,[pts],True,(0,255,0),2)
        cv2.putText(frame,text,(pts[0][0][0],pts[0][0][1]-10),
                    cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,0),2)

        if text not in opened_links:
            speak("QR code detected")
            opened_links.add(text)

            if text.startswith("http"):
                webbrowser.open(text)

    return frame

# -------------------- REAL TIME --------------------
def real_time_detection():

    global last_alert_time

    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        start = time.time()

        r1, r2 = detect_objects(frame)
        frame, labels = draw_boxes(frame, r1, r2)
        frame = scan_qr(frame)

        # 🚨 ALERT
        for label in labels:
            if label.lower() in danger_objects:
                if time.time() - last_alert_time > alert_cooldown:

                    speak(f"Warning {label} detected")

                    filename = f"detections/{label}_{datetime.now().strftime('%H%M%S')}.jpg"
                    cv2.imwrite(filename, frame)

                    last_alert_time = time.time()

        # FPS
        fps = 1 / (time.time() - start)
        cv2.putText(frame, f"FPS: {int(fps)}", (10,30),
                    cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,255,0),2)

        cv2.imshow("AI SMART SURVEILLANCE", frame)

        if cv2.waitKey(1) == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

# -------------------- IMAGE DETECTION --------------------
def image_detection():
    path = filedialog.askopenfilename()
    if not path:
        return

    img = cv2.imread(path)

    r1, r2 = detect_objects(img)
    img, _ = draw_boxes(img, r1, r2)
    img = scan_qr(img)

    cv2.imshow("Result", img)

# -------------------- GUI --------------------
def create_gui():

    root = Tk()
    root.title("AI Object Detection & QR Scanner")
    root.geometry("500x500")

    Label(root, text="AI SMART SURVEILLANCE SYSTEM",
          font=("Arial",16,"bold")).pack(pady=20)

    Button(root,text="Real Time Detection",
           font=("Arial",14),command=real_time_detection).pack(pady=10)

    Button(root,text="Image Detection",
           font=("Arial",14),command=image_detection).pack(pady=10)

    Button(root,text="Exit",
           font=("Arial",14),command=root.quit).pack(pady=20)

    root.mainloop()

# -------------------- MAIN --------------------
if __name__ == "__main__":
    create_gui()