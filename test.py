import cv2
from ultralytics import YOLO

model = YOLO("E:/firepro/best.pt")

results = model.predict(
    source="E:/firepro/image.png",
    conf=0.4,
    show=True
)

cv2.waitKey(0)
cv2.destroyAllWindows()