# ESP32CAM Comprehensive Fixes and Improvements

## تحلیل مشکلات اصلی و راه‌حل‌ها

### 1. **مشکل احراز هویت (Authentication Issue)**

**مشکل:**
- ESP32CAM از `AUTH_HEADER` استفاده می‌کرد که فرمت صحیح نبود
- سرور انتظار `Authorization: Bearer token` داشت
- عدم تطابق در پروتکل احراز هویت

**راه‌حل:**
```cpp
// قبل از اصلاح
const char* AUTH_HEADER = "Authorization: Bearer esp32cam_secure_token_2024";
client.addHeader("Authorization", AUTH_HEADER);

// بعد از اصلاح
const char* AUTH_TOKEN = "esp32cam_secure_token_2024";
client.addHeader("Authorization", "Bearer " + String(AUTH_TOKEN));
```

### 2. **مشکل پروتکل WebSocket**

**مشکل:**
- عدم مدیریت صحیح احراز هویت
- عدم ارسال ping/pong
- عدم مدیریت timeout

**راه‌حل:**
```cpp
// اضافه کردن متغیرهای جدید
bool isAuthenticated = false;
unsigned long authTimeout = 0;
const unsigned long authTimeoutDuration = 10000;
unsigned long lastPingTime = 0;
const unsigned long pingInterval = 30000;
unsigned long lastHeartbeatTime = 0;
const unsigned long heartbeatInterval = 10000;

// مدیریت احراز هویت
if (!isAuthenticated) {
  if (data.indexOf("connection_ack") != -1) {
    isAuthenticated = true;
    sendLog("Authentication successful");
  } else if (millis() - authTimeout > authTimeoutDuration) {
    sendLog("Authentication timeout", "error");
    client.close();
    return;
  }
}
```

### 3. **مشکل مدیریت حافظه**

**مشکل:**
- Memory leaks در `last_captured_fb`
- عدم آزادسازی صحیح حافظه
- عدم مدیریت fragmentation

**راه‌حل:**
```cpp
// حذف متغیر مشکل‌ساز
// camera_fb_t* last_captured_fb = nullptr; // حذف شد

// آزادسازی صحیح حافظه
esp_camera_fb_return(fb);

// بررسی fragmentation
size_t largestFreeBlock = heap_caps_get_largest_free_block(MALLOC_CAP_8BIT);
if (largestFreeBlock < 10000) {
  sendLog("Memory fragmentation detected", "warning");
  client.send("{\"type\":\"system_warning\",\"message\":\"Memory fragmentation detected\"}");
}
```

### 4. **مشکل پایداری اتصال**

**مشکل:**
- عدم ارسال heartbeat
- عدم مدیریت reconnect صحیح
- عدم timeout برای احراز هویت

**راه‌حل:**
```cpp
// ارسال heartbeat
void sendHeartbeat() {
  if (isConnected && isAuthenticated) {
    String heartbeat = "{\"type\":\"heartbeat\",\"timestamp\":\"" + String(millis()) + "\",\"fps\":" + String(fps, 2) + ",\"memory\":" + String(ESP.getFreeHeap()) + "}";
    client.send(heartbeat);
  }
}

// ارسال ping
void sendPing() {
  if (isConnected && isAuthenticated) {
    client.ping();
    lastPingTime = millis();
  }
}

// افزایش تعداد تلاش‌های reconnect
const int maxReconnectAttempts = 5; // از 3 به 5 افزایش یافت
```

### 5. **مشکل پردازش فریم**

**مشکل:**
- عدم ارسال metadata صحیح
- عدم تطابق با انتظارات سرور
- عدم مدیریت خطاهای فریم

**راه‌حل:**
```cpp
// ارسال metadata قبل از فریم
String frameMetadata = "{\"type\":\"frame_metadata\",\"size\":" + String(fb->len) + ",\"format\":\"jpeg\",\"timestamp\":\"" + String(millis()) + "\"}";
client.send(frameMetadata);

// ارسال metadata برای عکس دستی
String photoMetadata = "{\"type\":\"photo_data\",\"size\":" + String(fb->len) + ",\"format\":\"jpeg\",\"timestamp\":\"" + String(millis()) + "\"}";
client.send(photoMetadata);
```

### 6. **بهبودهای اضافی**

