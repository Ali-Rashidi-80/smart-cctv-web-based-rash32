# Professional Security Video Recording System Guide

## Overview

The Professional Security Video Recording System provides enterprise-grade video monitoring with 60 FPS recording, intelligent frame validation, automatic segmentation, and organized folder management. This system is designed specifically for security camera applications using ESP32-CAM with advanced image enhancement and professional video quality standards.

## 🎯 **Key Features**

### **High-Quality Recording**
- **60 FPS Recording**: Professional-grade 60 frames per second for smooth security footage
- **Frame Validation**: Intelligent validation to prevent empty or corrupted frames
- **Quality Control**: Minimum quality thresholds to ensure usable footage
- **Professional Encoding**: MP4 format with optimized compression

### **Intelligent Segmentation**
- **Automatic Segmentation**: Videos are automatically split into manageable segments
- **Frame Accumulation**: Waits for sufficient frames before creating video files
- **Smart Merging**: Automatically merges segments into complete hour videos
- **Interruption Handling**: Gracefully handles recording interruptions

### **Organized Folder Structure**
- **Hierarchical Organization**: Year/Month/Day/Type structure
- **Type-Based Sorting**: Complete hours, partial segments, and merged videos
- **Automatic Cleanup**: 14-day retention with intelligent cleanup
- **Easy Navigation**: Clear folder structure for quick access

## 🏗️ **System Architecture**

### **Core Components**

#### **ProfessionalVideoSegment**
- Manages individual video segments
- Validates frame quality and format
- Tracks frame count and duration
- Ensures proper video encoding

#### **ProfessionalVideoRecorder**
- Orchestrates the entire recording process
- Manages segment creation and merging
- Handles folder organization
- Controls quality standards

### **Recording Flow**
```
ESP32-CAM → Frame Processing → Frame Validation → Segment Creation → Video Encoding → File Management
     ↓              ↓              ↓              ↓              ↓              ↓
  Raw Frame   Enhancement   Quality Check   Frame Buffer   MP4 Creation   Organized Storage
```

## 📁 **Folder Structure**

### **Directory Layout**
```
security_videos/
├── 2025_08/                    # Year_Month
│   ├── 20250815/              # Date
│   │   ├── complete_hours/    # Full 1-hour videos
│   │   │   ├── complete_hour_20250815_140000.mp4
│   │   │   └── complete_hour_20250815_150000.mp4
│   │   ├── partial_segments/  # Incomplete segments
│   │   │   ├── partial_140000_00.mp4
│   │   │   └── partial_140000_01.mp4
│   │   └── merged_videos/     # Merged partial segments
│   │       └── merged_20250815_140000.mp4
│   └── 20250816/
└── 2025_09/
```

### **File Naming Convention**
- **Complete Hours**: `complete_hour_YYYYMMDD_HHMMSS.mp4`
- **Partial Segments**: `partial_HHMMSS_SS.mp4` (SS = segment number)
- **Merged Videos**: `merged_YYYYMMDD_HHMMSS.mp4`

## ⚙️ **Configuration**

### **Recording Settings**
```python
FRAME_RATE_RECORDING = 60        # 60 FPS for smooth footage
MIN_FRAMES_PER_SECOND = 30       # Minimum frames to consider valid
RECORDING_DURATION_HOURS = 1     # Target duration per file
RETENTION_DAYS = 14              # Automatic cleanup period
MAX_VIDEO_SEGMENTS = 10          # Maximum segments before forcing new hour
```

### **Quality Thresholds**
- **Frame Validation**: Checks dimensions, brightness, and variance
- **Minimum Quality**: 30% quality score for frame acceptance
- **Video Quality**: 95% encoding quality for maximum detail
- **Resolution**: 640x480 with Lanczos interpolation

## 🔧 **API Endpoints**

### **📊 Recording Status**
```http
GET /security_recording/status
```
Returns comprehensive recording status including:
- Active status and current hour
- Directory information
- Segment count and frame statistics
- Quality metrics

### **🎬 Video Segments**
```http
GET /security_recording/segments
```
Returns detailed information about current video segments:
- Segment numbers and timestamps
- Frame counts and durations
- Ready status and completion state
- File paths and metadata

### **📁 Directory Structure**
```http
GET /security_recording/directory_structure
```
Returns organized folder structure:
- Current year/month/date directories
- Subdirectory contents and file counts
- File listings and organization

### **🔗 Merge Segments**
```http
POST /security_recording/merge_segments
```
Manually triggers segment merging:
- Saves current segments
- Merges partial segments into complete hours
- Updates file organization

### **⏰ Force New Hour**
```http
POST /security_recording/force_new_hour
```
Forces start of new hour recording:
- Saves current segments
- Creates new hour directory
- Resets segment counter

### **📈 Quality Metrics**
```http
GET /security_recording/quality_metrics
```
Returns recording quality statistics:
- Target vs. actual FPS
- Frame efficiency metrics
- Quality control settings
- Performance indicators

## 🎥 **Video Processing Pipeline**

### **Frame Processing Steps**

#### **1. Frame Reception**
- Receive frame from ESP32-CAM
- Apply image enhancement
- Validate frame quality

#### **2. Frame Validation**
```python
def _validate_frame(self, frame: np.ndarray) -> bool:
    # Check frame dimensions (640x480x3)
    # Verify brightness levels (5-250 range)
    # Calculate frame variance (minimum 10)
    # Ensure proper color format (BGR)
```

