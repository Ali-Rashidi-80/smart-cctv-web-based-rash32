
# 📦 DynamicPortManager - README & API DOC

---

## 🚀 معرفی

**DynamicPortManager** یک ماژول پیشرفته و مقاوم برای مدیریت پورت‌های آزاد و اشغال در پروژه‌های شبکه‌ای (FastAPI و ...) است که:
- از **قفل فایل بین‌پروسه‌ای** (filelock) برای جلوگیری از race condition استفاده می‌کند.
- قبل از هر ذخیره، **بکاپ خودکار** از فایل جیسون می‌گیرد.
- **تاریخچه تغییرات** پورت فعال را به صورت پارامتریک نگه می‌دارد.
- از **لاگ رنگی و ساختارمند** و **لاگینگ JSON** برای مانیتورینگ حرفه‌ای پشتیبانی می‌کند.
- **APIهای کامل** برای استفاده در هر برنامه دیگر (وب، مانیتورینگ، DevOps و...) دارد.
- در برابر خطاهای فایل، پوشه، دسترسی، و ... کاملاً مقاوم است.

---

## 🛠️ نصب پیش‌نیازها

```bash
pip install filelock colorama persiantools fastapi
```

---

## 📂 ساختار فایل‌ها

```
project-root/
│
├── utils/
│   └── port_state/
│       ├── dynamic_ports.json
│       └── backups/
│           └── dynamic_ports_YYYYMMDD_HHMMSS.json
│   └── dynamic_port_manager.py
│
├── server_fastapi.py
└── api_ports.py
```

---

## ⚙️ استفاده در پروژه

### ۱. **ایمپورت و مقداردهی**

```python
from utils.dynamic_port_manager import DynamicPortManager

# هر سرویس می‌تواند فایل مخصوص خود داشته باشد
port_manager = DynamicPortManager(
    start=3000,
    end=9000,
    json_path="utils/port_state/dynamic_ports_service1.json",
    refresh_interval=10,   # ثانیه
    history_max=50         # تعداد رکورد تاریخچه
)
```

### ۲. **دریافت پورت آزاد و مدیریت**

```python
port = port_manager.pick_port()      # کمترین پورت آزاد را انتخاب و اشغال می‌کند
port_manager.release_port()          # پورت فعال را آزاد می‌کند
state = port_manager.get_state()     # دریافت وضعیت کامل (برای مانیتورینگ)
port_manager.stop()                  # آزادسازی منابع و توقف thread
```

---

## 📝 **ساختار فایل جیسون**

```json
{
  "current_port": 3000,
  "free_ports": [8001, 8002, 8003],
  "used_ports": [3000],
  "port_usage": {"3000": 3, "8001": 1},
  "history": [
    {"time": "1403/05/01 12:00 doshanbe", "prev": null, "new": 3000},
    {"time": "1403/05/01 12:10 doshanbe", "prev": 3000, "new": 8001}
  ],
  "last_checked": "1403/05/01 12:10 doshanbe",
  "change_count": 2,
  "last_error": null,
  "last_error_time": null,
  "settings": {
    "port_range": [3000, 9000],
    "json_path": "utils/port_state/dynamic_ports_service1.json",
    "history_max": 50
  }
}
```

---

## 🎨 **نمونه لاگ رنگی کنسول**

```
[1403/05/01 12:10 doshanbe] | PICK       | Active:3000 | Free:[8001...8020](20)   | Used:[3000]             | Note:DynamicPortManager started.
```

---

## 🔗 **API مستندات (FastAPI)**

### **پیش‌نیاز:**
در فایل `api_ports.py` یا مشابه، این کد را قرار دهید و در main اپ خود اضافه کنید:
```python
from fastapi import FastAPI
from api_ports import router as port_router

app = FastAPI()
app.include_router(port_router, prefix="/api/v1")
```

---

### **اندپوینت‌ها**

