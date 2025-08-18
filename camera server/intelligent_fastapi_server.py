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
from collections import deque, defaultdict
from typing import List, Optional, Dict, Any, Tuple
import json
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import math
import statistics
from enum import Enum
import heapq
from advanced_image_enhancement import image_enhancer, enhance_frame_for_server, EnhancementMode
import os
import datetime
from pathlib import Path

# Configure advanced logging with intelligent filtering
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('intelligent_fastapi_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Intelligent logging filter to reduce repetitive messages
class IntelligentLogFilter:
    def __init__(self):
        self.last_warnings = {}
        self.warning_cooldown = 30  # 30 seconds between similar warnings
        self.last_info_logs = {}
        self.info_cooldown = 60     # 60 seconds between similar info logs
    
    def should_log_warning(self, message_key: str, message: str) -> bool:
        current_time = time.time()
        if message_key not in self.last_warnings:
            self.last_warnings[message_key] = current_time
            return True
        
        if current_time - self.last_warnings[message_key] > self.warning_cooldown:
            self.last_warnings[message_key] = current_time
            return True
        
        return False
    
    def should_log_info(self, message_key: str, message: str) -> bool:
        current_time = time.time()
        if message_key not in self.last_info_logs:
            self.last_info_logs[message_key] = current_time
            return True
        
        if current_time - self.last_info_logs[message_key] > self.info_cooldown:
            self.last_info_logs[message_key] = current_time
            return True
        
        return False

# Global intelligent log filter
intelligent_log_filter = IntelligentLogFilter()

# Advanced enums for system states
class SystemState(Enum):
    OPTIMAL = "optimal"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    RECOVERING = "recovering"

class FramePriority(Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3

# Advanced data structures for intelligent frame management
@dataclass
class AdvancedFrameData:
    """Advanced frame data structure with comprehensive metadata"""
    frame: np.ndarray
    timestamp: float
    sequence_number: int
    quality_score: float = 0.0
    network_delay: float = 0.0
    processing_time: float = 0.0
    priority: float = 0.0
    frame_size: int = 0
    encoding_time: float = 0.0
    client_id: Optional[str] = None
    
    def __post_init__(self):
        self.priority = self.calculate_priority()
        self.frame_size = self.frame.nbytes if self.frame is not None else 0
    
    def calculate_priority(self) -> float:
        """Calculate frame priority based on multiple intelligent factors"""
        current_time = time.time()
        
        # Age factor with exponential decay
        age_factor = math.exp(-(current_time - self.timestamp) * 2.0)
        
        # Quality factor normalized to 0-1
        quality_factor = self.quality_score / 100.0
        
        # Network delay factor (penalize high delays)
        delay_factor = max(0, 1.0 - self.network_delay * 5.0)
        
        # Size factor (prefer smaller frames for faster transmission)
        size_factor = max(0, 1.0 - (self.frame_size / (1024 * 1024)))  # Normalize to 1MB
        
        # Weighted combination with adaptive weights
        priority = (
            age_factor * 0.35 +
            quality_factor * 0.25 +
            delay_factor * 0.25 +
            size_factor * 0.15
        )
        
        return priority

@dataclass
class AdvancedNetworkMetrics:
    """Advanced network performance metrics with predictive analysis"""
    avg_latency: float = 0.0
    jitter: float = 0.0
    packet_loss_rate: float = 0.0
    bandwidth_utilization: float = 0.0
    connection_stability: float = 1.0
    predicted_latency: float = 0.0
    congestion_level: float = 0.0
    last_update: float = 0.0
    latency_history: List[float] = field(default_factory=list)
    frame_intervals: List[float] = field(default_factory=list)
    bandwidth_history: List[float] = field(default_factory=list)
    
    def update_metrics(self, new_latency: float, new_interval: float, frame_size: int = 0):
        """Update network metrics with advanced statistical analysis"""
        current_time = time.time()
        
        # Update histories
        self.latency_history.append(new_latency)
        self.frame_intervals.append(new_interval)
        if frame_size > 0:
            self.bandwidth_history.append(frame_size / new_interval if new_interval > 0 else 0)
        
        # Keep only recent history for real-time analysis
        max_history = 100
        if len(self.latency_history) > max_history:
            self.latency_history = self.latency_history[-max_history:]
        if len(self.frame_intervals) > max_history:
            self.frame_intervals = self.frame_intervals[-max_history:]
        if len(self.bandwidth_history) > max_history:
            self.bandwidth_history = self.bandwidth_history[-max_history:]
        
        # Calculate advanced metrics
        if len(self.latency_history) > 5:
            # Moving average with exponential weighting
            weights = [math.exp(i * 0.1) for i in range(len(self.latency_history))]
            weighted_latency = sum(w * l for w, l in zip(weights, self.latency_history))
            self.avg_latency = weighted_latency / sum(weights)
            
            # Calculate jitter using standard deviation
            self.jitter = statistics.stdev(self.latency_history[-20:]) if len(self.latency_history) > 1 else 0
            
            # Calculate packet loss rate based on interval analysis
            expected_interval = 1.0 / 60.0  # 60 FPS target
            interval_variations = [abs(x - expected_interval) for x in self.frame_intervals[-20:]]
            self.packet_loss_rate = min(1.0, statistics.mean(interval_variations) / expected_interval)
            
            # Predict future latency using linear regression
            if len(self.latency_history) > 10:
                x = list(range(len(self.latency_history[-10:])))
                y = self.latency_history[-10:]
                try:
                    slope, intercept = np.polyfit(x, y, 1)
                    self.predicted_latency = slope * (len(x) + 1) + intercept
                except:
                    self.predicted_latency = self.avg_latency
            
            # Calculate congestion level
            if len(self.bandwidth_history) > 5:
                avg_bandwidth = statistics.mean(self.bandwidth_history[-10:])
                max_bandwidth = max(self.bandwidth_history[-10:])
                self.congestion_level = avg_bandwidth / max_bandwidth if max_bandwidth > 0 else 0
        
        self.last_update = current_time

@dataclass
class IntelligentAdaptiveController:
    """Intelligent adaptive control system with machine learning principles - Optimized for ESP32-CAM"""
    target_fps: int = 30  # Optimized for ESP32-CAM
    min_quality: int = 60  # Higher minimum quality for security camera
    max_quality: int = 90  # Slightly lower max to prevent overload
    current_quality: int = 80  # Start with good quality
    compensation_factor: float = 1.0
    buffer_target: int = 70  # Lower buffer target for faster processing
    adaptation_rate: float = 0.08  # Slower adaptation for stability
    learning_rate: float = 0.05  # Slower learning for ESP32-CAM
    performance_history: List[float] = field(default_factory=list)
    quality_history: List[int] = field(default_factory=list)
    compensation_history: List[float] = field(default_factory=list)
    system_state: SystemState = SystemState.OPTIMAL
    adaptation_confidence: float = 1.0
    
    def adapt_parameters(self, current_fps: float, buffer_utilization: float, 
                        network_metrics: AdvancedNetworkMetrics) -> Tuple[int, float, SystemState]:
        """Intelligent parameter adaptation with state machine"""
        # Update histories
        self.performance_history.append(current_fps)
        self.quality_history.append(self.current_quality)
        self.compensation_history.append(self.compensation_factor)
        
        # Keep history manageable
        max_history = 200
        if len(self.performance_history) > max_history:
            self.performance_history = self.performance_history[-max_history:]
        if len(self.quality_history) > max_history:
            self.quality_history = self.quality_history[-max_history:]
        if len(self.compensation_history) > max_history:
            self.compensation_history = self.compensation_history[-max_history:]
        
        # Determine system state
        self.system_state = self.determine_system_state(current_fps, buffer_utilization, network_metrics)
        
        # Adaptive parameter adjustment based on state
        if self.system_state == SystemState.CRITICAL:
            # Aggressive adaptation for critical state
            self.adaptation_rate = 0.3
            quality_change = -max(10, int((self.target_fps - current_fps) / 3))
            self.current_quality = max(self.min_quality, self.current_quality + quality_change)
            
        elif self.system_state == SystemState.DEGRADED:
            # Moderate adaptation for degraded state
            self.adaptation_rate = 0.2
            if current_fps < self.target_fps * 0.8:
                quality_change = -max(5, int((self.target_fps - current_fps) / 4))
                self.current_quality = max(self.min_quality, self.current_quality + quality_change)
            elif current_fps > self.target_fps * 0.95:
                quality_change = min(3, int((current_fps - self.target_fps * 0.8) / 10))
                self.current_quality = min(self.max_quality, self.current_quality + quality_change)
                
        elif self.system_state == SystemState.OPTIMAL:
            # Conservative adaptation for optimal state
            self.adaptation_rate = 0.1
            if current_fps > self.target_fps * 0.95:
                quality_change = min(2, int((current_fps - self.target_fps * 0.9) / 15))
                self.current_quality = min(self.max_quality, self.current_quality + quality_change)
        
        # Intelligent compensation factor calculation
        network_factor = 1.0 + network_metrics.jitter * 15.0  # Increase for high jitter
        buffer_factor = 1.0 + (1.0 - buffer_utilization) * 0.8  # Increase if buffer is empty
        performance_factor = 1.0 + (self.target_fps - current_fps) / self.target_fps  # Increase if FPS is low
        congestion_factor = 1.0 + network_metrics.congestion_level * 0.5  # Increase for congestion
        
        # Combine factors with state-based weighting
        if self.system_state == SystemState.CRITICAL:
            self.compensation_factor = min(4.0, network_factor * buffer_factor * performance_factor * 1.5)
        else:
            self.compensation_factor = min(3.0, network_factor * buffer_factor * performance_factor * congestion_factor)
        
        # Update adaptation confidence based on stability
        if len(self.performance_history) > 20:
            recent_stability = 1.0 - statistics.stdev(self.performance_history[-20:]) / self.target_fps
            self.adaptation_confidence = max(0.1, min(1.0, recent_stability))
        
        return self.current_quality, self.compensation_factor, self.system_state
    
    def determine_system_state(self, current_fps: float, buffer_utilization: float, 
                             network_metrics: AdvancedNetworkMetrics) -> SystemState:
        """Determine system state based on multiple factors"""
        # Calculate state scores
        fps_score = current_fps / self.target_fps
        buffer_score = buffer_utilization / 100.0
        network_score = 1.0 - min(1.0, network_metrics.jitter * 10.0)
        
        # Combined score
        combined_score = (fps_score * 0.4 + buffer_score * 0.3 + network_score * 0.3)
        
        # State determination
        if combined_score < 0.5:
            return SystemState.CRITICAL
        elif combined_score < 0.8:
            return SystemState.DEGRADED
        elif combined_score < 0.95:
            return SystemState.RECOVERING
        else:
            return SystemState.OPTIMAL

# Advanced frame rate compensation and optimization system
@dataclass
class FrameRateController:
    """Advanced frame rate controller with intelligent compensation - Optimized for ESP32-CAM"""
    target_fps: int = 30  # Optimized target for ESP32-CAM stability
    min_fps: int = 15  # Lower minimum for ESP32-CAM capabilities
    max_fps: int = 30  # Realistic max for ESP32-CAM
    current_fps: float = 60.0
    frame_intervals: List[float] = field(default_factory=list)
    compensation_history: List[float] = field(default_factory=list)
    adaptive_compensation: float = 1.0
    frame_drop_threshold: float = 0.6  # More aggressive frame dropping for ESP32-CAM
    network_latency_buffer: float = 0.2  # Increased buffer for network issues
    quality_adaptation_rate: float = 0.1  # Slower adaptation for stability
    compensation_stability: float = 1.0
    
    def calculate_optimal_interval(self, network_jitter: float, buffer_utilization: float) -> float:
        """Calculate optimal frame interval with intelligent compensation"""
        base_interval = 1.0 / self.target_fps
        
        # Network compensation factor
        network_factor = 1.0 + (network_jitter * 10.0)  # Increase interval for high jitter
        
        # Buffer compensation factor
        if buffer_utilization < 0.3:  # Low buffer utilization
            buffer_factor = 1.0 + (0.3 - buffer_utilization) * 2.0  # Increase interval
        elif buffer_utilization > 0.8:  # High buffer utilization
            buffer_factor = 0.8  # Decrease interval to clear buffer
        else:
            buffer_factor = 1.0
        
        # FPS-based compensation
        if self.current_fps < self.min_fps:
            fps_factor = 0.7  # Aggressive compensation for low FPS
        elif self.current_fps < self.target_fps * 0.8:
            fps_factor = 0.85  # Moderate compensation
        else:
            fps_factor = 1.0
        
        # Calculate adaptive compensation
        self.adaptive_compensation = min(2.5, network_factor * buffer_factor * fps_factor)
        
        # Apply stability smoothing
        if len(self.compensation_history) > 0:
            avg_compensation = statistics.mean(self.compensation_history[-10:])
            self.adaptive_compensation = (self.adaptive_compensation * 0.7 + avg_compensation * 0.3)
        
        self.compensation_history.append(self.adaptive_compensation)
        if len(self.compensation_history) > 50:
            self.compensation_history.pop(0)
        
        return base_interval * self.adaptive_compensation
    
    def update_fps(self, new_fps: float):
        """Update current FPS with smoothing"""
        if len(self.frame_intervals) > 0:
            # Calculate FPS from recent intervals
            recent_intervals = self.frame_intervals[-20:]
            if len(recent_intervals) > 0:
                avg_interval = statistics.mean(recent_intervals)
                calculated_fps = 1.0 / avg_interval if avg_interval > 0 else new_fps
                self.current_fps = (self.current_fps * 0.8 + calculated_fps * 0.2)
            else:
                self.current_fps = new_fps
        else:
            self.current_fps = new_fps
    
    def should_drop_frame(self, buffer_utilization: float, network_jitter: float) -> bool:
        """Determine if frame should be dropped for optimal performance"""
        if buffer_utilization > 0.9:  # Buffer nearly full
            return True
        if network_jitter > 0.2:  # High network instability
            return True
        if self.current_fps < self.min_fps * 0.8:  # Very low FPS
            return True
        return False

# Enhanced frame buffer with intelligent management
@dataclass
class IntelligentFrameBuffer:
    """Intelligent frame buffer with advanced management and frame buffering delay"""
    max_size: int = 150
    frames: deque = field(default_factory=lambda: deque(maxlen=150))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=150))
    priorities: deque = field(default_factory=lambda: deque(maxlen=150))
    quality_scores: deque = field(default_factory=lambda: deque(maxlen=150))
    
    # Frame buffering delay for smoother streaming - increased to 1.0 seconds
    buffering_delay: float = 1.0  # 1000ms delay to accumulate frames for smoother streaming
    min_buffered_frames: int = 8   # Increased minimum frames before streaming starts
    max_buffering_time: float = 2.0  # Increased maximum buffering time
    last_stream_time: float = 0.0
    buffering_active: bool = False
    
    def add_frame(self, frame: np.ndarray, timestamp: float, priority: float = 1.0, quality: float = 50.0):
        """Add frame with intelligent overflow handling and buffering delay"""
        if len(self.frames) >= self.max_size * 0.95:
            # Remove lowest priority frames first
            self._remove_low_priority_frames()
        
        self.frames.append(frame)
        self.timestamps.append(timestamp)
        self.priorities.append(priority)
        self.quality_scores.append(quality)
        
        # Activate buffering if we have enough frames
        if len(self.frames) >= self.min_buffered_frames and not self.buffering_active:
            self.buffering_active = True
            self.last_stream_time = timestamp
    
    def should_start_streaming(self, current_time: float) -> bool:
        """Determine if streaming should start based on buffering conditions"""
        if not self.buffering_active:
            return False
        
        # Check if we have enough frames and buffering time has passed
        if len(self.frames) >= self.min_buffered_frames:
            if current_time - self.last_stream_time >= self.buffering_delay:
                return True
        
        # Force streaming if buffering time is too long
        if current_time - self.last_stream_time >= self.max_buffering_time:
            return True
        
        return False
    
    def get_buffering_status(self) -> dict:
        """Get current buffering status"""
        current_time = time.time()
        return {
            'buffering_active': self.buffering_active,
            'buffered_frames': len(self.frames),
            'min_required': self.min_buffered_frames,
            'buffering_delay': self.buffering_delay,
            'time_since_last_stream': current_time - self.last_stream_time,
            'ready_to_stream': self.should_start_streaming(current_time)
        }
    
    def reset_buffering(self):
        """Reset buffering state after streaming"""
        self.buffering_active = False
        self.last_stream_time = time.time()
    
    def get_best_frame(self) -> Optional[Tuple[np.ndarray, float, float]]:
        """Get the best frame based on priority and quality"""
        if not self.frames:
            return None
        
        # Find frame with highest priority and good quality
        best_index = 0
        best_score = 0.0
        
        for i in range(len(self.frames)):
            priority = self.priorities[i]
            quality = self.quality_scores[i]
            age_factor = 1.0 / (1.0 + (time.time() - self.timestamps[i]) * 2.0)
            
            score = priority * 0.5 + quality * 0.3 + age_factor * 0.2
            if score > best_score:
                best_score = score
                best_index = i
        
        frame = self.frames[best_index]
        timestamp = self.timestamps[best_index]
        quality = self.quality_scores[best_index]
        
        # Remove the selected frame
        self._remove_frame_at_index(best_index)
        
        return frame, timestamp, quality
    
    def _remove_low_priority_frames(self):
        """Remove frames with lowest priority when buffer is full"""
        if len(self.frames) == 0:
            return
        
        # Find frame with lowest priority
        min_priority = float('inf')
        min_priority_index = -1
        
        for i, priority in enumerate(self.priorities):
            if priority < min_priority:
                min_priority = priority
                min_priority_index = i
        
        if min_priority_index >= 0:
            self._remove_frame_at_index(min_priority_index)
    
    def _remove_frame_at_index(self, index: int):
        """Remove frame at specific index"""
        if 0 <= index < len(self.frames):
            # Convert to list, remove, and convert back to deque
            frames_list = list(self.frames)
            timestamps_list = list(self.timestamps)
            priorities_list = list(self.priorities)
            quality_scores_list = list(self.quality_scores)
            
            frames_list.pop(index)
            timestamps_list.pop(index)
            priorities_list.pop(index)
            quality_scores_list.pop(index)
            
            self.frames = deque(frames_list, maxlen=self.max_size)
            self.timestamps = deque(timestamps_list, maxlen=self.max_size)
            self.priorities = deque(priorities_list, maxlen=self.max_size)
            self.quality_scores = deque(quality_scores_list, maxlen=self.max_size)
    
    def get_utilization(self) -> float:
        """Get buffer utilization percentage"""
        return len(self.frames) / self.max_size * 100.0
    
    def clear(self):
        """Clear all frames"""
        self.frames.clear()
        self.timestamps.clear()
        self.priorities.clear()
        self.quality_scores.clear()
        self.reset_buffering()

