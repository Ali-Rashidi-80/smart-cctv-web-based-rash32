"""
System management module for the spy_servo system.
This module handles system-level operations like performance monitoring, 
frame processing, and system health management.
"""

import asyncio
import time
import os
import gc
import logging
import signal
import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, Depends

# Setup logger
logger = logging.getLogger("system_manager")

# Global system state reference (will be set by main server)
system_state = None

# Global dependencies (will be set by main server)
insert_log_func = None
send_to_web_clients_func = None
send_to_pico_client_func = None
send_to_esp32cam_client_func = None
get_current_user_func = None

def set_system_state(state):
    """Set the system state reference from main server"""
    global system_state
    system_state = state

def get_system_state():
    """Safely get system state, creating temporary one if needed"""
    global system_state
    if system_state is None:
        logger.warning("⚠️ system_state not initialized yet, creating temporary state")
        # Create a temporary system state for initialization
        class TempSystemState:
            def __init__(self):
                self.frame_buffer_lock = asyncio.Lock()
                self.web_clients_lock = asyncio.Lock()
                self.performance_lock = asyncio.Lock()
                self.frame_buffer = []
                self.web_clients = []
                self.performance_metrics = {"avg_frame_latency": 0.0, "frame_processing_overhead": 0.0, "frame_drop_rate": 0.0, "memory_usage": 0.0, "cpu_usage": 0.0}
                self.frame_count = 0
                self.frame_drop_count = 0
                self.frame_skip_count = 0
                self.invalid_frame_count = 0
                self.current_quality = 80
                self.adaptive_quality = False
                self.realtime_enabled = False
                self.processing_enabled = True
                self.last_error_reset = time.time()
                self.last_performance_update = time.time()
                self.last_backup_time = time.time()
                self.last_frame_cache_cleanup = time.time()
                self.last_disk_space = 'N/A'
                self.memory_warning_sent = False
                self.frame_processing_times = []
                self.frame_cache = {}
                self.error_counts = {"websocket": 0, "database": 0, "frame_processing": 0, "memory": 0}
                self.last_cleanup_time = None
                self.system_shutdown = False
                self.frame_latency_sum = 0.0
                self.processing_timeout = 5.0
        system_state = TempSystemState()
    return system_state

def set_dependencies(log_func, web_clients_func, pico_func, esp32cam_func, current_user_func):
    """Set the dependencies from main server"""
    global insert_log_func, send_to_web_clients_func, send_to_pico_client_func, send_to_esp32cam_client_func, get_current_user_func
    insert_log_func = log_func
    send_to_web_clients_func = web_clients_func
    send_to_pico_client_func = pico_func
    send_to_esp32cam_client_func = esp32cam_func
    get_current_user_func = current_user_func

async def insert_log(message: str, log_type: str, source: str = "system_manager"):
    """Insert log entry using the main server's log function"""
    if insert_log_func:
        await insert_log_func(message, log_type, source)
    else:
        logger.info(f"[{source}] {message}")

async def send_to_web_clients(message):
    """Send message to web clients using the main server's function"""
    if send_to_web_clients_func:
        await send_to_web_clients_func(message)
    else:
        logger.warning("Web clients function not available")

async def send_to_pico_client(message):
    """Send message to pico client using the main server's function"""
    if send_to_pico_client_func:
        await send_to_pico_client_func(message)
    else:
        logger.warning("Pico client function not available")

async def send_to_esp32cam_client(message):
    """Send message to esp32cam client using the main server's function"""
    if send_to_esp32cam_client_func:
        await send_to_esp32cam_client_func(message)
    else:
        logger.warning("ESP32CAM client function not available")

def get_current_user(request: Request):
    """Get current user using the main server's function"""
    if get_current_user_func:
        return get_current_user_func(request)
    else:
        logger.warning("Current user function not available")
        return None