#### **لاگینگ بهتر:**
```cpp
void sendLog(const String& message, const String& log_type = "info") {
  if (isConnected && isAuthenticated) {
    String json = "{\"type\":\"log\",\"message\":\"" + message + "\",\"log_type\":\"" + log_type + "\",\"timestamp\":\"" + String(millis()) + "\"}";
    client.send(json);
  }
  Serial.println("[" + log_type.toUpperCase() + "] " + message);
}
```

#### **مدیریت خطاهای بهتر:**
```cpp
// بررسی احراز هویت timeout
if (isConnected && !isAuthenticated && (millis() - authTimeout > authTimeoutDuration)) {
  sendLog("Authentication timeout, reconnecting...", "error");
  client.close();
  isConnected = false;
  delay(1000);
  return;
}
```

#### **ارسال اطلاعات دستگاه:**
```cpp
// ارسال پیام اولیه بعد از احراز هویت
String initialMessage = "{\"type\":\"device_info\",\"device\":\"esp32cam\",\"version\":\"1.0\",\"capabilities\":[\"photo\",\"flash\",\"stream\"]}";
client.send(initialMessage);
```

## تغییرات کلیدی

### **متغیرهای جدید اضافه شده:**
- `isAuthenticated`: وضعیت احراز هویت
- `authTimeout`: زمان timeout احراز هویت
- `lastPingTime`: زمان آخرین ping
- `lastHeartbeatTime`: زمان آخرین heartbeat
- `pingInterval`: فاصله زمانی ping
- `heartbeatInterval`: فاصله زمانی heartbeat

### **توابع جدید:**
- `sendHeartbeat()`: ارسال heartbeat به سرور
- `sendPing()`: ارسال ping به سرور

### **بهبودهای امنیتی:**
- احراز هویت صحیح با Bearer token
- timeout برای احراز هویت
- بررسی وضعیت اتصال قبل از ارسال داده

### **بهبودهای پایداری:**
- افزایش تعداد تلاش‌های reconnect
- مدیریت بهتر حافظه
- ارسال heartbeat و ping منظم
- بررسی fragmentation حافظه

### **بهبودهای عملکرد:**
- ارسال metadata صحیح
- مدیریت بهتر خطاها
- لاگینگ بهتر
- کنترل نرخ فریم بهبود یافته

## نحوه استفاده

1. **کامپایل و آپلود کد:**
   ```bash
   # در PlatformIO
   pio run --target upload
   ```

2. **بررسی لاگ‌ها:**
   - لاگ‌ها در Serial Monitor نمایش داده می‌شوند
   - لاگ‌ها به سرور نیز ارسال می‌شوند

3. **بررسی وضعیت اتصال:**
   - ESP32CAM پیام‌های heartbeat ارسال می‌کند
   - وضعیت احراز هویت در لاگ‌ها قابل مشاهده است

## تست و تأیید

### **تست احراز هویت:**
- ESP32CAM باید پیام "Authentication successful" را نمایش دهد
- سرور باید اتصال را تأیید کند

### **تست پایداری:**
- ESP32CAM باید heartbeat منظم ارسال کند
- اتصال باید پایدار باشد

### **تست عملکرد:**
- فریم‌ها باید با metadata صحیح ارسال شوند
- عکس‌های دستی باید به درستی کار کنند

## نکات مهم

1. **تنظیمات شبکه:** مطمئن شوید که SSID و password صحیح هستند
2. **تنظیمات سرور:** مطمئن شوید که آدرس سرور و پورت صحیح هستند
3. **احراز هویت:** مطمئن شوید که AUTH_TOKEN با سرور مطابقت دارد
4. **حافظه:** ESP32CAM حافظه محدودی دارد، مراقب memory leaks باشید

## عیب‌یابی

### **مشکل اتصال:**
- بررسی تنظیمات WiFi
- بررسی آدرس سرور
- بررسی پورت

### **مشکل احراز هویت:**
- بررسی AUTH_TOKEN
- بررسی لاگ‌های سرور
- بررسی timeout

### **مشکل حافظه:**
- بررسی لاگ‌های حافظه
- بررسی fragmentation
- restart دوربین در صورت نیاز

## نتیجه‌گیری

این تغییرات باعث بهبود قابل توجهی در پایداری، امنیت و عملکرد ESP32CAM می‌شود. مشکلات اصلی احراز هویت، مدیریت حافظه و پایداری اتصال حل شده‌اند. 