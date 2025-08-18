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
from queue import Queue, deque, PriorityQueue
from threading import Lock, Thread, Event, Condition
import logging
from collections import deque, defaultdict
import asyncio
import threading
import math
import statistics
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any
import heapq

# Configure advanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('intelligent_flask_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
sock = Sock(app)

# Advanced data structures for intelligent frame management
@dataclass
class FrameData:
    """Advanced frame data structure with metadata"""
    frame: np.ndarray
    timestamp: float
    sequence_number: int
    quality_score: float = 0.0
    network_delay: float = 0.0
    processing_time: float = 0.0
    priority: float = 0.0
    
    def __post_init__(self):
        self.priority = self.calculate_priority()
    
    def calculate_priority(self) -> float:
        """Calculate frame priority based on multiple factors"""
        age_factor = max(0, 1.0 - (time.time() - self.timestamp) * 2.0)  # Decay with age
        quality_factor = self.quality_score / 100.0
        delay_factor = max(0, 1.0 - self.network_delay * 0.1)  # Penalize high delay
        return (age_factor * 0.4 + quality_factor * 0.3 + delay_factor * 0.3)

@dataclass
class NetworkMetrics:
    """Advanced network performance metrics"""
    avg_latency: float = 0.0
    jitter: float = 0.0
    packet_loss_rate: float = 0.0
    bandwidth_utilization: float = 0.0
    connection_stability: float = 1.0
    last_update: float = 0.0
    latency_history: List[float] = field(default_factory=list)
    frame_intervals: List[float] = field(default_factory=list)
    
    def update_metrics(self, new_latency: float, new_interval: float):
        """Update network metrics with exponential moving average"""
        self.latency_history.append(new_latency)
        self.frame_intervals.append(new_interval)
        
        # Keep only recent history
        if len(self.latency_history) > 50:
            self.latency_history.pop(0)
        if len(self.frame_intervals) > 50:
            self.frame_intervals.pop(0)
        
        # Calculate metrics
        if len(self.latency_history) > 5:
            self.avg_latency = statistics.mean(self.latency_history[-10:])
            self.jitter = statistics.stdev(self.latency_history[-10:]) if len(self.latency_history) > 1 else 0
            
            # Calculate packet loss rate based on interval variations
            expected_interval = 1.0 / 60.0  # 60 FPS target
            interval_variations = [abs(x - expected_interval) for x in self.frame_intervals[-10:]]
            self.packet_loss_rate = min(1.0, statistics.mean(interval_variations) / expected_interval)
        
        self.last_update = time.time()

@dataclass
class AdaptiveController:
    """Intelligent adaptive control system"""
    target_fps: int = 60
    min_quality: int = 50
    max_quality: int = 95
    current_quality: int = 85
    compensation_factor: float = 1.0
    buffer_target: int = 90
    performance_history: List[float] = field(default_factory=list)
    quality_history: List[int] = field(default_factory=list)
    adaptation_rate: float = 0.1
    
    def adapt_parameters(self, current_fps: float, buffer_utilization: float, 
                        network_metrics: NetworkMetrics) -> Tuple[int, float]:
        """Intelligent parameter adaptation"""
        # Update history
        self.performance_history.append(current_fps)
        self.quality_history.append(self.current_quality)
        
        if len(self.performance_history) > 100:
            self.performance_history.pop(0)
        if len(self.quality_history) > 100:
            self.quality_history.pop(0)
        
        # Calculate performance trends
        if len(self.performance_history) > 10:
            recent_fps = self.performance_history[-10:]
            avg_fps = statistics.mean(recent_fps)
            fps_trend = statistics.mean(recent_fps[-5:]) - statistics.mean(recent_fps[:5])
            
            # Quality adaptation based on performance
            target_fps = self.target_fps
            if avg_fps < target_fps * 0.7:  # Poor performance
                quality_change = -max(5, int((target_fps - avg_fps) / 2))
                self.current_quality = max(self.min_quality, self.current_quality + quality_change)
            elif avg_fps > target_fps * 0.9 and fps_trend > 0:  # Good performance
                quality_change = min(3, int((avg_fps - target_fps * 0.8) / 5))
                self.current_quality = min(self.max_quality, self.current_quality + quality_change)
            
            # Compensation factor adaptation
            network_factor = 1.0 + network_metrics.jitter * 10.0  # Increase compensation for high jitter
            buffer_factor = 1.0 + (1.0 - buffer_utilization) * 0.5  # Increase if buffer is empty
            performance_factor = 1.0 + (target_fps - avg_fps) / target_fps  # Increase if FPS is low
            
            self.compensation_factor = min(3.0, network_factor * buffer_factor * performance_factor)
        
        return self.current_quality, self.compensation_factor

