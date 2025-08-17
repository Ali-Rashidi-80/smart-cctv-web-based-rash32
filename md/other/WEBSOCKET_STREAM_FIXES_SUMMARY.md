# خلاصه اصلاحات WebSocket و استریم

## مشکلات حل شده

### 1. قطع شدن اتصال اصلی هنگام بستن استریم
- **مشکل**: هنگام بستن استریم، اتصال WebSocket اصلی نیز قطع می‌شد
- **راه‌حل**: 
  - ایجاد اتصال جداگانه `streamWebSocket` برای استریم
  - جداسازی مدیریت اتصال استریم از اتصال اصلی
  - متدهای جدید: `setupStreamWebSocket()`, `closeStreamWebSocket()`, `scheduleStreamReconnect()`

### 2. استفاده از HTTP/HTTPS برای وبسایت و فقط WebSocket برای استریم
- **مشکل**: همه ارتباطات از WebSocket استفاده می‌کردند
- **راه‌حل**:
  - وبسایت از HTTP/HTTPS برای API calls استفاده می‌کند
  - فقط استریم از WebSocket استفاده می‌کند
  - دستورات سروو و دوربین از طریق HTTP ارسال می‌شوند

### 3. ارسال دستورات ناخواسته در زمان لودینگ
- **مشکل**: در زمان لودینگ صفحه، دستورات سروو و دوربین ارسال می‌شدند
- **راه‌حل**:
  - حذف راه‌اندازی خودکار WebSocket در `init()`
  - تنظیم event listener ها فقط در صورت نیاز
  - اطمینان از قطع بودن استریم در ابتدا

### 4. تنظیم استریم روی قطع به صورت پیشفرض
- **مشکل**: استریم در ابتدا فعال بود
- **راه‌حل**:
  - تنظیم `isStreaming = false` در constructor
  - اضافه کردن `this.isStreaming = false` در `init()`
  - نمایش وضعیت "قطع" در UI

## تغییرات اعمال شده

### فایل `static/js/index/script.js`

#### Constructor
```javascript
constructor() {
    this.websocket = null;
    this.streamWebSocket = null; // اتصال جداگانه برای استریم
    this.isStreaming = false;
    // ...
    this.systemStatus = {
        websocket: 'disconnected',
        stream: 'disconnected', // وضعیت جداگانه برای استریم
        // ...
    };
}
```

#### متدهای جدید
- `setupStreamWebSocket()`: راه‌اندازی اتصال استریم جداگانه
- `closeStreamWebSocket()`: بستن اتصال استریم
- `scheduleStreamReconnect()`: تلاش مجدد اتصال استریم

#### متد `toggleStream()`
```javascript
async toggleStream() {
    if (!this.isStreaming) {
        this.setupStreamWebSocket(); // فقط اتصال استریم
    } else {
        this.closeStreamWebSocket(); // فقط بستن استریم
    }
}
```

#### متد `updateStatusModal()`
```javascript
updateStatusModal() {
    // وضعیت WebSocket عمومی
    if (wsStatus) {
        // ...
    }
    
    // وضعیت استریم جداگانه
    if (streamStatus) {
        const val = this.language === 'fa' ? 
            (this.systemStatus.stream === 'connected' ? 'متصل' : 'قطع') : 
            this.systemStatus.stream;
        streamStatus.textContent = val;
        setStatusClass(streamStatus, this.systemStatus.stream === 'connected' ? 'connected' : 'disconnected');
    }
}
```

### فایل `templates/index.html`

#### اضافه کردن عنصر وضعیت استریم
```html
<div class="status-item" id="status-stream">
    <i class="fas fa-video"></i>
    <span class="status-label" data-key="streamLabel">{{ translations[lang]['streamLabel'] }}</span>
    <span class="status-value" id="streamStatus">--</span>
</div>
```

### فایل `core/translations_ui.py`

#### اضافه کردن ترجمه‌های جدید
```python
"fa": {
    # ...
    "streamLabel": "استریم",
},
"en": {
    # ...
    "streamLabel": "Stream",
}
```

## مزایای تغییرات

1. **جداسازی مسئولیت‌ها**: اتصال استریم و اتصال اصلی مستقل هستند
2. **عملکرد بهتر**: کاهش ترافیک WebSocket غیرضروری
3. **تجربه کاربری بهتر**: استریم فقط در صورت نیاز فعال می‌شود
4. **پایداری بیشتر**: قطع شدن استریم روی اتصال اصلی تأثیر نمی‌گذارد
5. **مدیریت بهتر منابع**: استفاده بهینه از پهنای باند و منابع سرور

## تست و تأیید

- ✅ استریم در ابتدا قطع است
- ✅ بستن استریم اتصال اصلی را قطع نمی‌کند
- ✅ دستورات سروو از طریق HTTP ارسال می‌شوند
- ✅ وضعیت استریم جداگانه نمایش داده می‌شود
- ✅ خطاهای Chrome Extension فیلتر می‌شوند 