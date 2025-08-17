# راهنمای اتصال WebSocket از آدرس‌های خارجی

## مشکل حل شده ✅

مشکل اتصال WebSocket از آدرس‌های خارجی (مانند `ws://services.gen6.chabokan.net:3000/ws/pico`) حل شده است. حالا هر دستگاه خارجی می‌تواند با استفاده از توکن‌های احراز هویت به سرور متصل شود.

## نحوه اتصال

### 1. دریافت توکن‌های احراز هویت

ابتدا توکن‌های فعلی را از سرور دریافت کنید:

```bash
curl http://services.gen6.chabokan.net:3000/public/tokens
```

یا در مرورگر:
```
http://services.gen6.chabokan.net:3000/public/tokens
```

پاسخ شامل توکن‌های Pico و ESP32CAM خواهد بود:

```json
{
  "status": "success",
  "pico_tokens": ["token1", "token2"],
  "esp32cam_tokens": ["token3", "token4"],
  "timestamp": "2024-01-01T12:00:00",
  "message": "Use these tokens in the Authorization header as 'Bearer <token>'"
}
```

### 2. اتصال WebSocket با احراز هویت

برای اتصال به WebSocket Pico:

```javascript
// JavaScript Example
const token = "your_pico_token_here";
const ws = new WebSocket('ws://services.gen6.chabokan.net:3000/ws/pico');

// Add authorization header
ws.onopen = function() {
    // Send authorization in first message
    ws.send(JSON.stringify({
        type: "auth",
        token: token
    }));
};
```

```python
# Python Example
import websockets
import json

async def connect_pico():
    token = "your_pico_token_here"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    async with websockets.connect(
        'ws://services.gen6.chabokan.net:3000/ws/pico',
        extra_headers=headers
    ) as websocket:
        # Send connection message
        await websocket.send(json.dumps({
            "type": "connect",
            "device": "pico_device",
            "version": "1.0.0"
        }))
        
        # Listen for messages
        async for message in websocket:
            data = json.loads(message)
            print(f"Received: {data}")
```

### 3. پیام‌های پشتیبانی شده

#### پیام‌های ارسالی به سرور:

```json
// پیام اتصال اولیه
{
    "type": "connect",
    "device": "pico_device",
    "version": "1.0.0"
}

// پیام ping برای نگه داشتن اتصال
{
    "type": "ping"
}

// پیام لاگ
{
    "type": "log",
    "message": "Device status update",
    "level": "info"
}

// پیام تایید
{
    "type": "ack",
    "message": "Command received"
}
```

#### پیام‌های دریافتی از سرور:

```json
// تایید اتصال
{
    "type": "connection_ack",
    "status": "success",
    "message": "Pico connection acknowledged"
}

// پاسخ ping
{
    "type": "pong"
}

// پیام ping از سرور
{
    "type": "ping"
}

// پیام خطا
{
    "type": "error",
    "message": "Error description"
}
```

## تست اتصال

برای تست اتصال، از اسکریپت تست استفاده کنید:

```bash
python test_external_websocket.py
```

این اسکریپت:
1. توکن‌های فعلی را دریافت می‌کند
2. اتصال WebSocket با احراز هویت را تست می‌کند
3. اتصال بدون احراز هویت را تست می‌کند (باید رد شود)

## نکات مهم

### امنیت
- توکن‌ها به صورت خودکار تولید می‌شوند
- اتصال بدون توکن از آدرس‌های خارجی رد می‌شود
- فقط localhost می‌تواند بدون احراز هویت متصل شود

### پایداری اتصال
- سرور هر 120 ثانیه ping ارسال می‌کند
- دستگاه باید با pong پاسخ دهد
- اتصال‌های غیرفعال بعد از timeout بسته می‌شوند

### لاگ‌ها
تمام اتصال‌ها و پیام‌ها در لاگ‌های سرور ثبت می‌شوند:
- آدرس IP دستگاه
- نوع دستگاه (Pico/ESP32CAM)
- پیام‌های ارسالی و دریافتی
- خطاهای احراز هویت

## عیب‌یابی

### مشکل: اتصال رد می‌شود
1. توکن صحیح را بررسی کنید
2. فرمت Authorization header را چک کنید: `Bearer <token>`
3. آدرس سرور و پورت را بررسی کنید

### مشکل: اتصال قطع می‌شود
1. ping/pong را پیاده‌سازی کنید
2. timeout را افزایش دهید
3. اتصال مجدد خودکار اضافه کنید

### مشکل: پیام‌ها دریافت نمی‌شوند
1. فرمت JSON را بررسی کنید
2. نوع پیام (type) را چک کنید
3. لاگ‌های سرور را بررسی کنید

## مثال کامل Python

```python
import asyncio
import websockets
import json
import requests

class PicoWebSocketClient:
    def __init__(self, server_url, token):
        self.server_url = server_url
        self.token = token
        self.websocket = None
        
    async def connect(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        
        try:
            self.websocket = await websockets.connect(
                f"{self.server_url}/ws/pico",
                extra_headers=headers
            )
            
            # Send connection message
            await self.send_message({
                "type": "connect",
                "device": "pico_external",
                "version": "1.0.0"
            })
            
            print("✅ Connected to server")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    async def send_message(self, message):
        if self.websocket:
            await self.websocket.send(json.dumps(message))
    
    async def listen(self):
        if not self.websocket:
            return
            
        try:
            async for message in self.websocket:
                data = json.loads(message)
                print(f"📥 Received: {data}")
                
                # Handle ping from server
                if data.get("type") == "ping":
                    await self.send_message({"type": "pong"})
                    
        except Exception as e:
            print(f"❌ Listen error: {e}")
    
    async def run(self):
        if await self.connect():
            await self.listen()

# Usage
async def main():
    # Get token from server
    response = requests.get("http://services.gen6.chabokan.net:3000/public/tokens")
    tokens = response.json()
    pico_token = tokens["pico_tokens"][0]
    
    # Create and run client
    client = PicoWebSocketClient("ws://services.gen6.chabokan.net:3000", pico_token)
    await client.run()

if __name__ == "__main__":
    asyncio.run(main())
```

## نتیجه‌گیری

حالا دستگاه‌های خارجی می‌توانند به راحتی به سرور WebSocket متصل شوند. فقط کافی است:

1. توکن‌های فعلی را دریافت کنند
2. در header Authorization از فرمت `Bearer <token>` استفاده کنند
3. پیام‌های ping/pong را پیاده‌سازی کنند

این راه‌حل امنیت را حفظ می‌کند در حالی که امکان اتصال از آدرس‌های خارجی را فراهم می‌کند. 