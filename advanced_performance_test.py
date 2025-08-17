import requests
import time
import json
import cv2
import numpy as np
from threading import Thread
import statistics
import matplotlib.pyplot as plt
import asyncio
import websockets
import aiohttp
import aiofiles
from datetime import datetime
import os

class AdvancedPerformanceTester:
    def __init__(self, flask_url="http://localhost:3002", fastapi_url="http://localhost:3003"):
        self.flask_url = flask_url
        self.fastapi_url = fastapi_url
        self.results = {
            'flask': {
                'latency': [], 'fps': [], 'response_times': [], 
                'quality_levels': [], 'compensation_factors': [],
                'buffer_utilization': [], 'network_jitter': []
            },
            'fastapi': {
                'latency': [], 'fps': [], 'response_times': [], 
                'quality_levels': [], 'compensation_factors': [],
                'buffer_utilization': [], 'network_jitter': []
            }
        }
        self.test_log = []
        
    def log_test(self, message):
        """Log test messages with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.test_log.append(log_entry)
        print(log_entry)
    
    async def test_websocket_connection(self, server_type, url):
        """Test WebSocket connection stability"""
        self.log_test(f"🔌 Testing {server_type.upper()} WebSocket connection...")
        
        try:
            ws_url = url.replace('http', 'ws') + '/ws'
            async with websockets.connect(ws_url) as websocket:
                # Send ping message
                await websocket.send(json.dumps({'type': 'ping'}))
                
                # Wait for pong response
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                
                if data.get('type') == 'pong':
                    self.log_test(f"✅ {server_type.upper()} WebSocket ping/pong successful")
                    return True
                else:
                    self.log_test(f"❌ {server_type.upper()} WebSocket unexpected response")
                    return False
                    
        except Exception as e:
            self.log_test(f"❌ {server_type.upper()} WebSocket test failed: {e}")
            return False
    
    async def test_websocket_stats(self, server_type, url):
        """Test WebSocket stats endpoint"""
        self.log_test(f"📊 Testing {server_type.upper()} WebSocket stats...")
        
        try:
            ws_url = url.replace('http', 'ws') + '/ws_stats'
            async with websockets.connect(ws_url) as websocket:
                stats_received = 0
                start_time = time.time()
                
                while time.time() - start_time < 10:  # Test for 10 seconds
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        data = json.loads(response)
                        
                        # Store stats
                        self.results[server_type]['fps'].append(data.get('fps', 0))
                        self.results[server_type]['latency'].append(data.get('latency_ms', 0))
                        self.results[server_type]['quality_levels'].append(data.get('quality_level', 85))
                        self.results[server_type]['compensation_factors'].append(data.get('compensation_factor', 1.0))
                        self.results[server_type]['buffer_utilization'].append(data.get('buffer_utilization', 0))
                        self.results[server_type]['network_jitter'].append(data.get('network_jitter', 0))
                        
                        stats_received += 1
                        
                    except asyncio.TimeoutError:
                        break
                
                self.log_test(f"📈 {server_type.upper()} received {stats_received} stats updates")
                return stats_received > 0
                
        except Exception as e:
            self.log_test(f"❌ {server_type.upper()} WebSocket stats test failed: {e}")
            return False
    
    def test_single_frame_endpoint(self, server_type, url, num_requests=100):
        """Test single frame endpoint performance with detailed analysis"""
        self.log_test(f"\n🔍 Testing {server_type.upper()} single frame endpoint ({num_requests} requests)...")
        
        latencies = []
        response_times = []
        image_sizes = []
        
        for i in range(num_requests):
            start_time = time.time()
            
            try:
                response = requests.get(f"{url}/esp32_frame", timeout=10)
                end_time = time.time()
                
                if response.status_code == 200:
                    response_time = (end_time - start_time) * 1000  # Convert to ms
                    response_times.append(response_time)
                    
                    # Get additional headers
                    quality = int(response.headers.get('X-Frame-Quality', 85))
                    compensation = float(response.headers.get('X-Compensation-Factor', 1.0))
                    buffer_size = int(response.headers.get('X-Buffer-Size', 0))
                    
                    # Calculate image size for latency estimation
                    img_size = len(response.content)
                    image_sizes.append(img_size)
                    latency = response_time / (img_size / 1024)  # ms per KB
                    latencies.append(latency)
                    
                    # Store additional metrics
                    self.results[server_type]['quality_levels'].append(quality)
                    self.results[server_type]['compensation_factors'].append(compensation)
                    
                    if (i + 1) % 20 == 0:
                        self.log_test(f"  Completed {i + 1}/{num_requests} requests")
                        
            except Exception as e:
                self.log_test(f"  Error on request {i + 1}: {e}")
        
        # Calculate comprehensive statistics
        if response_times:
            avg_response = statistics.mean(response_times)
            min_response = min(response_times)
            max_response = max(response_times)
            std_response = statistics.stdev(response_times) if len(response_times) > 1 else 0
            
            self.log_test(f"  📊 Response Time Stats (ms):")
            self.log_test(f"    Average: {avg_response:.2f}")
            self.log_test(f"    Min: {min_response:.2f}")
            self.log_test(f"    Max: {max_response:.2f}")
            self.log_test(f"    Std Dev: {std_response:.2f}")
        
        if latencies:
            avg_latency = statistics.mean(latencies)
            self.log_test(f"  📊 Average Latency: {avg_latency:.2f} ms/KB")
        
        if image_sizes:
            avg_size = statistics.mean(image_sizes)
            self.log_test(f"  📊 Average Image Size: {avg_size/1024:.1f} KB")
        
        self.results[server_type]['response_times'].extend(response_times)
        self.results[server_type]['latency'].extend(latencies)
    
    def test_performance_stats(self, server_type, url, duration=30):
        """Test performance stats endpoint over time"""
        self.log_test(f"\n📈 Testing {server_type.upper()} performance stats for {duration} seconds...")
        
        fps_values = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                response = requests.get(f"{url}/performance_stats", timeout=5)
                if response.status_code == 200:
                    stats = response.json()
                    fps = stats.get('fps', 0)
                    fps_values.append(fps)
                    
                    # Store comprehensive stats
                    self.results[server_type]['fps'].append(fps)
                    self.results[server_type]['latency'].append(stats.get('latency_ms', 0))
                    self.results[server_type]['quality_levels'].append(stats.get('quality_level', 85))
                    self.results[server_type]['compensation_factors'].append(stats.get('compensation_factor', 1.0))
                    self.results[server_type]['buffer_utilization'].append(stats.get('buffer_utilization', 0))
                    
                    if 'network_stats' in stats:
                        self.results[server_type]['network_jitter'].append(stats['network_stats'].get('jitter', 0))
                    
                    self.log_test(f"  FPS: {fps:.2f}, Quality: {stats.get('quality_level', 85)}, "
                                f"Compensation: {stats.get('compensation_factor', 1.0):.3f}, "
                                f"Buffer: {stats.get('buffer_utilization', 0):.1f}%")
                    
                time.sleep(1)
                
            except Exception as e:
                self.log_test(f"  Error getting stats: {e}")
                time.sleep(1)
        
        if fps_values:
            avg_fps = statistics.mean(fps_values)
            max_fps = max(fps_values)
            min_fps = min(fps_values)
            self.log_test(f"  📊 FPS Stats:")
            self.log_test(f"    Average: {avg_fps:.2f}")
            self.log_test(f"    Max: {max_fps:.2f}")
            self.log_test(f"    Min: {min_fps:.2f}")
    
    def test_video_stream(self, server_type, url, duration=15):
        """Test video stream performance with frame analysis"""
        self.log_test(f"\n🎥 Testing {server_type.upper()} video stream for {duration} seconds...")
        
        start_time = time.time()
        frame_count = 0
        frame_sizes = []
        
        try:
            response = requests.get(f"{url}/esp32_video_feed", stream=True, timeout=duration + 10)
            
            if response.status_code == 200:
                current_frame_data = b""
                in_frame = False
                
                for chunk in response.iter_content(chunk_size=1024):
                    if b'--frame' in chunk:
                        if in_frame and current_frame_data:
                            frame_sizes.append(len(current_frame_data))
                            frame_count += 1
                        current_frame_data = b""
                        in_frame = True
                    elif in_frame:
                        current_frame_data += chunk
                    
                    if time.time() - start_time >= duration:
                        break
                        
        except Exception as e:
            self.log_test(f"  Error in video stream: {e}")
        
        elapsed_time = time.time() - start_time
        actual_fps = frame_count / elapsed_time if elapsed_time > 0 else 0
        
        self.log_test(f"  📊 Video Stream Stats:")
        self.log_test(f"    Frames received: {frame_count}")
        self.log_test(f"    Duration: {elapsed_time:.2f} seconds")
        self.log_test(f"    Actual FPS: {actual_fps:.2f}")
        
        if frame_sizes:
            avg_frame_size = statistics.mean(frame_sizes)
            self.log_test(f"    Average frame size: {avg_frame_size/1024:.1f} KB")
    
    async def run_comprehensive_test(self):
        """Run comprehensive performance test on both servers"""
        self.log_test("🚀 Starting Advanced Performance Test")
        self.log_test("=" * 60)
        
        # Test Flask server
        self.log_test("\n🔥 Testing FLASK Server")
        self.log_test("-" * 40)
        
        try:
            # Test WebSocket connections
            await self.test_websocket_connection('flask', self.flask_url)
            await self.test_websocket_stats('flask', self.flask_url)
            
            # Test endpoints
            self.test_single_frame_endpoint('flask', self.flask_url, 50)
            self.test_performance_stats('flask', self.flask_url, 20)
            self.test_video_stream('flask', self.flask_url, 15)
            
        except Exception as e:
            self.log_test(f"❌ Flask server test failed: {e}")
        
        # Test FastAPI server
        self.log_test("\n⚡ Testing FASTAPI Server")
        self.log_test("-" * 40)
        
        try:
            # Test WebSocket connections
            await self.test_websocket_connection('fastapi', self.fastapi_url)
            await self.test_websocket_stats('fastapi', self.fastapi_url)
            
            # Test endpoints
            self.test_single_frame_endpoint('fastapi', self.fastapi_url, 50)
            self.test_performance_stats('fastapi', self.fastapi_url, 20)
            self.test_video_stream('fastapi', self.fastapi_url, 15)
            
        except Exception as e:
            self.log_test(f"❌ FastAPI server test failed: {e}")
        
        # Generate comprehensive report
        self.generate_advanced_report()
        
        # Save results to file
        self.save_results()
    
    def generate_advanced_report(self):
        """Generate comprehensive performance comparison report"""
        self.log_test("\n" + "=" * 80)
        self.log_test("📊 ADVANCED PERFORMANCE COMPARISON REPORT")
        self.log_test("=" * 80)
        
        for server_type in ['flask', 'fastapi']:
            self.log_test(f"\n🔍 {server_type.upper()} DETAILED RESULTS:")
            self.log_test("-" * 50)
            
            # Response time analysis
            response_times = self.results[server_type]['response_times']
            if response_times:
                avg_response = statistics.mean(response_times)
                std_response = statistics.stdev(response_times) if len(response_times) > 1 else 0
                self.log_test(f"📈 Response Time: {avg_response:.2f} ± {std_response:.2f} ms")
            
            # FPS analysis
            fps_values = self.results[server_type]['fps']
            if fps_values:
                avg_fps = statistics.mean(fps_values)
                max_fps = max(fps_values)
                min_fps = min(fps_values)
                self.log_test(f"🎥 FPS: {avg_fps:.2f} (min: {min_fps:.2f}, max: {max_fps:.2f})")
            
            # Quality analysis
            quality_values = self.results[server_type]['quality_levels']
            if quality_values:
                avg_quality = statistics.mean(quality_values)
                self.log_test(f"🎨 Average Quality: {avg_quality:.1f}")
            
            # Compensation analysis
            compensation_values = self.results[server_type]['compensation_factors']
            if compensation_values:
                avg_compensation = statistics.mean(compensation_values)
                self.log_test(f"⚖️ Average Compensation: {avg_compensation:.3f}")
            
            # Buffer utilization
            buffer_values = self.results[server_type]['buffer_utilization']
            if buffer_values:
                avg_buffer = statistics.mean(buffer_values)
                self.log_test(f"📦 Average Buffer Utilization: {avg_buffer:.1f}%")
            
            # Network jitter
            jitter_values = self.results[server_type]['network_jitter']
            if jitter_values:
                avg_jitter = statistics.mean(jitter_values)
                self.log_test(f"🌐 Average Network Jitter: {avg_jitter:.4f}")
        
        # Winner determination
        self.log_test(f"\n🏆 COMPREHENSIVE WINNER ANALYSIS:")
        self.log_test("-" * 40)
        
        flask_avg_response = statistics.mean(self.results['flask']['response_times']) if self.results['flask']['response_times'] else float('inf')
        fastapi_avg_response = statistics.mean(self.results['fastapi']['response_times']) if self.results['fastapi']['response_times'] else float('inf')
        
        flask_avg_fps = statistics.mean(self.results['flask']['fps']) if self.results['flask']['fps'] else 0
        fastapi_avg_fps = statistics.mean(self.results['fastapi']['fps']) if self.results['fastapi']['fps'] else 0
        
        flask_avg_quality = statistics.mean(self.results['flask']['quality_levels']) if self.results['flask']['quality_levels'] else 0
        fastapi_avg_quality = statistics.mean(self.results['fastapi']['quality_levels']) if self.results['fastapi']['quality_levels'] else 0
        
        # Calculate overall score
        flask_score = 0
        fastapi_score = 0
        
        if fastapi_avg_response < flask_avg_response:
            fastapi_score += 1
            self.log_test("⚡ FastAPI wins in Response Time!")
        else:
            flask_score += 1
            self.log_test("🔥 Flask wins in Response Time!")
        
        if fastapi_avg_fps > flask_avg_fps:
            fastapi_score += 1
            self.log_test("⚡ FastAPI wins in FPS!")
        else:
            flask_score += 1
            self.log_test("🔥 Flask wins in FPS!")
        
        if fastapi_avg_quality > flask_avg_quality:
            fastapi_score += 1
            self.log_test("⚡ FastAPI wins in Quality!")
        else:
            flask_score += 1
            self.log_test("🔥 Flask wins in Quality!")
        
        self.log_test(f"\n📊 FINAL SCORE:")
        self.log_test(f"  Flask: {flask_score}/3")
        self.log_test(f"  FastAPI: {fastapi_score}/3")
        
        if fastapi_score > flask_score:
            self.log_test("🏆 FastAPI is the overall winner!")
        elif flask_score > fastapi_score:
            self.log_test("🏆 Flask is the overall winner!")
        else:
            self.log_test("🤝 It's a tie!")
        
        self.log_test(f"\n📋 RECOMMENDATIONS:")
        self.log_test("-" * 20)
        self.log_test("• FastAPI excels in high-performance scenarios with async processing")
        self.log_test("• Flask provides better stability and easier debugging")
        self.log_test("• Use FastAPI for production with high frame rates")
        self.log_test("• Use Flask for development and testing")
        self.log_test("• Both servers now feature intelligent network compensation")
    
    def save_results(self):
        """Save test results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"performance_test_results_{timestamp}.json"
        
        # Prepare data for saving
        save_data = {
            'timestamp': timestamp,
            'test_log': self.test_log,
            'results': self.results,
            'summary': {
                'flask': {
                    'avg_response_time': statistics.mean(self.results['flask']['response_times']) if self.results['flask']['response_times'] else 0,
                    'avg_fps': statistics.mean(self.results['flask']['fps']) if self.results['flask']['fps'] else 0,
                    'avg_quality': statistics.mean(self.results['flask']['quality_levels']) if self.results['flask']['quality_levels'] else 0
                },
                'fastapi': {
                    'avg_response_time': statistics.mean(self.results['fastapi']['response_times']) if self.results['fastapi']['response_times'] else 0,
                    'avg_fps': statistics.mean(self.results['fastapi']['fps']) if self.results['fastapi']['fps'] else 0,
                    'avg_quality': statistics.mean(self.results['fastapi']['quality_levels']) if self.results['fastapi']['quality_levels'] else 0
                }
            }
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(save_data, f, indent=2)
            self.log_test(f"\n💾 Results saved to: {filename}")
        except Exception as e:
            self.log_test(f"\n❌ Error saving results: {e}")

async def main():
    """Main function to run advanced performance tests"""
    print("🎯 Advanced ESP32-CAM Frame Server Performance Tester")
    print("=" * 60)
    
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
    
    # Run advanced performance test
    tester = AdvancedPerformanceTester(
        flask_url=flask_url or "http://localhost:3002",
        fastapi_url=fastapi_url or "http://localhost:3003"
    )
    
    await tester.run_comprehensive_test()

if __name__ == "__main__":
    asyncio.run(main()) 