#### `GET /api/v1/port/state`
**توضیح:** دریافت وضعیت کامل پورت‌ها و تنظیمات  
**پاسخ:**
```json
{
  "current_port": 3000,
  "free_ports": [8001, 8002],
  "used_ports": [3000],
  ...
}
```

---

#### `POST /api/v1/port/pick`
**توضیح:** انتخاب و اشغال کمترین پورت آزاد  
**پاسخ:**
```json
{"status": "success", "port": 3000}
```

---

#### `POST /api/v1/port/release`
**توضیح:** آزادسازی پورت فعال  
**پاسخ:**
```json
{"status": "success"}
```

---

#### `GET /api/v1/port/free`
**توضیح:** دریافت لیست پورت‌های آزاد  
**پاسخ:**
```json
{"free_ports": [8001, 8002, 8003]}
```

---

#### `GET /api/v1/port/used`
**توضیح:** دریافت لیست پورت‌های اشغال  
**پاسخ:**
```json
{"used_ports": [3000]}
```

---

#### `GET /api/v1/port/history`
**توضیح:** دریافت تاریخچه تغییرات پورت فعال  
**پاسخ:**
```json
{"history": [{"time": "...", "prev": null, "new": 3000}, ...]}
```

---

#### `GET /api/v1/port/backup/list`
**توضیح:** لیست بکاپ‌های جیسون  
**پاسخ:**
```json
{"backups": ["dynamic_ports_20240721_155445.json", ...]}
```

---

#### `GET /api/v1/port/backup/download?filename=...`
**توضیح:** دانلود یک بکاپ خاص  
**پاسخ:** فایل جیسون بکاپ

---

#### `GET /api/v1/port/log/json`
**توضیح:** دریافت لاگ ساختارمند (برای ELK یا مانیتورینگ)  
**پاسخ:**
```json
{
  "status": "ok"
}
```
(لاگ ساختارمند در کنسول چاپ می‌شود.)

---

## 🧑‍💻 **نکات توسعه و شخصی‌سازی**

- می‌توانید برای هر سرویس، یک فایل جیسون جداگانه تعریف کنید.
- پارامتر `history_max` را برای کنترل حجم تاریخچه تغییر دهید.
- اگر نیاز به لاگینگ JSON برای ELK دارید، از متد `log_json` استفاده کنید.
- اگر نیاز به بکاپ‌گیری بیشتر دارید، پوشه `backups/` را مانیتور کنید.
- اگر چندین برنامه همزمان دارید، قفل فایل (filelock) از race condition جلوگیری می‌کند.

---

## 🛡️ **پایداری و امنیت**

- در صورت خراب شدن یا خالی بودن فایل جیسون، فایل حذف و بازسازی می‌شود.
- همه خطاهای فایل و IO هندل می‌شوند و برنامه هیچ‌وقت کرش نمی‌کند.
- بکاپ خودکار قبل از هر ذخیره انجام می‌شود.
- پوشه و زیرپوشه‌ها همیشه ساخته می‌شوند.

---

## 🏁 **شروع سریع**

```python
from utils.dynamic_port_manager import DynamicPortManager

pm = DynamicPortManager(3000, 9000, json_path="utils/port_state/dynamic_ports_service1.json")
port = pm.pick_port()
print("Selected port:", port)
pm.release_port()
pm.stop()
```

---

## 📣 **پیشنهادات و توسعه بیشتر**

- اگر نیاز به اندپوینت یا قابلیت خاص دیگری داری، کافیست در همین پروژه issue باز کنی یا به توسعه‌دهنده پیام بدهی!
- برای مانیتورینگ حرفه‌ای، می‌توانی لاگینگ JSON را به ELK یا Grafana ارسال کنی.

---

**موفق باشی! این ماژول برای پروژه‌های حرفه‌ای و مقیاس‌پذیر طراحی شده است.**  
اگر سوال یا نیاز به راهنمایی داشتی، همینجا بپرس!