# Global intelligent systems with enhanced frame rate control
frame_rate_controller = FrameRateController()
intelligent_buffer = IntelligentFrameBuffer()
frame_buffer = intelligent_buffer.frames  # Backward compatibility
frame_queue = asyncio.PriorityQueue(maxsize=100)
frame_lock = asyncio.Lock()
latest_frame: Optional[np.ndarray] = None
sequence_counter = 0

# Advanced monitoring systems
network_metrics = AdvancedNetworkMetrics()
adaptive_controller = IntelligentAdaptiveController()

# Initialize performance stats with ESP32-CAM optimized settings
performance_stats = {
    'fps': 0.0,
    'buffer_size': 0,
    'latency': 0.0,
    'dropped_frames': 0,
    'quality_level': 80,  # Start with good quality for security camera
    'compensation_factor': 1.0,
    'network_jitter': 0.0,
    'packet_loss_rate': 0.0,
    'buffer_utilization': 0.0,
    'frame_processing_time': 0.0,
    'total_frames_processed': 0,
    'avg_frame_quality': 0.0,
    'system_state': SystemState.OPTIMAL.value,
    'adaptation_confidence': 1.0,
    'predicted_latency': 0.0,
    'congestion_level': 0.0,
    'min_fps_achieved': 15.0,  # Adjusted for ESP32-CAM
    'max_fps_achieved': 0.0,
    'avg_fps_1min': 0.0,
    'fps_stability': 1.0,
    'frame_drop_rate': 0.0,
    'buffer_efficiency': 0.0,
    'compensation_effectiveness': 1.0,
    'network_adaptation_speed': 0.0,
    'quality_adaptation_speed': 0.0,
    'total_frames_dropped': 0,
    'total_frames_sent': 0,
    'stream_uptime': 0.0,
    'last_frame_drop_time': 0.0,
    'consecutive_drops': 0,
    'recovery_speed': 0.0,
    'enhancement_mode': 'auto',
    'enhancement_time': 0.0,
    'quality_improvement': 0.0
}

# FPS tracking for stability analysis
fps_history = deque(maxlen=300)  # 5 minutes at 1-second intervals
frame_drop_history = deque(maxlen=100)
compensation_history = deque(maxlen=100)

# Connection management
active_connections: List[WebSocket] = []
clients_lock = asyncio.Lock()
connection_stats = defaultdict(lambda: {
    'connected_time': 0.0,
    'frames_received': 0,
    'last_activity': 0.0,
    'avg_latency': 0.0,
    'total_bytes_received': 0
})

# FastAPI app with advanced lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Intelligent FastAPI Server with Advanced Compensation...")
    logger.info("Features: ML-based adaptation, predictive analysis, intelligent buffering")
    
    # Start background tasks
    asyncio.create_task(intelligent_frame_processor())
    asyncio.create_task(system_monitor())
    
    yield
    
    # Shutdown
    logger.info("Shutting down Intelligent FastAPI Server...")

app = FastAPI(
    title="Intelligent ESP32-CAM Frame Server",
    description="Advanced frame server with ML-based compensation and predictive analysis",
    version="4.0.0",
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

async def intelligent_frame_processor():
    """Enhanced async frame processor with advanced frame rate control, compensation, and professional security recording"""
    global latest_frame, performance_stats, network_metrics, adaptive_controller, frame_rate_controller, intelligent_buffer, security_recorder
    
    frame_timestamps = deque(maxlen=300)
    processing_stats = deque(maxlen=150)
    last_fps_update = time.time()
    fps_update_interval = 0.5  # Update FPS every 500ms
    
    # Start security recording if not already active
    if not security_recorder.recording_active:
        security_recorder.start_new_recording()
    
    while True:
        try:
            current_time = time.time()
            
            # Process frames from priority queue with intelligent prioritization
            if not frame_queue.empty():
                priority, frame_data = await frame_queue.get()
                
                async with frame_lock:
                    # Apply advanced image enhancement for server environments
                    enhanced_frame, enhancement_stats = enhance_frame_for_server(frame_data.frame)
                    
                    # Update latest frame with enhanced version
                    latest_frame = enhanced_frame
                    
                    # Add enhanced frame to professional security recording
                    # Only record frames that meet quality standards
                    if enhanced_frame is not None and enhanced_frame.size > 0:
                        security_recorder.add_frame(enhanced_frame)
                    
                    # Calculate frame quality and priority with enhanced frame
                    quality_score = calculate_frame_quality(enhanced_frame)
                    priority_score = frame_data.priority
                    
                    # Add enhanced frame to intelligent buffer
                    intelligent_buffer.add_frame(
                        frame=enhanced_frame,
                        timestamp=frame_data.timestamp,
                        priority=priority_score,
                        quality=quality_score
                    )
                    
                    # Update performance stats with enhancement information
                    if 'mode' in enhancement_stats:
                        performance_stats['enhancement_mode'] = enhancement_stats['mode']
                    if 'processing_time' in enhancement_stats:
                        performance_stats['enhancement_time'] = enhancement_stats['processing_time'] * 1000
                    if 'quality_improvement' in enhancement_stats:
                        performance_stats['quality_improvement'] = enhancement_stats['quality_improvement']
                    
                    # Add frame timestamp for FPS calculation
                    frame_timestamps.append(current_time)
                    if len(frame_timestamps) > 300:
                        frame_timestamps.popleft()
                    
                    # Update frame rate controller
                    frame_rate_controller.frame_intervals.append(frame_data.timestamp)
                    if len(frame_rate_controller.frame_intervals) > 100:
                        frame_rate_controller.frame_intervals.pop(0)
                    
                    # Update comprehensive performance statistics
                    await update_enhanced_performance_stats(frame_data, frame_timestamps)
                    
            # Update FPS tracking periodically
            if current_time - last_fps_update >= fps_update_interval:
                await update_frame_rate_metrics()
                last_fps_update = current_time
            
            # Adaptive control update with frame rate awareness
            await update_enhanced_adaptive_control()
            
            # Cleanup old recordings periodically (every hour)
            if int(current_time) % 3600 == 0:
                security_recorder.cleanup_old_recordings()
            
            # Intelligent sleep based on system load
            buffer_utilization = intelligent_buffer.get_utilization() / 100.0
            if buffer_utilization > 0.8:
                await asyncio.sleep(0.0005)  # Faster processing when buffer is full
            else:
                await asyncio.sleep(0.001)  # Normal processing
            
        except Exception as e:
            logger.error(f"Error in enhanced frame processor: {e}")
            await asyncio.sleep(0.01)

async def update_enhanced_performance_stats(frame_data: AdvancedFrameData, frame_timestamps: deque):
    """Update comprehensive performance statistics with advanced frame rate metrics"""
    global performance_stats, network_metrics, frame_rate_controller, intelligent_buffer
    
    current_time = time.time()
    
    # Calculate FPS with enhanced accuracy and proper error handling
    if len(frame_timestamps) > 1:
        time_window = current_time - frame_timestamps[0]
        if time_window > 0.001:  # Minimum time window to prevent division by zero
            current_fps = len(frame_timestamps) / time_window
            performance_stats['fps'] = current_fps
            
            # Update frame rate controller
            frame_rate_controller.update_fps(current_fps)
            
            # Track FPS history for stability analysis
            fps_history.append(current_fps)
            if len(fps_history) > 300:
                fps_history.popleft()
        else:
            # Handle very small time windows
            performance_stats['fps'] = 0.0
    else:
        # No frames received yet
        performance_stats['fps'] = 0.0
    
    # Enhanced buffer statistics
    performance_stats['buffer_size'] = len(intelligent_buffer.frames)
    performance_stats['buffer_utilization'] = intelligent_buffer.get_utilization()
    performance_stats['frame_processing_time'] = frame_data.processing_time
    performance_stats['total_frames_processed'] += 1
    
    # Update network metrics with frame size
    if len(frame_timestamps) > 1:
        try:
            interval = frame_data.timestamp - frame_timestamps[-2]
            if interval > 0:  # Prevent negative intervals
                network_metrics.update_metrics(frame_data.network_delay, interval, frame_data.frame_size)
        except (IndexError, ValueError) as e:
            logger.debug(f"Error updating network metrics: {e}")
        
        performance_stats['network_jitter'] = network_metrics.jitter
        performance_stats['packet_loss_rate'] = network_metrics.packet_loss_rate
        performance_stats['predicted_latency'] = network_metrics.predicted_latency
        performance_stats['congestion_level'] = network_metrics.congestion_level

async def update_frame_rate_metrics():
    """Update comprehensive frame rate metrics and stability analysis"""
    global performance_stats, frame_rate_controller, fps_history, frame_drop_history
    
    current_time = time.time()
    
    # Calculate FPS stability with proper error handling
    if len(fps_history) > 10:
        recent_fps = list(fps_history)[-30:]  # Last 30 seconds
        if recent_fps and statistics.mean(recent_fps) > 0:
            try:
                fps_stability = 1.0 - (statistics.stdev(recent_fps) / statistics.mean(recent_fps))
                performance_stats['fps_stability'] = max(0.0, min(1.0, fps_stability))
            except (statistics.StatisticsError, ZeroDivisionError):
                performance_stats['fps_stability'] = 0.0
        else:
            performance_stats['fps_stability'] = 0.0
        
        # Track min/max FPS with safety checks
        if recent_fps:
            performance_stats['min_fps_achieved'] = min(performance_stats['min_fps_achieved'], min(recent_fps))
            performance_stats['max_fps_achieved'] = max(performance_stats['max_fps_achieved'], max(recent_fps))
        
        # Calculate 1-minute average FPS
        if len(fps_history) >= 60:
            try:
                performance_stats['avg_fps_1min'] = statistics.mean(list(fps_history)[-60:])
            except statistics.StatisticsError:
                performance_stats['avg_fps_1min'] = 0.0
    
    # Calculate frame drop rate
    total_frames = performance_stats['total_frames_processed']
    dropped_frames = performance_stats['dropped_frames']
    if total_frames > 0:
        performance_stats['frame_drop_rate'] = (dropped_frames / total_frames) * 100.0
    
    # Calculate buffer efficiency with error handling
    buffer_utilization = intelligent_buffer.get_utilization() / 100.0
    if buffer_utilization > 0.1 and frame_rate_controller.target_fps > 0:  # Buffer has some content
        try:
            performance_stats['buffer_efficiency'] = min(1.0, performance_stats['fps'] / frame_rate_controller.target_fps)
        except ZeroDivisionError:
            performance_stats['buffer_efficiency'] = 0.0
    else:
        performance_stats['buffer_efficiency'] = 0.0
    
    # Calculate compensation effectiveness with error handling
    if len(compensation_history) > 5 and performance_stats['fps'] > 0:
        try:
            recent_compensation = list(compensation_history)[-10:]
            avg_compensation = statistics.mean(recent_compensation)
            if avg_compensation > 0:
                performance_stats['compensation_effectiveness'] = min(1.0, frame_rate_controller.target_fps / (performance_stats['fps'] * avg_compensation))
            else:
                performance_stats['compensation_effectiveness'] = 1.0
        except (statistics.StatisticsError, ZeroDivisionError):
            performance_stats['compensation_effectiveness'] = 1.0
    else:
        performance_stats['compensation_effectiveness'] = 1.0
    
    # Update stream uptime
    if performance_stats['stream_uptime'] == 0:
        performance_stats['stream_uptime'] = current_time
    performance_stats['stream_uptime'] = current_time - performance_stats['stream_uptime']

async def update_enhanced_adaptive_control():
    """Update adaptive control parameters with enhanced frame rate awareness"""
    global performance_stats, adaptive_controller, frame_rate_controller, intelligent_buffer
    
    current_fps = performance_stats['fps']
    buffer_utilization = intelligent_buffer.get_utilization() / 100.0
    
    # Enhanced quality adaptation with frame rate guarantees
    quality, compensation, system_state = adaptive_controller.adapt_parameters(
        current_fps, buffer_utilization, network_metrics
    )
    
    # ESP32-CAM optimized minimum FPS guarantee - improved quality reduction system with dead zones
    if current_fps < frame_rate_controller.min_fps and current_fps > 0:
        # Improved quality reduction system with dead zones for security camera
        if current_fps < 1.0:
            # For very low FPS (0.5-1.0), use minimal quality reduction with dead zone
            quality_reduction = int((1.0 - current_fps) * 8)  # Reduced from 15 to 8
            quality = max(75, quality - quality_reduction)  # Increased minimum from 65 to 75
            compensation = min(2.5, compensation * 1.2)
            
            # Intelligent logging - only log once per 30 seconds for similar issues
            warning_key = f"very_low_fps_{int(current_fps * 10)}"
            if intelligent_log_filter.should_log_warning(warning_key, f"Very low FPS ({current_fps:.1f} < {frame_rate_controller.min_fps})"):
                logger.warning(f"ESP32-CAM: Very low FPS ({current_fps:.1f} < {frame_rate_controller.min_fps}), reducing quality to {quality}, compensation: {compensation:.2f}")
        elif current_fps < 2.0:
            # For low FPS (1.0-2.0), use very gentle quality reduction with dead zone
            quality_reduction = int((2.0 - current_fps) * 4)  # Reduced from 8 to 4
            quality = max(78, quality - quality_reduction)  # Increased minimum from 70 to 78
            compensation = min(2.0, compensation * 1.1)
            
            # Intelligent logging
            warning_key = f"low_fps_{int(current_fps * 10)}"
            if intelligent_log_filter.should_log_warning(warning_key, f"Low FPS ({current_fps:.1f} < {frame_rate_controller.min_fps})"):
                logger.warning(f"ESP32-CAM: Low FPS ({current_fps:.1f} < {frame_rate_controller.min_fps}), reducing quality to {quality}, compensation: {compensation:.2f}")
        else:
            # For moderate low FPS (2.0+), use minimal reduction with dead zone
            quality = max(80, quality - 3)  # Increased minimum from 75 to 80
            compensation = min(1.8, compensation * 1.05)  # Less aggressive compensation
            
            # Intelligent logging
            warning_key = f"moderate_low_fps_{int(current_fps)}"
            if intelligent_log_filter.should_log_warning(warning_key, f"FPS below minimum ({current_fps:.1f} < {frame_rate_controller.min_fps})"):
                logger.warning(f"ESP32-CAM: FPS below minimum ({current_fps:.1f} < {frame_rate_controller.min_fps}), reducing quality to {quality}")
    elif current_fps == 0:
        # No frames received - this is normal when no ESP32 is connected
        if intelligent_log_filter.should_log_info("no_frames", "No frames received"):
            logger.debug("ESP32-CAM: No frames received - waiting for connection")
    
    # ESP32-CAM optimized frame rate-based quality adjustment with dead zones
    if current_fps < frame_rate_controller.target_fps * 0.6:  # Lower threshold for dead zone
        quality = max(78, quality - 3)  # Higher minimum quality with dead zone
    elif current_fps > frame_rate_controller.target_fps * 0.9:  # Lower threshold
        quality = min(90, quality + 3)  # Gradual increase
    
    # ESP32-CAM optimized network condition-based optimization with dead zones
    if performance_stats['network_jitter'] > 0.25:  # Higher threshold for dead zone
        quality = max(78, quality - 2)  # Higher minimum quality with dead zone
        compensation = min(1.8, compensation * 1.03)  # Less aggressive
    
    # ESP32-CAM optimized buffer-based optimization with dead zones
    if buffer_utilization > 0.9:  # Higher threshold for dead zone
        quality = max(78, quality - 2)  # Higher minimum quality with dead zone
        compensation = min(1.8, compensation * 1.02)  # Less aggressive
    
    performance_stats['quality_level'] = quality
    performance_stats['compensation_factor'] = compensation
    performance_stats['system_state'] = system_state.value
    performance_stats['adaptation_confidence'] = adaptive_controller.adaptation_confidence
    
    # Update frame rate controller compensation
    frame_rate_controller.adaptive_compensation = compensation
    compensation_history.append(compensation)
    if len(compensation_history) > 100:
        compensation_history.popleft()

async def system_monitor():
    """Background system monitor for health checks and optimization"""
    while True:
        try:
            # Monitor system health
            if performance_stats['fps'] < 10 and len(frame_buffer) < 10:
                if intelligent_log_filter.should_log_warning("low_performance", "System performance degraded"):
                    logger.warning("System performance degraded - low FPS and buffer")
            
            # Monitor memory usage (if available)
            if len(frame_buffer) > frame_buffer.maxlen * 0.9:
                if intelligent_log_filter.should_log_warning("high_buffer_utilization", "Buffer utilization high"):
                    logger.warning("Buffer utilization high - consider optimization")
            
            # Log periodic statistics with intelligent filtering
            if performance_stats['total_frames_processed'] % 1000 == 0:
                if intelligent_log_filter.should_log_info("system_status", "System status update"):
                    logger.info(f"System Status: FPS={performance_stats['fps']:.2f}, "
                              f"Quality={performance_stats['quality_level']}, "
                              f"State={performance_stats['system_state']}")
            
            await asyncio.sleep(5)  # Check every 5 seconds
            
        except Exception as e:
            logger.error(f"Error in system monitor: {e}")
            await asyncio.sleep(10)

@app.get("/")
async def root():
    """Root endpoint with comprehensive server information"""
    return {
        "server": "Intelligent FastAPI ESP32-CAM Frame Server",
        "version": "4.0.0",
        "features": [
            "ML-based adaptive control",
            "Predictive network analysis",
            "Intelligent frame prioritization",
            "Advanced compensation algorithms",
            "Real-time system state monitoring",
            "Comprehensive performance metrics"
        ],
        "system_state": performance_stats['system_state'],
        "endpoints": {
            "video_feed": "/esp32_video_feed",
            "single_frame": "/esp32_frame",
            "performance": "/performance_stats",
            "health": "/health",
            "reset_stats": "/reset_stats",
            "system_info": "/system_info"
        }
    }

@app.get("/esp32_frame")
async def get_single_frame():
    """Intelligent single frame endpoint with advanced optimization"""
    global latest_frame, performance_stats
    
    if latest_frame is None:
        raise HTTPException(status_code=503, detail="No frame available", 
                          headers={'Retry-After': '1'})
    
    # Use adaptive quality with intelligent encoding
    quality = performance_stats['quality_level']
    
    # Optimize encoding parameters based on system state
    encode_params = [
        int(cv2.IMWRITE_JPEG_QUALITY), quality,
        int(cv2.IMWRITE_JPEG_OPTIMIZE), 1,
        int(cv2.IMWRITE_JPEG_PROGRESSIVE), 1
    ]
    
    # Add state-specific optimizations
    if performance_stats['system_state'] == SystemState.CRITICAL.value:
        encode_params.extend([int(cv2.IMWRITE_JPEG_QUALITY), max(45, quality - 15)])
    
    start_time = time.time()
    ret, buffer = cv2.imencode('.jpg', latest_frame, encode_params)
    encoding_time = time.time() - start_time
    
    if not ret:
        raise HTTPException(status_code=500, detail="Frame encoding failed")
    
    # Comprehensive response headers
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
        'X-System-State': performance_stats['system_state'],
        'X-Adaptation-Confidence': f"{performance_stats['adaptation_confidence']:.3f}",
        'X-Predicted-Latency': f"{performance_stats['predicted_latency']:.4f}",
        'X-Congestion-Level': f"{performance_stats['congestion_level']:.3f}",
        'X-Total-Frames': str(performance_stats['total_frames_processed'])
    }
    
    return Response(content=buffer.tobytes(), media_type="image/jpeg", headers=headers)

