# ESP32CAM WebSocket Connection Fix

## Problem
The ESP32CAM was getting a 502 Bad Gateway error when trying to connect to the WebSocket server. The issue was that the code was configured to connect to the wrong server.

## Root Cause
- **Old Configuration**: `services.gen6.chabokan.net:3000` (non-secure)
- **Correct Configuration**: `smart-cctv-rash32.chbk.app:443` (secure WSS)

## Changes Made

### 1. Updated Server Configuration in `src/main.cpp`
```cpp
// OLD (incorrect)
const char* websocket_server = "services.gen6.chabokan.net"; 
const uint16_t websocket_port = 3000; 

// NEW (correct)
const char* websocket_server = "smart-cctv-rash32.chbk.app"; 
const uint16_t websocket_port = 443; 
```

### 2. Updated WebSocket Protocol
```cpp
// OLD (non-secure)
String url = String("ws://") + websocket_server + ":" + String(websocket_port) + websocket_path;

// NEW (secure)
String url = String("wss://") + websocket_server + websocket_path;
```

### 3. Updated Connection Method
```cpp
// OLD
if (client.connect(websocket_server, websocket_port, websocket_path)) {

// NEW
if (client.connect(websocket_server, websocket_port, websocket_path, "wss")) {
```

### 4. Updated Test Files
- Updated `test_connection.cpp` with correct server configuration
- Updated `src/main_fixed.cpp` with correct server configuration

## Testing the Connection

### Method 1: HTML Test Page
1. Open `test_websocket_connection.html` in a web browser
2. Click "Connect" to test the WebSocket connection
3. Check the log for connection status and any errors

### Method 2: Python Test Script
1. Install required packages:
   ```bash
   pip install websockets aiohttp
   ```
2. Run the test script:
   ```bash
   python test_websocket.py
   ```

### Method 3: ESP32CAM Test
1. Upload the updated code to your ESP32CAM
2. Monitor the Serial output for connection status
3. Look for these success messages:
   ```
   [INFO] Connecting to wss://smart-cctv-rash32.chbk.app/ws/esp32cam
   [INFO] WebSocket connected!
   [INFO] Authentication successful
   ```

## Expected Behavior

### Successful Connection
- WebSocket connects to `wss://smart-cctv-rash32.chbk.app/ws/esp32cam`
- Authentication with token `esp32cam_secure_token_2024` succeeds
- Camera starts streaming frames
- Heartbeat messages are sent regularly

### Error Handling
- Automatic reconnection on connection loss
- Deep sleep mode if connection fails repeatedly
- Memory management and error recovery

## Troubleshooting

### If Still Getting 502 Error
1. **Check Server Status**: Verify `smart-cctv-rash32.chbk.app` is accessible
2. **Check SSL Certificate**: Ensure the server has valid SSL certificates
3. **Check WebSocket Endpoint**: Verify `/ws/esp32cam` endpoint exists
4. **Check Authorization**: Ensure the token `esp32cam_secure_token_2024` is valid

### Common Issues
1. **SSL Certificate Issues**: The ESP32CAM might have trouble with certain SSL certificates
2. **Network Issues**: WiFi connectivity problems
3. **Server Configuration**: WebSocket endpoint might not be properly configured
4. **Authentication**: Token might be expired or invalid

### Debug Steps
1. Test with the HTML page first to verify server accessibility
2. Test with Python script to verify WebSocket functionality
3. Check ESP32CAM Serial output for detailed error messages
4. Verify WiFi connection and signal strength

## Configuration Summary

| Setting | Value |
|---------|-------|
| Server | `smart-cctv-rash32.chbk.app` |
| Port | `443` |
| Protocol | `wss://` (secure WebSocket) |
| Path | `/ws/esp32cam` |
| Auth Token | `esp32cam_secure_token_2024` |
| WiFi SSID | `SAMSUNG` |
| WiFi Password | `panzer790` |

## Next Steps
1. Upload the updated code to your ESP32CAM
2. Test the connection using the provided test tools
3. Monitor the Serial output for any remaining issues
4. If problems persist, check server logs and network configuration 