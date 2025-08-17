#include "esp_camera.h"
#include <WiFi.h>
// Disable compression to avoid potential issues
// #define WEBSOCKETS_USE_COMPRESSION 1
#include <ArduinoWebsockets.h>
#include <nvs_flash.h>
#include <ArduinoJson.h>

using namespace websockets;

// اطلاعات شبکه و سرور وب‌سوکت
const char* ssid = "SAMSUNG";      // SSID شبکه Wi-Fi
const char* password = "panzer790"; // رمز عبور شبکه Wi-Fi
const char* websocket_server = "services.gen6.chabokan.net"; // آدرس سرور
const uint16_t websocket_port = 26852; // پورت WebSocket
const char* websocket_path = "/ws";

// تنظیمات احراز هویت - اصلاح شده
const char* AUTH_TOKEN = "esp32cam_secure_token_2024";


// پین‌های مربوط به دوربین (مدل AI-THINKER)
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22
#define FLASH_GPIO_NUM     4 // پین فلاش LED (PWM)

// تنظیمات PWM برای فلاش
#define FLASH_PWM_CHANNEL  1
#define FLASH_PWM_FREQ     1000
#define FLASH_PWM_RESOLUTION 8
#define MAX_FLASH_DUTY     230 // 90% از 255

// متغیرهای برنامه - بهبود یافته
WebsocketsClient client;
bool isConnected = false;

// متغیرهای مانیتورینگ نرخ فریم
unsigned long lastFrameTime = 0;
unsigned long frameCount = 0;
float fps = 0;

// متغیرهای heartbeat و اتصال
unsigned long lastHeartbeat = 0;
const unsigned long HEARTBEAT_INTERVAL = 30000; // 30 ثانیه
unsigned long connectionAttempts = 0;
const unsigned long MAX_CONNECTION_ATTEMPTS = 5;

// تابع ارسال لاگ
void sendLog(String message) {
  Serial.println(message);
  // ارسال لاگ به سرور در صورت اتصال با فرمت JSON
  if (isConnected) {
    String logJson = "{\"type\":\"log\",\"message\":\"" + message + "\"}";
    client.send(logJson);
  }
}

// callback برای رویدادهای وب‌سوکت
void onEventsCallback(WebsocketsEvent event, String data) {
  if (event == WebsocketsEvent::ConnectionOpened) {
    sendLog("Connection opened");
    isConnected = true;
  } else if (event == WebsocketsEvent::ConnectionClosed) {
    sendLog("Connection closed");
    isConnected = false;
  }
}

// تابع اتصال به وب‌سوکت با احراز هویت
void connectWebSocket() {
  String url = String("ws://") + websocket_server + ":" + String(websocket_port) + websocket_path;
  Serial.print("Connecting to ");
  Serial.println(url);
  Serial.print("Using token: ");
  Serial.println(AUTH_TOKEN);
  
  // تنظیم headers برای احراز هویت
  client.addHeader("Authorization", "Bearer " + String(AUTH_TOKEN));
  client.addHeader("X-Device-Type", "ESP32CAM");
  client.addHeader("X-Device-ID", WiFi.macAddress());
  client.addHeader("X-Device-Version", "1.0.0");
  client.addHeader("X-Connection-Type", "WebSocket");
  
  if (client.connect(websocket_server, websocket_port, websocket_path)) {
    Serial.println("WebSocket connected successfully!");
    isConnected = true;
    
    // ارسال پیام اتصال موفق
    String connectMsg = "{\"type\":\"connection\",\"status\":\"connected\",\"device\":\"ESP32CAM\",\"token\":\"" + String(AUTH_TOKEN) + "\"}";
    client.send(connectMsg);
  } else {
    Serial.println("WebSocket connection failed.");
    isConnected = false;
  }
}

