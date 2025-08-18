#!/usr/bin/env python3
"""
Test script for checking stream connection stability and buffer behavior
"""

import requests
import time
import threading
import cv2
import numpy as np
from io import BytesIO

def test_flask_stream():
    """Test Flask server stream connection"""
    print("🔍 Testing Flask server stream...")
    
    try:
        # Test health endpoint first
        health_response = requests.get("http://localhost:3002/health", timeout=5)
        if health_response.status_code == 200:
            print("✅ Flask server is running")
        else:
            print("❌ Flask server health check failed")
            return
    except Exception as e:
        print(f"❌ Flask server not accessible: {e}")
        return
    
    # Test video stream
    try:
        print("📹 Testing Flask video stream...")
        response = requests.get("http://localhost:3002/esp32_video_feed", stream=True, timeout=30)
        
        if response.status_code == 200:
            print("✅ Flask video stream connected successfully")
            
            frame_count = 0
            start_time = time.time()
            last_frame_time = start_time
            
            for chunk in response.iter_content(chunk_size=1024):
                if b'--frame' in chunk:
                    frame_count += 1
                    current_time = time.time()
                    
                    if frame_count % 30 == 0:  # Log every 30 frames
                        elapsed = current_time - start_time
                        fps = frame_count / elapsed if elapsed > 0 else 0
                        print(f"📊 Flask: Frame {frame_count}, FPS: {fps:.2f}, Time: {current_time - last_frame_time:.3f}s")
                        last_frame_time = current_time
                    
                    # Test for 10 seconds
                    if current_time - start_time > 10:
                        print(f"✅ Flask stream test completed: {frame_count} frames in 10 seconds")
                        break
        else:
            print(f"❌ Flask video stream failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Flask stream test error: {e}")

def test_fastapi_stream():
    """Test FastAPI server stream connection"""
    print("\n🔍 Testing FastAPI server stream...")
    
    try:
        # Test health endpoint first
        health_response = requests.get("http://localhost:3003/health", timeout=5)
        if health_response.status_code == 200:
            print("✅ FastAPI server is running")
        else:
            print("❌ FastAPI server health check failed")
            return
    except Exception as e:
        print(f"❌ FastAPI server not accessible: {e}")
        return
    
    # Test video stream
    try:
        print("📹 Testing FastAPI video stream...")
        response = requests.get("http://localhost:3003/esp32_video_feed", stream=True, timeout=30)
        
        if response.status_code == 200:
            print("✅ FastAPI video stream connected successfully")
            
            frame_count = 0
            start_time = time.time()
            last_frame_time = start_time
            
            for chunk in response.iter_content(chunk_size=1024):
                if b'--frame' in chunk:
                    frame_count += 1
                    current_time = time.time()
                    
                    if frame_count % 30 == 0:  # Log every 30 frames
                        elapsed = current_time - start_time
                        fps = frame_count / elapsed if elapsed > 0 else 0
                        print(f"📊 FastAPI: Frame {frame_count}, FPS: {fps:.2f}, Time: {current_time - last_frame_time:.3f}s")
                        last_frame_time = current_time
                    
                    # Test for 10 seconds
                    if current_time - start_time > 10:
                        print(f"✅ FastAPI stream test completed: {frame_count} frames in 10 seconds")
                        break
        else:
            print(f"❌ FastAPI video stream failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ FastAPI stream test error: {e}")

def test_buffer_behavior():
    """Test buffer behavior when no frames are available"""
    print("\n🔍 Testing buffer behavior...")
    
    servers = [
        ("Flask", "http://localhost:3002"),
        ("FastAPI", "http://localhost:3003")
    ]
    
    for server_name, server_url in servers:
        print(f"\n📊 Testing {server_name} buffer behavior...")
        
        try:
            # Get performance stats
            stats_response = requests.get(f"{server_url}/performance_stats", timeout=5)
            if stats_response.status_code == 200:
                stats = stats_response.json()
                print(f"📈 {server_name} Stats:")
                print(f"   Buffer Size: {stats.get('buffer_size', 0)}")
                print(f"   Buffer Utilization: {stats.get('buffer_utilization', 0):.1f}%")
                print(f"   FPS: {stats.get('fps', 0):.2f}")
                print(f"   Compensation Factor: {stats.get('compensation_factor', 1.0):.3f}")
            else:
                print(f"❌ {server_name} stats not available")
                
        except Exception as e:
            print(f"❌ {server_name} stats error: {e}")

def test_empty_buffer_stream():
    """Test stream behavior when buffer is empty"""
    print("\n🔍 Testing empty buffer stream behavior...")
    
    servers = [
        ("Flask", "http://localhost:3002/esp32_video_feed"),
        ("FastAPI", "http://localhost:3003/esp32_video_feed")
    ]
    
    for server_name, stream_url in servers:
        print(f"\n📹 Testing {server_name} empty buffer behavior...")
        
        try:
            response = requests.get(stream_url, stream=True, timeout=15)
            
            if response.status_code == 200:
                print(f"✅ {server_name} stream connected (empty buffer test)")
                
                frame_count = 0
                start_time = time.time()
                empty_frames = 0
                
                for chunk in response.iter_content(chunk_size=1024):
                    if b'--frame' in chunk:
                        frame_count += 1
                        current_time = time.time()
                        
                        # Check if frame is empty (just boundary)
                        if len(chunk.strip()) < 100:  # Very small frame
                            empty_frames += 1
                        
                        if frame_count % 10 == 0:
                            elapsed = current_time - start_time
                            print(f"📊 {server_name}: Frame {frame_count}, Empty: {empty_frames}, Time: {elapsed:.1f}s")
                        
                        # Test for 5 seconds
                        if current_time - start_time > 5:
                            print(f"✅ {server_name} empty buffer test completed: {frame_count} frames, {empty_frames} empty")
                            break
            else:
                print(f"❌ {server_name} stream failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ {server_name} empty buffer test error: {e}")

def main():
    """Main test function"""
    print("🚀 Starting Stream Connection Tests")
    print("=" * 50)
    
    # Test basic stream functionality
    test_flask_stream()
    test_fastapi_stream()
    
    # Test buffer behavior
    test_buffer_behavior()
    
    # Test empty buffer behavior
    test_empty_buffer_stream()
    
    print("\n" + "=" * 50)
    print("✅ All tests completed!")

if __name__ == "__main__":
    main() 