#### **3. Segment Management**
- Add validated frames to current segment
- Monitor frame count and duration
- Create new segments when needed
- Maintain segment organization

#### **4. Video Encoding**
- Use OpenCV VideoWriter with MP4 codec
- Apply professional encoding settings
- Ensure consistent frame dimensions
- Optimize for security footage quality

#### **5. File Organization**
- Save segments to appropriate directories
- Merge partial segments into complete hours
- Maintain folder structure
- Handle cleanup and retention

## 📊 **Quality Control**

### **Frame Validation Criteria**

#### **Dimension Requirements**
- **Width**: Minimum 100 pixels
- **Height**: Minimum 100 pixels
- **Channels**: Exactly 3 (BGR color)
- **Data Type**: uint8

#### **Content Validation**
- **Brightness**: Mean value between 5-250
- **Variance**: Minimum variance of 10
- **Format**: Proper numpy array structure
- **Size**: Non-empty array

#### **Quality Scoring**
```python
def calculate_frame_quality(frame: np.ndarray) -> float:
    # Sharpness (Laplacian variance)
    # Brightness (mean intensity)
    # Contrast (standard deviation)
    # Edge density (Canny detection)
    # Weighted combination for final score
```

### **Video Quality Standards**
- **Encoding Quality**: 95% JPEG quality
- **Frame Rate**: Consistent 60 FPS
- **Resolution**: 640x480 with interpolation
- **Codec**: MP4 with H.264 compatibility

## 🔄 **Automatic Operations**

### **Hourly Rotation**
- **New Hour Detection**: Automatic at 3600 seconds
- **Segment Management**: Maximum 10 segments per hour
- **Directory Creation**: Automatic folder structure
- **File Organization**: Type-based sorting

### **Segment Merging**
- **Automatic Merging**: When segments reach 58+ minutes
- **Quality Preservation**: Maintains original frame quality
- **File Cleanup**: Removes individual segments after merge
- **Metadata Tracking**: Preserves timing information

### **Cleanup Operations**
- **Retention Policy**: 14-day automatic cleanup
- **Storage Management**: Removes old recordings
- **Directory Cleanup**: Removes empty folders
- **Logging**: Tracks all cleanup operations

## 🛠️ **Maintenance and Monitoring**

### **Daily Tasks**
- **Status Check**: Verify recording is active
- **File Creation**: Monitor new video files
- **Quality Check**: Review frame validation logs
- **Storage Check**: Monitor disk space usage

### **Weekly Tasks**
- **Segment Review**: Check segment organization
- **Merge Verification**: Ensure segments are properly merged
- **Performance Review**: Analyze FPS and quality metrics
- **Cleanup Verification**: Confirm automatic cleanup is working

### **Monthly Tasks**
- **Retention Review**: Adjust retention policy if needed
- **Storage Analysis**: Review storage usage patterns
- **Performance Optimization**: Adjust quality settings
- **System Health**: Comprehensive system review

## 🚨 **Troubleshooting**

### **Common Issues**

#### **Videos Won't Open**
- **Cause**: Empty frames or corrupted segments
- **Solution**: Check frame validation logs
- **Prevention**: Enable frame validation

#### **Low Frame Rate**
- **Cause**: Insufficient frames from ESP32-CAM
- **Solution**: Check camera connection and settings
- **Prevention**: Monitor FPS metrics

#### **Storage Issues**
- **Cause**: Large file sizes or retention issues
- **Solution**: Check cleanup operations
- **Prevention**: Monitor storage usage

#### **Segment Problems**
- **Cause**: Interrupted recordings
- **Solution**: Use merge segments endpoint
- **Prevention**: Monitor segment health

### **Debug Commands**
```bash
# Check recording status
curl http://localhost:3003/security_recording/status

# View video segments
curl http://localhost:3003/security_recording/segments

# Check directory structure
curl http://localhost:3003/security_recording/directory_structure

# Force segment merging
curl -X POST http://localhost:3003/security_recording/merge_segments

# Check quality metrics
curl http://localhost:3003/security_recording/quality_metrics
```

## 📈 **Performance Optimization**

### **Frame Rate Optimization**
- **Target FPS**: 60 FPS for smooth footage
- **Minimum FPS**: 30 FPS for acceptable quality
- **Buffer Management**: Intelligent frame buffering
- **Quality Adjustment**: Dynamic quality based on performance

### **Storage Optimization**
- **Compression**: Efficient MP4 encoding
- **Segmentation**: Smart file splitting
- **Cleanup**: Automatic retention management
- **Organization**: Logical folder structure

### **Quality Optimization**
- **Frame Validation**: Prevent corrupted frames
- **Enhancement**: Apply image enhancement
- **Encoding**: Professional video settings
- **Monitoring**: Real-time quality metrics

## 🔮 **Future Enhancements**

### **Planned Features**
- **Motion Detection**: Only record when motion detected
- **Cloud Storage**: Automatic cloud backup
- **AI Analysis**: Automatic threat detection
- **Multi-Camera**: Support for multiple devices

### **Advanced Capabilities**
- **Smart Compression**: Adaptive quality based on content
- **Event Tagging**: Mark important events
- **Analytics**: Advanced usage statistics
- **Integration**: Third-party system support

---

## Support

For technical support or feature requests, please refer to the main system documentation or contact the development team.

**Version**: 2.0.0  
**Last Updated**: August 2025  
**Compatibility**: ESP32-CAM + FastAPI Server v4.0+  
**Recording Quality**: 60 FPS Professional Grade 