# Global intelligent systems
frame_buffer = deque(maxlen=100)  # کاهش بافر برای کاهش تأخیر
frame_queue = PriorityQueue(maxsize=50)  # کاهش صف برای سرعت بیشتر
frame_lock = Lock()
frame_condition = Condition(frame_lock)
latest_frame: Optional[np.ndarray] = None
sequence_counter = 0

# Advanced monitoring systems
network_metrics = NetworkMetrics()
adaptive_controller = AdaptiveController()
performance_stats = {
    'fps': 0.0,
    'buffer_size': 0,
    'latency': 0.0,
    'dropped_frames': 0,
    'quality_level': 85,
    'compensation_factor': 1.0,
    'network_jitter': 0.0,
    'packet_loss_rate': 0.0,
    'buffer_utilization': 0.0,
    'frame_processing_time': 0.0,
    'total_frames_processed': 0,
    'avg_frame_quality': 0.0
}

# Connection management
clients = []
clients_lock = Lock()
connection_stats = defaultdict(lambda: {
    'connected_time': 0.0,
    'frames_received': 0,
    'last_activity': 0.0,
    'avg_latency': 0.0
})

# Intelligent frame processor
class IntelligentFrameProcessor(Thread):
    """Advanced frame processor with intelligent buffering and compensation"""
    
    def __init__(self):
        super().__init__(daemon=True)
        self.running = True
        self.frame_timestamps = deque(maxlen=200)
        self.processing_stats = deque(maxlen=100)
        
    def run(self):
        while self.running:
            try:
                # Process frames from priority queue
                if not frame_queue.empty():
                    priority, frame_data = frame_queue.get_nowait()
                    
                    with frame_lock:
                        # Update latest frame
                        latest_frame = frame_data.frame
                        
                        # Add to buffer with intelligent management
                        if len(frame_buffer) >= frame_buffer.maxlen * 0.95:
                            # Remove oldest frames when buffer is nearly full
                            while len(frame_buffer) > frame_buffer.maxlen * 0.8:
                                frame_buffer.popleft()
                                if self.frame_timestamps:
                                    self.frame_timestamps.popleft()
                                performance_stats['dropped_frames'] += 1
                        
                        frame_buffer.append(frame_data)
                        self.frame_timestamps.append(frame_data.timestamp)
                        
                        # Update performance statistics
                        self.update_performance_stats(frame_data)
                        
                        # Notify waiting consumers
                        frame_condition.notify_all()
                
                # Adaptive control update
                self.update_adaptive_control()
                
                time.sleep(0.001)  # 1ms sleep for responsive processing
                
            except Exception as e:
                logger.error(f"Error in frame processor: {e}")
                time.sleep(0.01)
    
    def update_performance_stats(self, frame_data: FrameData):
        """Update comprehensive performance statistics"""
        current_time = time.time()
        
        # Calculate FPS
        if len(self.frame_timestamps) > 1:
            time_window = current_time - self.frame_timestamps[0]
            if time_window > 0:
                performance_stats['fps'] = len(self.frame_timestamps) / time_window
        
        performance_stats['buffer_size'] = len(frame_buffer)
        performance_stats['buffer_utilization'] = len(frame_buffer) / frame_buffer.maxlen * 100
        performance_stats['frame_processing_time'] = frame_data.processing_time
        performance_stats['total_frames_processed'] += 1
        
        # Update network metrics
        if len(self.frame_timestamps) > 1:
            interval = frame_data.timestamp - self.frame_timestamps[-2]
            network_metrics.update_metrics(frame_data.network_delay, interval)
            
            performance_stats['network_jitter'] = network_metrics.jitter
            performance_stats['packet_loss_rate'] = network_metrics.packet_loss_rate
    
    def update_adaptive_control(self):
        """Update adaptive control parameters"""
        current_fps = performance_stats['fps']
        buffer_utilization = performance_stats['buffer_utilization'] / 100.0
        
        quality, compensation = adaptive_controller.adapt_parameters(
            current_fps, buffer_utilization, network_metrics
        )
        
        performance_stats['quality_level'] = quality
        performance_stats['compensation_factor'] = compensation

# Start intelligent frame processor
frame_processor = IntelligentFrameProcessor()
frame_processor.start()

