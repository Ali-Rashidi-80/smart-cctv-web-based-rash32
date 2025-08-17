# حل مشکلات لاگ‌های کنسول

## مشکلات شناسایی شده و حل شده

### 1. DeprecationWarning برای `asyncio.get_event_loop().set_debug(False)`

**مشکل:**
```
DeprecationWarning: There is no current event loop
asyncio.get_event_loop().set_debug(False)
```

**راه حل:**
- استفاده از `asyncio.get_running_loop()` به جای `asyncio.get_event_loop()`
- اضافه کردن error handling برای زمانی که event loop در حال اجرا نیست
- ایجاد event loop موقت در صورت نیاز

**کد اصلاح شده:**
```python
# Set asyncio debug to False to reduce noise (modern approach)
try:
    loop = asyncio.get_running_loop()
    loop.set_debug(False)
except RuntimeError:
    # No running loop, create one temporarily
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_debug(False)
    except Exception:
        pass  # Ignore if we can't set debug mode
```

### 2. تکرار لاگ‌های lifespan

**مشکل:**
- دو `lifespan` function تعریف شده بود
- هر سرور uvicorn lifespan خودش را داشت
- لاگ‌های تکراری در startup

**راه حل:**
- حذف lifespan تکراری
- غیرفعال کردن lifespan برای سرورهای ثانویه
- استفاده از `config.lifespan = "off"` برای سرورهای غیر اصلی

**کد اصلاح شده:**
```python
def run_server_on_port(port, service_name):
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        log_config=LOGGING_CONFIG,
        access_log=False,
        loop="asyncio"
    )
    # Disable lifespan for secondary servers
    if service_name != "MAIN SERVER":
        config.lifespan = "off"
    server = uvicorn.Server(config)
    server.run()
```

### 3. لاگ‌های تکراری DynamicPortManager

**مشکل:**
- لاگ‌های مکرر در background refresh
- لاگ‌های غیرضروری در cleanup
- تکرار لاگ‌های initialization

**راه حل:**
- کاهش فرکانس لاگ‌های refresh (هر 30 ثانیه)
- کاهش فرکانس لاگ‌های cleanup (هر 60 ثانیه)
- لاگ initialization فقط یک بار
- بهبود منطق `_should_log` برای لاگ‌های معنادار

**کد اصلاح شده:**
```python
def _should_log(self, tag, prev, curr):
    # Reduce logging frequency - only log significant changes
    return (
        prev["current"] != curr["current"] or
        abs(prev["free_count"] - curr["free_count"]) > 2 or  # Only log if free count changes by more than 2
        abs(prev["used_count"] - curr["used_count"]) > 1 or  # Only log if used count changes by more than 1
        tag in ("INIT", "ERROR", "STOP", "PICK", "RELEASE")  # Always log important events
    )
```

### 4. تکرار DynamicPortManager initialization

**مشکل:**
- چندین instance از DynamicPortManager ایجاد می‌شد
- لاگ‌های تکراری initialization

**راه حل:**
- استفاده از Singleton pattern در `api_ports.py`
- جلوگیری از ایجاد instance های تکراری

### 5. تکرار Windows asyncio patch

**مشکل:**
- پیام موفقیت patch چندین بار نمایش داده می‌شد

**راه حل:**
- استفاده از `sys._asyncio_patch_applied` flag
- اعمال patch فقط یک بار

### 6. تکرار server process logs

**مشکل:**
- لاگ‌های uvicorn تکراری برای سرورهای مختلف

**راه حل:**
- کاهش log level برای سرورهای ثانویه به "error"
- غیرفعال کردن access_log برای سرورهای ثانویه

### 7. تکرار لاگ‌های DynamicPortManager

**مشکل:**
- لاگ‌های DynamicPortManager هم در کنسول و هم در فایل لاگ نمایش داده می‌شدند
- تکرار پیام‌های REFRESH

**راه حل:**
- حذف `logging.info` از متد `log_state`
- فقط نمایش در کنسول برای جلوگیری از تکرار

### 8. بهبود مدیریت لاگ‌ها

