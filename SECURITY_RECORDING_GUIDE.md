# Security Video Recording System Guide

## Overview

The Security Video Recording System provides automatic 24-hour video monitoring with enhanced frame quality and intelligent retention management. This system is designed specifically for security camera applications using ESP32-CAM with advanced image enhancement.

## Features

### 🎥 **Automatic Recording**
- **Continuous Recording**: 24/7 automatic video recording
- **1-Hour Segments**: Each video file covers exactly 1 hour
- **Enhanced Quality**: Frames are processed through `advanced_image_enhancement.py` before recording
- **High Resolution**: 640x480 resolution with 15 FPS for storage efficiency

### 🗂️ **Smart File Management**
- **Automatic Naming**: `security_YYYYMMDD_HHMMSS.mp4` format
- **14-Day Retention**: Automatic cleanup of old recordings
- **Storage Optimization**: MP4 format with efficient compression
- **Metadata Tracking**: File size, creation time, and age tracking

### 🔧 **Quality Control**
- **Enhanced Frames**: All recorded frames pass through image enhancement
- **Quality Thresholds**: Minimum 85% quality for security footage
- **Dead Zone Protection**: Quality never drops below 75% even in low FPS scenarios
- **Frame Rate Stability**: Consistent 15 FPS recording regardless of stream performance

## Configuration

### Recording Settings
```python
RECORDING_DURATION_HOURS = 1      # 1 hour per video file
RETENTION_DAYS = 14              # Keep videos for 14 days
FRAME_RATE_RECORDING = 15        # Recording frame rate
SECURITY_VIDEOS_DIR = "security_videos"  # Output directory
```

### Quality Thresholds
- **Very Low FPS (0.5-1.0)**: Minimum quality 75%
- **Low FPS (1.0-2.0)**: Minimum quality 78%
- **Moderate FPS (2.0+)**: Minimum quality 80%
- **Network Issues**: Minimum quality 78%
- **Buffer Issues**: Minimum quality 78%

## API Endpoints

### 📊 **Get Recording Status**
```http
GET /security_recording/status
```
Returns current recording status, configuration, and active session information.

### ▶️ **Start Recording**
```http
POST /security_recording/start
```
Manually start a new recording session (useful for testing or manual control).

### ⏹️ **Stop Recording**
```http
POST /security_recording/stop
```
Manually stop the current recording session.

### 📋 **List Recorded Videos**
```http
GET /security_recording/videos
```
Returns list of all recorded videos with metadata including:
- Filename and path
- File size in MB
- Creation timestamp
- Age in days
- Deletion status

### 🧹 **Manual Cleanup**
```http
POST /security_recording/cleanup
```
Manually trigger cleanup of old recordings (normally automatic).

## File Structure

### Directory Layout
```
security_videos/
├── security_20250815_020000.mp4  # 2:00 AM - 3:00 AM
├── security_20250815_030000.mp4  # 3:00 AM - 4:00 AM
├── security_20250815_040000.mp4  # 4:00 AM - 5:00 AM
├── ...
├── security_20250815_230000.mp4  # 11:00 PM - 12:00 AM
└── security_20250816_000000.mp4  # 12:00 AM - 1:00 AM (next day)
```

### File Naming Convention
- **Format**: `security_YYYYMMDD_HHMMSS.mp4`
- **Example**: `security_20250815_143000.mp4` = August 15, 2025, 2:30 PM
- **Duration**: Each file covers exactly 1 hour from the timestamp

## Automatic Operations

### 🔄 **Hourly Rotation**
- New recording starts every hour on the hour
- Previous recording automatically stops and saves
- Seamless transition between recording sessions

### 🗑️ **Automatic Cleanup**
- Runs every hour during frame processing
- Removes videos older than 14 days
- Maintains storage efficiency
- Logs all cleanup operations

### 📈 **Performance Integration**
- Recording status included in `/performance_stats`
- Automatic start when frame processing begins
- Quality monitoring and adjustment
- Error handling and recovery

## Quality Enhancement

### 🖼️ **Image Processing Pipeline**
1. **Raw Frame**: Received from ESP32-CAM
2. **Enhancement**: Processed through `advanced_image_enhancement.py`
3. **Quality Check**: Frame quality assessment
4. **Recording**: Enhanced frame saved to video file
5. **Streaming**: Enhanced frame sent to clients

