"""
Advanced Image Enhancement for Server Environments
Optimized for CPU-only processing with intelligent quality improvement,
lighting enhancement, and night vision capabilities for ESP32-CAM security applications.
"""

import cv2
import numpy as np
import time
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class EnhancementMode(Enum):
    AUTO = "auto"
    DAY = "day"
    NIGHT = "night"
    LOW_LIGHT = "low_light"
    SECURITY = "security"

@dataclass
class EnhancementSettings:
    """Advanced enhancement settings optimized for server environments"""
    # Quality enhancement
    sharpening_strength: float = 0.6  # Moderate sharpening for CPU efficiency
    denoise_strength: float = 0.4     # Light denoising to preserve detail
    contrast_enhancement: float = 0.3  # Subtle contrast boost
    
    # Lighting enhancement
    brightness_boost: float = 0.2      # Moderate brightness increase
    gamma_correction: float = 1.1      # Slight gamma adjustment
    histogram_equalization: bool = True # Enable for better dynamic range
    
    # Night vision optimization
    night_vision_threshold: int = 80   # Brightness threshold for night mode
    night_brightness_boost: float = 0.4 # Higher boost for night
    night_contrast_boost: float = 0.5   # Higher contrast for night
    noise_reduction_night: float = 0.6  # More aggressive denoising at night
    
    # Security camera optimizations
    edge_enhancement: float = 0.4      # Enhance edges for security
    detail_preservation: float = 0.7   # Preserve fine details
    motion_optimization: bool = True    # Optimize for motion detection
    
    # CPU optimization
    processing_quality: str = "balanced"  # balanced, fast, high_quality
    max_processing_time: float = 0.05   # Max 50ms per frame
    adaptive_processing: bool = True     # Adjust processing based on load