**تغییرات اعمال شده:**
- تنظیم `propagate = False` برای logger های مختلف
- جداسازی لاگ‌های uvicorn و app
- استفاده از JalaliFormatter برای فرمت‌بندی لاگ‌ها
- مدیریت بهتر handler های لاگ

## نتایج

### قبل از اصلاح:
```
[1404/05/05 14:01 yekshanbe] | INIT       | Active:-     | Free:[3003...3022](20)  | Used:[3000...3002](3)   | Note:DynamicPortManager started.
[1404/05/05 14:01 yekshanbe] | INIT       | Active:-     | Free:[3003...3022](20)  | Used:[3000...3002](3)   | Note:DynamicPortManager started.
[1404/05/05 14:01 yekshanbe] | REFRESH    | Active:-     | Free:[3000...3019](20)  | Used:[]
[1404/05/05 14:01 yekshanbe] | REFRESH    | Active:-     | Free:[3000...3019](20)  | Used:[]
...
DeprecationWarning: There is no current event loop
asyncio.get_event_loop().set_debug(False)
...
Successfully applied Windows asyncio patch for ConnectionResetError suppression
Successfully applied Windows asyncio patch for ConnectionResetError suppression
...
1404-05-05 14:01:50 yekshanbeh  INFO  Smart Camera System startup: initializing database and tables...
1404-05-05 14:01:50 yekshanbeh  INFO  Smart Camera System startup: initializing database and tables...
1404-05-05 14:01:50 yekshanbeh  INFO  STARTED server process [16392]
1404-05-05 14:01:50 yekshanbeh  INFO  STARTED server process [16392]
1404-05-05 14:01:50 yekshanbeh  INFO  STARTED server process [16392]
```

### بعد از اصلاح:
```
[1404/05/05 14:13 yekshanbe] | INIT       | Active:-     | Free:[3000...3019](20)  | Used:[]             | Note:DynamicPortManager started.
Successfully applied Windows asyncio patch for ConnectionResetError suppression
Smart Camera System startup: initializing database and tables...
Database and tables ready. Continuing startup...
Smart Camera System ready
[MAIN SERVER] Starting server on port 3000
[PICO SERVER] Starting server on port 3001
[ESP32CAM SERVER] Starting server on port 3002
[MULTI-PORT SERVER] All servers started:
  - Main website: http://0.0.0.0:3000
  - Pico WebSocket: ws://0.0.0.0:3001/ws/pico
  - ESP32CAM: ws://0.0.0.0:3002/ws/esp32cam
```

## تست‌های انجام شده

فایل `test_console_logs.py` برای تست مشکلات ایجاد شده که شامل:

1. **تست Logging Configuration**
2. **تست Asyncio Patch**
3. **تست DynamicPortManager**
4. **تست Lifespan Function**

### اجرای تست:
```bash
python test_console_logs.py
```

## نکات مهم

1. **DeprecationWarning حل شده** - دیگر هشدار منسوخ شدن نمایش داده نمی‌شود
2. **لاگ‌های تکراری حذف شده** - هر لاگ فقط یک بار نمایش داده می‌شود
3. **عملکرد بهبود یافته** - کاهش overhead لاگ‌های غیرضروری
4. **خوانایی بهتر** - لاگ‌ها منظم‌تر و قابل فهم‌تر شده‌اند

## فایل‌های تغییر یافته

1. `server_fastapi.py` - اصلاح lifespan، asyncio patch و کاهش لاگ‌های سرور
2. `utils/dynamic_port_manager.py` - کاهش لاگ‌های تکراری و حذف تکرار لاگ
3. `utils/api_ports.py` - استفاده از Singleton pattern
4. `CONSOLE_LOG_FIXES.md` - مستندات مشکلات حل شده

## نتیجه‌گیری

تمام مشکلات شناسایی شده در لاگ‌های کنسول با موفقیت حل شده‌اند. سیستم حالا لاگ‌های تمیزتر و کارآمدتری تولید می‌کند که برای debugging و monitoring مناسب‌تر است. 