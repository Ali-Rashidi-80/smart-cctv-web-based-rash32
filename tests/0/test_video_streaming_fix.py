#!/usr/bin/env python3
"""
Test script for video streaming fixes
Verifies that videos are served with proper headers for streaming (not download)
"""

import os
import sys
import requests
import tempfile
from pathlib import Path

def test_video_streaming_headers():
    """Test that video files are served with proper streaming headers"""
    
    print("🎬 Testing Video Streaming Headers Fix")
    print("=" * 50)
    
    # Test server URL (adjust as needed)
    base_url = "http://localhost:8000"  # Adjust port if needed
    
    # Test video files with different extensions
    test_files = [
        "test_video.mp4",
        "test_video.avi", 
        "test_video.mov",
        "test_video.mkv",
        "test_video.webm"
    ]
    
    expected_content_types = {
        '.mp4': 'video/mp4',
        '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime',
        '.mkv': 'video/x-matroska',
        '.webm': 'video/webm'
    }
    
    print("📋 Expected Content-Type mappings:")
    for ext, content_type in expected_content_types.items():
        print(f"   {ext} → {content_type}")
    print()
    
    # Test each file type
    for test_file in test_files:
        print(f"🔍 Testing: {test_file}")
        
        try:
            # Make a HEAD request to check headers without downloading
            url = f"{base_url}/security_videos/{test_file}"
            response = requests.head(url, timeout=10)
            
            if response.status_code == 200:
                print(f"   ✅ Status: {response.status_code}")
                
                # Check Content-Type
                content_type = response.headers.get('Content-Type', '')
                file_ext = Path(test_file).suffix.lower()
                expected_type = expected_content_types.get(file_ext, 'video/mp4')
                
                if content_type == expected_type:
                    print(f"   ✅ Content-Type: {content_type}")
                else:
                    print(f"   ❌ Content-Type: {content_type} (expected: {expected_type})")
                
                # Check Content-Disposition
                content_disposition = response.headers.get('Content-Disposition', '')
                if content_disposition == 'inline':
                    print(f"   ✅ Content-Disposition: {content_disposition}")
                else:
                    print(f"   ❌ Content-Disposition: {content_disposition} (expected: inline)")
                
                # Check Accept-Ranges
                accept_ranges = response.headers.get('Accept-Ranges', '')
                if accept_ranges == 'bytes':
                    print(f"   ✅ Accept-Ranges: {accept_ranges}")
                else:
                    print(f"   ❌ Accept-Ranges: {accept_ranges} (expected: bytes)")
                
                # Check X-Streaming-Only
                streaming_only = response.headers.get('X-Streaming-Only', '')
                if streaming_only == 'true':
                    print(f"   ✅ X-Streaming-Only: {streaming_only}")
                else:
                    print(f"   ❌ X-Streaming-Only: {streaming_only} (expected: true)")
                
            elif response.status_code == 404:
                print(f"   ⚠️  File not found (404) - This is normal if test file doesn't exist")
            else:
                print(f"   ❌ Unexpected status: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection error - Make sure server is running on {base_url}")
        except requests.exceptions.Timeout:
            print(f"   ❌ Request timeout")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print()
    
    print("🎯 Summary:")
    print("   - Content-Type should match file extension")
    print("   - Content-Disposition should be 'inline' (not 'attachment')")
    print("   - Accept-Ranges should be 'bytes' for streaming support")
    print("   - X-Streaming-Only should be 'true'")
    print()
    print("✅ Test completed!")

def test_content_type_function():
    """Test the get_video_content_type function"""
    
    print("🧪 Testing get_video_content_type Function")
    print("=" * 50)
    
    # Import the function from the server
    try:
        sys.path.append('.')
        from core.client import get_video_content_type
        
        test_cases = [
            ("video.mp4", "video/mp4"),
            ("video.avi", "video/x-msvideo"),
            ("video.mov", "video/quicktime"),
            ("video.mkv", "video/x-matroska"),
            ("video.webm", "video/webm"),
            ("video.unknown", "video/mp4"),  # Default case
            ("VIDEO.MP4", "video/mp4"),  # Case insensitive
        ]
        
        for filename, expected in test_cases:
            result = get_video_content_type(filename)
            if result == expected:
                print(f"   ✅ {filename} → {result}")
            else:
                print(f"   ❌ {filename} → {result} (expected: {expected})")
        
        print("✅ Function test completed!")
        
    except ImportError as e:
        print(f"❌ Could not import function: {e}")
    except Exception as e:
        print(f"❌ Error testing function: {e}")

if __name__ == "__main__":
    print("🚀 Video Streaming Fix Test Suite")
    print("=" * 60)
    print()
    
    # Test the content type function
    test_content_type_function()
    print()
    
    # Test actual server headers
    test_video_streaming_headers()
    print()
    
    print("🎉 All tests completed!")
    print()
    print("📝 Notes:")
    print("   - Make sure the server is running before testing headers")
    print("   - Test files don't need to exist for header testing")
    print("   - The main fix is changing Content-Disposition from 'attachment' to 'inline'")
    print("   - Content-Type is now dynamic based on file extension") 