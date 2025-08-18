from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import asyncio
import cv2
import numpy as np
import time
import logging
from collections import deque
from typing import List, Optional, Dict, Any
import json
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
import math

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Performance monitoring
@dataclass
class PerformanceStats:
    fps: float = 0.0
    buffer_size: int = 0
    latency: float = 0.0
    dropped_frames: int = 0
    total_frames: int = 0
    avg_frame_time: float = 0.0
    network_delay: float = 0.0
    microcontroller_delay: float = 0.0
    compensation_factor: float = 1.0
    quality_level: int = 85
    adaptive_quality: bool = True

@dataclass
class NetworkStats:
    avg_delay: float = 0.0
    jitter: float = 0.0
    packet_loss: int = 0
    last_frame_time: float = 0.0
    frame_intervals: List[float] = None
    
    def __post_init__(self):
        if self.frame_intervals is None:
            self.frame_intervals = []

@dataclass
class QualityController:
    target_fps: int = 60
    min_quality: int = 60
    max_quality: int = 95
    current_quality: int = 85
    performance_history: List[float] = None
    adjustment_threshold: float = 0.1
    
    def __post_init__(self):
        if self.performance_history is None:
            self.performance_history = []

# Global variables
frame_buffer = deque(maxlen=180)  # 3 seconds buffer at 60 FPS
frame_timestamps = deque(maxlen=180)
latest_frame: Optional[np.ndarray] = None
performance_stats = PerformanceStats()
network_stats = NetworkStats()
quality_controller = QualityController()
active_connections: List[WebSocket] = []
frame_lock = asyncio.Lock()
clients_lock = asyncio.Lock()

# FastAPI app with lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting intelligent FastAPI frame server...")
    yield
    # Shutdown
    logger.info("Shutting down FastAPI frame server...")

app = FastAPI(
    title="ESP32-CAM Frame Server",
    description="High-performance frame server with intelligent network compensation",
    version="3.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def calculate_network_compensation():
    """Calculate network compensation factors"""
    global network_stats, performance_stats
    
    if len(network_stats.frame_intervals) > 5:
        intervals = network_stats.frame_intervals[-30:]  # Last 30 intervals
        avg_interval = sum(intervals) / len(intervals)
        
        # Calculate jitter
        jitter = sum(abs(x - avg_interval) for x in intervals) / len(intervals)
        network_stats.jitter = jitter
        
        # Calculate compensation factor
        target_interval = 1.0 / quality_controller.target_fps
        if avg_interval > target_interval * 1.5:  # Network is slow
            performance_stats.compensation_factor = min(2.5, avg_interval / target_interval)
        elif avg_interval < target_interval * 0.5:  # Network is fast
            performance_stats.compensation_factor = max(0.3, avg_interval / target_interval)
        else:
            performance_stats.compensation_factor = 1.0

def adaptive_quality_control():
    """Adaptive quality control based on performance"""
    global quality_controller, performance_stats
    
    if len(quality_controller.performance_history) > 10:
        recent_fps = quality_controller.performance_history[-10:]
        avg_fps = sum(recent_fps) / len(recent_fps)
        
        target_fps = quality_controller.target_fps
        current_quality = quality_controller.current_quality
        
        # Adjust quality based on performance
        if avg_fps < target_fps * 0.7:  # Performance is poor
            new_quality = max(quality_controller.min_quality, current_quality - 8)
            quality_controller.current_quality = new_quality
            performance_stats.quality_level = new_quality
        elif avg_fps > target_fps * 0.9:  # Performance is good
            new_quality = min(quality_controller.max_quality, current_quality + 3)
            quality_controller.current_quality = new_quality
            performance_stats.quality_level = new_quality

def calculate_performance_stats():
    """Calculate real-time performance statistics"""
    global performance_stats, network_stats, quality_controller
    
    current_time = time.time()
    if len(frame_timestamps) > 1:
        time_window = current_time - frame_timestamps[0]
        if time_window > 0:
            performance_stats.fps = len(frame_timestamps) / time_window
            
            # Update quality controller history
            quality_controller.performance_history.append(performance_stats.fps)
            if len(quality_controller.performance_history) > 100:
                quality_controller.performance_history.pop(0)
    
    performance_stats.buffer_size = len(frame_buffer)
    performance_stats.total_frames = len(frame_timestamps)
    
    if len(frame_timestamps) > 1:
        frame_times = [frame_timestamps[i] - frame_timestamps[i-1] 
                      for i in range(1, len(frame_timestamps))]
        performance_stats.avg_frame_time = sum(frame_times) / len(frame_times) * 1000
    
    # Calculate network compensation
    calculate_network_compensation()
    
    # Adaptive quality control
    adaptive_quality_control()

async def frame_processor():
    """Async frame processor for optimal performance"""
    global latest_frame, frame_buffer, frame_timestamps, performance_stats, network_stats
    
    while True:
        try:
            await asyncio.sleep(0.001)  # 1ms sleep for async processing
            
            # Process frames in buffer
            if len(frame_buffer) > 150:  # Keep buffer at 80% capacity
                frame_buffer.popleft()
                if frame_timestamps:
                    frame_timestamps.popleft()
                performance_stats.dropped_frames += 1
                
                # Increase compensation if dropping frames
                performance_stats.compensation_factor = min(2.5, 
                    performance_stats.compensation_factor * 1.05)
            
            calculate_performance_stats()
            
        except Exception as e:
            logger.error(f"Error in frame processor: {e}")
            await asyncio.sleep(0.01)

@app.get("/")
async def root():
    """Root endpoint with server info"""
    return {
        "server": "FastAPI ESP32-CAM Frame Server",
        "version": "3.0.0",
        "features": [
            "Intelligent network compensation",
            "Adaptive quality control",
            "Advanced buffering (180 frames)",
            "Real-time performance monitoring"
        ],
        "endpoints": {
            "video_feed": "/esp32_video_feed",
            "single_frame": "/esp32_frame",
            "performance": "/performance_stats",
            "health": "/health",
            "reset_stats": "/reset_stats"
        }
    }

@app.get("/esp32_frame")
async def get_single_frame():
    """Get single frame with intelligent response"""
    global latest_frame, performance_stats
    
    if latest_frame is None:
        raise HTTPException(status_code=503, detail="No frame available")
    
    # Use adaptive quality
    quality = performance_stats.quality_level
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    ret, buffer = cv2.imencode('.jpg', latest_frame, encode_param)
    
    return Response(
        content=buffer.tobytes(),
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Frame-Quality": str(quality),
            "X-Compensation-Factor": str(performance_stats.compensation_factor),
            "X-Buffer-Size": str(performance_stats.buffer_size)
        }
    )