void setup() {
  Serial.begin(9600);
  Serial.println();

  // پیکربندی دوربین
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // تنظیم کیفیت تصویر
  if (psramFound()) {
    config.frame_size = FRAMESIZE_SVGA; 
    config.jpeg_quality = 15; // کیفیت متوسط برای تعادل بین حجم و کیفیت
    config.fb_count = 2; // بافر دوگانه برای پایداری
  } else {
    config.frame_size = FRAMESIZE_QVGA; // 320x240
    config.jpeg_quality = 15;
    config.fb_count = 1; // بافر تک برای دستگاه‌های بدون PSRAM
  }

  // مقداردهی اولیه دوربین
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  // تنظیمات اضافی دوربین
  sensor_t *s = esp_camera_sensor_get();
  s->set_brightness(s, 0); // روشنایی
  s->set_contrast(s, 0);   // کنتراست
  s->set_saturation(s, 0); // اشباع
  s->set_vflip(s, 0);      // چرخش عمودی
  s->set_hmirror(s, 1);    // چرخش افقی

  // اتصال به شبکه WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.println("WiFi connected");
  Serial.print("ESP32-CAM IP: ");
  Serial.println(WiFi.localIP());

  // تنظیم callback برای رویدادهای وب‌سوکت
  client.onEvent(onEventsCallback);
  
  // اتصال به وب‌سوکت سرور
  connectWebSocket();
  
  sendLog("ESP32CAM initialized successfully");
}

void loop() {
  // پردازش رویدادهای وب‌سوکت
  client.poll();

  // در صورت عدم اتصال، تلاش مجدد برای اتصال
  if (!isConnected) {
    if (connectionAttempts < MAX_CONNECTION_ATTEMPTS) {
      sendLog("Attempting to reconnect... (Attempt " + String(connectionAttempts + 1) + "/" + String(MAX_CONNECTION_ATTEMPTS) + ")");
      connectWebSocket();
      connectionAttempts++;
      delay(5000);
    } else {
      sendLog("Max reconnection attempts reached. Waiting longer before retry...");
      connectionAttempts = 0;
      delay(30000); // 30 ثانیه انتظار
    }
    return;
  }
  
  // Reset connection attempts on successful connection
  connectionAttempts = 0;
  
  // ارسال heartbeat
  unsigned long currentTime = millis();
  if (currentTime - lastHeartbeat >= HEARTBEAT_INTERVAL) {
    String heartbeat = "{\"type\":\"heartbeat\",\"timestamp\":" + String(currentTime) + ",\"device\":\"ESP32CAM\"}";
    client.send(heartbeat);
    lastHeartbeat = currentTime;
  }

  // گرفتن فریم از دوربین
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed");
    return;
  }

  // ارسال داده فریم (به صورت باینری) از طریق وب‌سوکت
  if (isConnected) {
    // ارسال metadata قبل از فریم با اطلاعات بیشتر
    String metadata = "{\"type\":\"frame\",\"size\":" + String(fb->len) + 
                     ",\"width\":" + String(fb->width) + 
                     ",\"height\":" + String(fb->height) + 
                     ",\"timestamp\":" + String(millis()) + 
                     ",\"fps\":" + String(fps, 2) + 
                     ",\"device\":\"ESP32CAM\"}";
    client.send(metadata);
    
    // ارسال فریم تصویر
    client.sendBinary((const char*)fb->buf, fb->len);
  }

  // آزادسازی بافر
  esp_camera_fb_return(fb);

  // محاسبه نرخ فریم
  frameCount++;
  if (currentTime - lastFrameTime >= 1000) {
    fps = frameCount * 1000.0 / (currentTime - lastFrameTime);
    sendLog("FPS: " + String(fps, 2));
    frameCount = 0;
    lastFrameTime = currentTime;
  }

  // کنترل نرخ فریم (هدف: 30 FPS)
  unsigned long frameDuration = 33; // 33 میلی‌ثانیه برای 30 FPS
  unsigned long elapsed = millis() - (currentTime - frameDuration);
  if (elapsed < frameDuration) {
    delay(frameDuration - elapsed); // تأخیر باقی‌مانده
  }
}