@app.route('/esp32_frame')
def esp32_frame():
    """Intelligent single frame endpoint with advanced response optimization"""
    global latest_frame, performance_stats
    
    with frame_lock:
        if latest_frame is None:
            return Response(status=503, headers={'Retry-After': '1'})
        
        # Use adaptive quality with intelligent encoding
        quality = performance_stats['quality_level']
        
        # Optimize encoding parameters based on performance
        encode_params = [
            int(cv2.IMWRITE_JPEG_QUALITY), quality,
            int(cv2.IMWRITE_JPEG_OPTIMIZE), 1,
            int(cv2.IMWRITE_JPEG_PROGRESSIVE), 1
        ]
        
        start_time = time.time()
        ret, buffer = cv2.imencode('.jpg', latest_frame, encode_params)
        encoding_time = time.time() - start_time
        
        if not ret:
            return Response(status=500)
        
        # Calculate response headers with comprehensive metrics
        headers = {
            'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
            'Expires': '0',
            'X-Frame-Quality': str(quality),
            'X-Compensation-Factor': f"{performance_stats['compensation_factor']:.3f}",
            'X-Buffer-Size': str(performance_stats['buffer_size']),
            'X-Buffer-Utilization': f"{performance_stats['buffer_utilization']:.1f}%",
            'X-Network-Jitter': f"{performance_stats['network_jitter']:.4f}",
            'X-Packet-Loss-Rate': f"{performance_stats['packet_loss_rate']:.3f}",
            'X-Encoding-Time': f"{encoding_time*1000:.2f}ms",
            'X-FPS': f"{performance_stats['fps']:.2f}",
            'X-Total-Frames': str(performance_stats['total_frames_processed'])
        }
        
        return Response(buffer.tobytes(), mimetype='image/jpeg', headers=headers)

@app.route('/esp32_video_feed')
def esp32_video_feed():
    """Advanced intelligent video stream with sophisticated compensation"""
    
    def generate_intelligent_stream():
        target_fps = 60  # افزایش به 60 FPS
        frame_interval = 1.0 / target_fps
        last_frame_time = time.time()
        consecutive_empty_frames = 0
        max_empty_frames = 30  # کاهش تعداد فریم‌های خالی مجاز
        frame_count = 0
        last_sent_frame = None  # نگهداری آخرین فریم ارسال شده
        
        while True:
            try:
                start_time = time.time()
                
                # Intelligent frame selection with compensation
                frame_to_send = None
                with frame_lock:
                    if frame_buffer:
                        # Select best frame based on priority and timing
                        frame_to_send = frame_buffer.popleft()
                        if frame_processor.frame_timestamps:
                            frame_processor.frame_timestamps.popleft()
                        consecutive_empty_frames = 0
                        frame_count += 1
                        last_sent_frame = frame_to_send  # ذخیره آخرین فریم
                    else:
                        consecutive_empty_frames += 1
                        # اگر فریم جدیدی نداریم، از آخرین فریم ارسال شده استفاده کنیم
                        if last_sent_frame is not None and consecutive_empty_frames < max_empty_frames:
                            frame_to_send = last_sent_frame
                
                if frame_to_send is not None:
                    # Advanced encoding with adaptive quality - بهینه‌سازی شده
                    quality = min(85, performance_stats['quality_level'])  # محدود کردن کیفیت برای سرعت
                    compensation = min(1.5, performance_stats['compensation_factor'])  # محدود کردن compensation
                    
                    # Optimize encoding based on network conditions
                    if performance_stats['network_jitter'] > 0.1:  # High jitter
                        quality = max(60, quality - 10)
                    
                    encode_params = [
                        int(cv2.IMWRITE_JPEG_QUALITY), quality,
                        int(cv2.IMWRITE_JPEG_OPTIMIZE), 1
                    ]
                    
                    ret, buffer = cv2.imencode('.jpg', frame_to_send.frame, encode_params)
                    frame_bytes = buffer.tobytes()
                    
                    # Calculate processing metrics
                    processing_time = time.time() - start_time
                    performance_stats['latency'] = processing_time * 1000
                    
                    # Apply intelligent compensation - بهینه‌سازی شده
                    adjusted_interval = frame_interval * compensation
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    
                    last_frame_time = time.time()
                    
                    # Intelligent sleep with compensation - بهینه‌سازی شده
                    elapsed = time.time() - start_time
                    sleep_time = max(0, adjusted_interval - elapsed)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                        
                else:
                    # Advanced empty buffer handling - بهینه‌سازی شده
                    if consecutive_empty_frames < max_empty_frames:
                        # Send keep-alive frame with minimal data
                        keep_alive_frame = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9'
                        
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + keep_alive_frame + b'\r\n')
                        
                        # Adaptive sleep based on compensation and buffer state - بهینه‌سازی شده
                        compensation = min(1.5, performance_stats['compensation_factor'])
                        buffer_utilization = performance_stats['buffer_utilization'] / 100.0
                        
                        # Shorter sleep if buffer is likely to fill soon - کاهش تأخیر
                        if buffer_utilization > 0.3:
                            sleep_time = frame_interval * compensation * 0.1  # کاهش تأخیر
                        else:
                            sleep_time = frame_interval * compensation * 0.2  # کاهش تأخیر
                        
                        time.sleep(sleep_time)
                    else:
                        # Extended sleep for very empty buffer - اما اتصال را قطع نکنیم
                        logger.warning(f"Buffer empty for {consecutive_empty_frames} frames, waiting for new frames...")
                        time.sleep(frame_interval * 1)  # کاهش زمان انتظار
                        consecutive_empty_frames = max_empty_frames - 10  # ریست کردن شمارنده
                        
            except Exception as e:
                logger.error(f"Error in intelligent video stream: {e}")
                time.sleep(0.005)  # کاهش تأخیر در صورت خطا
    
    response = Response(generate_intelligent_stream(), 
                       mimetype='multipart/x-mixed-replace; boundary=frame')
    response.headers.update({
        'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
        'Pragma': 'no-cache',
        'Expires': '0',
        'X-Compensation-Factor': f"{performance_stats['compensation_factor']:.3f}",
        'X-Quality-Level': str(performance_stats['quality_level']),
        'X-Network-Jitter': f"{performance_stats['network_jitter']:.4f}"
    })
    return response

