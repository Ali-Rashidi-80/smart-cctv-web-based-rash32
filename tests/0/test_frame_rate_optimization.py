#!/usr/bin/env python3
"""
Comprehensive test script for frame rate optimization and compensation
Tests the enhanced FastAPI server with guaranteed 24-60 FPS streaming
"""

import asyncio
import aiohttp
import time
import json
import statistics
from typing import List, Dict, Any
import matplotlib.pyplot as plt
import numpy as np

class FrameRateOptimizationTester:
    def __init__(self, server_url: str = "http://localhost:3003"):
        self.server_url = server_url
        self.test_results = []
        self.fps_history = []
        self.latency_history = []
        self.quality_history = []
        self.compensation_history = []
        self.buffer_utilization_history = []
        
    async def test_server_health(self) -> bool:
        """Test basic server health"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.server_url}/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Server Health: {data['status']}")
                        print(f"   Current FPS: {data['fps']:.2f}")
                        print(f"   Buffer Size: {data['buffer_size']}")
                        print(f"   Compensation Factor: {data['compensation_factor']:.3f}")
                        return True
                    else:
                        print(f"❌ Server health check failed: {response.status}")
                        return False
        except Exception as e:
            print(f"❌ Server health check error: {e}")
            return False
    
    async def test_performance_stats(self) -> Dict[str, Any]:
        """Test performance statistics endpoint"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.server_url}/performance_stats") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Performance Stats Retrieved")
                        print(f"   FPS: {data['fps']:.2f} (Target: {data['target_fps']}, Min: {data['min_fps_guarantee']})")
                        print(f"   FPS Stability: {data['fps_stability']:.3f}")
                        print(f"   Frame Drop Rate: {data['frame_drop_rate']:.2f}%")
                        print(f"   Buffer Utilization: {data['buffer_utilization']:.1f}%")
                        print(f"   Compensation Effectiveness: {data['compensation_effectiveness']:.3f}")
                        return data
                    else:
                        print(f"❌ Performance stats failed: {response.status}")
                        return {}
        except Exception as e:
            print(f"❌ Performance stats error: {e}")
            return {}
    
    async def test_frame_rate_control(self) -> Dict[str, Any]:
        """Test frame rate control endpoint"""
        try:
            async with aiohttp.ClientSession() as session:
                # Get current settings
                async with session.get(f"{self.server_url}/frame_rate_control") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Frame Rate Control Retrieved")
                        print(f"   Target FPS: {data['target_fps']}")
                        print(f"   Min FPS: {data['min_fps']}")
                        print(f"   Current FPS: {data['current_fps']:.2f}")
                        print(f"   Adaptive Compensation: {data['adaptive_compensation']:.3f}")
                        return data
                    else:
                        print(f"❌ Frame rate control failed: {response.status}")
                        return {}
        except Exception as e:
            print(f"❌ Frame rate control error: {e}")
            return {}
    
    async def test_single_frame_endpoint(self) -> float:
        """Test single frame endpoint and measure latency"""
        try:
            start_time = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.server_url}/esp32_frame") as response:
                    if response.status == 200:
                        latency = (time.time() - start_time) * 1000
                        print(f"✅ Single Frame: {latency:.2f}ms")
                        
                        # Extract headers for analysis
                        headers = response.headers
                        quality = headers.get('X-Frame-Quality', 'Unknown')
                        compensation = headers.get('X-Compensation-Factor', 'Unknown')
                        buffer_utilization = headers.get('X-Buffer-Utilization', 'Unknown')
                        
                        print(f"   Quality: {quality}")
                        print(f"   Compensation: {compensation}")
                        print(f"   Buffer: {buffer_utilization}")
                        
                        return latency
                    else:
                        print(f"❌ Single frame failed: {response.status}")
                        return -1
        except Exception as e:
            print(f"❌ Single frame error: {e}")
            return -1
    
    async def monitor_stream_performance(self, duration: int = 30) -> Dict[str, List[float]]:
        """Monitor video stream performance for specified duration"""
        print(f"🔄 Monitoring stream performance for {duration} seconds...")
        
        start_time = time.time()
        fps_data = []
        latency_data = []
        quality_data = []
        compensation_data = []
        buffer_data = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.server_url}/esp32_video_feed") as response:
                    if response.status == 200:
                        # Extract initial headers
                        headers = response.headers
                        print(f"✅ Stream started")
                        print(f"   Target FPS: {headers.get('X-Target-FPS', 'Unknown')}")
                        print(f"   Min FPS: {headers.get('X-Min-FPS', 'Unknown')}")
                        
                        frame_count = 0
                        last_frame_time = time.time()
                        
                        async for chunk in response.content.iter_chunked(1024):
                            current_time = time.time()
                            
                            # Count frames and calculate FPS
                            frame_count += 1
                            if frame_count % 10 == 0:  # Sample every 10 frames
                                time_elapsed = current_time - start_time
                                current_fps = frame_count / time_elapsed
                                fps_data.append(current_fps)
                                
                                # Calculate frame interval
                                frame_interval = current_time - last_frame_time
                                latency_data.append(frame_interval * 1000)  # Convert to ms
                                last_frame_time = current_time
                                
                                # Get current stats
                                stats = await self.test_performance_stats()
                                if stats:
                                    quality_data.append(stats.get('quality_level', 0))
                                    compensation_data.append(stats.get('compensation_factor', 1.0))
                                    buffer_data.append(stats.get('buffer_utilization', 0.0))
                            
                            # Check if duration exceeded
                            if current_time - start_time >= duration:
                                break
                                
        except Exception as e:
            print(f"❌ Stream monitoring error: {e}")
        
        return {
            'fps': fps_data,
            'latency': latency_data,
            'quality': quality_data,
            'compensation': compensation_data,
            'buffer_utilization': buffer_data
        }
    
    async def test_frame_rate_adaptation(self) -> bool:
        """Test frame rate adaptation by changing settings"""
        try:
            async with aiohttp.ClientSession() as session:
                # Test different target FPS settings
                test_fps_values = [30, 45, 60]
                
                for target_fps in test_fps_values:
                    print(f"🔄 Testing target FPS: {target_fps}")
                    
                    # Update target FPS
                    async with session.post(
                        f"{self.server_url}/frame_rate_control",
                        params={'target_fps': target_fps}
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            print(f"   ✅ Updated to {data['target_fps']} FPS")
                            
                            # Wait for adaptation
                            await asyncio.sleep(5)
                            
                            # Check performance
                            stats = await self.test_performance_stats()
                            if stats:
                                current_fps = stats.get('fps', 0)
                                print(f"   Current FPS: {current_fps:.2f}")
                                
                                # Verify minimum FPS guarantee
                                min_fps = stats.get('min_fps_guarantee', 24)
                                if current_fps >= min_fps:
                                    print(f"   ✅ Minimum FPS guarantee maintained")
                                else:
                                    print(f"   ⚠️ FPS below minimum ({current_fps:.2f} < {min_fps})")
                        else:
                            print(f"   ❌ Failed to update FPS: {response.status}")
                
                return True
                
        except Exception as e:
            print(f"❌ Frame rate adaptation test error: {e}")
            return False
    
    def analyze_results(self, data: Dict[str, List[float]]):
        """Analyze test results and generate statistics"""
        print("\n📊 Performance Analysis:")
        print("=" * 50)
        
        if data['fps']:
            fps_stats = {
                'mean': statistics.mean(data['fps']),
                'median': statistics.median(data['fps']),
                'min': min(data['fps']),
                'max': max(data['fps']),
                'stdev': statistics.stdev(data['fps']) if len(data['fps']) > 1 else 0
            }
            
            print(f"FPS Statistics:")
            print(f"   Mean: {fps_stats['mean']:.2f}")
            print(f"   Median: {fps_stats['median']:.2f}")
            print(f"   Range: {fps_stats['min']:.2f} - {fps_stats['max']:.2f}")
            print(f"   Stability: {1 - (fps_stats['stdev'] / fps_stats['mean']):.3f}" if fps_stats['mean'] > 0 else "N/A")
            
            # Check FPS guarantees
            if fps_stats['min'] >= 24:
                print(f"   ✅ Minimum FPS guarantee (24) maintained")
            else:
                print(f"   ❌ Minimum FPS guarantee violated (min: {fps_stats['min']:.2f})")
        
        if data['latency']:
            latency_stats = {
                'mean': statistics.mean(data['latency']),
                'median': statistics.median(data['latency']),
                'min': min(data['latency']),
                'max': max(data['latency'])
            }
            
            print(f"\nLatency Statistics (ms):")
            print(f"   Mean: {latency_stats['mean']:.2f}")
            print(f"   Median: {latency_stats['median']:.2f}")
            print(f"   Range: {latency_stats['min']:.2f} - {latency_stats['max']:.2f}")
        
        if data['quality']:
            quality_stats = {
                'mean': statistics.mean(data['quality']),
                'min': min(data['quality']),
                'max': max(data['quality'])
            }
            
            print(f"\nQuality Statistics:")
            print(f"   Mean: {quality_stats['mean']:.1f}")
            print(f"   Range: {quality_stats['min']:.1f} - {quality_stats['max']:.1f}")
        
        if data['compensation']:
            compensation_stats = {
                'mean': statistics.mean(data['compensation']),
                'min': min(data['compensation']),
                'max': max(data['compensation'])
            }
            
            print(f"\nCompensation Statistics:")
            print(f"   Mean: {compensation_stats['mean']:.3f}")
            print(f"   Range: {compensation_stats['min']:.3f} - {compensation_stats['max']:.3f}")
    
    def generate_performance_report(self, data: Dict[str, List[float]]):
        """Generate comprehensive performance report"""
        print("\n📈 Performance Report:")
        print("=" * 50)
        
        # Overall assessment
        if data['fps']:
            avg_fps = statistics.mean(data['fps'])
            min_fps = min(data['fps'])
            
            print(f"Overall Performance Assessment:")
            if min_fps >= 24 and avg_fps >= 30:
                print(f"   🟢 EXCELLENT - Smooth streaming with guaranteed frame rate")
            elif min_fps >= 20 and avg_fps >= 25:
                print(f"   🟡 GOOD - Acceptable performance with minor issues")
            elif min_fps >= 15:
                print(f"   🟠 FAIR - Some performance issues detected")
            else:
                print(f"   🔴 POOR - Significant performance problems")
            
            print(f"   Average FPS: {avg_fps:.2f}")
            print(f"   Minimum FPS: {min_fps:.2f}")
            print(f"   FPS Stability: {1 - (statistics.stdev(data['fps']) / avg_fps):.3f}" if avg_fps > 0 else "N/A")
        
        # Compensation effectiveness
        if data['compensation']:
            avg_compensation = statistics.mean(data['compensation'])
            print(f"\nCompensation Analysis:")
            if avg_compensation > 1.5:
                print(f"   🔴 High compensation needed - system under stress")
            elif avg_compensation > 1.2:
                print(f"   🟡 Moderate compensation - some optimization needed")
            else:
                print(f"   🟢 Low compensation - system running optimally")
        
        # Buffer efficiency
        if data['buffer_utilization']:
            avg_buffer = statistics.mean(data['buffer_utilization'])
            print(f"\nBuffer Efficiency:")
            if avg_buffer > 80:
                print(f"   🔴 High buffer utilization - potential bottlenecks")
            elif avg_buffer > 50:
                print(f"   🟡 Moderate buffer utilization - normal operation")
            else:
                print(f"   🟢 Low buffer utilization - efficient operation")

async def main():
    """Main test function"""
    print("🚀 Frame Rate Optimization Test Suite")
    print("=" * 60)
    
    tester = FrameRateOptimizationTester()
    
    # Test 1: Server Health
    print("\n1. Testing Server Health...")
    if not await tester.test_server_health():
        print("❌ Server not available. Please start the FastAPI server first.")
        return
    
    # Test 2: Performance Statistics
    print("\n2. Testing Performance Statistics...")
    await tester.test_performance_stats()
    
    # Test 3: Frame Rate Control
    print("\n3. Testing Frame Rate Control...")
    await tester.test_frame_rate_control()
    
    # Test 4: Single Frame Endpoint
    print("\n4. Testing Single Frame Endpoint...")
    await tester.test_single_frame_endpoint()
    
    # Test 5: Stream Performance Monitoring
    print("\n5. Monitoring Stream Performance...")
    stream_data = await tester.monitor_stream_performance(duration=30)
    
    # Test 6: Frame Rate Adaptation
    print("\n6. Testing Frame Rate Adaptation...")
    await tester.test_frame_rate_adaptation()
    
    # Analysis and Report
    print("\n7. Analyzing Results...")
    tester.analyze_results(stream_data)
    tester.generate_performance_report(stream_data)
    
    print("\n✅ Test suite completed!")

if __name__ == "__main__":
    asyncio.run(main()) 