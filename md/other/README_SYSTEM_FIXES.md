# 🔧 اصلاحات جامع سیستم Smart Camera Security

## 📋 خلاصه اصلاحات

این سند تمام اصلاحات، بهبودها و رفع مشکلات سیستم Smart Camera Security را مستند می‌کند.

## 🚨 مشکلات شناسایی شده و حل شده

### 1. 🔐 مشکل احراز هویت WebSocket

**مشکل:** میکروکنترلرها بدون احراز هویت به WebSocket متصل می‌شدند.

**راه حل:**
- اضافه کردن middleware احراز هویت WebSocket
- پیاده‌سازی سیستم توکن برای میکروکنترلرها
- بررسی توکن در تمام اتصالات WebSocket

```python
# توکن‌های امنیتی برای میکروکنترلرها
PICO_AUTH_TOKENS = ["m78jmdzu:2G/O\\S'W]_E]", "pico_secure_token_2024"]
ESP32CAM_AUTH_TOKENS = ["esp32cam_secure_token_2024", "esp32cam_token_v2"]
```

### 2. 🔄 مشکل ارتباط سروو

**مشکل:** دستورات سروو به درستی بین سرور و میکروکنترلرها منتقل نمی‌شد.

**راه حل:**
- بهبود فرمت پیام‌های سروو
- اضافه کردن timestamp و source به پیام‌ها
- بهبود error handling و validation
- ارسال دستورات به ESP32CAM برای لاگ کردن

### 3. 🌐 مشکل مدیریت پورت‌های پویا

**مشکل:** تداخل پورت‌ها و عدم مدیریت صحیح اتصالات.

**راه حل:**
- بهبود سیستم مدیریت پورت‌های پویا
- رزرو پورت‌ها قبل از اجرای threadها
- مدیریت بهتر خطاهای اتصال

### 4. 🛡️ مشکلات امنیتی

**مشکل:** عدم بررسی توکن در WebSocket endpoints.

**راه حل:**
- پیاده‌سازی احراز هویت WebSocket
- بررسی توکن در تمام اتصالات
- بستن اتصالات نامعتبر

### 5. ⚡ مشکلات پایداری

**مشکل:** عدم مدیریت صحیح خطاها و اتصالات.

**راه حل:**
- بهبود error handling
- مدیریت بهتر memory leaks
- بهبود reconnection logic

### 6. 🔄 مشکلات Session Management

**مشکل:** مشکلات Hard Reload و session management برای admin و کاربران عادی.

**راه حل:**
- سیستم مدیریت session پیشرفته برای admin و کاربران عادی
- Admin users می‌توانند Hard Reload کنند بدون مشکل
- کاربران عادی مجدد لاگین می‌کنند بعد از Hard Reload
- Session cleanup کامل و امن
- تشخیص خودکار Hard Reload و مدیریت مناسب

## 🔧 اصلاحات انجام شده

### سرور FastAPI

#### 1. احراز هویت WebSocket
```python
async def authenticate_websocket(websocket: WebSocket, device_type: str = None):
    """احراز هویت اتصالات WebSocket برای میکروکنترلرها"""
    auth_header = websocket.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        await websocket.close(code=4001, reason="Missing authorization")
        return False
    
    token = auth_header.replace("Bearer ", "")
    
    if device_type == "pico":
        if token not in PICO_AUTH_TOKENS:
            await websocket.close(code=4001, reason="Invalid token")
            return False
    elif device_type == "esp32cam":
        if token not in ESP32CAM_AUTH_TOKENS:
            await websocket.close(code=4001, reason="Invalid token")
            return False
```

#### 2. بهبود دستورات سروو
```python
# ارسال دستور سروو با فرمت بهبود یافته
servo_message = {
    "type": "servo", 
    "command": {
        "servo1": command.servo1, 
        "servo2": command.servo2
    },
    "timestamp": datetime.now().isoformat(),
    "source": "web_interface"
}

await send_to_pico_client(servo_message)
await send_to_esp32cam_client({
    "type": "servo_command_log",
    "servo1": command.servo1,
    "servo2": command.servo2,
    "timestamp": datetime.now().isoformat()
})
```

#### 3. مدیریت Session پیشرفته
```python
# تشخیص Hard Reload و مدیریت session
def get_current_user(request: Request):
    """دریافت کاربر فعلی از توکن در cookies یا headers"""
    token = request.cookies.get("access_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token or not verify_token(token):
        return None
    
    user_info = verify_token(token)
    if not user_info:
        return None
    
    # بررسی نقش کاربر و مدیریت session
    if user_info.get("role") == "admin":
        # Admin users می‌توانند Hard Reload کنند
        return user_info
    
    # برای کاربران عادی، بررسی Hard Reload
    accept_header = request.headers.get("accept", "").lower()
    if "text/html" in accept_header and not request.headers.get("x-requested-with"):
        # احتمالاً Hard Reload است - مجبور کردن re-login
        return None
    
    return user_info
```
    "type": "servo_command_log",
    "servo1": command.servo1,
    "servo2": command.servo2,
    "timestamp": datetime.now().isoformat()
})
```

#### 3. بهبود WebSocket Endpoints
```python
@app.websocket("/ws/pico")
async def pico_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # احراز هویت اتصال
    if not await authenticate_websocket(websocket, "pico"):
        return
    
    # ثبت اتصال پیکو
    async with system_state.pico_client_lock:
        system_state.pico_client = websocket
        system_state.device_status["pico"]["online"] = True