@app.route('/performance_stats')
def get_performance_stats():
    """Comprehensive performance statistics with advanced metrics"""
    return jsonify({
        'fps': round(performance_stats['fps'], 2),
        'buffer_size': performance_stats['buffer_size'],
        'buffer_utilization': round(performance_stats['buffer_utilization'], 1),
        'latency_ms': round(performance_stats['latency'], 2),
        'dropped_frames': performance_stats['dropped_frames'],
        'quality_level': performance_stats['quality_level'],
        'compensation_factor': round(performance_stats['compensation_factor'], 3),
        'network_jitter': round(performance_stats['network_jitter'], 4),
        'packet_loss_rate': round(performance_stats['packet_loss_rate'], 3),
        'frame_processing_time': round(performance_stats['frame_processing_time'], 3),
        'total_frames_processed': performance_stats['total_frames_processed'],
        'avg_frame_quality': round(performance_stats['avg_frame_quality'], 1),
        'network_metrics': {
            'avg_latency': round(network_metrics.avg_latency, 4),
            'jitter': round(network_metrics.jitter, 4),
            'packet_loss_rate': round(network_metrics.packet_loss_rate, 3),
            'connection_stability': round(network_metrics.connection_stability, 3)
        },
        'adaptive_controller': {
            'target_fps': adaptive_controller.target_fps,
            'current_quality': adaptive_controller.current_quality,
            'compensation_factor': round(adaptive_controller.compensation_factor, 3),
            'adaptation_rate': adaptive_controller.adaptation_rate
        },
        'connection_stats': {
            'active_connections': len(clients),
            'total_connections': len(connection_stats)
        }
    })