@app.get("/esp32_video_feed")
async def video_feed():
    """High-performance video stream with intelligent frame delivery"""
    
    async def generate_frames():
        global frame_buffer, performance_stats, network_stats
        
        target_fps = quality_controller.target_fps
        frame_interval = 1.0 / target_fps
        last_frame_time = time.time()
        
        consecutive_empty_frames = 0
        max_empty_frames = 15
        
        while True:
            try:
                start_time = time.time()
                
                # Get frame from buffer with compensation
                frame_to_send = None
                async with frame_lock:
                    if frame_buffer:
                        frame_to_send = frame_buffer.popleft()
                        if frame_timestamps:
                            frame_timestamps.popleft()
                        consecutive_empty_frames = 0
                    else:
                        consecutive_empty_frames += 1
                
                if frame_to_send is not None:
                    # Use adaptive quality
                    quality = performance_stats.quality_level
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
                    ret, buffer = cv2.imencode('.jpg', frame_to_send, encode_param)
                    frame_bytes = buffer.tobytes()
                    
                    # Calculate processing latency
                    processing_time = time.time() - start_time
                    performance_stats.latency = processing_time * 1000
                    
                    # Apply network compensation
                    compensation = performance_stats.compensation_factor
                    adjusted_interval = frame_interval * compensation
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    
                    last_frame_time = time.time()
                    
                    # Intelligent sleep with compensation
                    elapsed = time.time() - start_time
                    sleep_time = max(0, adjusted_interval - elapsed)
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                        
                else:
                    # Handle empty buffer intelligently
                    if consecutive_empty_frames < max_empty_frames:
                        # Send empty frame to maintain connection
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + b'\r\n')
                        
                        # Adaptive sleep based on compensation
                        compensation = performance_stats.compensation_factor
                        sleep_time = frame_interval * compensation * 0.3
                        await asyncio.sleep(sleep_time)
                    else:
                        # Too many empty frames, increase sleep
                        await asyncio.sleep(frame_interval * 3)
                        
            except Exception as e:
                logger.error(f"Error in video feed: {e}")
                await asyncio.sleep(0.01)
    
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Compensation-Factor": str(performance_stats.compensation_factor),
            "X-Quality-Level": str(performance_stats.quality_level)
        }
    )

