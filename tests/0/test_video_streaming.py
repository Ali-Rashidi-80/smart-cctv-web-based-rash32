#!/usr/bin/env python3
"""
Test script for video streaming enhancements
"""

import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_video_config():
    """Test video configuration constants"""
    print("🔧 Testing Video Configuration...")
    
    try:
        from core.config import MAX_VIDEO_FILE_SIZE, VIDEO_STREAMING_THRESHOLD
        
        print(f"✅ MAX_VIDEO_FILE_SIZE: {MAX_VIDEO_FILE_SIZE / (1024**3):.1f} GB")
        print(f"✅ VIDEO_STREAMING_THRESHOLD: {VIDEO_STREAMING_THRESHOLD / (1024**2):.1f} MB")
        
        # Test different file size scenarios
        test_sizes = [
            (50 * 1024 * 1024, "50 MB - Standard Response"),
            (150 * 1024 * 1024, "150 MB - Streaming Response"),
            (1 * 1024 * 1024 * 1024, "1 GB - Streaming Response"),
            (2.5 * 1024 * 1024 * 1024, "2.5 GB - Would be rejected")
        ]
        
        print("\n📊 File Size Response Types:")
        for size, description in test_sizes:
            if size <= MAX_VIDEO_FILE_SIZE:
                response_type = "Streaming" if size > VIDEO_STREAMING_THRESHOLD else "Standard"
                status = "✅"
            else:
                response_type = "Rejected (too large)"
                status = "❌"
            
            print(f"{status} {description}: {response_type}")
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    
    return True

def test_video_function():
    """Test video serving function import"""
    print("\n🎥 Testing Video Function Import...")
    
    try:
        from core.client import serve_video_file
        print("✅ serve_video_file function imported successfully")
        
        # Check function signature
        import inspect
        sig = inspect.signature(serve_video_file)
        print(f"✅ Function signature: {sig}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_environment_variables():
    """Test environment variable configuration"""
    print("\n🌍 Testing Environment Variables...")
    
    # Check if .env file exists
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file found")
        
        # Read and check for video config
        with open(env_file, 'r') as f:
            content = f.read()
            
        if 'MAX_VIDEO_FILE_SIZE' in content:
            print("✅ MAX_VIDEO_FILE_SIZE configured in .env")
        else:
            print("⚠️ MAX_VIDEO_FILE_SIZE not in .env (using defaults)")
            
        if 'VIDEO_STREAMING_THRESHOLD' in content:
            print("✅ VIDEO_STREAMING_THRESHOLD configured in .env")
        else:
            print("⚠️ VIDEO_STREAMING_THRESHOLD not in .env (using defaults)")
    else:
        print("⚠️ .env file not found (using default configuration)")
        print("💡 Copy env_example.txt to .env to customize settings")

def test_security_videos_directory():
    """Test security videos directory"""
    print("\n📁 Testing Security Videos Directory...")
    
    try:
        from core.config import SECURITY_VIDEOS_DIR
        
        videos_dir = Path(SECURITY_VIDEOS_DIR)
        if videos_dir.exists():
            print(f"✅ Directory exists: {videos_dir}")
            
            # Count video files
            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
            video_files = [f for f in videos_dir.iterdir() 
                          if f.is_file() and f.suffix.lower() in video_extensions]
            
            print(f"✅ Found {len(video_files)} video files")
            
            # Show file sizes
            if video_files:
                print("\n📊 Video Files:")
                for video_file in video_files[:5]:  # Show first 5
                    try:
                        size = video_file.stat().st_size
                        size_mb = size / (1024 * 1024)
                        response_type = "Streaming" if size > 100 * 1024 * 1024 else "Standard"
                        print(f"  📹 {video_file.name}: {size_mb:.1f} MB ({response_type})")
                    except OSError:
                        print(f"  ❌ {video_file.name}: Error reading size")
                        
                if len(video_files) > 5:
                    print(f"  ... and {len(video_files) - 5} more files")
                    
        else:
            print(f"⚠️ Directory not found: {videos_dir}")
            print("💡 Create the directory or update SECURITY_VIDEOS_DIR in config")
            
    except ImportError as e:
        print(f"❌ Import error: {e}")

def main():
    """Main test function"""
    print("🚀 Video Streaming Enhancement Test")
    print("=" * 50)
    
    tests = [
        test_video_config,
        test_video_function,
        test_environment_variables,
        test_security_videos_directory
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Video streaming is ready to use.")
        print("\n💡 Next steps:")
        print("  1. Restart your server to apply changes")
        print("  2. Test with large video files (>100MB)")
        print("  3. Check browser network tab for streaming headers")
        print("  4. Monitor server logs for streaming messages")
    else:
        print("⚠️ Some tests failed. Check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 