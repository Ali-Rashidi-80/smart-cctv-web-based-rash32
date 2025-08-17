#include "esp_camera.h"
#include <WiFi.h>
#include <ArduinoWebsockets.h>
#include <ArduinoJson.h>

using namespace websockets;

// تست تنظیمات شبکه
const char* test_ssid = "SAMSUNG";      
const char* test_password = "panzer790"; 
const char* test_server = "smart-cctv-rash32.chbk.app"; 
const uint16_t test_port = 443; 
const char* test_path = "/ws/esp32cam";
const char* test_token = "esp32cam_secure_token_2024";

// متغیرهای تست
WebsocketsClient test_client;
bool test_connected = false;
bool test_authenticated = false;
unsigned long test_start_time = 0;
int test_attempts = 0;
const int max_test_attempts = 3;

// تابع تست اتصال WiFi
bool testWiFiConnection() {
  Serial.println("=== Testing WiFi Connection ===");
  
  WiFi.begin(test_ssid, test_password);
  unsigned long start_time = millis();
  
  while (WiFi.status() != WL_CONNECTED && (millis() - start_time) < 10000) {
    delay(500);
    Serial.print(".");
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected successfully!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal strength: ");
    Serial.println(WiFi.RSSI());
    return true;
  } else {
    Serial.println("\nWiFi connection failed!");
    return false;
  }
}

// تابع تست اتصال WebSocket
bool testWebSocketConnection() {
  Serial.println("=== Testing WebSocket Connection ===");
  
  test_client.addHeader("Authorization", "Bearer " + String(test_token));
  
  String test_url = String("wss://") + test_server + test_path;
  if (test_client.connect(test_url)) {
    Serial.println("WebSocket connected successfully!");
    test_connected = true;
    return true;
  } else {
    Serial.println("WebSocket connection failed!");
    return false;
  }
}

// تابع تست احراز هویت
bool testAuthentication() {
  Serial.println("=== Testing Authentication ===");
  
  if (!test_connected) {
    Serial.println("WebSocket not connected!");
    return false;
  }
  
  // ارسال پیام تست
  String test_message = "{\"type\":\"test\",\"message\":\"authentication_test\"}";
  test_client.send(test_message);
  
  // منتظر پاسخ
  unsigned long start_time = millis();
  while ((millis() - start_time) < 5000) {
    test_client.poll();
    delay(100);
  }
  
  if (test_authenticated) {
    Serial.println("Authentication successful!");
    return true;
  } else {
    Serial.println("Authentication failed!");
    return false;
  }
}

// تابع تست دوربین
bool testCamera() {
  Serial.println("=== Testing Camera ===");
  
  // راه‌اندازی دوربین
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = 5;
  config.pin_d1 = 18;
  config.pin_d2 = 19;
  config.pin_d3 = 21;
  config.pin_d4 = 36;
  config.pin_d5 = 39;
  config.pin_d6 = 34;
  config.pin_d7 = 35;
  config.pin_xclk = 0;
  config.pin_pclk = 22;
  config.pin_vsync = 25;
  config.pin_href = 23;
  config.pin_sccb_sda = 26;
  config.pin_sccb_scl = 27;
  config.pin_pwdn = 32;
  config.pin_reset = -1;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 80;
  config.fb_count = 2;
  
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    return false;
  }
  
  Serial.println("Camera initialized successfully!");
  
  // تست گرفتن فریم
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Failed to capture frame!");
    return false;
  }
  
  Serial.printf("Frame captured: %dx%d %db\n", fb->width, fb->height, fb->len);
  esp_camera_fb_return(fb);
  
  return true;
}

// تابع تست حافظه
void testMemory() {
  Serial.println("=== Testing Memory ===");
  
  size_t free_heap = ESP.getFreeHeap();
  size_t free_internal = heap_caps_get_free_size(MALLOC_CAP_8BIT);
  size_t largest_block = heap_caps_get_largest_free_block(MALLOC_CAP_8BIT);
  
  Serial.printf("Free heap: %d bytes\n", free_heap);
  Serial.printf("Free internal: %d bytes\n", free_internal);
  Serial.printf("Largest free block: %d bytes\n", largest_block);
  
  if (free_heap < 50000) {
    Serial.println("WARNING: Low heap memory!");
  }
  
  if (largest_block < 10000) {
    Serial.println("WARNING: Memory fragmentation detected!");
  }
}

// تابع تست عملکرد
void testPerformance() {
  Serial.println("=== Testing Performance ===");
  
  unsigned long start_time = millis();
  int frame_count = 0;
  
  // تست گرفتن 10 فریم
  for (int i = 0; i < 10; i++) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (fb) {
      frame_count++;
      esp_camera_fb_return(fb);
    }
    delay(100);
  }
  
  unsigned long end_time = millis();
  float fps = (frame_count * 1000.0) / (end_time - start_time);
  
  Serial.printf("Captured %d frames in %d ms\n", frame_count, end_time - start_time);
  Serial.printf("Average FPS: %.2f\n", fps);
}

// callback برای تست WebSocket
void onTestEventsCallback(WebsocketsEvent event, String data) {
  if (event == WebsocketsEvent::ConnectionOpened) {
    Serial.println("Test WebSocket connection opened");
  } else if (event == WebsocketsEvent::ConnectionClosed) {
    Serial.println("Test WebSocket connection closed");
    test_connected = false;
    test_authenticated = false;
  } else {
    // Handle text messages (data contains the message)
    if (data.length() > 0) {
      Serial.println("Received: " + data);
      if (data.indexOf("connection_ack") != -1) {
        test_authenticated = true;
      }
    }
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("ESP32CAM Connection Test Starting...");
  
  // تنظیم callback
  test_client.onEvent(onTestEventsCallback);
  
  // اجرای تست‌ها
  bool all_tests_passed = true;
  
  // تست WiFi
  if (!testWiFiConnection()) {
    all_tests_passed = false;
  }
  
  // تست WebSocket
  if (!testWebSocketConnection()) {
    all_tests_passed = false;
  }
  
  // تست احراز هویت
  if (!testAuthentication()) {
    all_tests_passed = false;
  }
  
  // تست دوربین
  if (!testCamera()) {
    all_tests_passed = false;
  }
  
  // تست حافظه
  testMemory();
  
  // تست عملکرد
  testPerformance();
  
  // نتیجه نهایی
  Serial.println("=== Test Results ===");
  if (all_tests_passed) {
    Serial.println("ALL TESTS PASSED! ESP32CAM is ready for production.");
  } else {
    Serial.println("SOME TESTS FAILED! Please check the issues above.");
  }
  
  // بستن اتصال
  if (test_connected) {
    test_client.close();
  }
}

void loop() {
  // تست کامل شده، فقط منتظر
  delay(1000);
} 