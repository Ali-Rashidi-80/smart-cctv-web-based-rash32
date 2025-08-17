# رفع مشکل DNS Resolution در ESP32CAM

## مشکل
ESP32CAM نمی‌تواند به سرور WebSocket متصل شود و خطای زیر را نمایش می‌دهد:
```
[E][WiFiGeneric.cpp:1583] hostByName(): DNS Failed for smart-cctv-rash32.chbk.app:
[E][WiFiClient.cpp:320] setSocketOption(): fail on -1, errno: 9, "Bad file number"
```

## علت مشکل
1. **DNS Resolution**: ESP32 نمی‌تواند نام دامنه را به IP تبدیل کند
2. **DNS Server**: DNS پیش‌فرض شبکه ممکن است مشکل داشته باشد
3. **Network Configuration**: تنظیمات شبکه ممکن است محدودیت داشته باشد

## راه‌حل‌های اعمال شده

### 1. تنظیم DNS های جایگزین
```cpp
// تنظیمات DNS - جدید
const char* primary_dns = "8.8.8.8";     // Google DNS
const char* secondary_dns = "8.8.4.4";   // Google DNS Secondary
```

### 2. بهبود اتصال WiFi
```cpp
// اتصال به WiFi با تنظیمات DNS
WiFi.begin(ssid, password);

// تنظیم DNS قبل از اتصال
IPAddress primaryDNS;
IPAddress secondaryDNS;
if (primaryDNS.fromString(primary_dns) && secondaryDNS.fromString(secondary_dns)) {
  WiFi.setDNS(primaryDNS, secondaryDNS);
  sendLog("DNS configured: " + String(primary_dns) + ", " + String(secondary_dns), "info");
}
```

### 3. تست DNS Resolution
```cpp
// تست DNS resolution
IPAddress serverIP;
if (WiFi.hostByName(websocket_server, serverIP, 10000)) {
  sendLog("DNS resolution successful: " + websocket_server + " -> " + serverIP.toString(), "info");
} else {
  sendLog("DNS resolution failed for: " + String(websocket_server), "error");
  // تلاش با DNS های جایگزین
  WiFi.setDNS(IPAddress(1, 1, 1, 1), IPAddress(1, 0, 0, 1)); // Cloudflare DNS
  delay(2000);
  if (WiFi.hostByName(websocket_server, serverIP, 10000)) {
    sendLog("DNS resolution successful with Cloudflare DNS", "info");
  } else {
    sendLog("DNS resolution failed with all DNS servers", "error");
  }
}
```

### 4. اتصال با IP مستقیم
```cpp
// حل DNS و اتصال با IP مستقیم
IPAddress serverIP;
bool dnsResolved = false;

// تلاش با DNS های مختلف
const char* dnsServers[] = {"8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1"};

for (int i = 0; i < 4; i++) {
  IPAddress dnsIP;
  if (dnsIP.fromString(dnsServers[i])) {
    WiFi.setDNS(dnsIP);
    sendLog("Trying DNS: " + String(dnsServers[i]), "info");
    delay(1000);
    
    if (WiFi.hostByName(websocket_server, serverIP, 10000)) {
      sendLog("DNS resolution successful with " + String(dnsServers[i]) + ": " + serverIP.toString(), "info");
      dnsResolved = true;
      break;
    }
  }
}
```

### 5. اضافه کردن Host Header
```cpp
// تنظیم headers برای احراز هویت - اصلاح شده
client.addHeader("Authorization", "Bearer " + String(AUTH_TOKEN));
client.addHeader("Host", websocket_server); // اضافه کردن Host header
```

## DNS های پیشنهادی
1. **Google DNS**: 8.8.8.8, 8.8.4.4
2. **Cloudflare DNS**: 1.1.1.1, 1.0.0.1
3. **OpenDNS**: 208.67.222.222, 208.67.220.220

## تست اتصال
برای تست اتصال، فایل `test_connection_simple.cpp` را کامپایل و اجرا کنید:
```bash
pio run -t upload -e esp32cam
pio device monitor
```

## نکات مهم
1. **Timeout**: برای DNS resolution از timeout 10 ثانیه استفاده کنید
2. **Retry Logic**: در صورت شکست، با DNS های مختلف تلاش کنید
3. **IP Caching**: IP حل شده را ذخیره کنید تا از DNS resolution مکرر جلوگیری کنید
4. **Network Stability**: اطمینان حاصل کنید که شبکه WiFi پایدار است

## عیب‌یابی
اگر همچنان مشکل دارید:
1. **Router DNS**: DNS روتر خود را بررسی کنید
2. **Firewall**: فایروال شبکه را بررسی کنید
3. **Network Restrictions**: محدودیت‌های شبکه را بررسی کنید
4. **Alternative Networks**: از شبکه WiFi دیگری تست کنید 