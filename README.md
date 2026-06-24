# 🔥 FirePro AI — Smart Surveillance Web System v2.0

A production-grade fire & object detection system with:
- **Web UI** (Flask + Socket.IO real-time streaming)
- **Firebase Authentication** (admin-only login)
- **Firestore database** (detection history)
- **Excel export** (formatted .xlsx with charts)
- **Advanced YOLO detection** (fire, smoke, objects, pose estimation)

---

## 📁 Project Structure

```
firepro_web/
├── app.py              ← Flask server + SocketIO routes
├── detection.py        ← YOLO engine (fire + object + pose)
├── firebase_utils.py   ← Auth + Firestore CRUD
├── excel_export.py     ← Formatted Excel with charts
├── requirements.txt
├── .env.example        ← Copy to .env
├── serviceAccountKey.json   ← Your Firebase Service Account (not committed)
└── templates/
    ├── login.html      ← Admin login (Firebase Auth)
    ├── dashboard.html  ← Live monitor + controls
    └── history.html    ← Detection log + stats + charts
```

---

## ⚡ Quick Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Firebase

#### A. Create Firebase Project
1. Go to https://console.firebase.google.com
2. Create a new project → **Enable Authentication**
3. Authentication → Sign-in method → Enable **Email/Password**
4. Add your admin user: Authentication → Users → Add user

#### B. Enable Firestore
1. Build → Firestore Database → Create database
2. Start in **production mode**
3. Add this security rule:
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /detections/{doc} {
      allow read, write: if request.auth != null;
    }
  }
}
```

#### C. Service Account Key
1. Project Settings (⚙) → Service accounts → Generate new private key
2. Save as `serviceAccountKey.json` in the project root

#### D. Web Config (for login.html)
1. Project Settings → General → Your apps → Add web app
2. Copy the `firebaseConfig` object
3. Paste it into `templates/login.html` where it says `YOUR_API_KEY`, etc.

### 3. Model paths
Edit `detection.py` and update:
```python
FIRE_MODEL_PATH = "E:/firepro/best.pt"      # Your fire detection model
OBJ_MODEL_PATH  = "E:/firepro/yolov8n.pt"   # YOLOv8 base model
POSE_MODEL_PATH = "E:/firepro/yolov8n-pose.pt"  # (optional) pose
```

Download models:
- **YOLOv8n**: `from ultralytics import YOLO; YOLO("yolov8n.pt")`  (auto-downloads)
- **YOLOv8n-pose**: `YOLO("yolov8n-pose.pt")`
- **Fire model**: Use your existing `best.pt` or train with Roboflow

### 4. Environment file
```bash
cp .env.example .env
# Edit .env with your FLASK_SECRET
```

### 5. Run the server
```bash
python app.py
```
Open: **http://localhost:5000**

---

## 🎮 Usage

### Login
- Navigate to `http://localhost:5000`
- Enter your Firebase admin email & password
- **Demo mode**: Click "⚡ Demo Mode" (no Firebase needed, local storage only)

### Live Monitor (`/dashboard`)
- **▶ START DETECTION** — Opens webcam and begins real-time detection
- **Settings panel** — Set alert objects, schedule, confidence, cooldown
- **💾 SAVE SETTINGS** — Apply settings (can change while running)
- **📸 SCREENSHOT** — Save current frame to `screenshots/`
- Keyboard: **F** = Fullscreen | **Q** = Quit | **S** = Screenshot

### Detection History (`/history`)
- Filter by label, severity, or date
- Sort any column
- Live stats: total, high priority, 7-day chart, label breakdown

### Excel Export
- Click **⬇ DOWNLOAD EXCEL** or `/api/export/excel`
- Gets 3 sheets: Detection Log, Summary, Charts

---

## 🧠 Advanced Detection Features

| Feature | Description |
|---|---|
| Fire model | Custom `best.pt` trained on fire/smoke dataset |
| Object model | YOLOv8n — 80 COCO classes |
| Pose model | YOLOv8n-pose — human skeleton overlay |
| Alert cooldown | Don't re-alert same label within N seconds |
| Zone filter | Only detect inside a defined polygon ROI |
| Time schedule | Only run detection during specified hours |
| Confidence sliders | Per-model adjustable thresholds |
| Severity levels | HIGH (fire/smoke) vs MEDIUM (objects) |

---

## 📊 Detection Database Schema (Firestore)

Collection: `detections`

| Field | Type | Example |
|---|---|---|
| label | string | "fire" |
| conf | number | 0.87 |
| severity | string | "HIGH" |
| source | string | "fire_model" |
| timestamp | string | "2024-01-15T22:31:05" |
| date | string | "2024-01-15" |
| time | string | "22:31:05" |
| bbox | array | [120, 80, 300, 240] |
| created_at | timestamp | ServerTimestamp |

---

## 🔗 API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/dashboard` | Live monitor UI |
| GET | `/history` | Detection history UI |
| POST | `/api/auth/login` | Login with Firebase token |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/settings` | Get current settings |
| POST | `/api/settings` | Update settings |
| POST | `/api/detection/start` | Start detection stream |
| POST | `/api/detection/stop` | Stop stream |
| GET | `/api/detection/status` | Stream status |
| GET | `/api/history` | Get detection records (JSON) |
| GET | `/api/stats` | Get aggregate statistics |
| GET | `/api/export/excel` | Download Excel report |
| POST | `/api/screenshot` | Take screenshot |

---

## 🚀 Recommended Models for Better Accuracy

### Fire Detection
- Train on: [Fire Detection Dataset (Roboflow)](https://roboflow.com/search?q=fire+detection)
- Recommended: YOLOv8m or YOLOv8l for higher accuracy
- Augmentation: brightness, rotation, mosaic

### Object Detection
- Upgrade to `yolov8s.pt` or `yolov8m.pt` for better accuracy
- Or use `yolov9c.pt` for latest architecture

### Dataset sources
- [Roboflow Universe](https://universe.roboflow.com) — Fire, smoke, weapon datasets
- [COCO](https://cocodataset.org) — General objects
- [Open Images](https://storage.googleapis.com/openimages/web/index.html)

---

## 📦 Dependencies Summary

```
Flask + Flask-SocketIO  → Web server + real-time streaming
firebase-admin          → Firebase Auth verification + Firestore
ultralytics             → YOLOv8 detection
opencv-python           → Video capture + frame processing
openpyxl                → Excel file generation
```
