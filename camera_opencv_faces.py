import os
import cv2
from base_camera import BaseCamera
import time
import Jetson.GPIO as GPIO
import smbus2
from smbus2 import SMBus

db = {'found_someone': False, 'fraction': 0, 'state': -1}
# fraction - фракция опознанного человека (0 - неизвестно,
#                                          1 - союзник,
#                                         -1 - противник)
#
# state - состояние машины (-1 - основной режим работы, с распознаванием;
#                            1 - начало стрельбы, распознавание приостанавливается; 
#                            2 - окончание стрельбы, запуск перехода в основной режим;
#                            0 - переход в основной режим работы, возобновление распознавания)

recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read('trainer/trainer.yml')
cascPath = '/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml'
faceCascade = cv2.CascadeClassifier(cascPath)

# id лиц врагов
enemies = [1]

# GPIO
GPIO_INTR = 24

bus = smbus2.SMBus(1)
SLAVE_ONE_ADDRESS = 0x03
CANNON_ADDRESS = 0x05

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(GPIO_INTR, GPIO.OUT)

# Обозначение области распознавания
upper_left = (250, 150)
bottom_right = (550, 450)

class Camera(BaseCamera):
    video_source = 0
    my_timing = 0

    def __init__(self):
        if os.environ.get('OPENCV_CAMERA_SOURCE'):
            Camera.set_video_source(int(os.environ['OPENCV_CAMERA_SOURCE']))
        super(Camera, self).__init__()

    @staticmethod
    def set_video_source(source):
        Camera.video_source = source

    @staticmethod
    def gstreamer_pipeline(
        capture_width=800,
        capture_height=600,
        display_width=800,
        display_height=600,
        framerate=30,
        flip_method=0,
    ):
        return (
            "nvarguscamerasrc ! "
            "video/x-raw(memory:NVMM), "
            "width=(int)%d, height=(int)%d, "
            "format=(string)NV12, framerate=(fraction)%d/1 ! "
            "nvvidconv flip-method=%d ! "
            "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
            "videoconvert ! "
            "video/x-raw, format=(string)BGR ! appsink"
            % (
                capture_width,
                capture_height,
                framerate,
                flip_method,
                display_width,
                display_height,
            )
        )

    @staticmethod
    def frames():
        GPIO.output(GPIO_INTR, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(GPIO_INTR, GPIO.LOW)
        time.sleep(1)
        GPIO.output(GPIO_INTR, GPIO.HIGH)
        
        bus.write_byte(CANNON_ADDRESS, ord('s'))

        # camera = cv2.VideoCapture(Camera.video_source)
        camera = cv2.VideoCapture(Camera.gstreamer_pipeline(flip_method=0), cv2.CAP_GSTREAMER)
        if not camera.isOpened():
            raise RuntimeError('Could not start camera.')

        while True:
            # Считывание текущего кадра
            _, img = camera.read()
            r = cv2.rectangle(img, upper_left, bottom_right, (100, 50, 200), 5)
            rect_frame = img[upper_left[1] : bottom_right[1], upper_left[0] : bottom_right[0]]

            if db['state'] == -1:
                gray = cv2.cvtColor(rect_frame, cv2.COLOR_BGR2GRAY)
            
                faces=faceCascade.detectMultiScale(
                    gray,
                    scaleFactor=1.2, #1.05
                    minNeighbors=5,
                    minSize=(40,40),
                )
                
                id = 0
                confidence = 0
                
                for (x,y,w,h) in faces:
                    id, confidence = recognizer.predict(gray[y:y+h,x:x+w])            
                    string = round(100 - confidence)
                    print(str(string) + '%')

                if (confidence < 55) and (id > 0) and (not db['found_someone']):
                    # остановка машины и серво
                    GPIO.output(GPIO_INTR, GPIO.LOW)
                    time.sleep(0.5)
                    GPIO.output(GPIO_INTR, GPIO.HIGH)
                    print('low')
                    bus.write_byte(SLAVE_ONE_ADDRESS, ord('0'))

                    if id in enemies:
                        db['fraction'] = -1
                    else:
                        db['fraction'] = 1

                    db['found_someone'] = True
                    db['state'] = 3

            elif db['state'] >= 0:

                # Начало стрельбы
                if db['state'] == 1:
                    Camera.my_timing = time.time()
                    bus.write_byte(CANNON_ADDRESS, ord('s'))
                    db['state'] = 2

                # Окончание стрельбы
                if (time.time() - Camera.my_timing > 3.0 and db['state'] == 2):
                    db['state'] = 0
                
                # Возвращение в исходное состояние
                if db['state'] == 0:
                    bus.write_byte(CANNON_ADDRESS, ord('f'))
                    GPIO.output(24, GPIO.HIGH)
                    db['state'] = -1
                    bus.write_byte(SLAVE_ONE_ADDRESS, ord('1'))

            # encode as a jpeg image and return it
            yield cv2.imencode('.jpg', img)[1].tobytes()

            if cv2.waitKey(1) == 27:
                bus.write_byte(SLAVE_ONE_ADDRESS, ord('0'))

