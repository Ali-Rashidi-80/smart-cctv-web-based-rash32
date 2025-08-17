# راهنمای عیب‌یابی سیستم لاگین پیشرفته

## 🚨 مشکلات رایج و راه‌حل‌ها

### 1. خطای Pydantic: `regex` is removed. use `pattern` instead

**مشکل:**
```
pydantic.errors.PydanticUserError: `regex` is removed. use `pattern` instead
```

**راه‌حل:**
- ✅ این مشکل در نسخه جدید Pydantic رخ می‌دهد
- ✅ در کد به‌روزرسانی شده، `regex` به `pattern` تغییر یافته است
- ✅ اگر هنوز این خطا را می‌بینید، فایل `server_fastapi.py` را به‌روزرسانی کنید

### 2. خطای Import: No module named 'pyotp'

**مشکل:**
```
ModuleNotFoundError: No module named 'pyotp'
```

**راه‌حل:**
```bash
# نصب وابستگی‌ها
pip install -r requirements.txt

# یا نصب دستی
pip install pyotp==2.9.0
```

### 3. خطای دیتابیس: no such column

**مشکل:**
```
sqlite3.OperationalError: no such column: email
```

**راه‌حل:**
- ✅ تابع `migrate_all_tables()` ستون‌های جدید را اضافه می‌کند
- ✅ سرور را restart کنید
- ✅ اگر مشکل ادامه داشت، فایل دیتابیس را backup کنید و دوباره ایجاد کنید

### 4. خطای 2FA: columns don't exist

**مشکل:**
```
sqlite3.OperationalError: no such column: two_fa_enabled
```

**راه‌حل:**
- ✅ کد به‌روزرسانی شده این مشکل را handle می‌کند
- ✅ اگر هنوز مشکل دارید، سرور را restart کنید

### 5. خطای CORS یا WebSocket

**مشکل:**
```
CORS error یا WebSocket connection failed
```

**راه‌حل:**
- ✅ مطمئن شوید که سرور روی پورت 3000 اجرا می‌شود
- ✅ مرورگر را refresh کنید
- ✅ کش مرورگر را پاک کنید

## 🔧 مراحل عیب‌یابی

### مرحله 1: بررسی وابستگی‌ها
```bash
# اجرای تست startup
python test_server_startup.py
```

### مرحله 2: بررسی سرور
```bash
# راه‌اندازی سرور
python server_fastapi.py

# بررسی لاگ‌ها برای خطاها
```

### مرحله 3: تست API
```bash
# تست endpoint های جدید
python test_enhanced_login.py
```

### مرحله 4: بررسی دیتابیس
```bash
# بررسی ساختار دیتابیس
sqlite3 smart_camera_system.db ".schema users"
```

## 📋 چک‌لیست عیب‌یابی

### قبل از راه‌اندازی:
- [ ] تمام وابستگی‌ها نصب شده‌اند
- [ ] فایل `requirements.txt` به‌روزرسانی شده است
- [ ] فایل `server_fastapi.py` به‌روزرسانی شده است
- [ ] فایل `templates/login.html` به‌روزرسانی شده است

### هنگام راه‌اندازی:
- [ ] سرور بدون خطا شروع می‌شود
- [ ] لاگ‌ها نشان می‌دهند که دیتابیس initialize شده است
- [ ] ستون‌های جدید به جدول users اضافه شده‌اند

### پس از راه‌اندازی:
- [ ] صفحه لاگین قابل دسترسی است
- [ ] کپچا نمایش داده می‌شود
- [ ] ثبت‌نام کاربر جدید کار می‌کند
- [ ] ورود کاربر کار می‌کند

## 🛠️ دستورات مفید

### پاک کردن و نصب مجدد:
```bash
# حذف فایل‌های cache
find . -name "*.pyc" -delete
find . -name "__pycache__" -delete

# نصب مجدد وابستگی‌ها
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

### بررسی دیتابیس:
```bash
# مشاهده ساختار جدول users
sqlite3 smart_camera_system.db "PRAGMA table_info(users);"

# مشاهده کاربران موجود
sqlite3 smart_camera_system.db "SELECT username, email, two_fa_enabled FROM users;"
```

### بررسی لاگ‌ها:
```bash
# مشاهده لاگ‌های اخیر
tail -f logs/app_$(date +%Y-%m-%d).log

# جستجو در لاگ‌ها
grep -i "error" logs/app_*.log
```

## 🆘 درخواست کمک

اگر مشکل حل نشد:

1. **اطلاعات سیستم:**
   - نسخه Python: `python --version`
   - نسخه pip: `pip --version`
   - سیستم عامل: `uname -a` (Linux) یا `systeminfo` (Windows)

2. **لاگ‌های کامل:**
   - لاگ‌های سرور
   - لاگ‌های مرورگر (F12 → Console)
   - پیام‌های خطا

3. **مراحل انجام شده:**
   - دستورات اجرا شده
   - تغییرات اعمال شده
   - نتیجه‌های تست‌ها

## 📞 پشتیبانی

- **GitHub Issues**: ایجاد issue جدید با جزئیات کامل
- **Email**: admin@example.com
- **Telegram**: @smart_camera_support

---

**آخرین به‌روزرسانی**: 2024  
**نسخه**: 2.0.0 