@app.get("/esp32_video_feed")
async def video_feed():
    """Ultra-optimized video stream with guaranteed 24-60 FPS, intelligent compensation, and frame buffering delay"""
    
    async def generate_optimized_stream():
        global frame_rate_controller, intelligent_buffer, performance_stats
        
        # Dynamic target FPS based on system capabilities
        target_fps = frame_rate_controller.target_fps
        min_fps = frame_rate_controller.min_fps
        frame_interval = 1.0 / target_fps
        
        last_frame_time = time.time()
        consecutive_empty_frames = 0
        max_empty_frames = 20  # Reduced for faster recovery
        frame_count = 0
        last_sent_frame = None
        frame_drop_count = 0
        recovery_mode = False
        
        # Performance tracking
        stream_start_time = time.time()
        frame_times = deque(maxlen=100)
        
        # Frame buffering delay system for smoother streaming
        buffering_start_time = time.time()
        initial_buffering_done = False
        
        while True:
            try:
                start_time = time.time()
                
                # Check if we should start streaming (frame buffering delay)
                if not initial_buffering_done:
                    buffering_status = intelligent_buffer.get_buffering_status()
                    if buffering_status['ready_to_stream']:
                        initial_buffering_done = True
                        buffering_time = time.time() - buffering_start_time
                        if intelligent_log_filter.should_log_info("buffering_complete", "Initial buffering completed"):
                            logger.info(f"ESP32-CAM: Initial frame buffering completed in {buffering_time:.3f}s, starting smooth stream")
                    else:
                        # Wait for buffering to complete
                        await asyncio.sleep(0.01)
                        continue
                
                # Get optimal frame with intelligent selection
                frame_to_send = None
                frame_quality = 0.0
                
                async with frame_lock:
                    # Use intelligent buffer for best frame selection
                    frame_result = intelligent_buffer.get_best_frame()
                    if frame_result:
                        frame_to_send, frame_timestamp, frame_quality = frame_result
                        consecutive_empty_frames = 0
                        frame_count += 1
                        last_sent_frame = frame_to_send
                        performance_stats['total_frames_sent'] += 1
                        
                        # Reset buffering after successful frame delivery
                        intelligent_buffer.reset_buffering()
                    else:
                        consecutive_empty_frames += 1
                        # Use last sent frame for continuity
                        if last_sent_frame is not None and consecutive_empty_frames < max_empty_frames:
                            frame_to_send = last_sent_frame
                            frame_quality = 50.0  # Default quality for repeated frame
                
                if frame_to_send is not None:
                    # Calculate optimal quality and encoding parameters
                    base_quality = performance_stats['quality_level']
                    
                    # ESP32-CAM optimized quality adjustment - prioritize quality for security camera
                    quality = base_quality
                    
                    # Frame rate-based quality adjustment - less aggressive for ESP32-CAM with dead zones
                    current_fps = performance_stats['fps']
                    if current_fps < min_fps:
                        # Improved quality reduction for low FPS scenarios with dead zones
                        if current_fps < 2.0:
                            quality = max(78, quality - 4)  # Higher minimum quality for very low FPS with dead zone
                        else:
                            quality = max(80, quality - 3)  # Higher minimum quality for low FPS with dead zone
                        recovery_mode = True
                    elif current_fps < target_fps * 0.6:  # Lower threshold for dead zone
                        quality = max(78, quality - 3)  # Higher minimum quality with dead zone
                    elif current_fps > target_fps * 0.9:  # Lower threshold
                        quality = min(90, quality + 3)  # Gradual quality increase
                        recovery_mode = False
                    
                    # Network condition-based optimization - more tolerant for ESP32-CAM with dead zones
                    network_jitter = performance_stats['network_jitter']
                    if network_jitter > 0.25:  # Higher threshold for dead zone
                        quality = max(78, quality - 2)  # Higher minimum quality with dead zone
                    
                    # Buffer utilization-based optimization - optimized for ESP32-CAM with dead zones
                    buffer_utilization = intelligent_buffer.get_utilization() / 100.0
                    if buffer_utilization > 0.9:  # Higher threshold for dead zone
                        quality = max(78, quality - 2)  # Higher minimum quality with dead zone
                    
                    # Frame quality-based adjustment - preserve detail for security with dead zones
                    if frame_quality < 45:  # Higher threshold for dead zone
                        quality = max(78, quality - 1)  # Minimal reduction, higher minimum with dead zone
                    
                    # ESP32-CAM optimized encoding parameters for security camera quality
                    encode_params = [
                        int(cv2.IMWRITE_JPEG_QUALITY), quality,
                        int(cv2.IMWRITE_JPEG_OPTIMIZE), 1,
                        int(cv2.IMWRITE_JPEG_PROGRESSIVE), 1
                    ]
                    
                    # Enhanced encoding for security camera detail preservation
                    if quality > 65:  # Lower threshold for ESP32-CAM
                        encode_params.extend([
                            int(cv2.IMWRITE_JPEG_PROGRESSIVE), 1,
                            int(cv2.IMWRITE_JPEG_OPTIMIZE), 1
                        ])
                    
                    # Additional quality parameters for high-quality security footage
                    if quality > 75:
                        encode_params.extend([
                            int(cv2.IMWRITE_JPEG_OPTIMIZE), 1
                        ])
                    
                    # Encode frame with optimized parameters
                    ret, buffer = cv2.imencode('.jpg', frame_to_send, encode_params)
                    if not ret:
                        logger.error("Frame encoding failed")
                        continue
                    
                    frame_bytes = buffer.tobytes()
                    
                    # Calculate processing metrics
                    processing_time = time.time() - start_time
                    performance_stats['latency'] = processing_time * 1000
                    
                    # ESP32-CAM optimized frame rate compensation with buffering delay
                    network_jitter = performance_stats['network_jitter']
                    buffer_utilization = intelligent_buffer.get_utilization() / 100.0
                    optimal_interval = frame_rate_controller.calculate_optimal_interval(network_jitter, buffer_utilization)
                    
                    # Apply frame rate compensation with ESP32-CAM specific adjustments
                    compensation = frame_rate_controller.adaptive_compensation
                    
                    # ESP32-CAM specific compensation factors with buffering consideration
                    esp32_compensation = 1.0
                    if current_fps < 2.0:  # Very low FPS (1.6-1.8 range)
                        esp32_compensation = 0.6  # Much faster frame delivery for very low FPS
                    elif current_fps < 10:  # Low FPS
                        esp32_compensation = 0.7  # Faster frame delivery for buffering
                    elif current_fps < 15:  # Moderate FPS
                        esp32_compensation = 0.8  # Moderate speedup
                    elif current_fps > 25:  # Good FPS
                        esp32_compensation = 1.1  # Slight slowdown for quality
                    
                    # Apply buffering delay factor for smoother streaming
                    buffering_factor = 1.0
                    if intelligent_buffer.buffering_active:
                        if current_fps < 2.0:
                            buffering_factor = 0.7  # Much faster delivery during buffering for very low FPS
                        else:
                            buffering_factor = 0.9  # Slightly faster delivery during buffering
                    
                    adjusted_interval = optimal_interval * compensation * esp32_compensation * buffering_factor
                    
                    # Ensure minimum frame rate with ESP32-CAM considerations
                    max_interval = 1.0 / min_fps
                    if adjusted_interval > max_interval:
                        adjusted_interval = max_interval
                        if intelligent_log_filter.should_log_info("interval_capped", "Adjusted interval capped"):
                            logger.debug(f"ESP32-CAM: Adjusted interval capped at {min_fps} FPS for stability")
                    
                    # Send frame
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    
                    last_frame_time = time.time()
                    frame_times.append(processing_time)
                    
                    # Intelligent sleep with frame rate compensation and buffering delay
                    elapsed = time.time() - start_time
                    sleep_time = max(0, adjusted_interval - elapsed)
                    
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                    
                    # Update frame drop tracking
                    if frame_drop_count > 0:
                        frame_drop_count = max(0, frame_drop_count - 1)
                        
                else:
                    # Handle empty buffer with intelligent recovery
                    if consecutive_empty_frames < max_empty_frames:
                        # Send minimal keep-alive frame
                        keep_alive_frame = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9'
                        
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + keep_alive_frame + b'\r\n')
                        
                        # Adaptive sleep based on system state and FPS
                        current_fps = performance_stats['fps']
                        buffer_utilization = intelligent_buffer.get_utilization() / 100.0
                        
                        # Improved recovery logic for low FPS scenarios
                        if current_fps < 2.0:
                            # For very low FPS, use longer recovery time to allow frame accumulation
                            sleep_time = frame_interval * 2.0  # Slower recovery for low FPS
                        elif current_fps < min_fps or buffer_utilization < 0.1:
                            sleep_time = frame_interval * 1.0  # Normal recovery
                        else:
                            sleep_time = frame_interval * 1.5  # Standard wait
                        
                        await asyncio.sleep(sleep_time)
                    else:
                        # Extended recovery mode with better handling
                        if intelligent_log_filter.should_log_warning("buffer_empty_recovery", "Buffer empty recovery mode"):
                            logger.warning(f"Buffer empty for {consecutive_empty_frames} frames, entering extended recovery mode")
                        
                        # Adaptive recovery time based on FPS
                        if current_fps < 2.0:
                            recovery_time = frame_interval * 3.0  # Longer recovery for very low FPS
                        else:
                            recovery_time = frame_interval * 2.0  # Standard recovery
                        
                        await asyncio.sleep(recovery_time)
                        consecutive_empty_frames = max_empty_frames - 10  # Reset counter more aggressively
                        
            except Exception as e:
                logger.error(f"Error in optimized video stream: {e}")
                await asyncio.sleep(0.01)  # Brief pause on error
    
    # Enhanced response headers with comprehensive metrics
    response = StreamingResponse(generate_optimized_stream(), 
                               media_type="multipart/x-mixed-replace; boundary=frame")
    response.headers.update({
        'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
        'Pragma': 'no-cache',
        'Expires': '0',
        'X-Target-FPS': str(frame_rate_controller.target_fps),
        'X-Min-FPS': str(frame_rate_controller.min_fps),
        'X-Current-FPS': f"{performance_stats['fps']:.2f}",
        'X-Compensation-Factor': f"{frame_rate_controller.adaptive_compensation:.3f}",
        'X-Quality-Level': str(performance_stats['quality_level']),
        'X-Network-Jitter': f"{performance_stats['network_jitter']:.4f}",
        'X-Buffer-Utilization': f"{intelligent_buffer.get_utilization():.1f}%",
        'X-System-State': performance_stats['system_state'],
        'X-FPS-Stability': f"{performance_stats['fps_stability']:.3f}",
        'X-Frame-Drop-Rate': f"{performance_stats['frame_drop_rate']:.2f}%",
        'X-Compensation-Effectiveness': f"{performance_stats['compensation_effectiveness']:.3f}",
        'X-Stream-Uptime': f"{performance_stats['stream_uptime']:.1f}s"
    })
    return response

@app.get("/performance_stats")
async def get_performance_stats():
    """Comprehensive performance statistics with advanced frame rate metrics, buffering status, and security recording"""
    return {
        'fps': round(performance_stats['fps'], 2),
        'min_fps_achieved': round(performance_stats['min_fps_achieved'], 2),
        'max_fps_achieved': round(performance_stats['max_fps_achieved'], 2),
        'avg_fps_1min': round(performance_stats['avg_fps_1min'], 2),
        'fps_stability': round(performance_stats['fps_stability'], 3),
        'target_fps': frame_rate_controller.target_fps,
        'min_fps_guarantee': frame_rate_controller.min_fps,
        'buffer_size': performance_stats['buffer_size'],
        'buffer_utilization': round(performance_stats['buffer_utilization'], 1),
        'buffer_efficiency': round(performance_stats['buffer_efficiency'], 3),
        'buffering_status': intelligent_buffer.get_buffering_status(),  # New buffering information
        'latency_ms': round(performance_stats['latency'], 2),
        'dropped_frames': performance_stats['dropped_frames'],
        'total_frames_dropped': performance_stats['total_frames_dropped'],
        'total_frames_sent': performance_stats['total_frames_sent'],
        'frame_drop_rate': round(performance_stats['frame_drop_rate'], 2),
        'consecutive_drops': performance_stats['consecutive_drops'],
        'quality_level': performance_stats['quality_level'],
        'compensation_factor': round(performance_stats['compensation_factor'], 3),
        'compensation_effectiveness': round(performance_stats['compensation_effectiveness'], 3),
        'network_jitter': round(performance_stats['network_jitter'], 4),
        'packet_loss_rate': round(performance_stats['packet_loss_rate'], 3),
        'frame_processing_time': round(performance_stats['frame_processing_time'], 3),
        'total_frames_processed': performance_stats['total_frames_processed'],
        'avg_frame_quality': round(performance_stats['avg_frame_quality'], 1),
        'system_state': performance_stats['system_state'],
        'adaptation_confidence': round(performance_stats['adaptation_confidence'], 3),
        'predicted_latency': round(performance_stats['predicted_latency'], 4),
        'congestion_level': round(performance_stats['congestion_level'], 3),
        'stream_uptime': round(performance_stats['stream_uptime'], 1),
        'recovery_speed': round(performance_stats['recovery_speed'], 3),
        'enhancement_mode': performance_stats['enhancement_mode'],
        'enhancement_time_ms': round(performance_stats['enhancement_time'], 2),
        'quality_improvement': round(performance_stats['quality_improvement'], 3),
        'security_recording': {
            'active': security_recorder.recording_active,
            'status': security_recorder.get_recording_status(),
            'configuration': {
                'recording_duration_hours': RECORDING_DURATION_HOURS,
                'retention_days': RETENTION_DAYS,
                'recording_fps': FRAME_RATE_RECORDING,
                'video_quality': security_recorder.video_quality,
                'output_directory': SECURITY_VIDEOS_DIR,
                'min_frames_per_second': MIN_FRAMES_PER_SECOND,
                'frame_validation': security_recorder.frame_validation_enabled
            }
        },
        'network_metrics': {
            'avg_latency': round(network_metrics.avg_latency, 4),
            'jitter': round(network_metrics.jitter, 4),
            'packet_loss_rate': round(network_metrics.packet_loss_rate, 3),
            'connection_stability': round(network_metrics.connection_stability, 3),
            'predicted_latency': round(network_metrics.predicted_latency, 4),
            'congestion_level': round(network_metrics.congestion_level, 3)
        },
        'adaptive_controller': {
            'target_fps': adaptive_controller.target_fps,
            'current_quality': adaptive_controller.current_quality,
            'compensation_factor': round(adaptive_controller.compensation_factor, 3),
            'adaptation_rate': adaptive_controller.adaptation_rate,
            'learning_rate': adaptive_controller.learning_rate,
            'system_state': adaptive_controller.system_state.value,
            'adaptation_confidence': round(adaptive_controller.adaptation_confidence, 3)
        },
        'connection_stats': {
            'active_connections': len(active_connections),
            'total_connections': len(connection_stats)
        }
    }

@app.get("/system_info")
async def get_system_info():
    """Advanced system information and diagnostics"""
    return {
        'server_info': {
            'name': 'Intelligent FastAPI ESP32-CAM Frame Server',
            'version': '4.0.0',
            'uptime': time.time() - (connection_stats[0]['connected_time'] if connection_stats else time.time()),
            'python_version': '3.8+',
            'async_support': True
        },
        'performance_summary': {
            'current_fps': round(performance_stats['fps'], 2),
            'target_fps': adaptive_controller.target_fps,
            'fps_efficiency': round(performance_stats['fps'] / adaptive_controller.target_fps * 100, 1),
            'buffer_efficiency': round(performance_stats['buffer_utilization'], 1),
            'quality_efficiency': round(performance_stats['quality_level'] / adaptive_controller.max_quality * 100, 1)
        },
        'system_health': {
            'state': performance_stats['system_state'],
            'confidence': round(performance_stats['adaptation_confidence'], 3),
            'stability': 'high' if performance_stats['adaptation_confidence'] > 0.8 else 'medium' if performance_stats['adaptation_confidence'] > 0.5 else 'low',
            'recommendations': get_system_recommendations()
        },
        'network_analysis': {
            'current_jitter': round(performance_stats['network_jitter'], 4),
            'predicted_latency': round(performance_stats['predicted_latency'], 4),
            'congestion_level': round(performance_stats['congestion_level'], 3),
            'packet_loss_rate': round(performance_stats['packet_loss_rate'], 3),
            'network_quality': 'excellent' if performance_stats['network_jitter'] < 0.05 else 'good' if performance_stats['network_jitter'] < 0.1 else 'poor'
        }
    }

