import cv2
import numpy as np

cap = cv2.VideoCapture(1)
lower = np.array([0, 0, 170])
upper = np.array([180, 50, 255])

while True:
    ret , frame = cap.read()
    if not ret:
        break

    img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(img, lower, upper)
    for i in range(len(mask)):
        for j in range(len(mask[i])):
            if mask[i][j] != 0:
                print("흰색검출")

    cv2.imshow('mask', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
