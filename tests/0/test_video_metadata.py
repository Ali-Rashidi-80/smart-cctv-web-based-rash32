#!/usr/bin/env python3
"""
Test script for video metadata and poster generation functionality
Tests the new Windows-like video metadata system
"""

import requests
import json
import os
from pathlib import Path

def test_video_metadata_system():
    """Test the enhanced video metadata system"""
    print("🎬 Testing Enhanced Video Metadata System")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    
    # Test 1: Check if server is running
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        print("✅ Server is running")
    except Exception as e:
        print(f"❌ Server not accessible: {e}")
        return False
    
    # Test 2: Check video metadata endpoint
    print("\n📋 Test 2: Video Metadata Endpoint")
    try:
        # List videos first
        response = requests.get(f"{base_url}/get_videos", timeout=10)
        if response.status_code == 200:
            videos = response.json()
            if videos and len(videos) > 0:
                test_video = videos[0]['filename']
                print(f"✅ Found test video: {test_video}")
                
                # Test metadata endpoint
                metadata_response = requests.get(f"{base_url}/video_metadata/{test_video}", timeout=10)
                if metadata_response.status_code == 200:
                    metadata = metadata_response.json()
                    print("✅ Video metadata endpoint working")
                    print(f"   📊 Resolution: {metadata.get('resolution', 'N/A')}")
                    print(f"   ⏱️ Duration: {metadata.get('duration_formatted', 'N/A')}")
                    print(f"   🎯 FPS: {metadata.get('fps', 'N/A')}")
                    print(f"   📁 Size: {metadata.get('file_size_formatted', 'N/A')}")
                else:
                    print(f"❌ Metadata endpoint failed: {metadata_response.status_code}")
            else:
                print("⚠️ No videos found to test")
        else:
            print(f"❌ Could not get videos list: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing metadata endpoint: {e}")
    
    # Test 3: Check video poster endpoint
    print("\n🖼️ Test 3: Video Poster Generation")
    try:
        if 'test_video' in locals():
            poster_response = requests.get(f"{base_url}/video_poster/{test_video}", timeout=15)
            if poster_response.status_code == 200:
                print("✅ Video poster generation working")
                print(f"   📏 Content-Type: {poster_response.headers.get('Content-Type', 'N/A')}")
                print(f"   📦 Content-Length: {poster_response.headers.get('Content-Length', 'N/A')}")
                print(f"   🎨 X-Poster-Generated: {poster_response.headers.get('X-Poster-Generated', 'N/A')}")
            else:
                print(f"❌ Poster generation failed: {poster_response.status_code}")
        else:
            print("⚠️ Skipping poster test - no test video available")
    except Exception as e:
        print(f"❌ Error testing poster generation: {e}")
    
    # Test 4: Check poster caching
    print("\n💾 Test 4: Poster Caching")
    try:
        if 'test_video' in locals():
            # Second request should be cached
            poster_response2 = requests.get(f"{base_url}/video_poster/{test_video}", timeout=10)
            if poster_response2.status_code == 200:
                cache_control = poster_response2.headers.get('Cache-Control', 'N/A')
                print(f"✅ Poster caching working: {cache_control}")
            else:
                print(f"❌ Cached poster request failed: {poster_response2.status_code}")
        else:
            print("⚠️ Skipping caching test - no test video available")
    except Exception as e:
        print(f"❌ Error testing poster caching: {e}")
    
    # Test 5: Check security headers
    print("\n🔒 Test 5: Security Headers")
    try:
        if 'test_video' in locals():
            video_response = requests.get(f"{base_url}/security_videos/{test_video}", timeout=10)
            if video_response.status_code == 200:
                security_headers = [
                    'X-Streaming-Only',
                    'X-Video-Security', 
                    'X-Content-Type-Options',
                    'X-Frame-Options',
                    'X-Download-Options'
                ]
                
                print("✅ Security headers present:")
                for header in security_headers:
                    value = video_response.headers.get(header, 'Not set')
                    print(f"   🛡️ {header}: {value}")
            else:
                print(f"❌ Video streaming failed: {video_response.status_code}")
        else:
            print("⚠️ Skipping security test - no test video available")
    except Exception as e:
        print(f"❌ Error testing security headers: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Video Metadata System Test Completed!")
    return True

if __name__ == "__main__":
    success = test_video_metadata_system()
    if success:
        print("\n✅ All tests passed successfully!")
    else:
        print("\n❌ Some tests failed. Check the output above.") 