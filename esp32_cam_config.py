"""
ESP32-CAM Optimized Configuration for Security Camera Applications
This file contains optimized settings specifically designed for ESP32-CAM
to achieve better quality and frame rate while maintaining detail for security purposes.
"""

# ESP32-CAM Hardware Specifications
ESP32_CAM_SPECS = {
    'max_resolution': (1600, 1200),  # OV2640 sensor max resolution
    'optimal_resolution': (800, 600),  # Optimal for 30 FPS
    'min_resolution': (640, 480),  # Minimum for acceptable quality
    'max_fps': 30,  # Hardware limitation
    'optimal_fps': 25,  # Sweet spot for quality/performance
    'min_fps': 15,  # Minimum acceptable FPS
    'jpeg_quality_range': (60, 90),  # Quality range for ESP32-CAM
    'optimal_jpeg_quality': 80,  # Best quality/performance balance
}

# Frame Rate Optimization Settings
FRAME_RATE_CONFIG = {
    'target_fps': 25,  # Optimized target for ESP32-CAM
    'min_fps': 15,  # Realistic minimum for ESP32-CAM
    'max_fps': 30,  # Hardware maximum
    'compensation_aggressiveness': 0.8,  # Less aggressive for stability
    'quality_reduction_threshold': 0.7,  # Lower threshold for quality preservation
    'recovery_speed': 0.9,  # Faster recovery for ESP32-CAM
}

# Quality Optimization Settings
QUALITY_CONFIG = {
    'min_quality': 60,  # Higher minimum for security camera
    'max_quality': 90,  # Slightly lower max to prevent overload
    'default_quality': 80,  # Good starting quality
    'quality_reduction_step': 5,  # Smaller steps for gradual adjustment
    'quality_increase_step': 3,  # Gradual quality increase
    'network_jitter_threshold': 0.2,  # Higher tolerance for ESP32-CAM
    'buffer_utilization_threshold': 0.85,  # Higher threshold
}

# Network Optimization Settings
NETWORK_CONFIG = {
    'latency_buffer': 0.2,  # Increased buffer for network issues
    'jitter_tolerance': 0.2,  # Higher tolerance for ESP32-CAM
    'packet_loss_threshold': 0.1,  # Acceptable packet loss rate
    'bandwidth_optimization': True,  # Enable bandwidth optimization
    'progressive_encoding': True,  # Enable progressive JPEG
    'compression_optimization': True,  # Enable compression optimization
}

# Buffer and Processing Settings
BUFFER_CONFIG = {
    'max_buffer_size': 50,  # Smaller buffer for faster processing
    'target_utilization': 70,  # Lower target for ESP32-CAM
    'frame_drop_threshold': 0.6,  # More aggressive frame dropping
    'processing_timeout': 0.1,  # Faster timeout for real-time
    'recovery_frames': 5,  # Fewer frames for recovery
}

# Security Camera Specific Settings
SECURITY_CONFIG = {
    'detail_preservation': True,  # Prioritize detail preservation
    'motion_detection_optimization': True,  # Optimize for motion detection
    'night_vision_consideration': True,  # Consider low-light conditions
    'face_recognition_optimization': True,  # Optimize for face recognition
    'license_plate_optimization': True,  # Optimize for license plate reading
}

# Encoding Optimization Settings
ENCODING_CONFIG = {
    'jpeg_optimize': True,  # Enable JPEG optimization
    'jpeg_progressive': True,  # Enable progressive encoding
    'quality_threshold_progressive': 65,  # Lower threshold for ESP32-CAM
    'additional_optimization_threshold': 75,  # Additional optimizations
    'chroma_subsampling': '4:2:0',  # Standard chroma subsampling
}

# Performance Monitoring Settings
MONITORING_CONFIG = {
    'fps_history_length': 300,  # 5 minutes at 1-second intervals
    'quality_history_length': 100,  # Track quality changes
    'network_metrics_history': 100,  # Track network performance
    'system_health_check_interval': 5,  # Check every 5 seconds
    'performance_log_interval': 1000,  # Log every 1000 frames
}

# ESP32-CAM Specific Recommendations
ESP32_CAM_RECOMMENDATIONS = {
    'wifi_settings': {
        'wifi_mode': 'WIFI_MODE_STA',  # Station mode for better performance
        'wifi_power': 'WIFI_POWER_19_5dBm',  # Maximum power for range
        'wifi_protocol': 'WIFI_PROTOCOL_11B | WIFI_PROTOCOL_11G',  # 802.11b/g for compatibility
    },
    'camera_settings': {
        'framesize': 'FRAMESIZE_VGA',  # 640x480 for good quality/performance
        'quality': 80,  # Good quality setting
        'brightness': 0,  # Default brightness
        'contrast': 0,  # Default contrast
        'saturation': 0,  # Default saturation
        'special_effect': 'WbModeAuto',  # Auto white balance
        'wb_mode': 'WbModeAuto',  # Auto white balance
        'ae_level': 0,  # Auto exposure level
        'aec_value': 300,  # Auto exposure control
        'gain_ctrl': 1,  # Enable gain control
        'agc_gain': 0,  # Auto gain control
        'gainceiling': 6,  # Gain ceiling
        'bpc': 0,  # Black pixel correction
        'wpc': 1,  # White pixel correction
        'raw_gma': 1,  # Raw gamma
        'lenc': 1,  # Lens correction
        'hmirror': 0,  # Horizontal mirror
        'vflip': 0,  # Vertical flip
        'dcw': 1,  # Downsize enable
        'colorbar': 0,  # Color bar test
    },
    'server_settings': {
        'max_connections': 5,  # Limit connections for ESP32-CAM
        'timeout': 30,  # Connection timeout
        'keep_alive': True,  # Enable keep-alive
        'compression': True,  # Enable compression
    }
}

def get_optimized_config():
    """Get optimized configuration for ESP32-CAM"""
    return {
        'frame_rate': FRAME_RATE_CONFIG,
        'quality': QUALITY_CONFIG,
        'network': NETWORK_CONFIG,
        'buffer': BUFFER_CONFIG,
        'security': SECURITY_CONFIG,
        'encoding': ENCODING_CONFIG,
        'monitoring': MONITORING_CONFIG,
        'recommendations': ESP32_CAM_RECOMMENDATIONS
    }

def get_esp32_cam_quality_settings():
    """Get ESP32-CAM specific quality settings"""
    return {
        'min_quality': QUALITY_CONFIG['min_quality'],
        'max_quality': QUALITY_CONFIG['max_quality'],
        'default_quality': QUALITY_CONFIG['default_quality'],
        'jpeg_optimize': ENCODING_CONFIG['jpeg_optimize'],
        'jpeg_progressive': ENCODING_CONFIG['jpeg_progressive'],
        'progressive_threshold': ENCODING_CONFIG['quality_threshold_progressive']
    }

def get_esp32_cam_frame_rate_settings():
    """Get ESP32-CAM specific frame rate settings"""
    return {
        'target_fps': FRAME_RATE_CONFIG['target_fps'],
        'min_fps': FRAME_RATE_CONFIG['min_fps'],
        'max_fps': FRAME_RATE_CONFIG['max_fps'],
        'compensation_aggressiveness': FRAME_RATE_CONFIG['compensation_aggressiveness']
    } 