import requests
import time
import json
import cv2
import numpy as np
from threading import Thread
import statistics

class PerformanceTester:
    def __init__(self, flask_url="http://localhost:3002", fastapi_url="http://localhost:3003"):
        self.flask_url = flask_url
        self.fastapi_url = fastapi_url
        self.results = {
            'flask': {'latency': [], 'fps': [], 'response_times': []},
            'fastapi': {'latency': [], 'fps': [], 'response_times': []}
        }
    
    def test_single_frame_endpoint(self, server_type, url, num_requests=100):
        """Test single frame endpoint performance"""
        print(f"\n🔍 Testing {server_type.upper()} single frame endpoint...")
        
        latencies = []
        response_times = []
        
        for i in range(num_requests):
            start_time = time.time()
            
            try:
                response = requests.get(f"{url}/esp32_frame", timeout=5)
                end_time = time.time()
                
                if response.status_code == 200:
                    response_time = (end_time - start_time) * 1000  # Convert to ms
                    response_times.append(response_time)
                    
                    # Calculate image size for latency estimation
                    img_size = len(response.content)
                    latency = response_time / (img_size / 1024)  # ms per KB
                    latencies.append(latency)
                    
                    if (i + 1) % 20 == 0:
                        print(f"  Completed {i + 1}/{num_requests} requests")
                        
            except Exception as e:
                print(f"  Error on request {i + 1}: {e}")
        
        # Calculate statistics
        if response_times:
            avg_response = statistics.mean(response_times)
            min_response = min(response_times)
            max_response = max(response_times)
            
            print(f"  📊 Response Time Stats (ms):")
            print(f"    Average: {avg_response:.2f}")
            print(f"    Min: {min_response:.2f}")
            print(f"    Max: {max_response:.2f}")
        
        if latencies:
            avg_latency = statistics.mean(latencies)
            print(f"  📊 Average Latency: {avg_latency:.2f} ms/KB")
        
        self.results[server_type]['response_times'].extend(response_times)
        self.results[server_type]['latency'].extend(latencies)
    
    def test_performance_stats(self, server_type, url, duration=30):
        """Test performance stats endpoint over time"""
        print(f"\n📈 Testing {server_type.upper()} performance stats for {duration} seconds...")
        
        fps_values = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                response = requests.get(f"{url}/performance_stats", timeout=2)
                if response.status_code == 200:
                    stats = response.json()
                    fps = stats.get('fps', 0)
                    fps_values.append(fps)
                    
                    print(f"  FPS: {fps:.2f}, Buffer: {stats.get('buffer_size', 0)}, "
                          f"Latency: {stats.get('latency_ms', 0):.2f}ms")
                    
                time.sleep(1)
                
            except Exception as e:
                print(f"  Error getting stats: {e}")
                time.sleep(1)
        
        if fps_values:
            avg_fps = statistics.mean(fps_values)
            max_fps = max(fps_values)
            print(f"  📊 FPS Stats:")
            print(f"    Average: {avg_fps:.2f}")
            print(f"    Max: {max_fps:.2f}")
        
        self.results[server_type]['fps'].extend(fps_values)
    
    def test_video_stream(self, server_type, url, duration=10):
        """Test video stream performance"""
        print(f"\n🎥 Testing {server_type.upper()} video stream for {duration} seconds...")
        
        start_time = time.time()
        frame_count = 0
        
        try:
            response = requests.get(f"{url}/esp32_video_feed", stream=True, timeout=duration + 5)
            
            if response.status_code == 200:
                for chunk in response.iter_content(chunk_size=1024):
                    if b'--frame' in chunk:
                        frame_count += 1
                    
                    if time.time() - start_time >= duration:
                        break
                        
        except Exception as e:
            print(f"  Error in video stream: {e}")
        
        elapsed_time = time.time() - start_time
        actual_fps = frame_count / elapsed_time if elapsed_time > 0 else 0
        
        print(f"  📊 Video Stream Stats:")
        print(f"    Frames received: {frame_count}")
        print(f"    Duration: {elapsed_time:.2f} seconds")
        print(f"    Actual FPS: {actual_fps:.2f}")
    
    def run_comprehensive_test(self):
        """Run comprehensive performance test on both servers"""
        print("🚀 Starting Comprehensive Performance Test")
        print("=" * 50)
        
        # Test Flask server
        print("\n🔥 Testing FLASK Server")
        print("-" * 30)
        
        try:
            self.test_single_frame_endpoint('flask', self.flask_url, 50)
            self.test_performance_stats('flask', self.flask_url, 15)
            self.test_video_stream('flask', self.flask_url, 10)
        except Exception as e:
            print(f"❌ Flask server test failed: {e}")
        
        # Test FastAPI server
        print("\n⚡ Testing FASTAPI Server")
        print("-" * 30)
        
        try:
            self.test_single_frame_endpoint('fastapi', self.fastapi_url, 50)
            self.test_performance_stats('fastapi', self.fastapi_url, 15)
            self.test_video_stream('fastapi', self.fastapi_url, 10)
        except Exception as e:
            print(f"❌ FastAPI server test failed: {e}")
        
        # Generate comparison report
        self.generate_report()
    
    def generate_report(self):
        """Generate performance comparison report"""
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE COMPARISON REPORT")
        print("=" * 60)
        
        for server_type in ['flask', 'fastapi']:
            print(f"\n🔍 {server_type.upper()} RESULTS:")
            print("-" * 30)
            
            # Response time analysis
            response_times = self.results[server_type]['response_times']
            if response_times:
                avg_response = statistics.mean(response_times)
                print(f"📈 Average Response Time: {avg_response:.2f} ms")
            
            # FPS analysis
            fps_values = self.results[server_type]['fps']
            if fps_values:
                avg_fps = statistics.mean(fps_values)
                max_fps = max(fps_values)
                print(f"🎥 Average FPS: {avg_fps:.2f}")
                print(f"🎥 Max FPS: {max_fps:.2f}")
        
        # Winner determination
        print(f"\n🏆 WINNER ANALYSIS:")
        print("-" * 20)
        
        flask_avg_response = statistics.mean(self.results['flask']['response_times']) if self.results['flask']['response_times'] else float('inf')
        fastapi_avg_response = statistics.mean(self.results['fastapi']['response_times']) if self.results['fastapi']['response_times'] else float('inf')
        
        flask_avg_fps = statistics.mean(self.results['flask']['fps']) if self.results['flask']['fps'] else 0
        fastapi_avg_fps = statistics.mean(self.results['fastapi']['fps']) if self.results['fastapi']['fps'] else 0
        
        if fastapi_avg_response < flask_avg_response:
            print("⚡ FastAPI wins in Response Time!")
        else:
            print("🔥 Flask wins in Response Time!")
        
        if fastapi_avg_fps > flask_avg_fps:
            print("⚡ FastAPI wins in FPS!")
        else:
            print("🔥 Flask wins in FPS!")
        
        print(f"\n📋 RECOMMENDATIONS:")
        print("-" * 20)
        print("• FastAPI is generally better for high-performance applications")
        print("• Flask is simpler and easier to debug")
        print("• Use FastAPI for production with high frame rates")
        print("• Use Flask for development and testing")

def main():
    """Main function to run performance tests"""
    print("🎯 ESP32-CAM Frame Server Performance Tester")
    print("=" * 50)
    
    # Check if servers are running
    flask_url = "http://localhost:3002"
    fastapi_url = "http://localhost:3003"
    
    print("🔍 Checking server availability...")
    
    try:
        response = requests.get(f"{flask_url}/health", timeout=2)
        print("✅ Flask server is running")
    except:
        print("❌ Flask server is not running on port 3002")
        flask_url = None
    
    try:
        response = requests.get(f"{fastapi_url}/health", timeout=2)
        print("✅ FastAPI server is running")
    except:
        print("❌ FastAPI server is not running on port 3003")
        fastapi_url = None
    
    if not flask_url and not fastapi_url:
        print("\n❌ No servers are running!")
        print("Please start the servers first:")
        print("  python optimized_flask_frame.py")
        print("  python fastapi_frame_server.py")
        return
    
    # Run performance test
    tester = PerformanceTester(
        flask_url=flask_url or "http://localhost:3002",
        fastapi_url=fastapi_url or "http://localhost:3003"
    )
    
    tester.run_comprehensive_test()

if __name__ == "__main__":
    main() 