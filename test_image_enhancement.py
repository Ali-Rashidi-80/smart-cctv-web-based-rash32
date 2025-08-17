"""
Test script for Advanced Image Enhancement functionality
Tests the image enhancement features optimized for server environments
"""

import requests
import json
import time
import cv2
import numpy as np
from advanced_image_enhancement import image_enhancer, EnhancementMode, get_enhancement_recommendations

def test_server_health():
    """Test server health and basic functionality"""
    print("🔍 Testing server health...")
    
    try:
        response = requests.get("http://localhost:3003/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server is healthy")
            print(f"   - FPS: {data.get('fps', 'N/A')}")
            print(f"   - Buffer utilization: {data.get('buffer_utilization', 'N/A')}%")
            print(f"   - System state: {data.get('system_state', 'N/A')}")
            return True
        else:
            print(f"❌ Server health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Server health check error: {e}")
        return False

def test_image_enhancement_status():
    """Test image enhancement status endpoint"""
    print("\n🔍 Testing image enhancement status...")
    
    try:
        response = requests.get("http://localhost:3003/image_enhancement", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Image enhancement status retrieved")
            print(f"   - Current mode: {data.get('current_mode', 'N/A')}")
            print(f"   - Enhancement time: {data.get('enhancement_time_ms', 'N/A')}ms")
            print(f"   - Quality improvement: {data.get('quality_improvement', 'N/A')}")
            print(f"   - Total frames enhanced: {data.get('total_frames_enhanced', 'N/A')}")
            print(f"   - Available modes: {data.get('available_modes', [])}")
            return True
        else:
            print(f"❌ Image enhancement status failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Image enhancement status error: {e}")
        return False

def test_enhancement_mode_switching():
    """Test switching between different enhancement modes"""
    print("\n🔍 Testing enhancement mode switching...")
    
    modes_to_test = ['auto', 'day', 'night', 'low_light', 'security']
    
    for mode in modes_to_test:
        try:
            print(f"   Testing mode: {mode}")
            response = requests.post(
                "http://localhost:3003/image_enhancement/mode",
                json={"mode": mode},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Mode '{mode}' set successfully")
            else:
                print(f"   ❌ Failed to set mode '{mode}': {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error setting mode '{mode}': {e}")

def test_enhancement_settings_update():
    """Test updating enhancement settings"""
    print("\n🔍 Testing enhancement settings update...")
    
    # Test different setting configurations
    test_settings = [
        {
            "sharpening_strength": 0.8,
            "contrast_enhancement": 0.4,
            "brightness_boost": 0.3
        },
        {
            "night_vision_threshold": 70,
            "night_brightness_boost": 0.5,
            "edge_enhancement": 0.6
        },
        {
            "processing_quality": "high_quality",
            "max_processing_time": 0.08,
            "detail_preservation": 0.8
        }
    ]
    
    for i, settings in enumerate(test_settings, 1):
        try:
            print(f"   Testing settings configuration {i}...")
            response = requests.post(
                "http://localhost:3003/image_enhancement",
                json=settings,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Settings configuration {i} updated successfully")
            else:
                print(f"   ❌ Failed to update settings {i}: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error updating settings {i}: {e}")

def test_performance_stats():
    """Test performance statistics including enhancement metrics"""
    print("\n🔍 Testing performance statistics...")
    
    try:
        response = requests.get("http://localhost:3003/performance_stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Performance stats retrieved")
            print(f"   - FPS: {data.get('fps', 'N/A')}")
            print(f"   - Quality level: {data.get('quality_level', 'N/A')}")
            print(f"   - Enhancement mode: {data.get('enhancement_mode', 'N/A')}")
            print(f"   - Enhancement time: {data.get('enhancement_time_ms', 'N/A')}ms")
            print(f"   - Quality improvement: {data.get('quality_improvement', 'N/A')}")
            print(f"   - Buffer utilization: {data.get('buffer_utilization', 'N/A')}%")
            return True
        else:
            print(f"❌ Performance stats failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Performance stats error: {e}")
        return False

def test_local_enhancement():
    """Test local image enhancement functionality"""
    print("\n🔍 Testing local image enhancement...")
    
    try:
        # Create a test image (simulate ESP32-CAM frame)
        test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        # Test different enhancement modes
        modes = [EnhancementMode.AUTO, EnhancementMode.DAY, EnhancementMode.NIGHT, EnhancementMode.SECURITY]
        
        for mode in modes:
            print(f"   Testing {mode.value} mode...")
            start_time = time.time()
            
            enhanced_frame, stats = image_enhancer.enhance_frame_quality(test_image, mode)
            
            processing_time = (time.time() - start_time) * 1000
            
            print(f"   ✅ {mode.value} mode processed in {processing_time:.2f}ms")
            print(f"      - Quality improvement: {stats.get('quality_improvement', 0):.3f}")
            print(f"      - Processing time: {stats.get('processing_time', 0)*1000:.2f}ms")
        
        return True
    except Exception as e:
        print(f"❌ Local enhancement test error: {e}")
        return False

def test_enhancement_recommendations():
    """Test enhancement recommendations"""
    print("\n🔍 Testing enhancement recommendations...")
    
    try:
        recommendations = get_enhancement_recommendations()
        print("✅ Enhancement recommendations:")
        
        for category, settings in recommendations.items():
            print(f"   {category}:")
            for key, value in settings.items():
                print(f"     - {key}: {value}")
        
        return True
    except Exception as e:
        print(f"❌ Enhancement recommendations error: {e}")
        return False

def test_enhancement_stats():
    """Test enhancement statistics"""
    print("\n🔍 Testing enhancement statistics...")
    
    try:
        stats = image_enhancer.get_enhancement_stats()
        print("✅ Enhancement statistics:")
        print(f"   - Total frames processed: {stats['total_frames_processed']}")
        print(f"   - Average processing time: {stats['avg_processing_time_ms']:.2f}ms")
        print(f"   - Mode switches: {stats['mode_switches']}")
        print(f"   - Current mode: {stats['current_mode']}")
        print(f"   - Average quality improvement: {stats['avg_quality_improvement']:.3f}")
        
        return True
    except Exception as e:
        print(f"❌ Enhancement statistics error: {e}")
        return False

def run_comprehensive_test():
    """Run comprehensive image enhancement test suite"""
    print("🚀 Starting Comprehensive Image Enhancement Test Suite")
    print("=" * 60)
    
    tests = [
        ("Server Health", test_server_health),
        ("Image Enhancement Status", test_image_enhancement_status),
        ("Enhancement Mode Switching", test_enhancement_mode_switching),
        ("Enhancement Settings Update", test_enhancement_settings_update),
        ("Performance Statistics", test_performance_stats),
        ("Local Enhancement", test_local_enhancement),
        ("Enhancement Recommendations", test_enhancement_recommendations),
        ("Enhancement Statistics", test_enhancement_stats)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Image enhancement is working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the server and enhancement configuration.")
    
    return passed == total

if __name__ == "__main__":
    success = run_comprehensive_test()
    exit(0 if success else 1) 