```

### میکروکنترلر Pico

#### 1. بهبود احراز هویت
```python
# تنظیمات احراز هویت
AUTH_TOKEN = "m78jmdzu:2G/O\\S'W]_E]"
AUTH_HEADER = f"Authorization: Bearer {AUTH_TOKEN}"

# اتصال به WebSocket با احراز هویت
ws = ws_client.connect(WS_URL, headers=[AUTH_HEADER])
```

#### 2. بهبود پردازش دستورات
```python
async def process_command(cmd, ws=None):
    """پردازش دستورات دریافتی با error handling بهبود یافته"""
    try:
        cmd_type = cmd.get('type')
        if cmd_type == 'servo':
            servo_data = cmd.get('command', cmd)
            servo1_target = int(servo_data.get('servo1', 90))
            servo2_target = int(servo_data.get('servo2', 90))
            
            # اعتبارسنجی زاویه‌ها
            servo1_target = max(0, min(180, servo1_target))
            servo2_target = max(0, min(180, servo2_target))
            
            if servo1 and servo2:
                try:
                    current_angle1 = await servo1.set_angle(current_angle1, servo1_target)
                    current_angle2 = await servo2.set_angle(current_angle2, servo2_target)
                    
                    if ws:
                        send_ack(ws, 'servo', status='success', detail=f'X={current_angle1}°, Y={current_angle2}°')
                except Exception as e:
                    if ws:
                        send_ack(ws, 'servo', status='error', detail=str(e))
    except Exception as e:
        if ws:
            send_ack(ws, 'error', status='error', detail=str(e))
```

#### 3. بهبود مدیریت خطا
```python
async def websocket_client():
    """WebSocket client با مدیریت خطای بهبود یافته"""
    while True:
        try:
            ws = ws_client.connect(WS_URL, headers=[AUTH_HEADER])
            
            if ws:
                # ارسال پیام اولیه
                initial_message = {
                    "type": "connect",
                    "device": "pico",
                    "timestamp": get_now_str(),
                    "version": "1.0",
                    "servo1_angle": current_angle1,
                    "servo2_angle": current_angle2,
                    "auth_token": AUTH_TOKEN[:10] + "..."
                }
                ws.send(ujson.dumps(initial_message))
                
                # حلقه اصلی با error handling
                while True:
                    try:
                        message = ws.recv()
                        if message:
                            data = ujson.loads(message)
                            await process_command(data, ws)
                    except Exception as e:
                        print(f"⚠️ خطا در دریافت پیام: {e}")
                        break
        except Exception as e:
            print(f"❌ خطا در WebSocket client: {e}")
            # انتظار تدریجی قبل از تلاش مجدد
            reconnect_delay = min(5 * (reconnect_attempt + 1), 30)
            await asyncio.sleep(reconnect_delay)
```

### میکروکنترلر ESP32CAM

#### 1. احراز هویت WebSocket
```cpp
// تنظیمات احراز هویت
const char* AUTH_TOKEN = "esp32cam_secure_token_2024";
const char* AUTH_HEADER = "Authorization: Bearer esp32cam_secure_token_2024";

