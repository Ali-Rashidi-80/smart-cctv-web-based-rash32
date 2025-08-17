# راهنمای عیب‌یابی سرور خارجی

## مشکل اصلی 🔍

سرور محلی به درستی کار می‌کند اما اتصال‌های خارجی به `services.gen6.chabokan.net:3000` کار نمی‌کند.

## مراحل عیب‌یابی

### مرحله 1: تشخیص مشکلات شبکه

```bash
python network_diagnostics.py
```

این اسکریپت موارد زیر را بررسی می‌کند:
- ✅ DNS resolution
- ✅ Port connectivity  
- ✅ HTTP endpoints
- ✅ WebSocket connection
- ✅ Firewall status

### مرحله 2: راه‌اندازی سرور خارجی

#### گزینه A: راه‌اندازی ساده
```bash
python start_external_server_simple.py
```

#### گزینه B: راه‌اندازی پیشرفته
```bash
python start_external_server.py
```

### مرحله 3: تست اتصال خارجی

```bash
python test_external_websocket.py
```

## مشکلات احتمالی و راه‌حل‌ها

### ❌ مشکل 1: سرور خارجی اجرا نمی‌شود

**علائم:**
- خطای "Port 3000 is already in use"
- سرور روی پورت 3000 اجرا می‌شود اما 3000 کار نمی‌کند

**راه‌حل:**
1. سرور فعلی را متوقف کنید
2. پورت 3000 را آزاد کنید
3. سرور را مجدداً راه‌اندازی کنید

```bash
# متوقف کردن سرور فعلی
Ctrl+C

# بررسی پورت‌های در حال استفاده
netstat -an | findstr :3000

# راه‌اندازی مجدد
python start_external_server_simple.py
```

### ❌ مشکل 2: DNS resolution failed

**علائم:**
- خطای "DNS resolution failed"
- عدم دسترسی به `services.gen6.chabokan.net`

**راه‌حل:**
1. بررسی اتصال اینترنت
2. بررسی DNS settings
3. استفاده از IP مستقیم

```bash
# تست DNS
nslookup services.gen6.chabokan.net

# تست ping
ping services.gen6.chabokan.net
```

### ❌ مشکل 3: Port 3000 is not reachable

**علائم:**
- خطای "Port 3000 is not reachable"
- سرور محلی کار می‌کند اما خارجی نه

**راه‌حل:**
1. بررسی firewall settings
2. بررسی router configuration
3. بررسی server binding

```bash
# بررسی firewall
netsh advfirewall show allprofiles state

# اضافه کردن exception برای پورت 3000
netsh advfirewall firewall add rule name="Spy Servoo External" dir=in action=allow protocol=TCP localport=3000
```

### ❌ مشکل 4: Authentication failed

**علائم:**
- اتصال WebSocket موفق اما احراز هویت رد می‌شود
- خطای "Invalid Pico token"

**راه‌حل:**
1. دریافت توکن‌های جدید
2. بررسی فرمت Authorization header
3. بررسی token expiration

```bash
# دریافت توکن‌های جدید
curl http://services.gen6.chabokan.net:3000/public/tokens

# تست با توکن جدید
python test_external_websocket.py
```

### ❌ مشکل 5: Server not bound to 0.0.0.0

**علائم:**
- اتصال localhost کار می‌کند
- اتصال خارجی کار نمی‌کند
- سرور فقط روی 127.0.0.1 اجرا می‌شود

**راه‌حل:**
1. اطمینان از اجرای سرور روی `0.0.0.0`
2. بررسی environment variables
3. استفاده از اسکریپت راه‌اندازی خارجی

```python
# در server_fastapi.py
uvicorn.run(
    app,
    host="0.0.0.0",  # مهم: نه localhost
    port=3000,
    log_level="info"
)
```

## اسکریپت‌های مفید

### 1. بررسی وضعیت سرور
```bash
python network_diagnostics.py
```

### 2. راه‌اندازی سرور خارجی
```bash
python start_external_server_simple.py
```

### 3. تست اتصال
```bash
python test_external_websocket.py
```

### 4. تست محلی
```bash
python test_local_websocket.py
```

## پیکربندی پیشنهادی

### Environment Variables
```bash
export HOST="0.0.0.0"
export PORT="3000"
export EXTERNAL_ACCESS="true"
```

### Firewall Rules (Windows)
```bash
# اضافه کردن exception برای پورت 3000
netsh advfirewall firewall add rule name="Spy Servoo External" dir=in action=allow protocol=TCP localport=3000
netsh advfirewall firewall add rule name="Spy Servoo External Out" dir=out action=allow protocol=TCP localport=3000
```

### Router Configuration
- Port forwarding برای پورت 3000
- DMZ یا NAT configuration
- Static IP برای سرور

## تست‌های تایید

### تست 1: HTTP Endpoints
```bash
curl http://services.gen6.chabokan.net:3000/health
curl http://services.gen6.chabokan.net:3000/public/tokens
```

### تست 2: WebSocket Connection
```bash
python test_external_websocket.py
```

### تست 3: Manual WebSocket Test
```javascript
// در browser console
const ws = new WebSocket('ws://services.gen6.chabokan.net:3000/ws/pico');
ws.onopen = () => console.log('Connected!');
ws.onmessage = (event) => console.log('Received:', event.data);
```

## لاگ‌های مهم

### سرور لاگ‌ها
```
[WebSocket] Pico connection attempt from <IP>
[WebSocket] Pico authenticated and connected from <IP>
[WebSocket] Pico message: {"type": "connect", ...}
```

### خطاهای رایج
```
❌ Connection refused: سرور اجرا نمی‌شود
❌ Timeout: مشکل شبکه یا firewall
❌ DNS resolution failed: مشکل DNS
❌ Invalid token: مشکل احراز هویت
```

## مراحل نهایی

1. **تشخیص:** `python network_diagnostics.py`
2. **راه‌اندازی:** `python start_external_server_simple.py`
3. **تست:** `python test_external_websocket.py`
4. **تایید:** بررسی لاگ‌ها و اتصال‌ها

## پشتیبانی

اگر مشکلات همچنان باقی است:

1. لاگ‌های کامل سرور را بررسی کنید
2. خروجی `network_diagnostics.py` را بررسی کنید
3. تنظیمات firewall و router را بررسی کنید
4. با administrator شبکه تماس بگیرید

## نتیجه‌گیری

با پیروی از این مراحل، سرور خارجی باید به درستی کار کند و دستگاه‌های خارجی بتوانند به WebSocket متصل شوند. کلید موفقیت:

- ✅ سرور روی `0.0.0.0:3000` اجرا شود
- ✅ Firewall پورت 3000 را مسدود نکند
- ✅ DNS resolution کار کند
- ✅ توکن‌های احراز هویت صحیح باشند 