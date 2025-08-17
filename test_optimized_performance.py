#!/usr/bin/env python3
"""
Test script for checking optimized performance of Flask and FastAPI servers
"""

import requests
import time
import threading
import cv2
import numpy as np
from io import BytesIO
import json

def test_server_performance(server_name, server_url):
    """Test server performance with detailed metrics"""
    print(f"\n🔍 Testing {server_name} server performance...")
    
    try:
        # Test health endpoint
        health_response = requests.get(f"{server_url}/health", timeout=5)
        if health_response.status_code == 200:
            print(f"✅ {server_name} server is running")
        else:
            print(f"❌ {server_name} server health check failed")
            return
    except Exception as e:
        print(f"❌ {server_name} server not accessible: {e}")
        return
    
    # Test performance stats
    try:
        stats_response = requests.get(f"{server_url}/performance_stats", timeout=5)
        if stats_response.status_code == 200:
            stats = stats_response.json()
            print(f"📊 {server_name} Performance Stats:")
            print(f"   FPS: {stats.get('fps', 0):.2f}")
            print(f"   Buffer Size: {stats.get('buffer_size', 0)}")
            print(f"   Buffer Utilization: {stats.get('buffer_utilization', 0):.1f}%")
            print(f"   Quality Level: {stats.get('quality_level', 0)}")
            print(f"   Compensation Factor: {stats.get('compensation_factor', 1.0):.3f}")
            print(f"   Network Jitter: {stats.get('network_jitter', 0):.4f}")
            print(f"   Latency: {stats.get('latency_ms', 0):.2f}ms")
        else:
            print(f"❌ {server_name} stats not available")
    except Exception as e:
        print(f"❌ {server_name} stats error: {e}")
    
    # Test video stream performance
    try:
        print(f"📹 Testing {server_name} video stream performance...")
        response = requests.get(f"{server_url}/esp32_video_feed", stream=True, timeout=30)
        
        if response.status_code == 200:
            print(f"✅ {server_name} video stream connected successfully")
            
            frame_count = 0
            start_time = time.time()
            last_frame_time = start_time
            total_bytes = 0
            
            for chunk in response.iter_content(chunk_size=1024):
                if b'--frame' in chunk:
                    frame_count += 1
                    current_time = time.time()
                    total_bytes += len(chunk)
                    
                    if frame_count % 60 == 0:  # Log every 60 frames
                        elapsed = current_time - start_time
                        fps = frame_count / elapsed if elapsed > 0 else 0
                        avg_frame_size = total_bytes / frame_count if frame_count > 0 else 0
                        time_since_last = current_time - last_frame_time
                        
                        print(f"📊 {server_name}: Frame {frame_count}, FPS: {fps:.2f}, "
                              f"Avg Frame Size: {avg_frame_size:.0f} bytes, "
                              f"Time: {time_since_last:.3f}s")
                        last_frame_time = current_time
                    
                    # Test for 15 seconds
                    if current_time - start_time > 15:
                        final_fps = frame_count / (current_time - start_time)
                        print(f"✅ {server_name} test completed: {frame_count} frames in 15 seconds")
                        print(f"📈 Final FPS: {final_fps:.2f}")
                        print(f"📊 Average Frame Size: {total_bytes/frame_count:.0f} bytes")
                        break
        else:
            print(f"❌ {server_name} video stream failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ {server_name} stream test error: {e}")

def test_frame_rate_consistency(server_name, server_url):
    """Test frame rate consistency over time"""
    print(f"\n⏱️ Testing {server_name} frame rate consistency...")
    
    try:
        response = requests.get(f"{server_url}/esp32_video_feed", stream=True, timeout=20)
        
        if response.status_code == 200:
            frame_times = []
            frame_count = 0
            start_time = time.time()
            
            for chunk in response.iter_content(chunk_size=1024):
                if b'--frame' in chunk:
                    current_time = time.time()
                    frame_times.append(current_time)
                    frame_count += 1
                    
                    # Test for 10 seconds
                    if current_time - start_time > 10:
                        break
            
            if len(frame_times) > 1:
                # Calculate frame intervals
                intervals = [frame_times[i] - frame_times[i-1] for i in range(1, len(frame_times))]
                avg_interval = sum(intervals) / len(intervals)
                min_interval = min(intervals)
                max_interval = max(intervals)
                std_interval = np.std(intervals) if len(intervals) > 1 else 0
                
                print(f"📊 {server_name} Frame Rate Analysis:")
                print(f"   Total Frames: {frame_count}")
                print(f"   Average Interval: {avg_interval*1000:.2f}ms")
                print(f"   Min Interval: {min_interval*1000:.2f}ms")
                print(f"   Max Interval: {max_interval*1000:.2f}ms")
                print(f"   Standard Deviation: {std_interval*1000:.2f}ms")
                print(f"   Calculated FPS: {1/avg_interval:.2f}")
                
                # Consistency score
                consistency = 1.0 - (std_interval / avg_interval)
                print(f"   Consistency Score: {consistency:.3f}")
                
                if consistency > 0.8:
                    print(f"   ✅ {server_name} frame rate is very consistent")
                elif consistency > 0.6:
                    print(f"   ⚠️ {server_name} frame rate is moderately consistent")
                else:
                    print(f"   ❌ {server_name} frame rate is inconsistent")
                    
        else:
            print(f"❌ {server_name} stream failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ {server_name} consistency test error: {e}")

def test_latency(server_name, server_url):
    """Test latency of single frame requests"""
    print(f"\n⚡ Testing {server_name} latency...")
    
    try:
        latencies = []
        
        for i in range(10):
            start_time = time.time()
            response = requests.get(f"{server_url}/esp32_frame", timeout=5)
            end_time = time.time()
            
            if response.status_code == 200:
                latency = (end_time - start_time) * 1000  # Convert to ms
                latencies.append(latency)
                print(f"   Request {i+1}: {latency:.2f}ms")
            else:
                print(f"   Request {i+1}: Failed ({response.status_code})")
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            
            print(f"📊 {server_name} Latency Summary:")
            print(f"   Average: {avg_latency:.2f}ms")
            print(f"   Min: {min_latency:.2f}ms")
            print(f"   Max: {max_latency:.2f}ms")
            
            if avg_latency < 100:
                print(f"   ✅ {server_name} latency is excellent")
            elif avg_latency < 200:
                print(f"   ⚠️ {server_name} latency is good")
            else:
                print(f"   ❌ {server_name} latency is poor")
                
    except Exception as e:
        print(f"❌ {server_name} latency test error: {e}")

def main():
    """Main test function"""
    print("🚀 Starting Optimized Performance Tests")
    print("=" * 60)
    
    servers = [
        ("Flask", "http://localhost:3002"),
        ("FastAPI", "http://localhost:3003")
    ]
    
    for server_name, server_url in servers:
        # Test basic performance
        test_server_performance(server_name, server_url)
        
        # Test frame rate consistency
        test_frame_rate_consistency(server_name, server_url)
        
        # Test latency
        test_latency(server_name, server_url)
    
    print("\n" + "=" * 60)
    print("✅ All optimized performance tests completed!")
    print("\n📋 Optimization Summary:")
    print("   • Reduced buffer sizes for lower latency")
    print("   • Increased target FPS to 60")
    print("   • Optimized frame processing intervals")
    print("   • Limited quality and compensation factors")
    print("   • Reduced sleep times for better responsiveness")

if __name__ == "__main__":
    main() 