@app.get("/performance_stats")
async def get_performance_stats():
    """Get comprehensive performance statistics"""
    return {
        "fps": round(performance_stats.fps, 2),
        "buffer_size": performance_stats.buffer_size,
        "latency_ms": round(performance_stats.latency, 2),
        "dropped_frames": performance_stats.dropped_frames,
        "total_frames": performance_stats.total_frames,
        "avg_frame_time_ms": round(performance_stats.avg_frame_time, 2),
        "active_connections": len(active_connections),
        "compensation_factor": round(performance_stats.compensation_factor, 3),
        "quality_level": performance_stats.quality_level,
        "network_stats": {
            "jitter": round(network_stats.jitter, 4),
            "avg_delay": round(network_stats.avg_delay, 4),
            "packet_loss": network_stats.packet_loss
        },
        "quality_controller": {
            "target_fps": quality_controller.target_fps,
            "current_quality": quality_controller.current_quality,
            "min_quality": quality_controller.min_quality,
            "max_quality": quality_controller.max_quality
        },
        "buffer_utilization": round(len(frame_buffer) / 180 * 100, 1),
        "compensation_active": performance_stats.compensation_factor != 1.0
    }

@app.get("/health")
async def health_check():
    """Enhanced health check"""
    return {
        "status": "healthy",
        "fps": round(performance_stats.fps, 2),
        "buffer_size": performance_stats.buffer_size,
        "active_connections": len(active_connections),
        "compensation_factor": round(performance_stats.compensation_factor, 3),
        "quality_level": performance_stats.quality_level,
        "network_jitter": round(network_stats.jitter, 4),
        "uptime": time.time() - network_stats.last_frame_time if network_stats.last_frame_time > 0 else 0
    }

@app.get("/reset_stats")
async def reset_stats():
    """Reset all performance statistics"""
    global performance_stats, network_stats, quality_controller
    
    performance_stats = PerformanceStats()
    network_stats = NetworkStats()
    quality_controller = QualityController()
    
    return {"status": "stats_reset", "message": "All statistics have been reset"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Robust WebSocket handler for frame reception"""
    global latest_frame, frame_buffer, frame_timestamps, active_connections, performance_stats, network_stats
    
    await websocket.accept()
    
    async with clients_lock:
        active_connections.append(websocket)
    logger.info(f"WebSocket client connected. Total clients: {len(active_connections)}")
    
    try:
        while True:
            try:
                # Receive data from ESP32-CAM
                data = await websocket.receive()
                
                if data.get("type") == "websocket.disconnect":
                    break
                
                # Handle binary data
                if "bytes" in data:
                    frame_data = data["bytes"]
                    img = np.frombuffer(frame_data, dtype=np.uint8)
                    frame = cv2.imdecode(img, cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        async with frame_lock:
                            latest_frame = frame
                            frame_buffer.append(frame)
                            frame_timestamps.append(time.time())
                            
                            # Update network stats
                            current_time = time.time()
                            if network_stats.last_frame_time > 0:
                                interval = current_time - network_stats.last_frame_time
                                network_stats.frame_intervals.append(interval)
                                if len(network_stats.frame_intervals) > 50:
                                    network_stats.frame_intervals.pop(0)
                            network_stats.last_frame_time = current_time
                            
                            # Maintain buffer size
                            if len(frame_buffer) > 160:  # Keep at 90% capacity
                                frame_buffer.popleft()
                                if frame_timestamps:
                                    frame_timestamps.popleft()
                                performance_stats.dropped_frames += 1
                                
                                # Increase compensation if dropping frames
                                performance_stats.compensation_factor = min(2.5, 
                                    performance_stats.compensation_factor * 1.05)
                                
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
                break
            except Exception as e:
                logger.error(f"Error processing WebSocket frame: {e}")
                # Continue processing other messages
                continue
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        async with clients_lock:
            if websocket in active_connections:
                active_connections.remove(websocket)
        logger.info(f"WebSocket client removed. Total clients: {len(active_connections)}")

@app.websocket("/ws_stats")
async def websocket_stats(websocket: WebSocket):
    """WebSocket endpoint for real-time performance stats"""
    await websocket.accept()
    
    try:
        while True:
            # Send performance stats every second
            stats = {
                "fps": round(performance_stats.fps, 2),
                "buffer_size": performance_stats.buffer_size,
                "latency_ms": round(performance_stats.latency, 2),
                "dropped_frames": performance_stats.dropped_frames,
                "active_connections": len(active_connections),
                "compensation_factor": round(performance_stats.compensation_factor, 3),
                "quality_level": performance_stats.quality_level,
                "network_jitter": round(network_stats.jitter, 4),
                "buffer_utilization": round(len(frame_buffer) / 180 * 100, 1)
            }
            await websocket.send_text(json.dumps(stats))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("Stats WebSocket disconnected")
    except Exception as e:
        logger.error(f"Stats WebSocket error: {e}")

# Start frame processor task
@app.on_event("startup")
async def startup_event():
    """Start background tasks on startup"""
    asyncio.create_task(frame_processor())

if __name__ == "__main__":
    uvicorn.run(
        "fastapi_frame_server:app",
        host="0.0.0.0",
        port=3003,
        reload=False,
        workers=1,
        loop="asyncio",
        access_log=True
    ) 