# Frame Processing Functions
async def preprocess_frame(frame_data: bytes) -> bytes:
    """Preprocess frame data for optimal transmission"""
    try:
        # Decode frame
        nparr = np.frombuffer(frame_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            logger.warning("Invalid frame data received")
            return frame_data
        
        # Get current quality setting
        quality = get_system_state().current_quality
        
        # Resize frame if needed for performance
        height, width = frame.shape[:2]
        if width > 640 or height > 480:
            scale = min(640/width, 480/height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            frame = cv2.resize(frame, (new_width, new_height))
        
        # Apply quality compression
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, processed_frame = cv2.imencode('.jpg', frame, encode_param)
        
        return processed_frame.tobytes()
        
    except Exception as e:
        logger.error(f"Frame preprocessing error: {e}")
        return frame_data

async def add_persian_text_overlay(frame_data: bytes) -> bytes:
    """Add Persian text overlay to frame"""
    try:
        # Decode frame
        nparr = np.frombuffer(frame_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return frame_data
        
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Add Persian text if needed
        # Note: Persian text rendering requires additional font support
        
        # Re-encode frame
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
        _, processed_frame = cv2.imencode('.jpg', frame, encode_param)
        
        return processed_frame.tobytes()
        
    except Exception as e:
        logger.error(f"Text overlay error: {e}")
        return frame_data

async def compress_frame_intelligently(frame_data: bytes) -> bytes:
    """Intelligently compress frame based on system performance"""
    try:
        # Get current performance metrics
        metrics = get_system_state().performance_metrics
        memory_usage = metrics.get("memory_usage", 0)
        cpu_usage = metrics.get("cpu_usage", 0)
        
        # Adjust quality based on system load
        base_quality = 80
        if memory_usage > 80 or cpu_usage > 80:
            base_quality = 60
        elif memory_usage > 60 or cpu_usage > 60:
            base_quality = 70
        
        # Decode and re-encode with adjusted quality
        nparr = np.frombuffer(frame_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return frame_data
        
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), base_quality]
        _, compressed_frame = cv2.imencode('.jpg', frame, encode_param)
        
        return compressed_frame.tobytes()
        
    except Exception as e:
        logger.error(f"Frame compression error: {e}")
        return frame_data

async def send_frame_to_clients(frame_data: bytes):
    """Send frame to all connected clients"""
    try:
        # Preprocess frame
        processed_frame = await preprocess_frame(frame_data)
        
        # Add text overlay if enabled
        if get_system_state().realtime_enabled:
            processed_frame = await add_persian_text_overlay(processed_frame)
        
        # Compress frame intelligently
        compressed_frame = await compress_frame_intelligently(processed_frame)
        
        # Send to web clients
        await send_to_web_clients({
            "type": "frame",
            "data": compressed_frame,
            "timestamp": datetime.now().isoformat()
        })
        
        # Update frame statistics
        get_system_state().frame_count += 1
        
    except Exception as e:
        logger.error(f"Error sending frame to clients: {e}")
        get_system_state().error_counts["frame_processing"] += 1

# Performance Management Functions
async def update_performance_metrics():
    """Update system performance metrics"""
    try:
        import psutil
        
        # Get system metrics
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Calculate frame processing metrics
        frame_times = get_system_state().frame_processing_times
        if frame_times:
            avg_latency = sum(frame_times) / len(frame_times)
            frame_times.clear()  # Clear old times
        else:
            avg_latency = 0.0
        
        # Update metrics
        get_system_state().performance_metrics.update({
            "memory_usage": memory.percent,
            "cpu_usage": cpu_percent,
            "avg_frame_latency": avg_latency,
            "frame_drop_rate": get_system_state().frame_drop_count / max(get_system_state().frame_count, 1)
        })
        
        # Check for memory warnings
        if memory.percent > 85 and not get_system_state().memory_warning_sent:
            await insert_log(f"High memory usage: {memory.percent}%", "warning", "system")
            get_system_state().memory_warning_sent = True
        elif memory.percent < 70:
            get_system_state().memory_warning_sent = False
            
    except ImportError:
        logger.warning("psutil not available for performance monitoring")
    except Exception as e:
        logger.error(f"Error updating performance metrics: {e}")

async def cleanup_frame_cache():
    """Clean up old frame cache entries"""
    try:
        cache = get_system_state().frame_cache
        current_time = time.time()
        
        # Remove entries older than 5 minutes
        expired_keys = [k for k, v in cache.items() if current_time - v.get('timestamp', 0) > 300]
        
        for key in expired_keys:
            del cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired frame cache entries")
            
    except Exception as e:
        logger.error(f"Error cleaning frame cache: {e}")

async def get_performance_metrics(user=None):
    """Get current performance metrics"""
    try:
        # Update metrics first
        await update_performance_metrics()
        
        metrics = get_system_state().performance_metrics.copy()
        metrics.update({
            "frame_count": get_system_state().frame_count,
            "frame_drop_count": get_system_state().frame_drop_count,
            "frame_skip_count": get_system_state().frame_skip_count,
            "invalid_frame_count": get_system_state().invalid_frame_count,
            "current_quality": get_system_state().current_quality,
            "adaptive_quality": get_system_state().adaptive_quality,
            "realtime_enabled": get_system_state().realtime_enabled,
            "processing_enabled": get_system_state().processing_enabled,
            "error_counts": get_system_state().error_counts.copy(),
            "timestamp": datetime.now().isoformat()
        })
        
        return {"status": "success", "data": metrics}
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        return {"status": "error", "error": str(e)}

# System Management Functions
def signal_handler(signum, frame):
    """Handle system signals for graceful shutdown"""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    get_system_state().system_shutdown = True
    
    # Perform cleanup tasks
    try:
        # Close database connections
        # Stop background tasks
        # Save system state
        logger.info("System shutdown completed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

async def robust_db_endpoint(func):
    """Decorator for robust database endpoint handling"""
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Database endpoint error in {func.__name__}: {e}")
            await insert_log(f"Database error in {func.__name__}: {e}", "error", "system")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    return wrapper

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler) 