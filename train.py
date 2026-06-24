from ultralytics import YOLO

model = YOLO("yolov8n.pt")

model.train(
    data="Fire-Detection/data.yaml",
    epochs=50,
    imgsz=640,
    batch=8
)