def get_system_recommendations() -> List[str]:
    """Generate intelligent system recommendations"""
    recommendations = []
    
    if performance_stats['fps'] < adaptive_controller.target_fps * 0.8:
        recommendations.append("Consider reducing quality to improve FPS")
    
    if performance_stats['buffer_utilization'] < 20:
        recommendations.append("Buffer underutilized - consider reducing compensation")
    
    if performance_stats['network_jitter'] > 0.15:
        recommendations.append("High network jitter detected - consider network optimization")
    
    if performance_stats['adaptation_confidence'] < 0.5:
        recommendations.append("Low adaptation confidence - system may need stabilization")
    
    if not recommendations:
        recommendations.append("System operating optimally")
    
    return recommendations

@app.get("/health")
async def health_check():
    """Advanced health check with comprehensive system status"""
    return {
        'status': 'healthy',
        'fps': round(performance_stats['fps'], 2),
        'buffer_size': performance_stats['buffer_size'],
        'buffer_utilization': round(performance_stats['buffer_utilization'], 1),
        'active_connections': len(active_connections),
        'compensation_factor': round(performance_stats['compensation_factor'], 3),
        'quality_level': performance_stats['quality_level'],
        'network_jitter': round(performance_stats['network_jitter'], 4),
        'packet_loss_rate': round(performance_stats['packet_loss_rate'], 3),
        'total_frames_processed': performance_stats['total_frames_processed'],
        'system_state': performance_stats['system_state'],
        'adaptation_confidence': round(performance_stats['adaptation_confidence'], 3),
        'system_uptime': time.time() - (connection_stats[0]['connected_time'] if connection_stats else time.time()),
        'queue_size': frame_queue.qsize()
    }

@app.get("/reset_stats")
async def reset_stats():
    """Reset all performance statistics and adaptive parameters"""
    global performance_stats, network_metrics, adaptive_controller, sequence_counter, frame_rate_controller, intelligent_buffer
    
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
        'avg_frame_quality': 0.0,
        'system_state': SystemState.OPTIMAL.value,
        'adaptation_confidence': 1.0,
        'predicted_latency': 0.0,
        'congestion_level': 0.0,
        'min_fps_achieved': 60.0,
        'max_fps_achieved': 0.0,
        'avg_fps_1min': 0.0,
        'fps_stability': 1.0,
        'frame_drop_rate': 0.0,
        'buffer_efficiency': 0.0,
        'compensation_effectiveness': 1.0,
        'network_adaptation_speed': 0.0,
        'quality_adaptation_speed': 0.0,
        'total_frames_dropped': 0,
        'total_frames_sent': 0,
        'stream_uptime': 0.0,
        'last_frame_drop_time': 0.0,
        'consecutive_drops': 0,
        'recovery_speed': 0.0
    })
    
    # Reset network metrics
    network_metrics.latency_history.clear()
    network_metrics.frame_intervals.clear()
    network_metrics.bandwidth_history.clear()
    
    # Reset adaptive controller
    adaptive_controller.performance_history.clear()
    adaptive_controller.quality_history.clear()
    adaptive_controller.compensation_history.clear()
    adaptive_controller.current_quality = 85
    adaptive_controller.compensation_factor = 1.0
    adaptive_controller.system_state = SystemState.OPTIMAL
    adaptive_controller.adaptation_confidence = 1.0
    
    # Reset frame rate controller
    frame_rate_controller.frame_intervals.clear()
    frame_rate_controller.compensation_history.clear()
    frame_rate_controller.adaptive_compensation = 1.0
    frame_rate_controller.current_fps = 30.0
    
    # Reset intelligent buffer
    intelligent_buffer.clear()
    
    # Reset sequence counter
    sequence_counter = 0
    
    # Clear tracking histories
    fps_history.clear()
    frame_drop_history.clear()
    compensation_history.clear()
    
    return {
        'status': 'stats_reset',
        'message': 'All statistics and adaptive parameters have been reset',
        'timestamp': time.time()
    }

@app.get("/frame_rate_control")
async def get_frame_rate_control():
    """Get current frame rate control settings and status"""
    return {
        'target_fps': frame_rate_controller.target_fps,
        'min_fps': frame_rate_controller.min_fps,
        'max_fps': frame_rate_controller.max_fps,
        'current_fps': round(frame_rate_controller.current_fps, 2),
        'adaptive_compensation': round(frame_rate_controller.adaptive_compensation, 3),
        'compensation_stability': round(frame_rate_controller.compensation_stability, 3),
        'frame_drop_threshold': frame_rate_controller.frame_drop_threshold,
        'network_latency_buffer': frame_rate_controller.network_latency_buffer,
        'quality_adaptation_rate': frame_rate_controller.quality_adaptation_rate,
        'buffer_utilization': round(intelligent_buffer.get_utilization(), 1),
        'buffer_size': len(intelligent_buffer.frames),
        'max_buffer_size': intelligent_buffer.max_size,
        'fps_stability': round(performance_stats['fps_stability'], 3),
        'frame_drop_rate': round(performance_stats['frame_drop_rate'], 2),
        'compensation_effectiveness': round(performance_stats['compensation_effectiveness'], 3),
        'system_health': {
            'fps_above_minimum': frame_rate_controller.current_fps >= frame_rate_controller.min_fps,
            'buffer_healthy': intelligent_buffer.get_utilization() < 80.0,
            'compensation_active': frame_rate_controller.adaptive_compensation > 1.0,
            'system_stable': performance_stats['fps_stability'] > 0.8
        }
    }

@app.get("/image_enhancement")
async def get_image_enhancement_status():
    """Get current image enhancement settings and statistics"""
    enhancement_stats = image_enhancer.get_enhancement_stats()
    return {
        'current_mode': performance_stats['enhancement_mode'],
        'enhancement_time_ms': round(performance_stats['enhancement_time'], 2),
        'quality_improvement': round(performance_stats['quality_improvement'], 3),
        'total_frames_enhanced': enhancement_stats['total_frames_processed'],
        'avg_processing_time_ms': round(enhancement_stats['avg_processing_time_ms'], 2),
        'mode_switches': enhancement_stats['mode_switches'],
        'avg_quality_improvement': round(enhancement_stats['avg_quality_improvement'], 3),
        'settings': enhancement_stats['settings'],
        'available_modes': [mode.value for mode in EnhancementMode],
        'recommendations': {
            'server_optimization': 'Balanced processing for CPU environments',
            'security_camera': 'Enhanced edge detection and detail preservation',
            'night_vision': 'Optimized for low-light conditions',
            'quality_optimization': 'Maximum quality with moderate performance impact'
        }
    }