@sock.route('/ws')
def websocket(ws):
    """Advanced WebSocket handler with intelligent error recovery and compensation"""
    global sequence_counter, clients
    
    client_id = id(ws)
    with clients_lock:
        clients.append(ws)
        connection_stats[client_id]['connected_time'] = time.time()
        connection_stats[client_id]['last_activity'] = time.time()
    
    logger.info(f"Advanced WebSocket client connected. Total clients: {len(clients)}")
    
    try:
        while True:
            try:
                data = ws.receive()
                if data is None:
                    break
                
                # Update client activity
                connection_stats[client_id]['last_activity'] = time.time()
                
                # Handle different data types intelligently
                if isinstance(data, bytes):
                    # Process frame data with advanced error handling
                    start_time = time.time()
                    
                    try:
                        img = np.frombuffer(data, dtype=np.uint8)
                        frame = cv2.imdecode(img, cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            # Calculate frame quality score
                            quality_score = calculate_frame_quality(frame)
                            
                            # Create advanced frame data
                            frame_data = FrameData(
                                frame=frame,
                                timestamp=time.time(),
                                sequence_number=sequence_counter,
                                quality_score=quality_score,
                                network_delay=time.time() - start_time,
                                processing_time=0.0
                            )
                            
                            sequence_counter += 1
                            connection_stats[client_id]['frames_received'] += 1
                            
                            # Add to priority queue with intelligent overflow handling
                            if not frame_queue.full():
                                frame_queue.put((-frame_data.priority, frame_data))
                            else:
                                # Remove lowest priority frame and add new one
                                try:
                                    frame_queue.get_nowait()
                                    frame_queue.put((-frame_data.priority, frame_data))
                                    performance_stats['dropped_frames'] += 1
                                except:
                                    pass
                    
                    except Exception as e:
                        logger.error(f"Error processing frame data: {e}")
                        continue
                        
                elif isinstance(data, str):
                    # Handle text commands
                    try:
                        command = json.loads(data)
                        if command.get('type') == 'ping':
                            response = {
                                'type': 'pong',
                                'timestamp': time.time(),
                                'server_stats': {
                                    'fps': round(performance_stats['fps'], 2),
                                    'buffer_utilization': round(performance_stats['buffer_utilization'], 1),
                                    'compensation_factor': round(performance_stats['compensation_factor'], 3)
                                }
                            }
                            ws.send(json.dumps(response))
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON received: {data}")
                        
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                continue
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Cleanup
        with clients_lock:
            if ws in clients:
                clients.remove(ws)
            if client_id in connection_stats:
                del connection_stats[client_id]
        logger.info(f"Advanced WebSocket client disconnected. Total clients: {len(clients)}")

def calculate_frame_quality(frame: np.ndarray) -> float:
    """Calculate frame quality score based on multiple factors"""
    try:
        # Calculate sharpness using Laplacian variance
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Calculate brightness
        brightness = np.mean(gray)
        
        # Calculate contrast
        contrast = np.std(gray)
        
        # Normalize and combine metrics
        sharpness_score = min(100, laplacian_var / 10)
        brightness_score = max(0, min(100, brightness / 2.55))
        contrast_score = max(0, min(100, contrast / 2.55))
        
        # Weighted combination
        quality_score = (sharpness_score * 0.5 + brightness_score * 0.25 + contrast_score * 0.25)
        
        return quality_score
        
    except Exception as e:
        logger.error(f"Error calculating frame quality: {e}")
        return 50.0  # Default quality score

@app.route('/health')
def health_check():
    """Advanced health check with comprehensive system status"""
    return jsonify({
        'status': 'healthy',
        'fps': round(performance_stats['fps'], 2),
        'buffer_size': performance_stats['buffer_size'],
        'buffer_utilization': round(performance_stats['buffer_utilization'], 1),
        'active_connections': len(clients),
        'compensation_factor': round(performance_stats['compensation_factor'], 3),
        'quality_level': performance_stats['quality_level'],
        'network_jitter': round(performance_stats['network_jitter'], 4),
        'packet_loss_rate': round(performance_stats['packet_loss_rate'], 3),
        'total_frames_processed': performance_stats['total_frames_processed'],
        'system_uptime': time.time() - connection_stats[0]['connected_time'] if connection_stats else 0,
        'frame_processor_active': frame_processor.is_alive(),
        'queue_size': frame_queue.qsize()
    })

@app.route('/reset_stats')
def reset_stats():
    """Reset all performance statistics and adaptive parameters"""
    global performance_stats, network_metrics, adaptive_controller, sequence_counter
    
    # Reset performance stats
    performance_stats.update({
        'fps': 0.0,
        'buffer_size': 0,
        'latency': 0.0,
        'dropped_frames': 0,
        'quality_level': 85,
        'compensation_factor': 1.0,
        'network_jitter': 0.0,
        'packet_loss_rate': 0.0,
        'buffer_utilization': 0.0,
        'frame_processing_time': 0.0,
        'total_frames_processed': 0,
        'avg_frame_quality': 0.0
    })
    
    # Reset network metrics
    network_metrics.latency_history.clear()
    network_metrics.frame_intervals.clear()
    
    # Reset adaptive controller
    adaptive_controller.performance_history.clear()
    adaptive_controller.quality_history.clear()
    adaptive_controller.current_quality = 85
    adaptive_controller.compensation_factor = 1.0
    
    # Reset sequence counter
    sequence_counter = 0
    
    # Clear frame buffer
    with frame_lock:
        frame_buffer.clear()
        frame_processor.frame_timestamps.clear()
    
    return jsonify({
        'status': 'stats_reset',
        'message': 'All statistics and adaptive parameters have been reset',
        'timestamp': time.time()
    })

if __name__ == '__main__':
    logger.info("Starting Intelligent Flask Server with Advanced Compensation...")
    logger.info("Features: Intelligent buffering, adaptive quality control, network compensation")
    app.run(host='0.0.0.0', port=3002, threaded=True, debug=False) 