class AdvancedImageEnhancer:
    """Advanced image enhancement optimized for server environments"""
    
    def __init__(self):
        self.settings = EnhancementSettings()
        self.current_mode = EnhancementMode.AUTO
        self.processing_stats = {
            'total_frames': 0,
            'avg_processing_time': 0.0,
            'mode_switches': 0,
            'quality_scores': []
        }
        
        # Initialize enhancement kernels
        self._init_kernels()
        
    def _init_kernels(self):
        """Initialize optimized processing kernels"""
        # Sharpening kernel optimized for CPU
        self.sharpen_kernel = np.array([
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0]
        ], dtype=np.float32) * 0.25  # Normalized for efficiency
        
        # Edge enhancement kernel
        self.edge_kernel = np.array([
            [-1, -1, -1],
            [-1,  8, -1],
            [-1, -1, -1]
        ], dtype=np.float32) * 0.1
        
        # Noise reduction kernel
        self.denoise_kernel = np.array([
            [1, 1, 1],
            [1, 2, 1],
            [1, 1, 1]
        ], dtype=np.float32) / 10.0
        
    def detect_lighting_conditions(self, frame: np.ndarray) -> EnhancementMode:
        """Intelligently detect lighting conditions for optimal enhancement"""
        try:
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Calculate average brightness
            avg_brightness = np.mean(gray)
            
            # Calculate brightness variance (indicates lighting uniformity)
            brightness_variance = np.var(gray)
            
            # Calculate histogram analysis
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            dark_pixels = np.sum(hist[:50])  # Very dark pixels
            bright_pixels = np.sum(hist[200:])  # Very bright pixels
            
            # Determine lighting mode
            if avg_brightness < self.settings.night_vision_threshold:
                if dark_pixels > bright_pixels * 2:
                    return EnhancementMode.NIGHT
                else:
                    return EnhancementMode.LOW_LIGHT
            elif avg_brightness > 150:
                return EnhancementMode.DAY
            else:
                return EnhancementMode.SECURITY
                
        except Exception as e:
            logger.warning(f"Error detecting lighting conditions: {e}")
            return EnhancementMode.AUTO
    
    def enhance_frame_quality(self, frame: np.ndarray, mode: EnhancementMode = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Enhance frame quality with intelligent processing optimized for server environments"""
        start_time = time.time()
        
        try:
            # Auto-detect mode if not specified
            if mode is None:
                mode = self.detect_lighting_conditions(frame)
            
            # Update mode if changed
            if mode != self.current_mode:
                self.current_mode = mode
                self.processing_stats['mode_switches'] += 1
            
            # Apply mode-specific enhancements
            if mode == EnhancementMode.NIGHT:
                enhanced_frame = self._enhance_night_vision(frame)
            elif mode == EnhancementMode.LOW_LIGHT:
                enhanced_frame = self._enhance_low_light(frame)
            elif mode == EnhancementMode.DAY:
                enhanced_frame = self._enhance_day_light(frame)
            elif mode == EnhancementMode.SECURITY:
                enhanced_frame = self._enhance_security(frame)
            else:  # AUTO mode
                enhanced_frame = self._enhance_auto(frame)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Update statistics
            self.processing_stats['total_frames'] += 1
            self.processing_stats['avg_processing_time'] = (
                (self.processing_stats['avg_processing_time'] * (self.processing_stats['total_frames'] - 1) + processing_time) 
                / self.processing_stats['total_frames']
            )
            
            # Calculate quality improvement score
            quality_score = self._calculate_quality_improvement(frame, enhanced_frame)
            self.processing_stats['quality_scores'].append(quality_score)
            if len(self.processing_stats['quality_scores']) > 100:
                self.processing_stats['quality_scores'].pop(0)
            
            return enhanced_frame, {
                'mode': mode.value,
                'processing_time': processing_time,
                'quality_improvement': quality_score,
                'avg_processing_time': self.processing_stats['avg_processing_time']
            }
            
        except Exception as e:
            logger.error(f"Error enhancing frame: {e}")
            return frame, {'error': str(e)}
    
    def _enhance_night_vision(self, frame: np.ndarray) -> np.ndarray:
        """Advanced night vision enhancement optimized for security cameras"""
        try:
            # Convert to LAB color space for better luminance processing
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l_channel = lab[:, :, 0]
            
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced_l = clahe.apply(l_channel)
            
            # Brightness boost for night vision
            enhanced_l = cv2.add(enhanced_l, int(255 * self.settings.night_brightness_boost))
            
            # Apply gamma correction for better visibility
            gamma = 0.8  # Darker gamma for night vision
            enhanced_l = np.power(enhanced_l / 255.0, gamma) * 255
            enhanced_l = np.clip(enhanced_l, 0, 255).astype(np.uint8)
            
            # Noise reduction optimized for night vision
            enhanced_l = cv2.bilateralFilter(enhanced_l, 9, 75, 75)
            
            # Sharpening for detail preservation
            enhanced_l = cv2.filter2D(enhanced_l, -1, self.sharpen_kernel)
            
            # Update LAB channel
            lab[:, :, 0] = enhanced_l
            
            # Convert back to BGR
            enhanced_frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
            # Final contrast boost
            enhanced_frame = cv2.convertScaleAbs(enhanced_frame, alpha=1.0 + self.settings.night_contrast_boost, beta=0)
            
            return enhanced_frame
            
        except Exception as e:
            logger.error(f"Error in night vision enhancement: {e}")
            return frame
    
    def _enhance_low_light(self, frame: np.ndarray) -> np.ndarray:
        """Low light enhancement with balanced quality and performance"""
        try:
            # Apply CLAHE for better dynamic range
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l_channel = lab[:, :, 0]
            
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced_l = clahe.apply(l_channel)
            
            # Moderate brightness boost
            enhanced_l = cv2.add(enhanced_l, int(255 * self.settings.brightness_boost))
            
            # Gentle noise reduction
            enhanced_l = cv2.bilateralFilter(enhanced_l, 5, 50, 50)
            
            # Subtle sharpening
            enhanced_l = cv2.filter2D(enhanced_l, -1, self.sharpen_kernel)
            
            lab[:, :, 0] = enhanced_l
            enhanced_frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
            return enhanced_frame
            
        except Exception as e:
            logger.error(f"Error in low light enhancement: {e}")
            return frame
    
    def _enhance_day_light(self, frame: np.ndarray) -> np.ndarray:
        """Day light enhancement focusing on detail preservation and security"""
        try:
            # Apply histogram equalization for better contrast
            if self.settings.histogram_equalization:
                yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
                yuv[:, :, 0] = cv2.equalizeHist(yuv[:, :, 0])
                enhanced_frame = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
            else:
                enhanced_frame = frame.copy()
            
            # Edge enhancement for security applications
            if self.settings.edge_enhancement > 0:
                edge_enhanced = cv2.filter2D(enhanced_frame, -1, self.edge_kernel)
                enhanced_frame = cv2.addWeighted(enhanced_frame, 1.0, edge_enhanced, self.settings.edge_enhancement, 0)
            
            # Detail preservation sharpening
            if self.settings.detail_preservation > 0:
                sharpened = cv2.filter2D(enhanced_frame, -1, self.sharpen_kernel)
                enhanced_frame = cv2.addWeighted(enhanced_frame, 1.0, sharpened, self.settings.detail_preservation, 0)
            
            # Subtle contrast enhancement
            if self.settings.contrast_enhancement > 0:
                enhanced_frame = cv2.convertScaleAbs(enhanced_frame, alpha=1.0 + self.settings.contrast_enhancement, beta=0)
            
            return enhanced_frame
            
        except Exception as e:
            logger.error(f"Error in day light enhancement: {e}")
            return frame
    
    def _enhance_security(self, frame: np.ndarray) -> np.ndarray:
        """Security-focused enhancement optimized for surveillance"""
        try:
            # Apply CLAHE for better dynamic range
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l_channel = lab[:, :, 0]
            
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            enhanced_l = clahe.apply(l_channel)
            
            # Edge enhancement for motion detection
            edge_enhanced = cv2.filter2D(enhanced_l, -1, self.edge_kernel)
            enhanced_l = cv2.addWeighted(enhanced_l, 0.8, edge_enhanced, 0.2, 0)
            
            # Sharpening for detail preservation
            enhanced_l = cv2.filter2D(enhanced_l, -1, self.sharpen_kernel)
            
            # Noise reduction
            enhanced_l = cv2.bilateralFilter(enhanced_l, 7, 60, 60)
            
            lab[:, :, 0] = enhanced_l
            enhanced_frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
            # Contrast enhancement for better visibility
            enhanced_frame = cv2.convertScaleAbs(enhanced_frame, alpha=1.1, beta=5)
            
            return enhanced_frame
            
        except Exception as e:
            logger.error(f"Error in security enhancement: {e}")
            return frame
    
    def _enhance_auto(self, frame: np.ndarray) -> np.ndarray:
        """Automatic enhancement based on detected conditions"""
        try:
            # Detect lighting conditions
            mode = self.detect_lighting_conditions(frame)
            
            # Apply appropriate enhancement
            if mode == EnhancementMode.NIGHT:
                return self._enhance_night_vision(frame)
            elif mode == EnhancementMode.LOW_LIGHT:
                return self._enhance_low_light(frame)
            elif mode == EnhancementMode.DAY:
                return self._enhance_day_light(frame)
            else:
                return self._enhance_security(frame)
                
        except Exception as e:
            logger.error(f"Error in auto enhancement: {e}")
            return frame
    
    def _calculate_quality_improvement(self, original: np.ndarray, enhanced: np.ndarray) -> float:
        """Calculate quality improvement score"""
        try:
            # Convert to grayscale
            orig_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
            enh_gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
            
            # Calculate sharpness improvement (Laplacian variance)
            orig_sharpness = cv2.Laplacian(orig_gray, cv2.CV_64F).var()
            enh_sharpness = cv2.Laplacian(enh_gray, cv2.CV_64F).var()
            
            # Calculate contrast improvement
            orig_contrast = np.std(orig_gray)
            enh_contrast = np.std(enh_gray)
            
            # Calculate brightness improvement
            orig_brightness = np.mean(orig_gray)
            enh_brightness = np.mean(enh_gray)
            
            # Normalized improvement scores
            sharpness_improvement = (enh_sharpness - orig_sharpness) / max(orig_sharpness, 1)
            contrast_improvement = (enh_contrast - orig_contrast) / max(orig_contrast, 1)
            brightness_improvement = (enh_brightness - orig_brightness) / max(orig_brightness, 1)
            
            # Weighted quality score
            quality_score = (
                sharpness_improvement * 0.4 +
                contrast_improvement * 0.3 +
                brightness_improvement * 0.3
            )
            
            return max(0, min(1, quality_score))  # Normalize to 0-1
            
        except Exception as e:
            logger.error(f"Error calculating quality improvement: {e}")
            return 0.0
    
    def get_enhancement_stats(self) -> Dict[str, Any]:
        """Get enhancement processing statistics"""
        return {
            'total_frames_processed': self.processing_stats['total_frames'],
            'avg_processing_time_ms': self.processing_stats['avg_processing_time'] * 1000,
            'mode_switches': self.processing_stats['mode_switches'],
            'current_mode': self.current_mode.value,
            'avg_quality_improvement': np.mean(self.processing_stats['quality_scores']) if self.processing_stats['quality_scores'] else 0.0,
            'settings': {
                'sharpening_strength': self.settings.sharpening_strength,
                'denoise_strength': self.settings.denoise_strength,
                'contrast_enhancement': self.settings.contrast_enhancement,
                'brightness_boost': self.settings.brightness_boost,
                'night_vision_threshold': self.settings.night_vision_threshold
            }
        }
    
    def update_settings(self, new_settings: Dict[str, Any]):
        """Update enhancement settings"""
        for key, value in new_settings.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
                logger.info(f"Updated enhancement setting: {key} = {value}")

# Global enhancer instance
image_enhancer = AdvancedImageEnhancer()

def enhance_frame_for_server(frame: np.ndarray, mode: EnhancementMode = None) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Convenience function for frame enhancement in server environments"""
    return image_enhancer.enhance_frame_quality(frame, mode)

def get_enhancement_recommendations() -> Dict[str, Any]:
    """Get enhancement recommendations for different scenarios"""
    return {
        'server_optimization': {
            'processing_quality': 'balanced',
            'max_processing_time': 0.05,
            'adaptive_processing': True
        },
        'security_camera': {
            'edge_enhancement': 0.4,
            'detail_preservation': 0.7,
            'motion_optimization': True
        },
        'night_vision': {
            'night_vision_threshold': 80,
            'night_brightness_boost': 0.4,
            'night_contrast_boost': 0.5,
            'noise_reduction_night': 0.6
        },
        'quality_optimization': {
            'sharpening_strength': 0.6,
            'contrast_enhancement': 0.3,
            'histogram_equalization': True
        }
    } 