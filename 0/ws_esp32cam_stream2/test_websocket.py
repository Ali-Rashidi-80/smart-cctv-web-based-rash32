#!/usr/bin/env python3
"""
WebSocket Connection Test for ESP32CAM
Tests connection to smart-cctv-rash32.chbk.app
"""

import asyncio
import websockets
import json
import ssl
import sys
from datetime import datetime

# Configuration
WS_URL = "wss://smart-cctv-rash32.chbk.app/ws/esp32cam"
AUTH_TOKEN = "esp32cam_secure_token_2024"

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

async def test_websocket_connection():
    """Test WebSocket connection to the server"""
    
    log("Starting WebSocket connection test...")
    log(f"Target URL: {WS_URL}")
    log(f"Auth Token: {AUTH_TOKEN}")
    
    try:
        # Create SSL context for secure connection
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        log("Attempting to connect...")
        
        # Connect to WebSocket
        async with websockets.connect(
            WS_URL,
            ssl=ssl_context,
            extra_headers={
                "Authorization": f"Bearer {AUTH_TOKEN}"
            }
        ) as websocket:
            log("WebSocket connection established successfully!", "SUCCESS")
            
            # Send authentication message
            auth_message = {
                "type": "auth",
                "token": AUTH_TOKEN,
                "device": "esp32cam",
                "timestamp": datetime.now().isoformat()
            }
            
            log("Sending authentication message...")
            await websocket.send(json.dumps(auth_message))
            log("Authentication message sent")
            
            # Wait for response
            log("Waiting for server response...")
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                log(f"Received response: {response}", "SUCCESS")
                
                # Try to parse as JSON
                try:
                    response_data = json.loads(response)
                    log(f"Parsed JSON response: {json.dumps(response_data, indent=2)}")
                except json.JSONDecodeError:
                    log("Response is not valid JSON")
                    
            except asyncio.TimeoutError:
                log("No response received within 10 seconds", "WARNING")
            
            # Send a test message
            test_message = {
                "type": "test",
                "message": "Hello from Python test client",
                "timestamp": datetime.now().isoformat()
            }
            
            log("Sending test message...")
            await websocket.send(json.dumps(test_message))
            log("Test message sent")
            
            # Wait for any additional responses
            log("Waiting for additional responses...")
            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    log(f"Received: {response}")
            except asyncio.TimeoutError:
                log("No more responses received")
            
            log("Connection test completed successfully!", "SUCCESS")
            
    except websockets.exceptions.InvalidURI as e:
        log(f"Invalid URI: {e}", "ERROR")
        return False
    except websockets.exceptions.InvalidHandshake as e:
        log(f"Invalid handshake: {e}", "ERROR")
        return False
    except websockets.exceptions.ConnectionClosed as e:
        log(f"Connection closed: {e}", "ERROR")
        return False
    except OSError as e:
        log(f"Network error: {e}", "ERROR")
        return False
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        return False
    
    return True

async def test_http_connection():
    """Test basic HTTP connection to verify server is reachable"""
    
    import aiohttp
    
    log("Testing HTTP connection to server...")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test HTTPS connection
            https_url = "https://smart-cctv-rash32.chbk.app"
            
            async with session.get(https_url, ssl=False) as response:
                log(f"HTTP Status: {response.status}")
                log(f"Server: {response.headers.get('Server', 'Unknown')}")
                
                if response.status == 200:
                    log("HTTP connection successful!", "SUCCESS")
                    return True
                else:
                    log(f"HTTP connection failed with status {response.status}", "ERROR")
                    return False
                    
    except Exception as e:
        log(f"HTTP connection test failed: {e}", "ERROR")
        return False

async def main():
    """Main test function"""
    
    log("=" * 50)
    log("ESP32CAM WebSocket Connection Test")
    log("=" * 50)
    
    # Test HTTP connection first
    http_success = await test_http_connection()
    
    if not http_success:
        log("HTTP connection failed. Server might be down.", "ERROR")
        return
    
    # Test WebSocket connection
    ws_success = await test_websocket_connection()
    
    log("=" * 50)
    if ws_success:
        log("ALL TESTS PASSED! WebSocket connection is working.", "SUCCESS")
    else:
        log("WebSocket connection test failed.", "ERROR")
    log("=" * 50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("Test interrupted by user", "WARNING")
    except Exception as e:
        log(f"Test failed with error: {e}", "ERROR")
        sys.exit(1) 