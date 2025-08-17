# سیستم لاگین پیشرفته - Smart Camera System

## 🚀 ویژگی‌های جدید اضافه شده

### 1. 🔐 کپچا (CAPTCHA) دو بعدی مدرن
- **کپچا تعاملی**: کپچاهای دو بعدی با طراحی مدرن و جذاب
- **امنیت بالا**: محافظت در برابر حملات خودکار و ربات‌ها
- **تجربه کاربری بهتر**: امکان کلیک برای تولید مجدد کپچا
- **سه نوع کپچا**: برای ورود، ثبت‌نام و بازیابی رمز عبور

### 2. 📝 سیستم ثبت‌نام کاربران
- **ثبت‌نام خودکار**: کاربران جدید می‌توانند ثبت‌نام کنند
- **اعتبارسنجی پیشرفته**: بررسی تکراری نبودن نام کاربری و ایمیل
- **نمایش قدرت رمز عبور**: نشان‌دهنده قدرت رمز عبور در زمان تایپ
- **قوانین امنیتی**: حداقل 8 کاراکتر با ترکیب حروف و اعداد

### 3. 🔑 بازیابی رمز عبور
- **بازیابی از طریق ایمیل**: ارسال لینک بازیابی به ایمیل کاربر
- **توکن امن**: تولید توکن‌های امن و منحصر به فرد
- **محدودیت زمانی**: توکن‌ها پس از 24 ساعت منقضی می‌شوند
- **امنیت بالا**: عدم افشای وجود یا عدم وجود ایمیل

### 4. 🔒 احراز هویت دو مرحله‌ای (2FA)
- **QR Code**: تولید QR Code برای اپلیکیشن‌های احراز هویت
- **TOTP**: پشتیبانی از استاندارد TOTP (Time-based One-Time Password)
- **ورودی OTP**: 6 رقم کد تأیید با تجربه کاربری بهینه
- **امنیت مضاعف**: محافظت اضافی برای حساب‌های کاربری

### 5. 🎨 رابط کاربری مدرن
- **طراحی ریسپانسیو**: سازگار با تمام دستگاه‌ها
- **انیمیشن‌های جذاب**: ذرات متحرک در پس‌زمینه
- **رنگ‌بندی مدرن**: استفاده از CSS Variables برای مدیریت بهتر رنگ‌ها
- **آیکون‌های FontAwesome**: آیکون‌های زیبا و حرفه‌ای

### 6. 🔐 امنیت پیشرفته
- **Rate Limiting**: محدودیت تعداد درخواست‌ها
- **Blocking System**: مسدود کردن IP پس از تلاش‌های ناموفق
- **Password Hashing**: رمزنگاری امن رمزهای عبور با bcrypt
- **Session Management**: مدیریت جلسات کاربری

### 7. 🌐 ورود با شبکه‌های اجتماعی
- **گوگل**: ورود با حساب گوگل (در حال توسعه)
- **گیت‌هاب**: ورود با حساب گیت‌هاب (در حال توسعه)
- **قابلیت گسترش**: امکان اضافه کردن شبکه‌های اجتماعی دیگر

## 📋 نحوه استفاده

### نصب وابستگی‌ها
```bash
pip install -r requirements.txt
```

### راه‌اندازی سرور
```bash
python server_fastapi.py
```

### دسترسی به سیستم
- **آدرس**: `http://localhost:3000/login`
- **کاربر پیش‌فرض**: `admin`
- **رمز عبور**: `admin123`

## 🗄️ ساختار دیتابیس

### جدول users (به‌روزرسانی شده)
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    is_active BOOLEAN DEFAULT 1,
    two_fa_enabled BOOLEAN DEFAULT 0,
    two_fa_secret TEXT,
    created_at TEXT NOT NULL
);
```

### جدول password_recovery (جدید)
```sql
CREATE TABLE password_recovery (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    expires_at TEXT NOT NULL,
    used BOOLEAN DEFAULT 0,
    created_at TEXT NOT NULL
);
```

## 🔧 API Endpoints جدید

### ثبت‌نام کاربر
```http
POST /register
Content-Type: application/json

{
    "username": "newuser",
    "email": "user@example.com",
    "password": "SecurePass123!"
}
```

### بازیابی رمز عبور
```http
POST /recover-password
Content-Type: application/json

{
    "email": "user@example.com"
}
```

### تأیید 2FA
```http
POST /verify-2fa
Content-Type: application/json

{
    "secret": "username:secret_key",
    "otp": "123456"
}
```

## 🛡️ ویژگی‌های امنیتی

### Rate Limiting
- **درخواست‌های عمومی**: 120 درخواست در دقیقه
- **تلاش‌های ورود**: 3 تلاش قبل از مسدود شدن
- **مدت مسدودیت**: 10 دقیقه

### Password Security
- **حداقل طول**: 8 کاراکتر
- **ترکیب کاراکترها**: حروف بزرگ، کوچک، اعداد و نمادها
- **هش امن**: استفاده از bcrypt با salt

### Session Security
- **توکن JWT**: توکن‌های امن با زمان انقضا
- **HttpOnly Cookies**: محافظت در برابر XSS
- **SameSite**: محافظت در برابر CSRF

## 🎯 بهبودهای آینده

### ایمیل
- [ ] پیاده‌سازی ارسال ایمیل واقعی
- [ ] قالب‌های ایمیل زیبا
- [ ] تأیید ایمیل در ثبت‌نام

### شبکه‌های اجتماعی
- [ ] ورود با گوگل
- [ ] ورود با گیت‌هاب
- [ ] ورود با تلگرام

### امنیت بیشتر
- [ ] IP Whitelist/Blacklist
- [ ] Device Fingerprinting
- [ ] Behavioral Analysis

### تجربه کاربری
- [ ] Dark Mode
- [ ] زبان‌های بیشتر
- [ ] انیمیشن‌های پیشرفته‌تر

## 🐛 عیب‌یابی

### مشکلات رایج

#### کپچا نمایش داده نمی‌شود
- بررسی کنید که JavaScript فعال باشد
- مرورگر را refresh کنید

#### خطای دیتابیس
- فایل دیتابیس را بررسی کنید
- سرور را restart کنید

#### مشکل 2FA
- اپلیکیشن احراز هویت را بررسی کنید
- زمان سیستم را چک کنید

## 📞 پشتیبانی

برای گزارش مشکلات یا پیشنهادات:
- **GitHub Issues**: ایجاد issue جدید
- **Email**: admin@example.com

---

**توسعه‌دهنده**: Smart Camera System Team  
**نسخه**: 2.0.0  
**تاریخ**: 2024 