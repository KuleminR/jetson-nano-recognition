import os
import cv2
from base_camera import BaseCamera
import time
import Jetson.GPIO as GPIO
import smbus2
from smbus2 import SMBus
import numpy as np

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

# Цвета фракций
# 1 - enemy (blue)
# 2 - ally (green)
# 3 - unknown (yellow)
# x[0] - min, x[1] - max
# [h, s, v]
colors = np.array([[[100, 100, 100], [125, 200, 200]],
                [[39, 100, 100],[80, 200, 200]],
                [[21, 100, 100],[37, 200, 200]]])


# GPIO
GPIO_INTR = 24

bus = smbus2.SMBus(1)
SLAVE_ONE_ADDRESS = 0x03
CANNON_ADDRESS = 0x05

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(GPIO_INTR, GPIO.OUT)

# Область распознавания
upper_left = (350, 250)
bottom_right = (450, 350)

class Camera(BaseCamera):
    video_source = 0
    my_timing = 0

    def __init__(self):
        print(colors[0][0])
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

        #camera = cv2.VideoCapture(Camera.video_source)
        camera = cv2.VideoCapture(Camera.gstreamer_pipeline(flip_method=0), cv2.CAP_GSTREAMER)
        if not camera.isOpened():
            raise RuntimeError('Could not start camera.')

        while True:
            # Считывание текущего кадра
            _, img = camera.read()

            rect_frame = img[upper_left[1] : bottom_right[1], upper_left[0] : bottom_right[0]]

            if db['state'] == -1:
                
                GPIO.output(24, GPIO.HIGH)
                
                hsv = cv2.cvtColor(rect_frame, cv2.COLOR_BGR2HSV)

                mask_enemy = cv2.inRange(hsv, colors[0][0], colors[0][1])

                mask_ally = cv2.inRange(hsv, colors[1][0], colors[1][1])

                mask_unknown = cv2.inRange(hsv, colors[2][0], colors[2][1])

                confidence_list = [np.mean(mask_enemy), np.mean(mask_ally), np.mean(mask_unknown)]
                max_confidence_value = max(confidence_list)

                if (max_confidence_value > 160):
                    # остановка машины и серво
                    GPIO.output(GPIO_INTR, GPIO.LOW)
                    time.sleep(1)
                    GPIO.output(GPIO_INTR, GPIO.HIGH)

                    bus.write_byte(SLAVE_ONE_ADDRESS, ord('0'))

                    max_confidence_index = confidence_list.index(max_confidence_value)
                    if (max_confidence_index == 0):
                        print('enemy')
                        db['fraction'] = -1
                    elif (max_confidence_index == 1):
                        print('ally')
                        db['fraction'] = 1
                    elif (max_confidence_index == 2):
                        print('unknown')
                        db['fraction'] = 0
                    
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
                    time.sleep(0.5)
                    db['state'] = -1
                    bus.write_byte(SLAVE_ONE_ADDRESS, ord('1'))

            # encode as a jpeg image and return it
            r = cv2.rectangle(img, upper_left, bottom_right, (100, 50, 200), 5)
            yield cv2.imencode('.jpg', img)[1].tobytes()

            if cv2.waitKey(1) == 27:
                bus.write_byte(SLAVE_ONE_ADDRESS, ord('0'))