### 🎯 **Enhancement Modes**
- **Auto**: Intelligent mode selection based on lighting
- **Day**: Optimized for daylight conditions
- **Night**: Enhanced for low-light scenarios
- **Security**: Maximum detail preservation
- **Low-Light**: Balanced enhancement for dim conditions

## Storage Management

### 💾 **Space Requirements**
- **Per Hour**: Approximately 50-100 MB (depending on content)
- **Per Day**: 1.2-2.4 GB
- **14 Days**: 17-34 GB total storage

### 🔍 **Retention Policy**
- **Active Period**: 14 days
- **Cleanup Trigger**: Automatic (hourly) + Manual endpoint
- **Deletion Criteria**: Age > 14 days
- **Backup Recommendation**: Important footage should be backed up before cleanup

## Monitoring and Maintenance

### 📊 **Status Monitoring**
- Recording status available via API
- Integration with performance statistics
- Automatic error detection and recovery
- Logging of all operations

### 🛠️ **Maintenance Tasks**
- **Daily**: Check recording status and file creation
- **Weekly**: Verify storage space and cleanup operations
- **Monthly**: Review retention policy and adjust if needed
- **As Needed**: Manual cleanup for immediate space recovery

## Troubleshooting

### ❌ **Common Issues**

#### Recording Not Starting
- Check if frame processing is active
- Verify directory permissions
- Check available disk space
- Review error logs

#### Poor Video Quality
- Verify image enhancement is working
- Check frame rate and quality settings
- Monitor system performance
- Adjust quality thresholds if needed

#### Storage Issues
- Check available disk space
- Verify cleanup operations are running
- Review retention policy
- Consider manual cleanup

### 🔧 **Debug Commands**
```bash
# Check recording status
curl http://localhost:3003/security_recording/status

# List all videos
curl http://localhost:3003/security_recording/videos

# Manual cleanup
curl -X POST http://localhost:3003/security_recording/cleanup

# Check performance stats
curl http://localhost:3003/performance_stats
```

## Best Practices

### 🎯 **Optimization**
- Monitor storage usage regularly
- Adjust retention period based on needs
- Use manual cleanup for immediate space recovery
- Consider backup strategy for important footage

### 🔒 **Security**
- Secure access to video files
- Implement proper authentication for API endpoints
- Regular security audits of recorded content
- Encrypt sensitive recordings if needed

### 📈 **Performance**
- Monitor system resources during recording
- Adjust frame rate if needed for performance
- Balance quality vs. storage requirements
- Use appropriate enhancement modes

## Integration Examples

### 🐍 **Python Client**
```python
import requests

# Get recording status
status = requests.get("http://localhost:3003/security_recording/status").json()
print(f"Recording active: {status['recording_active']}")

# List videos
videos = requests.get("http://localhost:3003/security_recording/videos").json()
for video in videos['videos']:
    print(f"{video['filename']}: {video['size_mb']}MB, {video['age_days']} days old")
```

### 🌐 **Web Dashboard**
```javascript
// Fetch recording status
fetch('/security_recording/status')
    .then(response => response.json())
    .then(data => {
        console.log('Recording:', data.recording_active);
        console.log('Current file:', data.current_status.current_file);
    });
```

## Future Enhancements

### 🚀 **Planned Features**
- **Motion Detection**: Only record when motion detected
- **Cloud Storage**: Automatic upload to cloud services
- **Compression Options**: Multiple quality/compression levels
- **Event Tagging**: Mark important events in recordings
- **Analytics**: Usage statistics and performance metrics

### 🔮 **Advanced Capabilities**
- **AI Analysis**: Automatic threat detection
- **Smart Compression**: Adaptive quality based on content
- **Multi-Camera**: Support for multiple ESP32-CAM devices
- **Live Streaming**: Real-time video streaming capabilities

---

## Support

For technical support or feature requests, please refer to the main system documentation or contact the development team.

**Version**: 1.0.0  
**Last Updated**: August 2025  
**Compatibility**: ESP32-CAM + FastAPI Server v4.0+ 