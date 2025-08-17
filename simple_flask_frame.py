from flask import Flask, render_template, request, jsonify, url_for, Response
from flask_cors import CORS
from flask_sock import Sock
import sqlite3
import datetime
import json
import os
import time
import numpy as np
import cv2
from queue import Queue
from threading import Lock

app = Flask(__name__)
CORS(app)
sock = Sock(app)



# متغیرهای جهانی برای مدیریت فریم‌های ESP32-CAM
esp32_frame_queue = Queue(maxsize=1)
frame_lock = Lock()
latest_frame = None



# لیست اتصال‌های وب‌سوکت فعال
clients = []

#@app.route('/')
#def index():
#    return render_template('index.html')


@app.route('/esp32_frame')
def esp32_frame():
    global latest_frame
    with frame_lock:
        if latest_frame is None:
            return Response(status=503)  # Service Unavailable
        ret, buffer = cv2.imencode('.jpg', latest_frame)
        return Response(buffer.tobytes(), mimetype='image/jpeg')

@app.route('/esp32_video_feed')
def esp32_video_feed():
    def generate():
        global latest_frame
        while True:
            with frame_lock:
                if latest_frame is None:
                    continue
                ret, buffer = cv2.imencode('.jpg', latest_frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.1)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@sock.route('/ws')
def websocket(ws):
    global latest_frame
    clients.append(ws)
    print("یک کلاینت وب‌سوکت متصل شد. تعداد:", len(clients))
    try:
        while True:
            data = ws.receive()
            if data is None:
                break
            try:
                # بررسی اگر داده باینری (فریم از ESP32-CAM) باشد
                if isinstance(data, bytes):
                    img = np.frombuffer(data, dtype=np.uint8)
                    frame = cv2.imdecode(img, cv2.IMREAD_COLOR)
                    if frame is not None:
                        with frame_lock:
                            latest_frame = frame
                            if esp32_frame_queue.full():
                                esp32_frame_queue.get()
                            esp32_frame_queue.put(frame)
            except Exception as e:
                print("❌ خطا در پردازش پیام وب‌سوکت:", e)
    except Exception as e:
        print("❌ خطا در وب‌سوکت:", e)
    finally:
        clients.remove(ws)
        print("یک کلاینت وب‌سوکت قطع شد. تعداد:", len(clients))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3002, threaded=True)