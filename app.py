#!/usr/bin/env python
from importlib import import_module
import os
from flask import Flask, render_template, Response, request, jsonify
import camera_opencv_color
from camera_opencv_color import db

Camera = import_module('camera_opencv_color').Camera
from camera_opencv import bus, SLAVE_ONE_ADDRESS

app = Flask(__name__)

@app.route('/')
def index():
    """Video streaming home page."""
    return render_template('index.html')


def gen(camera):
    """Video streaming generator function."""
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/video_feed')
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    return Response(gen(Camera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/get_db')
def get_db():
    return jsonify(db)


@app.route('/fire', methods=['POST'])
def fire():
    firing = request.args.get('fire_value')
    db['found_someone'] = False
    if firing == 'True':
        db['state'] = 1
        return Response('200')
    elif firing == 'False':
        db['state'] = 0
        return Response('200')
    return Response('400')


# Начало движения
@app.route('/start')
def start():
    bus.write_byte(SLAVE_ONE_ADDRESS, ord('1'))
    return Response('200')


# Остановка машины
@app.route('/stop')
def stop():
    bus.write_byte(SLAVE_ONE_ADDRESS, ord('0'))
    return Response('200')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, threaded=True)