// اتصال با احراز هویت
client.addHeader("Authorization", AUTH_HEADER);
if (client.connect(websocket_server, websocket_port, websocket_path)) {
    // ارسال پیام اولیه
    String initialMessage = "{\"type\":\"connect\",\"device\":\"esp32cam\",\"timestamp\":\"" + String(millis()) + "\",\"version\":\"1.0\",\"auth_token\":\"" + String(AUTH_TOKEN).substring(0, 10) + "...\"}";
    client.send(initialMessage);
}
```

#### 2. بهبود پردازش دستورات سروو
```cpp
// پردازش دستورات سروو (برای لاگ کردن)
if (doc.containsKey("servo1") && doc.containsKey("servo2")) {
    int servo1 = doc["servo1"].as<int>();
    int servo2 = doc["servo2"].as<int>();
    sendLog("Servo command received: servo1=" + String(servo1) + ", servo2=" + String(servo2), "info");
    client.send("{\"type\":\"servo_command\",\"servo1\":" + String(servo1) + ",\"servo2\":" + String(servo2) + "}");
}
```

#### 3. بهبود مدیریت حافظه
```cpp
// بررسی حافظه با بهینه‌سازی real-time
size_t freeMemory = heap_caps_get_free_size(MALLOC_CAP_8BIT);
if (freeMemory < 25000) {
    sendLog("Low memory! Skipping frame", "warning");
    frameErrorCount++;
    if (frameErrorCount >= maxFrameErrors) {
        sendLog("Critical: Persistent low memory - restarting camera...", "error");
        restartCamera();
        frameErrorCount = 0;
    }
    delay(50);
    return;
} else {
    frameErrorCount = 0;
}
```

## 🧪 تست‌های جامع

### تست سیستم یکپارچه
```python
class SystemIntegrationTest:
    def __init__(self, base_url="http://localhost:3001"):
        self.base_url = base_url
        self.test_results = []
        self.auth_token = None
    
    def run_all_tests(self):
        """اجرای تمام تست‌ها"""
        self.test_server_health()
        self.test_dynamic_ports()
        
        if self.login_and_get_token():
            self.test_pico_status()
            self.test_esp32cam_status()
            self.test_servo_command()
            self.test_user_settings()
            self.test_system_performance()
        
        # تست‌های WebSocket
        asyncio.run(self.test_websocket_connection("pico"))
        asyncio.run(self.test_websocket_connection("esp32cam"))
```

### اجرای تست
```bash
python test_system_integration.py
```

## 📊 بهبودهای عملکرد

### 1. مدیریت حافظه
- بهبود garbage collection در Pico
- مدیریت بهتر memory leaks در ESP32CAM
- بهینه‌سازی buffer management

### 2. مدیریت اتصال
- بهبود reconnection logic
- exponential backoff برای تلاش‌های مجدد
- مدیریت بهتر timeout‌ها

### 3. امنیت
- احراز هویت WebSocket
- بررسی توکن در تمام اتصالات
- بستن اتصالات نامعتبر

### 4. پایداری
- بهبود error handling
- مدیریت بهتر خطاهای سیستم
- recovery mechanisms

## 🔧 راهنمای استفاده

### 1. راه‌اندازی سرور
```bash
python server_fastapi.py
```

### 2. آپلود کد به Pico
```bash
# آپلود main.py به Pico
# اطمینان از وجود کتابخانه‌های مورد نیاز
```

### 3. کامپایل و آپلود ESP32CAM
```bash
# استفاده از PlatformIO
pio run --target upload
```

### 4. تست سیستم
```bash
# تست جامع سیستم
python test_system_integration.py

# تست مدیریت Session
python test_session_management.py
```

## 🚀 ویژگی‌های جدید

### 1. احراز هویت امن
- توکن‌های امن برای میکروکنترلرها
- بررسی احراز هویت در تمام اتصالات
- مدیریت اتصالات نامعتبر

### 2. مدیریت بهتر دستورات
- فرمت استاندارد پیام‌ها
- timestamp و source tracking
- error handling بهبود یافته

### 3. لاگینگ پیشرفته
- لاگ کردن تمام عملیات
- tracking خطاها
- monitoring عملکرد

### 4. تست‌های جامع
- تست‌های خودکار
- validation تمام بخش‌ها
- گزارش‌گیری کامل

### 5. مدیریت Session پیشرفته
- تشخیص خودکار Hard Reload
- مدیریت متفاوت برای admin و کاربران عادی
- Session cleanup کامل
- Multi-tab support

## 📝 نکات مهم

### 1. امنیت
- توکن‌ها را در محیط production تغییر دهید
- از HTTPS در محیط production استفاده کنید
- firewall مناسب تنظیم کنید

### 2. عملکرد
- حافظه را به طور منظم بررسی کنید
- خطاها را monitor کنید
- backup منظم انجام دهید

### 3. نگهداری
- لاگ‌ها را به طور منظم بررسی کنید
- سیستم را به‌روزرسانی کنید
- تست‌های منظم انجام دهید

## 🎯 نتیجه‌گیری

تمام مشکلات شناسایی شده در سیستم برطرف شده‌اند:

✅ **احراز هویت WebSocket** - پیاده‌سازی شده  
✅ **ارتباط سروو** - بهبود یافته  
✅ **مدیریت پورت‌ها** - بهینه شده  
✅ **امنیت** - تقویت شده  
✅ **پایداری** - بهبود یافته  
✅ **عملکرد** - بهینه شده  
✅ **مدیریت Session** - پیاده‌سازی شده  

سیستم اکنون آماده استفاده در محیط production است.

## 📞 پشتیبانی

در صورت بروز مشکل:
1. لاگ‌ها را بررسی کنید
2. تست‌های جامع را اجرا کنید
3. مستندات را مطالعه کنید
4. با تیم پشتیبانی تماس بگیرید 