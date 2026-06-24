from ultralytics import YOLO
import cv2
import os
import winsound
from datetime import datetime
import customtkinter as ctk
from tkinter import messagebox

# ---------------- MODELS ----------------
model_fire = YOLO("E:/firepro/best.pt")
model_obj = YOLO("E:/firepro/yolov8n.pt")

os.makedirs("alerts", exist_ok=True)
os.makedirs("screenshots", exist_ok=True)

selected_objects = []
start_time = None
end_time = None
running = False

# ---------------- TIME CHECK ----------------
def is_time_valid():

    now = datetime.now().time()

    if start_time <= end_time:
        return start_time <= now <= end_time
    else:
        return now >= start_time or now <= end_time


# ---------------- SCREENSHOT ----------------
def screenshot(frame):

    name = f"screenshots/{datetime.now().strftime('%H%M%S')}.jpg"
    cv2.imwrite(name, frame)


# ---------------- DETECTION ----------------
def start_detection():

    global running
    running = True

    cap = cv2.VideoCapture(0)

    while running:

        ret, frame = cap.read()
        if not ret:
            break

        annotated = frame.copy()

        if is_time_valid():

            fire_results = model_fire(frame, conf=0.4)
            obj_results = model_obj(frame, conf=0.4)

            # ---------- FIRE MODEL ----------
            for box in fire_results[0].boxes:

                cls = int(box.cls[0])
                label = model_fire.names[cls]

                x1,y1,x2,y2 = map(int, box.xyxy[0])

                cv2.rectangle(annotated,(x1,y1),(x2,y2),(0,0,255),2)
                cv2.putText(annotated,label,(x1,y1-10),
                            cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,0,255),2)

                if label in selected_objects:

                    winsound.Beep(1200,400)

                    filename=f"alerts/{label}_{datetime.now().strftime('%H%M%S')}.jpg"
                    cv2.imwrite(filename,frame)

            # ---------- OBJECT MODEL ----------
            for box in obj_results[0].boxes:

                cls=int(box.cls[0])
                label=model_obj.names[cls]

                x1,y1,x2,y2=map(int,box.xyxy[0])

                cv2.rectangle(annotated,(x1,y1),(x2,y2),(0,255,0),2)
                cv2.putText(annotated,label,(x1,y1-10),
                            cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,255,0),2)

                if label in selected_objects:

                    winsound.Beep(900,400)

                    filename=f"alerts/{label}_{datetime.now().strftime('%H%M%S')}.jpg"
                    cv2.imwrite(filename,frame)

        cv2.imshow("AI Smart Detection", annotated)

        key = cv2.waitKey(1)

        if key == ord("q"):
            break

        if key == ord("s"):
            screenshot(frame)

        if key == ord("f"):
            cv2.setWindowProperty(
                "AI Smart Detection",
                cv2.WND_PROP_FULLSCREEN,
                cv2.WINDOW_FULLSCREEN
            )

    cap.release()
    cv2.destroyAllWindows()


# ---------------- STOP ----------------
def stop_detection():
    global running
    running = False


# ---------------- SETTINGS ----------------
def save_settings():

    global selected_objects,start_time,end_time

    objects = object_entry.get().lower().split(",")
    selected_objects = [o.strip() for o in objects]

    try:

        start_time = datetime.strptime(start_entry.get(), "%H:%M").time()
        end_time = datetime.strptime(end_entry.get(), "%H:%M").time()

    except:
        messagebox.showerror("Error","Time format must be HH:MM")
        return

    messagebox.showinfo("Saved","Settings saved successfully")


# ---------------- UI ----------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("🔥 AI Smart Surveillance System")
root.geometry("500x450")

title = ctk.CTkLabel(root,
text="🔥 AI Fire & Object Detection",
font=("Arial",22,"bold"))
title.pack(pady=15)

frame = ctk.CTkFrame(root)
frame.pack(padx=20,pady=10,fill="both",expand=True)

ctk.CTkLabel(frame,
text="Objects to Alert (comma separated)").pack(pady=5)

object_entry = ctk.CTkEntry(frame,width=250)
object_entry.insert(0,"fire, smoke, person")
object_entry.pack(pady=5)

ctk.CTkLabel(frame,text="Start Time (HH:MM)").pack(pady=5)

start_entry = ctk.CTkEntry(frame)
start_entry.insert(0,"20:00")
start_entry.pack(pady=5)

ctk.CTkLabel(frame,text="End Time (HH:MM)").pack(pady=5)

end_entry = ctk.CTkEntry(frame)
end_entry.insert(0,"10:00")
end_entry.pack(pady=5)

ctk.CTkButton(frame,
text="💾 Save Settings",
command=save_settings).pack(pady=10)

ctk.CTkButton(frame,
text="▶ Start Detection",
command=start_detection).pack(pady=5)

ctk.CTkButton(frame,
text="⏹ Stop Detection",
command=stop_detection,
fg_color="red").pack(pady=5)

info = ctk.CTkLabel(root,
text="Keyboard:\nF Fullscreen | Q Quit | S Screenshot",
font=("Arial",12))
info.pack(pady=10)

root.mainloop()