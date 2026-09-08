import cv2

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("❌ Camera couldn't be opened")
    exit()

while True:
    ret, frame = cap.read()

    if not ret:
        print("❌ Couldn't read frame")
        break

    cv2.imshow("Webcam", frame)

    if cv2.waitKey(1) & 0xFF == ord("x"):
        break

cap.release()
cv2.destroyAllWindows()