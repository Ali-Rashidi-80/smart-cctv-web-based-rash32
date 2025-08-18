# Intelligent ESP32-CAM Frame Server

## 🚀 Overview

This project provides two highly optimized, intelligent frame servers for ESP32-CAM with advanced compensation algorithms and robust error handling. Both servers feature ML-based adaptive control, predictive network analysis, and intelligent frame prioritization.

## 📋 Features

### 🔥 Intelligent Flask Server (`intelligent_flask_server.py`)
- **Advanced Buffer Management**: 200-frame buffer with intelligent overflow handling
- **Priority Queue Processing**: Frame prioritization based on quality, age, and network conditions
- **Adaptive Quality Control**: Dynamic JPEG quality adjustment (50-95)
- **Network Compensation**: Real-time jitter and packet loss compensation
- **Frame Quality Analysis**: Multi-factor quality scoring (sharpness, brightness, contrast)
- **Robust WebSocket Handling**: Intelligent error recovery and connection management

### ⚡ Intelligent FastAPI Server (`intelligent_fastapi_server.py`)
- **ML-Based Adaptive Control**: Machine learning principles for parameter adaptation
- **Predictive Network Analysis**: Linear regression for latency prediction
- **System State Management**: Optimal/Degraded/Critical/Recovering states
- **Advanced Buffer Management**: 250-frame buffer with async processing
- **Congestion Detection**: Real-time bandwidth utilization monitoring
- **Comprehensive Metrics**: 20+ performance indicators

## 🛠️ Installation

### Prerequisites
```bash
pip install -r requirements_fastapi.txt
```

### Additional Dependencies for Flask
```bash
pip install flask flask-cors flask-sock
```

## 🚀 Quick Start

### 1. Start Flask Server
```bash
python intelligent_flask_server.py
```
- **Port**: 3002
- **Features**: Intelligent buffering, adaptive quality control, network compensation

### 2. Start FastAPI Server
```bash
python intelligent_fastapi_server.py
```
- **Port**: 3003
- **Features**: ML-based adaptation, predictive analysis, intelligent buffering

## 📡 Endpoints

### Common Endpoints (Both Servers)
- `GET /esp32_frame` - Single frame with intelligent response
- `GET /esp32_video_feed` - Intelligent video stream
- `GET /performance_stats` - Comprehensive performance metrics
- `GET /health` - Advanced health check
- `GET /reset_stats` - Reset all statistics
- `WebSocket /ws` - Frame reception with error recovery

### FastAPI Additional Endpoints
- `GET /` - Server information and features
- `GET /system_info` - Advanced system diagnostics
- `WebSocket /ws_stats` - Real-time performance stats

## 🔧 Key Improvements

### ✅ Fixed Issues
1. **Buffer Management**: 
   - Prevents black screen when buffer is empty
   - Maintains connection during frame droughts
   - Intelligent reuse of last frame when no new frames available

2. **Stream Stability**:
   - Keep-alive frames prevent connection drops
   - Adaptive sleep times based on buffer state
   - Automatic recovery from empty buffer conditions

3. **Error Handling**:
   - Robust WebSocket error recovery
   - Graceful degradation under poor network conditions
   - Comprehensive logging and monitoring

### 🧠 Intelligent Features
1. **Frame Prioritization**:
   - Age-based priority decay
   - Quality score integration
   - Network delay compensation
   - Size-based optimization

2. **Adaptive Control**:
   - Real-time FPS monitoring
   - Dynamic quality adjustment
   - Network condition awareness
   - Performance trend analysis

3. **Network Compensation**:
   - Jitter measurement and compensation
   - Packet loss rate calculation
   - Bandwidth utilization monitoring
   - Predictive latency analysis

## 📊 Performance Metrics

### Real-time Monitoring
- **FPS**: Current and target frame rates
- **Buffer Utilization**: Percentage of buffer capacity used
- **Network Jitter**: Real-time network stability measurement
- **Quality Level**: Current JPEG compression quality
- **Compensation Factor**: Network compensation multiplier
- **System State**: Current operational state (Optimal/Degraded/Critical)

### Advanced Metrics (FastAPI)
- **Predicted Latency**: ML-based latency prediction
- **Congestion Level**: Network congestion detection
- **Adaptation Confidence**: System stability confidence
- **Performance Efficiency**: FPS and quality efficiency scores

## 🧪 Testing

### Stream Connection Test
```bash
python test_stream_connection.py
```
Tests both servers for:
- Stream connection stability
- Buffer behavior under empty conditions
- Performance metrics accuracy
- Error recovery capabilities

### Manual Testing
1. **Browser Test**: Visit `http://localhost:3002/esp32_video_feed` or `http://localhost:3003/esp32_video_feed`
2. **Single Frame**: `http://localhost:3002/esp32_frame` or `http://localhost:3003/esp32_frame`
3. **Performance Stats**: `http://localhost:3002/performance_stats` or `http://localhost:3003/performance_stats`

## 🔍 Troubleshooting

### Common Issues
1. **Black Screen**: 
   - ✅ **FIXED**: Server now maintains connection and reuses last frame
   - Check WebSocket connection from ESP32-CAM
   - Monitor buffer utilization in performance stats

2. **Connection Drops**:
   - ✅ **FIXED**: Keep-alive frames prevent premature disconnection
   - Check network stability
   - Monitor compensation factor in stats

3. **Low FPS**:
   - Check ESP32-CAM frame rate
   - Monitor quality level adjustments
   - Check network jitter values

### Debug Information
- **Log Files**: `intelligent_flask_server.log` and `intelligent_fastapi_server.log`
- **Performance Stats**: Real-time metrics via `/performance_stats`
- **System Info**: FastAPI `/system_info` for detailed diagnostics

## 📈 Performance Comparison

| Feature | Flask Server | FastAPI Server |
|---------|-------------|----------------|
| Buffer Size | 200 frames | 250 frames |
| Processing | Threaded | Async |
| Quality Range | 50-95 | 45-95 |
| State Management | Basic | Advanced (4 states) |
| ML Features | No | Yes |
| Prediction | No | Yes |
| Congestion Detection | No | Yes |

## 🎯 Recommendations

### Use Flask Server When:
- You need simpler debugging
- Threading is preferred over async
- Basic adaptive control is sufficient
- Development and testing scenarios

### Use FastAPI Server When:
- Maximum performance is required
- Advanced ML-based adaptation is needed
- Predictive analysis is important
- Production environments with high load

## 🔄 Updates

### Latest Fixes (v4.0)
- ✅ **Fixed**: Black screen issue when buffer is empty
- ✅ **Fixed**: Connection drops during frame droughts
- ✅ **Added**: Intelligent frame reuse mechanism
- ✅ **Added**: Keep-alive frames for connection stability
- ✅ **Improved**: Buffer management algorithms
- ✅ **Enhanced**: Error recovery and logging

## 📝 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Feel free to submit issues and enhancement requests! 