@app.post("/image_enhancement")
async def update_image_enhancement_settings(settings: dict):
    """Update image enhancement settings"""
    try:
        image_enhancer.update_settings(settings)
        return {
            'status': 'success',
            'message': 'Image enhancement settings updated successfully',
            'updated_settings': settings
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating settings: {str(e)}")

from pydantic import BaseModel

class EnhancementModeRequest(BaseModel):
    mode: str

@app.post("/image_enhancement/mode")
async def set_enhancement_mode(request: EnhancementModeRequest):
    """Set specific enhancement mode"""
    try:
        enhancement_mode = EnhancementMode(request.mode.lower())
        # Force the mode for the next frame
        performance_stats['enhancement_mode'] = request.mode.lower()
        return {
            'status': 'success',
            'message': f'Enhancement mode set to {request.mode}',
            'mode': request.mode.lower()
        }
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Available modes: {[m.value for m in EnhancementMode]}")

@app.post("/frame_rate_control")
async def update_frame_rate_control(target_fps: int = None, min_fps: int = None):
    """Update frame rate control settings"""
    global frame_rate_controller
    
    if target_fps is not None:
        if 24 <= target_fps <= 60:
            frame_rate_controller.target_fps = target_fps
            logger.info(f"Target FPS updated to {target_fps}")
        else:
            raise HTTPException(status_code=400, detail="Target FPS must be between 24 and 60")
    
    if min_fps is not None:
        if 15 <= min_fps <= 30:
            frame_rate_controller.min_fps = min_fps
            logger.info(f"Minimum FPS updated to {min_fps}")
        else:
            raise HTTPException(status_code=400, detail="Minimum FPS must be between 15 and 30")
    
    return {
        'status': 'updated',
        'target_fps': frame_rate_controller.target_fps,
        'min_fps': frame_rate_controller.min_fps,
        'message': 'Frame rate control settings updated successfully'
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Advanced WebSocket handler with intelligent error recovery and compensation"""
    global sequence_counter, active_connections
    
    await websocket.accept()
    
    client_id = str(id(websocket))
    async with clients_lock:
        active_connections.append(websocket)
        connection_stats[client_id]['connected_time'] = time.time()
        connection_stats[client_id]['last_activity'] = time.time()
    
    logger.info(f"Advanced WebSocket client connected. Total clients: {len(active_connections)}")
    
    try:
        while True:
            try:
                # Receive data from ESP32-CAM
                data = await websocket.receive()
                
                if data.get("type") == "websocket.disconnect":
                    break
                
                # Update client activity
                connection_stats[client_id]['last_activity'] = time.time()
                
                # Handle binary data
                if "bytes" in data:
                    frame_data = data["bytes"]
                    start_time = time.time()
                    
                    try:
                        img = np.frombuffer(frame_data, dtype=np.uint8)
                        frame = cv2.imdecode(img, cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            # Calculate frame quality score
                            quality_score = calculate_frame_quality(frame)
                            
                            # Create advanced frame data
                            advanced_frame = AdvancedFrameData(
                                frame=frame,
                                timestamp=time.time(),
                                sequence_number=sequence_counter,
                                quality_score=quality_score,
                                network_delay=time.time() - start_time,
                                processing_time=0.0,
                                client_id=client_id
                            )
                            
                            sequence_counter += 1
                            connection_stats[client_id]['frames_received'] += 1
                            connection_stats[client_id]['total_bytes_received'] += len(frame_data)
                            
                            # Add to priority queue with intelligent overflow handling
                            if not frame_queue.full():
                                await frame_queue.put((-advanced_frame.priority, advanced_frame))
                            else:
                                # Remove lowest priority frame and add new one
                                try:
                                    await frame_queue.get()
                                    await frame_queue.put((-advanced_frame.priority, advanced_frame))
                                    performance_stats['dropped_frames'] += 1
                                    performance_stats['total_frames_dropped'] += 1
                                    
                                    # Update frame drop tracking
                                    current_time = time.time()
                                    frame_drop_history.append(current_time)
                                    if len(frame_drop_history) > 100:
                                        frame_drop_history.popleft()
                                    
                                    # Calculate consecutive drops
                                    if len(frame_drop_history) > 1:
                                        time_diff = current_time - frame_drop_history[-2]
                                        if time_diff < 1.0:  # Drops within 1 second
                                            performance_stats['consecutive_drops'] += 1
                                        else:
                                            performance_stats['consecutive_drops'] = 0
                                    
                                    performance_stats['last_frame_drop_time'] = current_time
                                except:
                                    pass
                    
                    except Exception as e:
                        logger.error(f"Error processing WebSocket frame: {e}")
                        continue
                        
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
                break
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                continue
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Cleanup
        async with clients_lock:
            if websocket in active_connections:
                active_connections.remove(websocket)
            if client_id in connection_stats:
                del connection_stats[client_id]
        logger.info(f"Advanced WebSocket client removed. Total clients: {len(active_connections)}")

@app.websocket("/ws_stats")
async def websocket_stats(websocket: WebSocket):
    """WebSocket endpoint for real-time performance stats"""
    await websocket.accept()
    
    try:
        while True:
            # Send comprehensive performance stats every second
            stats = {
                "fps": round(performance_stats['fps'], 2),
                "buffer_size": performance_stats['buffer_size'],
                "latency_ms": round(performance_stats['latency'], 2),
                "dropped_frames": performance_stats['dropped_frames'],
                "active_connections": len(active_connections),
                "compensation_factor": round(performance_stats['compensation_factor'], 3),
                "quality_level": performance_stats['quality_level'],
                "network_jitter": round(performance_stats['network_jitter'], 4),
                "buffer_utilization": round(performance_stats['buffer_utilization'], 1),
                "system_state": performance_stats['system_state'],
                "adaptation_confidence": round(performance_stats['adaptation_confidence'], 3),
                "predicted_latency": round(performance_stats['predicted_latency'], 4),
                "congestion_level": round(performance_stats['congestion_level'], 3)
            }
            await websocket.send_text(json.dumps(stats))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("Stats WebSocket disconnected")
    except Exception as e:
        logger.error(f"Stats WebSocket error: {e}")

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
        
        # Calculate edge density
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
        
        # Normalize and combine metrics
        sharpness_score = min(100, laplacian_var / 10)
        brightness_score = max(0, min(100, brightness / 2.55))
        contrast_score = max(0, min(100, contrast / 2.55))
        edge_score = min(100, edge_density * 1000)
        
        # Weighted combination with edge detection
        quality_score = (
            sharpness_score * 0.4 + 
            brightness_score * 0.2 + 
            contrast_score * 0.2 + 
            edge_score * 0.2
        )
        
        return quality_score
        
    except Exception as e:
        logger.error(f"Error calculating frame quality: {e}")
        return 50.0  # Default quality score

# Video recording configuration for security monitoring
SECURITY_VIDEOS_DIR = "security_videos"
RECORDING_DURATION_HOURS = 1  # 1 hour per video file
RETENTION_DAYS = 14  # Keep videos for 14 days
FRAME_RATE_RECORDING = 60  # 60 FPS for smooth security footage
MIN_FRAMES_PER_SECOND = 30  # Minimum frames to consider a second valid

# STRICT segment management - NO SMALL VIDEOS ALLOWED
MIN_FRAMES_PER_SEGMENT = 3600      # Minimum 1 minute at 60 FPS (3600 frames)
MIN_SEGMENT_DURATION = 60.0        # Minimum 1 minute duration
TARGET_SEGMENT_DURATION = 600.0    # Target 10 minutes per segment
MAX_SEGMENT_DURATION = 1800.0      # Maximum 30 minutes per segment
ABSOLUTE_MIN_SEGMENT_SIZE = 1024 * 500  # 500KB minimum file size

# Segment merging strategy
MERGE_STRATEGY = "CONTINUOUS"      # CONTINUOUS, HOURLY, or MANUAL
AUTO_MERGE_THRESHOLD = 1800.0     # Auto-merge when segments reach 30 minutes total

# Create security videos directory if it doesn't exist
os.makedirs(SECURITY_VIDEOS_DIR, exist_ok=True)

class ProfessionalVideoSegment:
    """Professional video segment with STRICT size controls and comprehensive error handling"""
    
    def __init__(self, start_time: datetime.datetime, target_duration: int = 3600):
        self.start_time = start_time
        self.target_duration = target_duration  # seconds
        self.frames = []
        self.frame_timestamps = []
        self.is_complete = False
        self.file_path = None
        self.video_writer = None
        self.segment_number = 0
        self.creation_time = time.time()
        
        # STRICT validation flags
        self.is_valid_for_save = False
        self.merge_priority = 0  # Higher priority for older segments
        
        # Error handling and recovery
        self.error_count = 0
        self.last_error_time = 0.0
        self.max_errors = 5
        self.error_cooldown = 60.0  # 1 minute between error attempts
        
        # Resource management
        self.resources_allocated = False
        self.cleanup_required = False
        
    def add_frame(self, frame: np.ndarray, timestamp: float) -> bool:
        """Add frame to segment with comprehensive error handling and validation"""
        try:
            # Input validation
            if frame is None:
                logger.debug("Skipping None frame")
                return False
                
            if not hasattr(frame, 'size') or frame.size == 0:
                logger.debug("Skipping empty frame")
                return False
            
            # Frame format validation with error handling
            try:
                if len(frame.shape) != 3 or frame.shape[2] != 3:
                    logger.warning(f"Invalid frame format: {frame.shape if hasattr(frame, 'shape') else 'None'}")
                    return False
                
                # Check for corrupted frame data
                if not np.isfinite(frame).all():
                    logger.warning("Frame contains non-finite values, skipping")
                    return False
                    
            except Exception as e:
                logger.error(f"Frame validation error: {e}")
                return False
            
            # Add frame with timestamp validation
            try:
                if timestamp <= 0:
                    timestamp = time.time()
                
                self.frames.append(frame.copy())
                self.frame_timestamps.append(timestamp)
                
                # Update validation status
                self._update_validation_status()
                return True
                
            except Exception as e:
                logger.error(f"Error adding frame to segment: {e}")
                self._handle_error("frame_addition", e)
                return False
                
        except Exception as e:
            logger.error(f"Critical error in add_frame: {e}")
            self._handle_error("critical_frame_error", e)
            return False
    
    def _handle_error(self, error_type: str, error: Exception):
        """Comprehensive error handling with recovery mechanisms"""
        current_time = time.time()
        
        # Check if we're in error cooldown
        if current_time - self.last_error_time < self.error_cooldown:
            self.error_count += 1
        else:
            # Reset error count after cooldown
            self.error_count = 1
            self.last_error_time = current_time
        
        # Log error with context
        logger.error(f"Segment {self.segment_number} error ({error_type}): {error}")
        logger.error(f"Error count: {self.error_count}/{self.max_errors}")
        
        # Check if we should mark segment as problematic
        if self.error_count >= self.max_errors:
            logger.critical(f"Segment {self.segment_number} exceeded error limit, marking for cleanup")
            self.cleanup_required = True
        
        # Attempt recovery based on error type
        if error_type == "frame_addition":
            self._attempt_frame_recovery()
        elif error_type == "critical_frame_error":
            self._attempt_critical_recovery()
    
    def _attempt_frame_recovery(self):
        """Attempt to recover from frame addition errors"""
        try:
            # Clear any corrupted frames
            if len(self.frames) > 0:
                # Validate last frame
                last_frame = self.frames[-1]
                if not self._validate_frame_integrity(last_frame):
                    logger.info("Removing corrupted last frame during recovery")
                    self.frames.pop()
                    if self.frame_timestamps:
                        self.frame_timestamps.pop()
            
            # Update validation status
            self._update_validation_status()
            
        except Exception as e:
            logger.error(f"Frame recovery failed: {e}")
    
    def _attempt_critical_recovery(self):
        """Attempt to recover from critical errors"""
        try:
            # Clear all frames and start fresh
            logger.info("Performing critical recovery - clearing all frames")
            self.frames.clear()
            self.frame_timestamps.clear()
            self.is_valid_for_save = False
            
            # Reset error state
            self.error_count = 0
            self.last_error_time = time.time()
            
        except Exception as e:
            logger.error(f"Critical recovery failed: {e}")
    
    def _validate_frame_integrity(self, frame: np.ndarray) -> bool:
        """Validate frame data integrity"""
        try:
            if frame is None:
                return False
            
            # Check basic properties
            if not hasattr(frame, 'shape') or len(frame.shape) != 3:
                return False
            
            # Check for corrupted data
            if not np.isfinite(frame).all():
                return False
            
            # Check for reasonable values
            if frame.min() < 0 or frame.max() > 255:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _update_validation_status(self):
        """Update whether this segment is valid for saving with error handling"""
        try:
            frame_count = len(self.frames)
            duration = self.get_duration()
            
            # STRICT requirements - must meet ALL criteria
            self.is_valid_for_save = (
                frame_count >= MIN_FRAMES_PER_SEGMENT and
                duration >= MIN_SEGMENT_DURATION and
                frame_count >= MIN_FRAMES_PER_SECOND * duration and  # Ensure proper frame rate
                not self.cleanup_required  # Don't save if cleanup is required
            )
            
            # Update merge priority based on age
            age = time.time() - self.creation_time
            self.merge_priority = int(age / 60)  # Priority increases with age in minutes
            
        except Exception as e:
            logger.error(f"Error updating validation status: {e}")
            self.is_valid_for_save = False
    
    def get_duration(self) -> float:
        """Get actual duration of segment in seconds with error handling"""
        try:
            if len(self.frame_timestamps) < 2:
                return 0.0
            
            # Validate timestamps
            valid_timestamps = [ts for ts in self.frame_timestamps if ts > 0 and np.isfinite(ts)]
            
            if len(valid_timestamps) < 2:
                return 0.0
            
            return valid_timestamps[-1] - valid_timestamps[0]
            
        except Exception as e:
            logger.error(f"Error calculating duration: {e}")
            return 0.0
    
    def get_frame_count(self) -> int:
        """Get total frame count with validation"""
        try:
            return len(self.frames)
        except Exception as e:
            logger.error(f"Error getting frame count: {e}")
            return 0
    
    def get_estimated_size_kb(self) -> float:
        """Get estimated file size in KB with error handling"""
        try:
            if len(self.frames) == 0:
                return 0.0
            
            # Validate frame dimensions
            valid_frames = [f for f in self.frames if self._validate_frame_integrity(f)]
            
            if len(valid_frames) == 0:
                return 0.0
            
            # Use first valid frame for dimension calculation
            frame = valid_frames[0]
            height, width, channels = frame.shape
            
            # Rough estimate: frames * width * height * channels * compression_factor
            estimated_size = len(valid_frames) * width * height * channels * 0.15 / 1024
            return max(0.0, estimated_size)
            
        except Exception as e:
            logger.error(f"Error calculating estimated size: {e}")
            return 0.0
    
    def is_ready_for_save(self) -> bool:
        """Check if segment meets STRICT requirements for saving"""
        try:
            # Check if cleanup is required
            if self.cleanup_required:
                return False
            
            return self.is_valid_for_save
            
        except Exception as e:
            logger.error(f"Error checking save readiness: {e}")
            return False
    
    def should_create_new_segment(self) -> bool:
        """Check if we should create a new segment - STRICT controls with error handling"""
        try:
            # NEVER create new segment if current one is too small
            if not self.is_valid_for_save:
                return False
            
            # Don't create new segment if cleanup is required
            if self.cleanup_required:
                return False
            
            # Create new segment only when we've reached target duration
            duration = self.get_duration()
            if duration >= TARGET_SEGMENT_DURATION:
                return True
            
            # Create new segment if we've reached maximum duration
            if duration >= MAX_SEGMENT_DURATION:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking segment creation: {e}")
            return False
    
    def can_be_merged(self) -> bool:
        """Check if this segment can be merged with others"""
        try:
            # Can merge if it has some content but doesn't meet save requirements
            return (len(self.frames) > 0 and 
                   not self.is_valid_for_save and 
                   not self.cleanup_required)
            
        except Exception as e:
            logger.error(f"Error checking merge capability: {e}")
            return False
    
    def get_merge_key(self) -> str:
        """Get key for merging - segments with same key can be merged"""
        try:
            # Group segments by hour for merging
            return self.start_time.strftime('%Y%m%d_%H')
            
        except Exception as e:
            logger.error(f"Error getting merge key: {e}")
            return "unknown"
    
    def cleanup(self):
        """Clean up resources with comprehensive error handling"""
        try:
            # Release video writer
            if self.video_writer is not None:
                try:
                    self.video_writer.release()
                except Exception as e:
                    logger.error(f"Error releasing video writer: {e}")
                finally:
                    self.video_writer = None
            
            # Clear frame data
            try:
                self.frames.clear()
                self.frame_timestamps.clear()
            except Exception as e:
                logger.error(f"Error clearing frame data: {e}")
            
            # Reset state
            self.is_complete = False
            self.is_valid_for_save = False
            self.cleanup_required = False
            self.error_count = 0
            
            logger.debug(f"Segment {self.segment_number} cleanup completed")
            
        except Exception as e:
            logger.error(f"Critical error during segment cleanup: {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        try:
            if self.video_writer is not None:
                self.video_writer.release()
        except:
            pass

class ProfessionalVideoRecorder:
    """Professional video recorder with STRICT size controls, comprehensive error handling, and system resilience"""
    
    def __init__(self):
        self.recording_active = False
        self.current_hour_start = None
        self.current_hour_dir = None
        self.current_segments: List[ProfessionalVideoSegment] = []
        self.recording_fps = FRAME_RATE_RECORDING
        self.video_quality = 95  # High quality for security footage
        self.accumulated_frames = 0
        self.accumulated_time = 0.0
        self.frame_validation_enabled = True
        self.min_frame_quality = 30.0
        self.last_frame_time = None
        
        # Auto-save protection
        self.last_auto_save_time = time.time()
        self.auto_save_interval = 60  # Auto-save small segments every 60 seconds
        self.auto_save_enabled = True
        
        # Low FPS handling
        self.low_fps_mode = False
        self.low_fps_threshold = 5.0  # Consider FPS low if below 5
        self.low_fps_recording_fps = 1.0  # Use 1 FPS for low FPS mode
        
        # Directory management
        self.complete_hours_dir = None
        self.partial_segments_dir = None
        self.merged_videos_dir = None
        
        # Merge management
        self.pending_merge_segments = []  # Segments waiting to be merged
        self.last_merge_check = time.time()
        self.merge_check_interval = 300  # Check for merges every 5 minutes
        
        # System health and recovery
        self.system_health = {
            'total_errors': 0,
            'recovery_attempts': 0,
            'last_recovery_time': 0.0,
            'system_state': 'healthy',
            'performance_metrics': {}
        }
        
        # Error handling and recovery
        self.max_consecutive_errors = 10
        self.error_recovery_cooldown = 120.0  # 2 minutes between recovery attempts
        self.auto_recovery_enabled = True
        
        # Resource monitoring
        self.resource_monitor = {
            'disk_space_warning': 1024 * 1024 * 1024,  # 1GB warning threshold
            'memory_warning': 0.8,  # 80% memory usage warning
            'cpu_warning': 0.9,     # 90% CPU usage warning
        }
        
        # Performance tracking
        self.performance_history = deque(maxlen=1000)
        self.last_performance_check = time.time()
        self.performance_check_interval = 60.0  # Check performance every minute
    
    def _start_new_hour(self):
        """Start recording for a new hour with comprehensive error handling and directory management"""
        try:
            current_time = datetime.datetime.now()
            self.current_hour_start = current_time.replace(minute=0, second=0, microsecond=0)
            
            # Create organized directory structure with error handling
            try:
                year_month = current_time.strftime("%Y_%m")
                date_str = current_time.strftime("%Y%m%d")
                hour_str = current_time.strftime("%H")
                
                # Base directory for current hour
                self.current_hour_dir = os.path.join(SECURITY_VIDEOS_DIR, year_month, date_str, hour_str)
                
                # Subdirectories
                self.complete_hours_dir = os.path.join(self.current_hour_dir, "complete_hours")
                self.partial_segments_dir = os.path.join(self.current_hour_dir, "partial_segments")
                self.merged_videos_dir = os.path.join(self.current_hour_dir, "merged_videos")
                
                # Create directories with error handling
                for directory in [self.current_hour_dir, self.complete_hours_dir, 
                                self.partial_segments_dir, self.merged_videos_dir]:
                    try:
                        os.makedirs(directory, exist_ok=True)
                    except Exception as e:
                        logger.error(f"Failed to create directory {directory}: {e}")
                        raise
                
            except Exception as e:
                logger.error(f"Directory creation failed: {e}")
                # Fallback to basic directory structure
                self._create_fallback_directory_structure()
            
            # Reset segment counter and state
            self._cleanup_current_segments()
            self.current_segments = []
            self.accumulated_frames = 0
            self.accumulated_time = 0.0
            
            # Update system health
            self._update_system_health("new_hour_started", "success")
            
            logger.info(f"Started new hour recording: {self.current_hour_start.strftime('%Y-%m-%d %H:%M:%S')}")
            
        except Exception as e:
            logger.error(f"Critical error starting new hour: {e}")
            self._handle_critical_error("new_hour_start", e)
    
    def _create_fallback_directory_structure(self):
        """Create fallback directory structure when primary creation fails"""
        try:
            fallback_dir = os.path.join(SECURITY_VIDEOS_DIR, "fallback", datetime.datetime.now().strftime("%Y%m%d_%H%M"))
            self.current_hour_dir = fallback_dir
            self.complete_hours_dir = os.path.join(fallback_dir, "complete_hours")
            self.partial_segments_dir = os.path.join(fallback_dir, "partial_segments")
            self.merged_videos_dir = os.path.join(fallback_dir, "merged_videos")
            
            for directory in [fallback_dir, self.complete_hours_dir, self.partial_segments_dir, self.merged_videos_dir]:
                os.makedirs(directory, exist_ok=True)
                
            logger.warning(f"Using fallback directory structure: {fallback_dir}")
            
        except Exception as e:
            logger.critical(f"Fallback directory creation failed: {e}")
            # Last resort - use current directory
            self.current_hour_dir = "."
            self.complete_hours_dir = "."
            self.partial_segments_dir = "."
            self.merged_videos_dir = "."
    
    def _cleanup_current_segments(self):
        """Clean up current segments with error handling and resource release"""
        try:
            logger.info(f"Cleaning up {len(self.current_segments)} current segments...")
            
            for segment in self.current_segments:
                try:
                    # Save segment if it has frames and hasn't been saved
                    if len(segment.frames) > 0 and segment.file_path is None:
                        logger.info(f"Saving segment {segment.segment_number} before cleanup: {len(segment.frames)} frames")
                        self._save_segment(segment, is_complete=False, force_save=True)
                    
                    # Clean up segment resources
                    segment.cleanup()
                    logger.debug(f"Cleaned up segment {segment.segment_number}")
                    
                except Exception as e:
                    logger.error(f"Error cleaning up segment {segment.segment_number}: {e}")
            
            # Clear the list
            self.current_segments.clear()
            
            # Force garbage collection to free memory
            import gc
            gc.collect()
            
            logger.info("Segment cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during segment cleanup: {e}")
    
    def start_new_recording(self):
        """Start new recording session with comprehensive error handling"""
        try:
            if self.recording_active:
                self.stop_current_recording()
            
            # Check system health before starting
            if not self._check_system_health():
                logger.warning("System health check failed, attempting recovery before starting recording")
                self._attempt_system_recovery()
            
            self._start_new_hour()
            self.recording_active = True
            
            # Update system health
            self._update_system_health("recording_started", "success")
            
            logger.info(f"Professional security recording started for hour: {self.current_hour_start.strftime('%Y-%m-%d %H:%M:%S')}")
            
        except Exception as e:
            logger.error(f"Critical error starting recording: {e}")
            self._handle_critical_error("recording_start", e)
            # Attempt recovery
            if self.auto_recovery_enabled:
                self._attempt_system_recovery()
    
    def add_frame(self, frame):
        """Add frame to current recording with comprehensive error handling and system resilience"""
        # Check if recording is active, if not, try to restart
        if not self.recording_active:
            logger.info("Recording not active, attempting to restart...")
            if self.force_restart_recording():
                logger.info("Recording restarted successfully")
            else:
                logger.warning("Failed to restart recording")
                return
        
        try:
            # System health check
            if not self._check_system_health():
                logger.warning("System health degraded, attempting recovery")
                self._attempt_system_recovery()
            
            # Validate frame with comprehensive error handling
            if not self._validate_frame(frame):
                logger.debug("Skipping invalid frame")
                return
            
            current_time = time.time()
            
            # Check if we should start a new hour
            if self._should_start_new_hour():
                self._start_new_hour()
            
            # Create new segment if needed
            if not self.current_segments:
                self._create_new_segment()
            
            current_segment = self.current_segments[-1]
            
            # Add frame to current segment with error handling
            if current_segment.add_frame(frame, current_time):
                self.accumulated_frames += 1
                
                # Check if current segment should be saved and new one created
                if current_segment.should_create_new_segment():
                    # Save current segment (it's now large enough)
                    if self._save_segment(current_segment, is_complete=False):
                        # Create new segment for next batch
                        self._create_new_segment()
                        
                        logger.info(f"Created new segment: {len(current_segment.frames)} frames, {current_segment.get_duration():.1f}s duration, {current_segment.get_estimated_size_kb():.1f}KB")
                    else:
                        logger.warning("Failed to save segment, keeping current segment")
            
            # Check for merge opportunities
            self._check_merge_opportunities()
            
            # Update timing with error handling
            if self.last_frame_time is not None:
                try:
                    frame_interval = current_time - self.last_frame_time
                    if frame_interval > 0 and frame_interval < 10.0:  # Sanity check
                        self.accumulated_time += frame_interval
                except Exception as e:
                    logger.error(f"Error updating timing: {e}")
            
            self.last_frame_time = current_time
            
            # Update performance metrics
            self._update_performance_metrics()
            
            # Check for low FPS and adjust recording settings
            self._check_and_adjust_fps_settings(current_time)
            
            # Auto-save small segments periodically for protection
            if self.auto_save_enabled and current_time - self.last_auto_save_time > self.auto_save_interval:
                self.auto_save_small_segments()
                self.last_auto_save_time = current_time
            
        except Exception as e:
            logger.error(f"Error adding frame to recording: {e}")
            self._handle_error("frame_addition", e)
            
            # If this is a connection error, try to save current segments
            if "connection" in str(e).lower() or "timeout" in str(e).lower():
                logger.warning("Connection error detected, attempting to save current segments...")
                try:
                    self._save_current_segments(force_save=True)
                except Exception as save_error:
                    logger.error(f"Failed to save segments during connection error: {save_error}")
    
    def _handle_error(self, error_type: str, error: Exception):
        """Comprehensive error handling with recovery mechanisms"""
        try:
            current_time = time.time()
            
            # Update system health
            self.system_health['total_errors'] += 1
            self.system_health['system_state'] = 'degraded'
            
            # Log error with context
            logger.error(f"Recording error ({error_type}): {error}")
            logger.error(f"Total errors: {self.system_health['total_errors']}")
            
            # Check if we need critical error handling
            if self.system_health['total_errors'] >= self.max_consecutive_errors:
                logger.critical("Maximum consecutive errors reached, triggering critical recovery")
                self._handle_critical_error(error_type, error)
            
            # Attempt automatic recovery if enabled
            if self.auto_recovery_enabled and current_time - self.system_health['last_recovery_time'] > self.error_recovery_cooldown:
                self._attempt_system_recovery()
                
        except Exception as e:
            logger.critical(f"Error in error handler: {e}")
    
    def _handle_critical_error(self, error_type: str, error: Exception):
        """Handle critical errors with system-wide recovery"""
        try:
            logger.critical(f"Critical error detected: {error_type} - {error}")
            
            # Update system state
            self.system_health['system_state'] = 'critical'
            self.system_health['last_recovery_time'] = time.time()
            
            # Stop recording to prevent further errors
            if self.recording_active:
                logger.critical("Stopping recording due to critical error")
                self.recording_active = False
            
            # Force cleanup of all resources
            self._force_cleanup_all_resources()
            
            # Attempt system recovery
            self._attempt_system_recovery()
            
        except Exception as e:
            logger.critical(f"Critical error in critical error handler: {e}")
            # Last resort - reset everything
            self._emergency_reset()
    
    def _attempt_system_recovery(self):
        """Attempt to recover the system from errors"""
        try:
            current_time = time.time()
            
            if current_time - self.system_health['last_recovery_time'] < self.error_recovery_cooldown:
                return
            
            logger.info("Attempting system recovery...")
            
            # Clean up problematic segments
            self._cleanup_problematic_segments()
            
            # Check and repair directory structure
            self._repair_directory_structure()
            
            # Reset error counters
            self.system_health['total_errors'] = 0
            self.system_health['system_state'] = 'recovering'
            self.system_health['last_recovery_time'] = current_time
            self.system_health['recovery_attempts'] += 1
            
            # Restart recording if it was stopped
            if not self.recording_active and self.system_health['recovery_attempts'] < 3:
                logger.info("Restarting recording after recovery")
                self.recording_active = True
                self._start_new_hour()
            
            logger.info("System recovery completed")
            
        except Exception as e:
            logger.error(f"System recovery failed: {e}")
            self.system_health['system_state'] = 'critical'
    
    def _cleanup_problematic_segments(self):
        """Clean up segments that have errors or are corrupted"""
        try:
            segments_to_remove = []
            
            for segment in self.current_segments:
                if segment.cleanup_required or segment.error_count >= segment.max_errors:
                    segments_to_remove.append(segment)
                    logger.info(f"Marking segment {segment.segment_number} for removal due to errors")
            
            # Remove problematic segments
            for segment in segments_to_remove:
                try:
                    segment.cleanup()
                    self.current_segments.remove(segment)
                except Exception as e:
                    logger.error(f"Error removing problematic segment: {e}")
            
            logger.info(f"Cleaned up {len(segments_to_remove)} problematic segments")
            
        except Exception as e:
            logger.error(f"Error during problematic segment cleanup: {e}")
    
    def _repair_directory_structure(self):
        """Repair directory structure if it's corrupted"""
        try:
            if not self.current_hour_dir or not os.path.exists(self.current_hour_dir):
                logger.warning("Current hour directory missing, recreating...")
                self._start_new_hour()
                return
            
            # Check subdirectories
            for dir_name, dir_path in [
                ("complete_hours", self.complete_hours_dir),
                ("partial_segments", self.partial_segments_dir),
                ("merged_videos", self.merged_videos_dir)
            ]:
                if not os.path.exists(dir_path):
                    logger.warning(f"Missing {dir_name} directory, recreating...")
                    os.makedirs(dir_path, exist_ok=True)
            
        except Exception as e:
            logger.error(f"Error repairing directory structure: {e}")
    
    def _force_cleanup_all_resources(self):
        """Force cleanup of all resources in emergency situations"""
        try:
            logger.critical("Force cleaning up all resources...")
            
            # Clean up all segments
            for segment in self.current_segments:
                try:
                    segment.cleanup()
                except:
                    pass
            
            self.current_segments.clear()
            
            # Reset state
            self.recording_active = False
            self.accumulated_frames = 0
            self.accumulated_time = 0.0
            
            logger.critical("Force cleanup completed")
            
        except Exception as e:
            logger.critical(f"Force cleanup failed: {e}")
    
    def _emergency_reset(self):
        """Emergency reset of the entire system"""
        try:
            logger.critical("EMERGENCY RESET - Resetting entire system...")
            
            # Force cleanup
            self._force_cleanup_all_resources()
            
            # Reset system health
            self.system_health = {
                'total_errors': 0,
                'recovery_attempts': 0,
                'last_recovery_time': time.time(),
                'system_state': 'reset',
                'performance_metrics': {}
            }
            
            # Reset performance tracking
            self.performance_history.clear()
            self.last_performance_check = time.time()
            
            logger.critical("Emergency reset completed")
            
        except Exception as e:
            logger.critical(f"Emergency reset failed: {e}")
    
    def _check_system_health(self) -> bool:
        """Check overall system health"""
        try:
            # Check error count
            if self.system_health['total_errors'] >= self.max_consecutive_errors:
                return False
            
            # Check system state
            if self.system_health['system_state'] in ['critical', 'reset']:
                return False
            
            # Check resource usage
            if not self._check_resource_usage():
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
            return False
    
    def _check_resource_usage(self) -> bool:
        """Check system resource usage"""
        try:
            # Check disk space
            if self.current_hour_dir and os.path.exists(self.current_hour_dir):
                try:
                    disk_usage = os.statvfs(self.current_hour_dir)
                    free_space = disk_usage.f_frsize * disk_usage.f_bavail
                    if free_space < self.resource_monitor['disk_space_warning']:
                        logger.warning(f"Low disk space: {free_space / (1024**3):.2f}GB available")
                        return False
                except Exception as e:
                    logger.warning(f"Could not check disk space: {e}")
            
            # Check memory usage (if psutil is available)
            try:
                import psutil
                memory_percent = psutil.virtual_memory().percent / 100.0
                if memory_percent > self.resource_monitor['memory_warning']:
                    logger.warning(f"High memory usage: {memory_percent*100:.1f}%")
                    return False
            except ImportError:
                pass  # psutil not available
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking resource usage: {e}")
            return False
    
    def _update_performance_metrics(self):
        """Update performance metrics"""
        try:
            current_time = time.time()
            
            if current_time - self.last_performance_check >= self.performance_check_interval:
                metrics = {
                    'timestamp': current_time,
                    'active_segments': len(self.current_segments),
                    'total_frames': self.accumulated_frames,
                    'total_time': self.accumulated_time,
                    'system_state': self.system_health['system_state'],
                    'error_count': self.system_health['total_errors']
                }
                
                self.performance_history.append(metrics)
                self.last_performance_check = current_time
                
                # Update system health performance metrics
                self.system_health['performance_metrics'] = metrics
                
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
    
    def _update_system_health(self, event: str, status: str):
        """Update system health status"""
        try:
            if status == "success":
                if self.system_health['system_state'] == 'recovering':
                    self.system_health['system_state'] = 'healthy'
                elif self.system_health['system_state'] == 'degraded':
                    self.system_health['system_state'] = 'recovering'
            
            logger.debug(f"System health update: {event} - {status} -> {self.system_health['system_state']}")
            
        except Exception as e:
            logger.error(f"Error updating system health: {e}")
    
    def _should_start_new_hour(self) -> bool:
        """Check if we should start a new hour"""
        if not self.current_hour_start:
            return True
        
        current_time = datetime.datetime.now()
        elapsed = (current_time - self.current_hour_start).total_seconds()
        
        return elapsed >= 3600  # 1 hour
    
    def _validate_frame(self, frame) -> bool:
        """Validate frame for recording"""
        if frame is None:
            return False
        
        try:
            # Check basic properties
            if not hasattr(frame, 'shape') or len(frame.shape) != 3:
                return False
            
            height, width, channels = frame.shape
            if width < 100 or height < 100 or channels != 3:
                return False
            
            # Check data type
            if frame.dtype != np.uint8:
                return False
            
            # Check if frame is not empty
            if frame.size == 0:
                return False
            
            # Check brightness (avoid completely black or white frames)
            mean_brightness = np.mean(frame)
            if mean_brightness < 5 or mean_brightness > 250:
                return False
            
            # Check variance (avoid completely uniform frames)
            variance = np.var(frame)
            if variance < 10:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _save_segment(self, segment: ProfessionalVideoSegment, is_complete: bool = False, force_save: bool = False):
        """Save video segment with flexible size validation - allows small videos for recovery"""
        # Check if we should force save (for recovery scenarios)
        if not force_save:
            # Normal validation - check if segment meets requirements
            if not segment.is_ready_for_save():
                logger.warning(f"Segment rejected for save - does not meet requirements: {len(segment.frames)} frames, {segment.get_duration():.1f}s duration")
                return None
            
            # Additional size validation for normal saves
            estimated_size_kb = segment.get_estimated_size_kb()
            if estimated_size_kb < (ABSOLUTE_MIN_SEGMENT_SIZE / 1024):
                logger.warning(f"Segment rejected - estimated size too small: {estimated_size_kb:.1f}KB < {(ABSOLUTE_MIN_SEGMENT_SIZE / 1024):.1f}KB")
                return None
        else:
            # Force save mode - save even small segments for recovery
            if len(segment.frames) == 0:
                logger.warning("Cannot save empty segment")
                return None
            
            logger.info(f"Force saving small segment for recovery: {len(segment.frames)} frames, {segment.get_duration():.1f}s duration")
        
        try:
            # Determine save location
            if is_complete:
                save_dir = self.complete_hours_dir
                filename = f"complete_{segment.start_time.strftime('%H%M%S')}_{segment.segment_number:02d}.mp4"
            else:
                save_dir = self.partial_segments_dir
                filename = f"partial_{segment.start_time.strftime('%H%M%S')}_{segment.segment_number:02d}.mp4"
            
            filepath = os.path.join(save_dir, filename)
            
            # Initialize video writer with professional settings and error handling
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                # Try different codecs if mp4v fails
                codecs_to_try = ['mp4v', 'XVID', 'MJPG', 'H264']
                video_writer = None
                
                for codec in codecs_to_try:
                    try:
                        fourcc = cv2.VideoWriter_fourcc(*codec)
                        
                        # Get frame dimensions
                        frame_height, frame_width = segment.frames[0].shape[:2]
                        
                        # Ensure consistent frame dimensions
                        target_width, target_height = 640, 480
                        if frame_width != target_width or frame_height != target_height:
                            # Resize all frames to target dimensions
                            resized_frames = []
                            for frame in segment.frames:
                                resized_frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)
                                resized_frames.append(resized_frame)
                            segment.frames = resized_frames
                        
                        # Create video writer with adjusted FPS for low FPS mode
                        effective_fps = self.recording_fps
                        if self.low_fps_mode:
                            effective_fps = max(1.0, self.recording_fps)  # Minimum 1 FPS
                        
                        video_writer = cv2.VideoWriter(
                            filepath, fourcc, effective_fps, (target_width, target_height), isColor=True
                        )
                        
                        if video_writer.isOpened():
                            logger.info(f"Successfully created video writer with codec {codec}")
                            break
                        else:
                            video_writer.release()
                            video_writer = None
                            
                    except Exception as e:
                        logger.warning(f"Failed to create video writer with codec {codec}: {e}")
                        if video_writer:
                            video_writer.release()
                            video_writer = None
                        continue
                
                if not video_writer:
                    logger.error(f"Failed to create video writer with any codec for {filepath}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error initializing video writer: {e}")
                return None
            
            # Write frames with quality validation
            valid_frames_written = 0
            for i, frame in enumerate(segment.frames):
                try:
                    # Validate frame before writing
                    if self._validate_frame(frame):
                        video_writer.write(frame)
                        valid_frames_written += 1
                    else:
                        logger.debug(f"Skipping invalid frame {i} in segment {segment.segment_number}")
                except Exception as e:
                    logger.error(f"Error writing frame {i}: {e}")
                    continue
            
            # Release video writer
            video_writer.release()
            
            if valid_frames_written == 0:
                logger.error(f"No valid frames written to {filepath}")
                os.remove(filepath)  # Remove empty file
                return None
            
            # FINAL STRICT validation - check actual file size
            try:
                file_size = os.path.getsize(filepath)
                
                # Only remove small files if NOT in force_save mode
                if file_size < ABSOLUTE_MIN_SEGMENT_SIZE and not force_save:
                    logger.error(f"CRITICAL: Video file created below minimum size ({file_size} bytes), removing: {filepath}")
                    os.remove(filepath)
                    return None
                elif file_size < ABSOLUTE_MIN_SEGMENT_SIZE and force_save:
                    logger.warning(f"Force save: Keeping small video file ({file_size} bytes) for recovery: {filepath}")
                
                # Log successful save with size information
                logger.info(f"✅ Saved segment: {filename} with {valid_frames_written} frames, {segment.get_duration():.1f}s duration, {file_size/1024:.1f}KB")
                
            except Exception as e:
                logger.error(f"Error checking file size: {e}")
                # Only remove file if we can't verify its size AND not in force_save mode
                if not force_save:
                    try:
                        os.remove(filepath)
                    except:
                        pass
                    return None
                else:
                    logger.warning(f"Force save: Keeping file despite size check error: {filepath}")
            
            # Update segment
            segment.file_path = filepath
            segment.is_complete = is_complete
            
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving segment: {e}")
            return None
    
    def _save_current_segments(self, force_save: bool = False):
        """Save all current segments with optional force save for recovery"""
        saved_files = []
        saved_count = 0
        
        for segment in self.current_segments:
            if segment.file_path is None:  # Not yet saved
                filepath = self._save_segment(segment, is_complete=False, force_save=force_save)
                if filepath:
                    saved_files.append(filepath)
                    saved_count += 1
        
        # Try to merge segments into complete hours
        if saved_files:
            self._merge_segments_to_hours()
        
        return saved_count
    
    def _merge_segments_to_hours(self):
        """Merge partial segments into complete hour videos"""
        try:
            partial_dir = self.partial_segments_dir
            if not os.path.exists(partial_dir):
                return
            
            # Group segments by hour
            hour_groups = {}
            for filename in os.listdir(partial_dir):
                if filename.startswith("partial_") and filename.endswith(".mp4"):
                    filepath = os.path.join(partial_dir, filename)
                    file_stat = os.stat(filepath)
                    
                    # Parse hour from filename
                    try:
                        hour_str = filename.split("_")[1][:2]  # Extract hour
                        hour = int(hour_str)
                        if hour not in hour_groups:
                            hour_groups[hour] = []
                        hour_groups[hour].append((filepath, file_stat.st_mtime))
                    except:
                        continue
            
            # Process each hour group
            for hour, files in hour_groups.items():
                if len(files) < 2:  # Need at least 2 files to merge
                    continue
                
                # Sort files by modification time
                files.sort(key=lambda x: x[1])
                
                # Calculate total duration
                total_duration = 0
                for filepath, _ in files:
                    try:
                        cap = cv2.VideoCapture(filepath)
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        duration = frame_count / fps if fps > 0 else 0
                        total_duration += duration
                        cap.release()
                    except:
                        continue
                
                # If total duration is close to 1 hour, merge them
                if total_duration >= 3500:  # At least 58 minutes
                    self._merge_video_files(files, hour)
                    
        except Exception as e:
            logger.error(f"Error merging segments: {e}")
    
    def _merge_video_files(self, files, hour):
        """Merge multiple video files into one complete hour video"""
        try:
            # Filter out files that are too small
            valid_files = []
            for filepath, _ in files:
                try:
                    file_size = os.path.getsize(filepath)
                    if file_size >= 1024 * 100:  # At least 100KB
                        valid_files.append((filepath, _))
                    else:
                        logger.warning(f"Skipping tiny file for merge: {filepath} ({file_size} bytes)")
                except:
                    continue
            
            if len(valid_files) < 2:
                logger.info(f"Not enough valid files to merge for hour {hour}")
                return
            
            # Create output filename
            current_date = datetime.datetime.now().strftime("%Y%m%d")
            output_filename = f"complete_hour_{current_date}_{hour:02d}0000.mp4"
            output_path = os.path.join(self.complete_hours_dir, output_filename)
            
            # Initialize output video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            output_writer = cv2.VideoWriter(
                output_path, fourcc, self.recording_fps, (640, 480), isColor=True
            )
            
            if not output_writer.isOpened():
                logger.error(f"Failed to create merged video writer: {output_path}")
                return
            
            total_frames_written = 0
            total_duration = 0.0
            
            # Process each input file
            for filepath, _ in valid_files:
                try:
                    cap = cv2.VideoCapture(filepath)
                    if not cap.isOpened():
                        continue
                    
                    # Get video properties
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    
                    if fps > 0 and frame_count > 0:
                        duration = frame_count / fps
                        total_duration += duration
                        
                        logger.info(f"Merging file: {os.path.basename(filepath)} - {frame_count} frames, {duration:.1f}s")
                    
                    while True:
                        ret, frame = cap.read()
                        if not ret:
                            break
                        
                        # Validate and resize frame
                        if self._validate_frame(frame):
                            resized_frame = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_LANCZOS4)
                            output_writer.write(resized_frame)
                            total_frames_written += 1
                    
                    cap.release()
                    
                except Exception as e:
                    logger.error(f"Error processing file {filepath}: {e}")
                    continue
            
            # Release output writer
            output_writer.release()
            
            if total_frames_written > 0 and total_duration >= 3000:  # At least 50 minutes
                logger.info(f"Merged {len(valid_files)} files into {output_filename} with {total_frames_written} frames, {total_duration:.1f}s duration")
                
                # Remove individual files after successful merge
                for filepath, _ in valid_files:
                    try:
                        os.remove(filepath)
                        logger.debug(f"Removed merged file: {filepath}")
                    except:
                        pass
            else:
                # Remove empty or too short output file
                os.remove(output_path)
                logger.warning(f"Merged video too short ({total_duration:.1f}s), removed: {output_filename}")
                
        except Exception as e:
            logger.error(f"Error merging video files: {e}")
    
    def stop_current_recording(self):
        """Stop current recording and save all segments with recovery protection"""
        if not self.recording_active:
            return
        
        try:
            logger.info("Stopping recording and saving all segments...")
            
            # Save all current segments (including small ones for recovery)
            saved_count = self._save_current_segments(force_save=True)
            
            # Try to merge into complete hours
            self._merge_segments_to_hours()
            
            self.recording_active = False
            logger.info(f"Stopped professional security recording session. Saved {saved_count} segments.")
            
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            # Even if there's an error, try to save what we have
            try:
                self._emergency_save_all_segments()
            except Exception as emergency_error:
                logger.critical(f"Emergency save also failed: {emergency_error}")
    
    def _emergency_save_all_segments(self):
        """Emergency save all segments when normal save fails"""
        try:
            logger.warning("Performing emergency save of all segments...")
            saved_count = 0
            
            for segment in self.current_segments:
                if len(segment.frames) > 0:
                    try:
                        # Force save even small segments
                        filepath = self._save_segment(segment, is_complete=False, force_save=True)
                        if filepath:
                            saved_count += 1
                            logger.info(f"Emergency saved segment: {len(segment.frames)} frames")
                    except Exception as e:
                        logger.error(f"Emergency save failed for segment: {e}")
            
            logger.info(f"Emergency save completed: {saved_count} segments saved")
            return saved_count
            
        except Exception as e:
            logger.critical(f"Emergency save completely failed: {e}")
            return 0
    
    def auto_save_small_segments(self):
        """Automatically save small segments that might be lost during disconnection"""
        try:
            saved_count = 0
            
            for segment in self.current_segments:
                # Save segments that have some frames but are too small for normal save
                if (len(segment.frames) > 0 and 
                    segment.file_path is None and 
                    not segment.is_ready_for_save()):
                    
                    # Only save if segment has been around for a while (to avoid saving very new segments)
                    segment_age = time.time() - segment.creation_time
                    if segment_age > 30:  # 30 seconds minimum age
                        try:
                            filepath = self._save_segment(segment, is_complete=False, force_save=True)
                            if filepath:
                                saved_count += 1
                                logger.info(f"Auto-saved small segment: {len(segment.frames)} frames, {segment.get_duration():.1f}s duration")
                            else:
                                logger.warning(f"Failed to auto-save small segment with {len(segment.frames)} frames")
                        except Exception as e:
                            logger.error(f"Auto-save failed for small segment: {e}")
            
            if saved_count > 0:
                logger.info(f"Auto-saved {saved_count} small segments for protection")
                # Try to merge segments after auto-saving
                self._merge_segments_to_hours()
            
            return saved_count
            
        except Exception as e:
            logger.error(f"Error in auto-save small segments: {e}")
            return 0
    
    def handle_camera_disconnection(self):
        """Handle camera disconnection by saving all current segments"""
        try:
            logger.warning("Camera disconnection detected, saving all current segments...")
            
            # Save all segments (including small ones)
            saved_count = self._save_current_segments(force_save=True)
            
            # Also try to auto-save any remaining small segments
            auto_saved = self.auto_save_small_segments()
            
            # Stop current recording session
            self.recording_active = False
            
            logger.info(f"Camera disconnection handled: {saved_count} segments saved, {auto_saved} auto-saved, recording stopped")
            
            return saved_count + auto_saved
            
        except Exception as e:
            logger.error(f"Error handling camera disconnection: {e}")
            # Try emergency save as last resort
            return self._emergency_save_all_segments()
    
    def handle_camera_reconnection(self):
        """Handle camera reconnection by starting new recording session"""
        try:
            logger.info("Camera reconnection detected, starting new recording session...")
            
            # Clean up any remaining segments from previous session
            self._cleanup_current_segments()
            
            # Reset recording state
            self.accumulated_frames = 0
            self.accumulated_time = 0.0
            self.last_frame_time = None
            self.last_auto_save_time = time.time()
            
            # Start new recording session
            self.start_new_recording()
            
            logger.info("Camera reconnection handled, new recording session started")
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling camera reconnection: {e}")
            return False
    
    def force_restart_recording(self):
        """Force restart recording session (useful for reconnection scenarios)"""
        try:
            logger.info("Force restarting recording session...")
            
            # Stop current session if active
            if self.recording_active:
                self.stop_current_recording()
            
            # Wait a moment for cleanup
            time.sleep(1)
            
            # Clean up any remaining resources
            self._cleanup_current_segments()
            
            # Reset all state
            self.accumulated_frames = 0
            self.accumulated_time = 0.0
            self.last_frame_time = None
            self.last_auto_save_time = time.time()
            
            # Start fresh recording session
            self.start_new_recording()
            
            logger.info("Recording session force restarted successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Error force restarting recording: {e}")
            return False
    
    def check_connection_status(self):
        """Check current connection and recording status"""
        try:
            current_time = time.time()
            
            # Check if we have recent frames
            has_recent_frames = False
            if self.last_frame_time:
                time_since_last_frame = current_time - self.last_frame_time
                has_recent_frames = time_since_last_frame < 30  # 30 seconds threshold
            
            # Check if recording is active
            recording_active = self.recording_active
            
            # Check if we have any segments
            has_segments = len(self.current_segments) > 0
            
            # Determine connection status
            if recording_active and has_recent_frames:
                connection_status = "connected"
            elif recording_active and not has_recent_frames and self.last_frame_time:
                connection_status = "disconnected"
            elif not recording_active:
                connection_status = "stopped"
            else:
                connection_status = "unknown"
            
            return {
                'connection_status': connection_status,
                'recording_active': recording_active,
                'has_recent_frames': has_recent_frames,
                'has_segments': has_segments,
                'last_frame_time': self.last_frame_time,
                'time_since_last_frame': round(current_time - self.last_frame_time, 1) if self.last_frame_time else None,
                'total_segments': len(self.current_segments),
                'total_frames': self.accumulated_frames
            }
            
        except Exception as e:
            logger.error(f"Error checking connection status: {e}")
            return {
                'connection_status': 'error',
                'error': str(e)
            }
    
    def _check_and_adjust_fps_settings(self, current_time):
        """Check current FPS and adjust recording settings for low FPS scenarios"""
        try:
            if self.last_frame_time is None:
                return
            
            # Calculate current FPS
            time_since_last_frame = current_time - self.last_frame_time
            if time_since_last_frame > 0:
                current_fps = 1.0 / time_since_last_frame
            else:
                current_fps = 0
            
            # Check if FPS is low
            if current_fps < self.low_fps_threshold and not self.low_fps_mode:
                logger.warning(f"Low FPS detected ({current_fps:.1f} < {self.low_fps_threshold}), switching to low FPS mode")
                self.low_fps_mode = True
                self.recording_fps = self.low_fps_recording_fps
                
                # Adjust auto-save interval for low FPS
                self.auto_save_interval = 30  # Save more frequently in low FPS mode
                
            elif current_fps >= self.low_fps_threshold and self.low_fps_mode:
                logger.info(f"FPS improved ({current_fps:.1f} >= {self.low_fps_threshold}), switching back to normal mode")
                self.low_fps_mode = False
                self.recording_fps = FRAME_RATE_RECORDING
                self.auto_save_interval = 60  # Back to normal interval
                
        except Exception as e:
            logger.error(f"Error checking FPS settings: {e}")
    
    def cleanup_old_recordings(self):
        """Remove recordings older than retention period"""
        try:
            current_time = datetime.datetime.now()
            retention_cutoff = current_time - datetime.timedelta(days=RETENTION_DAYS)
            
            # Clean up all video directories
            for root, dirs, files in os.walk(SECURITY_VIDEOS_DIR):
                for file in files:
                    if file.endswith('.mp4'):
                        filepath = os.path.join(root, file)
                        try:
                            file_time = datetime.datetime.fromtimestamp(os.path.getctime(filepath))
                            if file_time < retention_cutoff:
                                os.remove(filepath)
                                logger.info(f"Removed old recording: {file}")
                        except:
                            continue
            
            # Remove empty directories
            for root, dirs, files in os.walk(SECURITY_VIDEOS_DIR, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if not os.listdir(dir_path):  # Empty directory
                            os.rmdir(dir_path)
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Error cleaning up old recordings: {e}")
    
    def get_recording_status(self):
        """Get comprehensive recording status"""
        if not self.recording_active:
            return {
                'status': 'inactive',
                'current_hour': None,
                'current_directory': None,
                'segments_count': 0,
                'accumulated_frames': 0,
                'accumulated_time': 0.0
            }
        
        current_time = datetime.datetime.now()
        elapsed_seconds = (current_time - self.current_hour_start).total_seconds() if self.current_hour_start else 0
        
        # Calculate segment statistics
        total_segment_frames = sum(len(seg.frames) for seg in self.current_segments)
        total_segment_duration = sum(seg.get_duration() for seg in self.current_segments)
        
        # Calculate unsaved segments
        unsaved_segments = [seg for seg in self.current_segments if seg.file_path is None]
        small_unsaved_segments = [seg for seg in unsaved_segments if not seg.is_ready_for_save()]
        
        # Calculate current FPS
        current_fps = 0
        if self.last_frame_time:
            time_since_last_frame = time.time() - self.last_frame_time
            if time_since_last_frame > 0:
                current_fps = 1.0 / time_since_last_frame
        
        return {
            'status': 'active',
            'current_hour': self.current_hour_start.strftime('%H:00') if self.current_hour_start else None,
            'current_directory': self.current_hour_dir,
            'segments_count': len(self.current_segments),
            'accumulated_frames': self.accumulated_frames,
            'accumulated_time': round(self.accumulated_time, 2),
            'elapsed_seconds': round(elapsed_seconds, 1),
            'recording_fps': self.recording_fps,
            'current_fps': round(current_fps, 2),
            'low_fps_mode': self.low_fps_mode,
            'quality': self.video_quality,
            'frame_validation': self.frame_validation_enabled,
            'auto_save_enabled': self.auto_save_enabled,
            'auto_save_interval': self.auto_save_interval,
            'protection_status': {
                'unsaved_segments': len(unsaved_segments),
                'small_unsaved_segments': len(small_unsaved_segments),
                'total_frames_at_risk': sum(len(seg.frames) for seg in unsaved_segments),
                'last_auto_save': round(time.time() - self.last_auto_save_time, 1) if self.last_auto_save_time else None
            },
            'segment_stats': {
                'total_frames_in_segments': total_segment_frames,
                'total_duration_in_segments': round(total_segment_duration, 2),
                'min_frames_per_segment': MIN_FRAMES_PER_SEGMENT,
                'min_segment_duration': MIN_SEGMENT_DURATION,
                'target_segment_duration': TARGET_SEGMENT_DURATION
            }
        }

    def cleanup_tiny_videos(self):
        """Clean up any existing tiny video files that shouldn't exist"""
        try:
            cleaned_count = 0
            
            # First, try to merge small files instead of deleting them
            merged_count = self.merge_small_segments()
            
            # Then clean up any remaining tiny files
            for root, dirs, files in os.walk(SECURITY_VIDEOS_DIR):
                for file in files:
                    if file.endswith('.mp4'):
                        filepath = os.path.join(root, file)
                        try:
                            file_size = os.path.getsize(filepath)
                            if file_size < 1024 * 100:  # Less than 100KB
                                os.remove(filepath)
                                cleaned_count += 1
                                logger.info(f"Cleaned up tiny video file: {filepath} ({file_size} bytes)")
                        except Exception as e:
                            logger.debug(f"Could not check file {filepath}: {e}")
            
            if cleaned_count > 0 or merged_count > 0:
                logger.info(f"Cleanup completed: {merged_count} files merged, {cleaned_count} tiny files removed")
            
            return cleaned_count + merged_count
            
        except Exception as e:
            logger.error(f"Error cleaning up tiny videos: {e}")
            return 0

    def _create_new_segment(self):
        """Create new video segment with error handling"""
        try:
            segment_number = len(self.current_segments)
            new_segment = ProfessionalVideoSegment(
                datetime.datetime.now(), 
                target_duration=3600
            )
            new_segment.segment_number = segment_number
            self.current_segments.append(new_segment)
            
            logger.info(f"Created new segment {segment_number} for hour {self.current_hour_start.strftime('%H:%M')}")
            
        except Exception as e:
            logger.error(f"Error creating new segment: {e}")
            self._handle_error("segment_creation", e)

    def _check_merge_opportunities(self):
        """Check if we can merge small segments into larger ones with error handling"""
        try:
            current_time = time.time()
            
            # Check periodically
            if current_time - self.last_merge_check < self.merge_check_interval:
                return
            
            self.last_merge_check = current_time
            
            # Find segments that can be merged
            mergeable_segments = [seg for seg in self.current_segments if seg.can_be_merged()]
            
            if len(mergeable_segments) >= 2:
                # Group segments by merge key (same hour)
                merge_groups = {}
                for seg in mergeable_segments:
                    merge_key = seg.get_merge_key()
                    if merge_key not in merge_groups:
                        merge_groups[merge_key] = []
                    merge_groups[merge_key].append(seg)
                
                # Merge each group
                for merge_key, segments in merge_groups.items():
                    if len(segments) >= 2:
                        self._merge_segments(segments)
                        
        except Exception as e:
            logger.error(f"Error checking merge opportunities: {e}")
            self._handle_error("merge_check", e)

    def merge_small_segments(self):
        """Merge small segments into larger files to prevent tiny video files"""
        try:
            merged_count = 0
            
            # Group small segments by hour
            hour_groups = {}
            
            if os.path.exists(self.partial_segments_dir):
                for filename in os.listdir(self.partial_segments_dir):
                    if filename.startswith("partial_") and filename.endswith(".mp4"):
                        filepath = os.path.join(self.partial_segments_dir, filename)
                        try:
                            file_size = os.path.getsize(filepath)
                            
                            # Only merge small files
                            if file_size < ABSOLUTE_MIN_SEGMENT_SIZE:
                                # Extract hour from filename
                                hour_str = filename.split("_")[1][:2]
                                hour = int(hour_str)
                                
                                if hour not in hour_groups:
                                    hour_groups[hour] = []
                                hour_groups[hour].append((filepath, file_size))
                                
                        except Exception as e:
                            logger.error(f"Error processing file {filename}: {e}")
                            continue
            
            # Merge segments for each hour
            for hour, files in hour_groups.items():
                if len(files) < 2:  # Need at least 2 files to merge
                    continue
                
                # Sort by file size (smallest first)
                files.sort(key=lambda x: x[1])
                
                # Calculate total size
                total_size = sum(size for _, size in files)
                
                # Only merge if total size would be significant
                if total_size >= ABSOLUTE_MIN_SEGMENT_SIZE:
                    try:
                        merged_filepath = self._merge_video_files(files, hour)
                        if merged_filepath:
                            merged_count += 1
                            logger.info(f"Merged {len(files)} small segments into {os.path.basename(merged_filepath)}")
                    except Exception as e:
                        logger.error(f"Error merging segments for hour {hour}: {e}")
            
            logger.info(f"Merge completed: {merged_count} groups merged")
            return merged_count
            
        except Exception as e:
            logger.error(f"Error in merge_small_segments: {e}")
            return 0
    
    def _merge_video_files(self, files, hour):
        """Merge multiple video files into one"""
        try:
            # Create merged filename
            merged_filename = f"merged_{hour:02d}00_{int(time.time())}.mp4"
            merged_filepath = os.path.join(self.partial_segments_dir, merged_filename)
            
            # Get video properties from first file
            cap = cv2.VideoCapture(files[0][0])
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            
            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(merged_filepath, fourcc, fps, (width, height))
            
            if not out.isOpened():
                logger.error(f"Failed to create merged video writer: {merged_filepath}")
                return None
            
            # Write frames from all files
            for filepath, _ in files:
                cap = cv2.VideoCapture(filepath)
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    out.write(frame)
                cap.release()
            
            out.release()
            
            # Remove original files
            for filepath, _ in files:
                try:
                    os.remove(filepath)
                except Exception as e:
                    logger.error(f"Error removing original file {filepath}: {e}")
            
            return merged_filepath
            
        except Exception as e:
            logger.error(f"Error merging video files: {e}")
            return None
    
    def _merge_segments(self, segments: List[ProfessionalVideoSegment]):
        """Merge multiple small segments into one larger segment with comprehensive error handling"""
        try:
            # Sort segments by creation time
            segments.sort(key=lambda x: x.creation_time)
            
            # Calculate total content
            total_frames = sum(len(seg.frames) for seg in segments)
            total_duration = sum(seg.get_duration() for seg in segments)
            
            logger.info(f"Merging {len(segments)} segments: {total_frames} frames, {total_duration:.1f}s duration")
            
            # Create merged segment
            merged_segment = ProfessionalVideoSegment(
                segments[0].start_time,
                target_duration=3600
            )
            merged_segment.segment_number = len(self.current_segments)
            
            # Combine all frames in order with error handling
            for seg in segments:
                for i, frame in enumerate(seg.frames):
                    try:
                        timestamp = seg.frame_timestamps[i] if i < len(seg.frame_timestamps) else time.time()
                        if not merged_segment.add_frame(frame, timestamp):
                            logger.warning(f"Failed to add frame {i} from segment {seg.segment_number} to merged segment")
                    except Exception as e:
                        logger.error(f"Error adding frame {i} from segment {seg.segment_number}: {e}")
                        continue
            
            # Check if merged segment is now valid for saving
            if merged_segment.is_ready_for_save():
                # Save merged segment
                if self._save_segment(merged_segment, is_complete=False):
                    logger.info(f"Successfully merged and saved segment: {len(merged_segment.frames)} frames, {merged_segment.get_duration():.1f}s duration")
                    
                    # Remove original segments
                    for seg in segments:
                        if seg in self.current_segments:
                            self.current_segments.remove(seg)
                            seg.cleanup()
                    
                    # Add merged segment to current segments
                    self.current_segments.append(merged_segment)
                else:
                    logger.error("Failed to save merged segment")
                    merged_segment.cleanup()
            else:
                # Merged segment still too small, keep it for further merging
                logger.info(f"Merged segment still too small, keeping for further merging: {len(merged_segment.frames)} frames")
                
                # Remove original segments
                for seg in segments:
                    if seg in self.current_segments:
                        self.current_segments.remove(seg)
                        seg.cleanup()
                
                # Add merged segment to current segments
                self.current_segments.append(merged_segment)
                
        except Exception as e:
            logger.error(f"Error merging segments: {e}")
            self._handle_error("segment_merging", e)

# Global security video recorder
security_recorder = ProfessionalVideoRecorder()

@app.get("/security_recording/status")
async def get_security_recording_status():
    """Get current security recording status"""
    return {
        'recording_active': security_recorder.recording_active,
        'current_status': security_recorder.get_recording_status(),
        'configuration': {
            'recording_duration_hours': RECORDING_DURATION_HOURS,
            'retention_days': RETENTION_DAYS,
            'recording_fps': FRAME_RATE_RECORDING,
            'video_quality': security_recorder.video_quality,
            'output_directory': SECURITY_VIDEOS_DIR
        }
    }

@app.post("/security_recording/start")
async def start_security_recording():
    """Manually start security recording"""
    try:
        security_recorder.start_new_recording()
        return {
            'status': 'success',
            'message': 'Security recording started',
            'recording_status': security_recorder.get_recording_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting recording: {str(e)}")

@app.post("/security_recording/stop")
async def stop_security_recording():
    """Manually stop security recording"""
    try:
        security_recorder.stop_current_recording()
        return {
            'status': 'success',
            'message': 'Security recording stopped'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping recording: {str(e)}")

@app.get("/security_recording/videos")
async def list_security_videos():
    """List all recorded security videos with metadata"""
    try:
        videos = []
        for filename in os.listdir(SECURITY_VIDEOS_DIR):
            if filename.startswith("security_") and filename.endswith(".mp4"):
                filepath = os.path.join(SECURITY_VIDEOS_DIR, filename)
                file_stat = os.stat(filepath)
                
                # Parse timestamp from filename
                try:
                    timestamp_str = filename.replace("security_", "").replace(".mp4", "")
                    timestamp = datetime.datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                except:
                    timestamp = datetime.datetime.fromtimestamp(file_stat.st_ctime)
                
                videos.append({
                    'filename': filename,
                    'filepath': filepath,
                    'size_mb': round(file_stat.st_size / (1024 * 1024), 2),
                    'created': timestamp.isoformat(),
                    'age_days': (datetime.datetime.now() - timestamp).days,
                    'will_be_deleted': (datetime.datetime.now() - timestamp).days >= RETENTION_DAYS
                })
        
        # Sort by creation time (newest first)
        videos.sort(key=lambda x: x['created'], reverse=True)
        
        return {
            'total_videos': len(videos),
            'videos': videos,
            'retention_policy': f"{RETENTION_DAYS} days",
            'storage_used_mb': sum(v['size_mb'] for v in videos)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing videos: {str(e)}")

@app.post("/security_recording/cleanup")
async def manual_cleanup_recordings():
    """Manually trigger cleanup of old recordings"""
    try:
        before_count = len([f for f in os.listdir(SECURITY_VIDEOS_DIR) if f.endswith('.mp4')])
        security_recorder.cleanup_old_recordings()
        after_count = len([f for f in os.listdir(SECURITY_VIDEOS_DIR) if f.endswith('.mp4')])
        
        return {
            'status': 'success',
            'message': f'Cleanup completed. Removed {before_count - after_count} old recordings',
            'videos_remaining': after_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during cleanup: {str(e)}")

@app.post("/security_recording/handle_disconnection")
async def handle_camera_disconnection():
    """Manually handle camera disconnection by saving all current segments"""
    try:
        saved_count = security_recorder.handle_camera_disconnection()
        
        return {
            'status': 'success',
            'message': f'Camera disconnection handled. Saved {saved_count} segments.',
            'segments_saved': saved_count,
            'recording_active': security_recorder.recording_active
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error handling disconnection: {str(e)}")

@app.post("/security_recording/handle_reconnection")
async def handle_camera_reconnection():
    """Manually handle camera reconnection by starting new recording session"""
    try:
        success = security_recorder.handle_camera_reconnection()
        
        if success:
            return {
                'status': 'success',
                'message': 'Camera reconnection handled. New recording session started.',
                'recording_active': security_recorder.recording_active
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to handle camera reconnection")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error handling reconnection: {str(e)}")

@app.post("/security_recording/force_restart")
async def force_restart_recording():
    """Force restart recording session (useful for reconnection scenarios)"""
    try:
        success = security_recorder.force_restart_recording()
        
        if success:
            return {
                'status': 'success',
                'message': 'Recording session force restarted successfully.',
                'recording_active': security_recorder.recording_active
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to force restart recording")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error force restarting recording: {str(e)}")

@app.post("/security_recording/auto_save_small")
async def auto_save_small_segments():
    """Manually trigger auto-save of small segments"""
    try:
        saved_count = security_recorder.auto_save_small_segments()
        
        return {
            'status': 'success',
            'message': f'Auto-saved {saved_count} small segments.',
            'segments_saved': saved_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error auto-saving segments: {str(e)}")

@app.get("/security_recording/protection_status")
async def get_protection_status():
    """Get current protection status of video segments"""
    try:
        if not security_recorder.recording_active:
            return {
                'status': 'inactive',
                'message': 'No active recording session'
            }
        
        status = security_recorder.get_recording_status()
        protection = status.get('protection_status', {})
        
        return {
            'status': 'active',
            'protection_enabled': security_recorder.auto_save_enabled,
            'auto_save_interval_seconds': security_recorder.auto_save_interval,
            'unsaved_segments': protection.get('unsaved_segments', 0),
            'small_unsaved_segments': protection.get('small_unsaved_segments', 0),
            'total_frames_at_risk': protection.get('total_frames_at_risk', 0),
            'last_auto_save_seconds_ago': protection.get('last_auto_save'),
            'recommendations': []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting protection status: {str(e)}")

@app.get("/security_recording/connection_status")
async def get_connection_status():
    """Get current camera connection and recording status"""
    try:
        connection_status = security_recorder.check_connection_status()
        
        return {
            'status': 'success',
            'connection_info': connection_status,
            'recommendations': _get_connection_recommendations(connection_status)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting connection status: {str(e)}")

@app.get("/security_recording/debug_status")
async def get_debug_status():
    """Get detailed debug status for troubleshooting"""
    try:
        if not security_recorder.recording_active:
            return {
                'status': 'inactive',
                'message': 'No active recording session'
            }
        
        recording_status = security_recorder.get_recording_status()
        connection_status = security_recorder.check_connection_status()
        
        # Get detailed segment information
        segments_info = []
        for i, segment in enumerate(security_recorder.current_segments):
            segments_info.append({
                'segment_number': segment.segment_number,
                'frame_count': len(segment.frames),
                'duration': segment.get_duration(),
                'estimated_size_kb': segment.get_estimated_size_kb(),
                'is_ready_for_save': segment.is_ready_for_save(),
                'file_path': segment.file_path,
                'creation_time': segment.creation_time,
                'age_seconds': time.time() - segment.creation_time
            })
        
        return {
            'status': 'success',
            'recording_status': recording_status,
            'connection_status': connection_status,
            'segments_detail': segments_info,
            'system_info': {
                'low_fps_mode': security_recorder.low_fps_mode,
                'low_fps_threshold': security_recorder.low_fps_threshold,
                'auto_save_enabled': security_recorder.auto_save_enabled,
                'auto_save_interval': security_recorder.auto_save_interval,
                'last_auto_save_time': security_recorder.last_auto_save_time,
                'time_since_last_auto_save': time.time() - security_recorder.last_auto_save_time if security_recorder.last_auto_save_time else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting debug status: {str(e)}")

def _get_connection_recommendations(connection_status):
    """Get recommendations based on connection status"""
    recommendations = []
    
    status = connection_status.get('connection_status', 'unknown')
    
    if status == 'disconnected':
        recommendations.append("Camera appears to be disconnected. Try reconnecting the camera.")
        recommendations.append("Use /security_recording/handle_reconnection to start new session.")
    elif status == 'stopped':
        recommendations.append("Recording is stopped. Use /security_recording/start to begin recording.")
    elif status == 'connected':
        recommendations.append("Camera is connected and recording normally.")
    elif status == 'error':
        recommendations.append("Error detected. Try force restarting the recording session.")
        recommendations.append("Use /security_recording/force_restart to reset the system.")
    
    return recommendations

@app.get("/security_recording/segments")
async def get_video_segments():
    """Get information about current video segments and organization"""
    try:
        if not security_recorder.recording_active:
            return {
                'status': 'inactive',
                'message': 'No active recording session'
            }
        
        segments_info = []
        for i, segment in enumerate(security_recorder.current_segments):
            segments_info.append({
                'segment_number': segment.segment_number,
                'start_time': segment.start_time.isoformat(),
                'frame_count': segment.get_frame_count(),
                'duration': round(segment.get_duration(), 2),
                'is_ready': segment.is_ready_for_save(),
                'is_complete': segment.is_complete,
                'file_path': segment.file_path
            })
        
        return {
            'status': 'active',
            'current_hour': security_recorder.current_hour_start.strftime('%H:00'),
            'current_directory': security_recorder.current_hour_dir,
            'segments_count': len(segments_info),
            'segments': segments_info,
            'accumulated_frames': security_recorder.accumulated_frames,
            'accumulated_time': round(security_recorder.accumulated_time, 2)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting segments: {str(e)}")

@app.get("/security_recording/directory_structure")
async def get_directory_structure():
    """Get organized directory structure for video files"""
    try:
        current_time = datetime.datetime.now()
        year_month = current_time.strftime("%Y_%m")
        current_date = current_time.strftime("%Y%m%d")
        
        base_dir = os.path.join(SECURITY_VIDEOS_DIR, year_month, current_date)
        
        structure = {
            'base_directory': SECURITY_VIDEOS_DIR,
            'current_year_month': year_month,
            'current_date': current_date,
            'current_directory': base_dir,
            'subdirectories': {}
        }
        
        if os.path.exists(base_dir):
            for subdir in ['complete_hours', 'partial_segments', 'merged_videos']:
                subdir_path = os.path.join(base_dir, subdir)
                if os.path.exists(subdir_path):
                    files = [f for f in os.listdir(subdir_path) if f.endswith('.mp4')]
                    structure['subdirectories'][subdir] = {
                        'path': subdir_path,
                        'file_count': len(files),
                        'files': files[:10]  # Show first 10 files
                    }
                else:
                    structure['subdirectories'][subdir] = {
                        'path': subdir_path,
                        'file_count': 0,
                        'files': []
                    }
        
        return structure
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting directory structure: {str(e)}")

@app.post("/security_recording/merge_segments")
async def merge_video_segments():
    """Manually trigger merging of video segments into complete hours"""
    try:
        if not security_recorder.recording_active:
            raise HTTPException(status_code=400, detail="No active recording session")
        
        # Save current segments first
        security_recorder._save_current_segments()
        
        # Then merge
        security_recorder._merge_segments_to_hours()
        
        return {
            'status': 'success',
            'message': 'Video segments merged successfully',
            'current_segments': len(security_recorder.current_segments)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error merging segments: {str(e)}")

@app.post("/security_recording/force_new_hour")
async def force_new_hour():
    """Force start of a new hour recording"""
    try:
        if not security_recorder.recording_active:
            raise HTTPException(status_code=400, detail="No active recording session")
        
        # Save current segments
        security_recorder._save_current_segments()
        
        # Start new hour
        security_recorder._start_new_hour()
        
        return {
            'status': 'success',
            'message': 'New hour recording started',
            'new_hour_directory': security_recorder.current_hour_dir
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting new hour: {str(e)}")

@app.get("/security_recording/quality_metrics")
async def get_recording_quality_metrics():
    """Get quality metrics for current recording session"""
    try:
        if not security_recorder.recording_active:
            return {
                'status': 'inactive',
                'message': 'No active recording session'
            }
        
        # Calculate quality metrics
        total_frames = security_recorder.accumulated_frames
        total_time = security_recorder.accumulated_time
        
        if total_time > 0:
            actual_fps = total_frames / total_time
            fps_efficiency = (actual_fps / FRAME_RATE_RECORDING) * 100
        else:
            actual_fps = 0
            fps_efficiency = 0
        
        return {
            'status': 'active',
            'target_fps': FRAME_RATE_RECORDING,
            'actual_fps': round(actual_fps, 2),
            'fps_efficiency': round(fps_efficiency, 1),
            'total_frames': total_frames,
            'total_time': round(total_time, 2),
            'frame_validation_enabled': security_recorder.frame_validation_enabled,
            'min_frame_quality': security_recorder.min_frame_quality,
            'video_quality': security_recorder.video_quality
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting quality metrics: {str(e)}")

@app.post("/security_recording/cleanup_tiny_videos")
async def cleanup_tiny_videos():
    """Clean up existing tiny video files that shouldn't exist"""
    try:
        cleaned_count = security_recorder.cleanup_tiny_videos()
        
        return {
            'status': 'success',
            'message': f'Cleaned up {cleaned_count} tiny video files',
            'cleaned_count': cleaned_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cleaning up tiny videos: {str(e)}")

@app.get("/security_recording/segment_info")
async def get_segment_info():
    """Get detailed information about current video segments and their sizes"""
    try:
        if not security_recorder.recording_active:
            return {
                'status': 'inactive',
                'message': 'No active recording session'
            }
        
        segments_info = []
        for i, segment in enumerate(security_recorder.current_segments):
            # Calculate estimated file size
            estimated_size_kb = len(segment.frames) * 640 * 480 * 3 * 0.1 / 1024  # Rough estimate
            
            segments_info.append({
                'segment_number': segment.segment_number,
                'start_time': segment.start_time.isoformat(),
                'frame_count': segment.get_frame_count(),
                'duration': round(segment.get_duration(), 2),
                'is_ready': segment.is_ready_for_save(),
                'is_complete': segment.is_complete,
                'file_path': segment.file_path,
                'estimated_size_kb': round(estimated_size_kb, 1),
                'meets_minimum_requirements': segment.is_ready_for_save()
            })
        
        return {
            'status': 'active',
            'current_hour': security_recorder.current_hour_start.strftime('%H:00'),
            'current_directory': security_recorder.current_hour_dir,
            'segments_count': len(segments_info),
            'segments': segments_info,
            'segment_requirements': {
                'min_frames_per_segment': MIN_FRAMES_PER_SEGMENT,
                'min_segment_duration': MIN_SEGMENT_DURATION,
                'target_segment_duration': TARGET_SEGMENT_DURATION,
                'max_segment_duration': MAX_SEGMENT_DURATION
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting segment info: {str(e)}")

@app.post("/security_recording/force_merge_small_segments")
async def force_merge_small_segments():
    """Force merge any small segments to prevent incomplete security videos"""
    try:
        if not security_recorder.recording_active:
            return {
                'status': 'inactive',
                'message': 'No active recording session'
            }
        
        # Find all segments that can be merged
        mergeable_segments = [seg for seg in security_recorder.current_segments if seg.can_be_merged()]
        
        if len(mergeable_segments) < 2:
            return {
                'status': 'no_merge_needed',
                'message': 'Not enough small segments to merge',
                'mergeable_count': len(mergeable_segments)
            }
        
        # Group segments by merge key (same hour)
        merge_groups = {}
        for seg in mergeable_segments:
            merge_key = seg.get_merge_key()
            if merge_key not in merge_groups:
                merge_groups[merge_key] = []
            merge_groups[merge_key].append(seg)
        
        merged_count = 0
        for merge_key, segments in merge_groups.items():
            if len(segments) >= 2:
                # Sort by creation time to maintain order
                segments.sort(key=lambda x: x.creation_time)
                
                # Create merged segment
                merged_segment = ProfessionalVideoSegment(
                    segments[0].start_time,
                    target_duration=3600
                )
                merged_segment.segment_number = len(security_recorder.current_segments)
                
                # Combine all frames in chronological order
                for seg in segments:
                    for i, frame in enumerate(seg.frames):
                        timestamp = seg.frame_timestamps[i] if i < len(seg.frame_timestamps) else time.time()
                        merged_segment.add_frame(frame, timestamp)
                
                # Check if merged segment is now valid
                if merged_segment.is_ready_for_save():
                    # Save merged segment
                    filepath = security_recorder._save_segment(merged_segment, is_complete=False)
                    if filepath:
                        # Remove original segments
                        for seg in segments:
                            if seg in security_recorder.current_segments:
                                security_recorder.current_segments.remove(seg)
                                seg.cleanup()
                        
                        # Add merged segment
                        security_recorder.current_segments.append(merged_segment)
                        merged_count += 1
                        
                        logger.info(f"Successfully merged {len(segments)} segments into: {len(merged_segment.frames)} frames, {merged_segment.get_duration():.1f}s duration")
                else:
                    # Merged segment still too small, keep for further merging
                    logger.info(f"Merged segment still too small, keeping for further merging: {len(merged_segment.frames)} frames")
                    
                    # Remove original segments
                    for seg in segments:
                        if seg in security_recorder.current_segments:
                            security_recorder.current_segments.remove(seg)
                            seg.cleanup()
                    
                    # Add merged segment
                    security_recorder.current_segments.append(merged_segment)
        
        return {
            'status': 'success',
            'message': f'Force merged {merged_count} segment groups',
            'mergeable_segments_found': len(mergeable_segments),
            'merge_groups_processed': len(merge_groups),
            'segments_merged': merged_count,
            'remaining_segments': len(security_recorder.current_segments)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error force merging segments: {str(e)}")

@app.get("/security_recording/segment_health")
async def get_segment_health():
    """Get detailed health status of all video segments"""
    try:
        if not security_recorder.recording_active:
            return {
                'status': 'inactive',
                'message': 'No active recording session'
            }
        
        segments_health = []
        total_frames = 0
        total_duration = 0.0
        valid_segments = 0
        mergeable_segments = 0
        
        for i, segment in enumerate(security_recorder.current_segments):
            frame_count = segment.get_frame_count()
            duration = segment.get_duration()
            estimated_size_kb = segment.get_estimated_size_kb()
            
            total_frames += frame_count
            total_duration += duration
            
            health_status = {
                'segment_number': segment.segment_number,
                'start_time': segment.start_time.isoformat(),
                'frame_count': frame_count,
                'duration_seconds': round(duration, 2),
                'estimated_size_kb': round(estimated_size_kb, 1),
                'is_valid_for_save': segment.is_valid_for_save,
                'is_complete': segment.is_complete,
                'can_be_merged': segment.can_be_merged(),
                'merge_priority': segment.merge_priority,
                'age_minutes': round((time.time() - segment.creation_time) / 60, 1),
                'meets_minimum_requirements': (
                    frame_count >= MIN_FRAMES_PER_SEGMENT and
                    duration >= MIN_SEGMENT_DURATION and
                    estimated_size_kb >= (ABSOLUTE_MIN_SEGMENT_SIZE / 1024)
                )
            }
            
            segments_health.append(health_status)
            
            if segment.is_valid_for_save:
                valid_segments += 1
            elif segment.can_be_merged():
                mergeable_segments += 1
        
        return {
            'status': 'active',
            'current_hour': security_recorder.current_hour_start.strftime('%H:00'),
            'total_segments': len(segments_health),
            'valid_segments': valid_segments,
            'mergeable_segments': mergeable_segments,
            'total_frames': total_frames,
            'total_duration': round(total_duration, 2),
            'segments': segments_health,
            'requirements': {
                'min_frames_per_segment': MIN_FRAMES_PER_SEGMENT,
                'min_segment_duration': MIN_SEGMENT_DURATION,
                'target_segment_duration': TARGET_SEGMENT_DURATION,
                'max_segment_duration': MAX_SEGMENT_DURATION,
                'absolute_min_size_kb': ABSOLUTE_MIN_SEGMENT_SIZE / 1024
            },
            'health_score': round((valid_segments / len(segments_health)) * 100, 1) if segments_health else 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting segment health: {str(e)}")

@app.post("/security_recording/merge_small_segments")
async def merge_small_segments():
    """Merge small video segments into larger files"""
    try:
        merged_count = security_recorder.merge_small_segments()
        
        return {
            'status': 'success',
            'message': f'Merged {merged_count} groups of small segments',
            'merged_count': merged_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error merging small segments: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=3002,
        reload=False,
        workers=1,
        loop="asyncio",
        access_log=True
    ) 