#include <WiFi.h>
#include <ArduinoWebsockets.h>
#include <ArduinoJson.h>

using namespace websockets;

// اطلاعات شبکه و سرور
const char* ssid = "SAMSUNG";      
const char* password = "panzer790"; 
const char* websocket_server = "smart-cctv-rash32.chbk.app"; 
const uint16_t websocket_port = 443; 
const char* websocket_path = "/ws/esp32cam";

// تنظیمات احراز هویت - اصلاح شده
const char* AUTH_TOKEN = "esp32cam_secure_token_2024";

WebsocketsClient client;
bool isConnected = false;
bool isAuthenticated = false;

void onEventsCallback(WebsocketsEvent event, String data) {
  if (event == WebsocketsEvent::ConnectionOpened) {
    Serial.println("WebSocket connection opened");
    isConnected = true;
    isAuthenticated = false;
  } else if (event == WebsocketsEvent::ConnectionClosed) {
    Serial.println("WebSocket connection closed");
    isConnected = false;
    isAuthenticated = false;
  } else if (event == WebsocketsEvent::GotPing) {
    Serial.println("Received Ping");
    client.pong();
  } else if (event == WebsocketsEvent::GotPong) {
    Serial.println("Received Pong");
  } else {
    // Handle text messages
    if (data.length() > 0) {
      Serial.println("Received message: " + data);
      if (!isAuthenticated) {
        if (data.indexOf("connection_ack") != -1) {
          isAuthenticated = true;
          Serial.println("Authentication successful!");
          // Send device info
          String deviceInfo = "{\"type\":\"device_info\",\"device\":\"esp32cam\",\"version\":\"1.0\"}";
          client.send(deviceInfo);
        }
      }
    }
  }
}

void connectWebSocket() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected!");
    return;
  }

  Serial.println("Connecting to WebSocket...");
  
  // Set authorization header
  client.addHeader("Authorization", "Bearer " + String(AUTH_TOKEN));
  
  String url = String("wss://") + websocket_server + websocket_path;
  if (client.connect(url)) {
    Serial.println("WebSocket connected!");
    isConnected = true;
    isAuthenticated = false;
  } else {
    Serial.println("WebSocket connection failed!");
    isConnected = false;
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("ESP32CAM WebSocket Test Starting...");
  
  // Connect to WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
  
  // Set WebSocket callback
  client.onEvent(onEventsCallback);
  
  // Connect to WebSocket
  connectWebSocket();
  
  Serial.println("Setup complete");
}

void loop() {
  client.poll();

  if (!isConnected) {
    Serial.println("Reconnecting...");
    connectWebSocket();
    delay(5000);
    return;
  }

  // Send heartbeat every 10 seconds
  static unsigned long lastHeartbeat = 0;
  if (millis() - lastHeartbeat > 10000) {
    if (isAuthenticated) {
      String heartbeat = "{\"type\":\"heartbeat\",\"timestamp\":\"" + String(millis()) + "\"}";
      client.send(heartbeat);
      Serial.println("Heartbeat sent");
    }
    lastHeartbeat = millis();
  }

  delay(100);
} 