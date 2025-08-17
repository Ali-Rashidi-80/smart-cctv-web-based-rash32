#!/usr/bin/env python3
"""
Simple Video Streaming Test
Tests basic video streaming functionality
"""

import requests
import os
import sys

def test_video_streaming():
    """Test video streaming functionality"""
    print("🎬 Testing Video Streaming Functionality")
    print("=" * 50)
    
    # Test server connection
    try:
        response = requests.get("http://localhost:8000/", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
        else:
            print(f"❌ Server returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to server: {e}")
        return False
    
    # Check if security_videos directory exists
    if not os.path.exists("security_videos"):
        print("❌ security_videos directory not found")
        return False
    
    # List video files
    video_files = [f for f in os.listdir("security_videos") if f.endswith(('.mp4', '.avi', '.mov'))]
    if not video_files:
        print("❌ No video files found in security_videos directory")
        return False
    
    print(f"✅ Found {len(video_files)} video files")
    
    # Test streaming a video file
    test_video = video_files[0]
    print(f"🎥 Testing streaming for: {test_video}")
    
    try:
        # Test basic streaming
        response = requests.get(f"http://localhost:8000/security_videos/{test_video}", 
                              headers={'Range': 'bytes=0-1023'}, timeout=10)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📊 Content-Type: {response.headers.get('Content-Type', 'Not set')}")
        print(f"📊 Content-Range: {response.headers.get('Content-Range', 'Not set')}")
        print(f"📊 Accept-Ranges: {response.headers.get('Accept-Ranges', 'Not set')}")
        print(f"📊 X-Streaming-Only: {response.headers.get('X-Streaming-Only', 'Not set')}")
        
        if response.status_code in [200, 206]:
            print("✅ Video streaming endpoint working")
            
            # Check if response has content
            if len(response.content) > 0:
                print(f"✅ Received {len(response.content)} bytes")
            else:
                print("⚠️ No content received")
                
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error testing video streaming: {e}")
        return False
    
    # Test full file request
    try:
        response = requests.get(f"http://localhost:8000/security_videos/{test_video}", timeout=10)
        print(f"📊 Full file response status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Full file streaming working")
        else:
            print(f"❌ Full file streaming failed: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error testing full file streaming: {e}")
        return False
    
    print("\n🎉 Video streaming test completed successfully!")
    return True

if __name__ == "__main__":
    success = test_video_streaming()
    sys.exit(0 if success else 1) 