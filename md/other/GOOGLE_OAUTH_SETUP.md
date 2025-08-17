# راهنمای تنظیم Google OAuth برای سیستم لاگین

## 🚀 مراحل تنظیم Google OAuth

### 1. ایجاد پروژه در Google Cloud Console

1. به [Google Cloud Console](https://console.cloud.google.com/) بروید
2. یک پروژه جدید ایجاد کنید یا پروژه موجود را انتخاب کنید
3. نام پروژه: `Smart Camera System` (یا نام دلخواه)

### 2. فعال‌سازی Google+ API

1. در منوی سمت چپ، روی **APIs & Services** کلیک کنید
2. **Library** را انتخاب کنید
3. جستجو کنید: `Google+ API` یا `Google Identity`
4. **Google+ API** را انتخاب و **Enable** کنید

### 3. ایجاد OAuth 2.0 Credentials

1. در منوی **APIs & Services**، **Credentials** را انتخاب کنید
2. روی **Create Credentials** کلیک کنید
3. **OAuth 2.0 Client IDs** را انتخاب کنید
4. **Configure consent screen** را کلیک کنید

### 4. تنظیم OAuth Consent Screen

#### User Type:
- **External** را انتخاب کنید (برای کاربران عمومی)

#### App Information:
```
App name: Smart Camera System
User support email: your-email@gmail.com
App logo: (اختیاری)
```

#### Scopes:
- **email**
- **profile**
- **openid**

#### Test users:
- ایمیل‌های تست خود را اضافه کنید

### 5. ایجاد OAuth 2.0 Client ID

#### Application type:
- **Web application** را انتخاب کنید

#### Authorized redirect URIs:
```
http://localhost:3000/auth/google/callback
http://your-domain.com/auth/google/callback
```

#### Authorized JavaScript origins:
```
http://localhost:3000
http://your-domain.com
```

### 6. دریافت Client ID و Client Secret

پس از ایجاد، اطلاعات زیر را دریافت خواهید کرد:
- **Client ID**: `123456789-abcdefghijklmnop.apps.googleusercontent.com`
- **Client Secret**: `GOCSPX-abcdefghijklmnopqrstuvwxyz`

## 🔧 تنظیم متغیرهای محیطی

### روش 1: فایل .env (توصیه شده)

```bash
# فایل .env را در ریشه پروژه ایجاد کنید
GOOGLE_CLIENT_ID=your-client-id-here
GOOGLE_CLIENT_SECRET=your-client-secret-here
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/google/callback
```

### روش 2: متغیرهای سیستم

```bash
# Windows
set GOOGLE_CLIENT_ID=your-client-id-here
set GOOGLE_CLIENT_SECRET=your-client-secret-here

# Linux/Mac
export GOOGLE_CLIENT_ID=your-client-id-here
export GOOGLE_CLIENT_SECRET=your-client-secret-here
```

### روش 3: مستقیماً در کد (فقط برای تست)

در فایل `server_fastapi.py`:

```python
GOOGLE_CLIENT_ID = "your-client-id-here"
GOOGLE_CLIENT_SECRET = "your-client-secret-here"
```

## 🧪 تست Google OAuth

### 1. راه‌اندازی سرور

```bash
# نصب وابستگی‌ها
pip install -r requirements.txt

# راه‌اندازی سرور
python server_fastapi.py
```

### 2. تست ورود

1. به `http://localhost:3000/login` بروید
2. روی دکمه **ورود با گوگل** کلیک کنید
3. حساب گوگل خود را انتخاب کنید
4. مجوزها را تأیید کنید
5. باید به dashboard هدایت شوید

## 🔒 نکات امنیتی

### 1. محافظت از Client Secret

- هرگز Client Secret را در کد عمومی قرار ندهید
- از متغیرهای محیطی استفاده کنید
- در production، از HTTPS استفاده کنید

### 2. محدود کردن دامنه‌ها

```python
# در Google Cloud Console
Authorized redirect URIs:
- http://localhost:3000/auth/google/callback (development)
- https://your-domain.com/auth/google/callback (production)

Authorized JavaScript origins:
- http://localhost:3000 (development)
- https://your-domain.com (production)
```

### 3. Rate Limiting

سیستم از rate limiting استفاده می‌کند:
- 120 درخواست در دقیقه
- مسدودیت 15 دقیقه‌ای پس از 3 تلاش ناموفق

## 🐛 عیب‌یابی مشکلات رایج

### 1. خطای "redirect_uri_mismatch"

**مشکل:** URI بازگشت با تنظیمات Google مطابقت ندارد

**راه‌حل:**
- در Google Cloud Console، URI بازگشت را بررسی کنید
- مطمئن شوید که `http://localhost:3000/auth/google/callback` اضافه شده است

### 2. خطای "invalid_client"

**مشکل:** Client ID یا Client Secret اشتباه است

**راه‌حل:**
- متغیرهای محیطی را بررسی کنید
- Client ID و Client Secret را دوباره کپی کنید

### 3. خطای "access_denied"

**مشکل:** کاربر مجوزها را رد کرده است

**راه‌حل:**
- کاربر باید مجدداً تلاش کند
- مطمئن شوید که کاربر در لیست test users است

### 4. خطای "invalid_grant"

**مشکل:** Authorization code منقضی شده یا استفاده شده است

**راه‌حل:**
- کاربر باید مجدداً وارد شود
- این خطا طبیعی است و نیازی به رفع ندارد

## 📋 چک‌لیست نهایی

### قبل از راه‌اندازی:
- [ ] Google Cloud Console پروژه ایجاد شده
- [ ] Google+ API فعال شده
- [ ] OAuth 2.0 Client ID ایجاد شده
- [ ] Redirect URIs تنظیم شده
- [ ] متغیرهای محیطی تنظیم شده

### تست عملکرد:
- [ ] سرور بدون خطا راه‌اندازی می‌شود
- [ ] دکمه Google OAuth نمایش داده می‌شود
- [ ] redirect به Google کار می‌کند
- [ ] callback موفق است
- [ ] کاربر به dashboard هدایت می‌شود
- [ ] اطلاعات کاربر در دیتابیس ذخیره می‌شود

## 🚀 آماده‌سازی برای Production

### 1. دامنه و SSL

```python
# در production
GOOGLE_REDIRECT_URI = "https://your-domain.com/auth/google/callback"
```

### 2. تنظیمات امنیتی

```python
# در production، secure=True را تنظیم کنید
response.set_cookie(
    key="access_token",
    value=access_token,
    max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    httponly=True,
    secure=True,  # فقط HTTPS
    samesite="strict"
)
```

### 3. لاگ‌گیری

```python
# لاگ‌های OAuth را بررسی کنید
await insert_log(f"Google OAuth login: {user_data['username']}", "auth")
```

## 📞 پشتیبانی

اگر مشکلی دارید:

1. **لاگ‌های سرور** را بررسی کنید
2. **Google Cloud Console** را بررسی کنید
3. **Network tab** مرورگر را بررسی کنید
4. **Console** مرورگر را بررسی کنید

---

**آخرین به‌روزرسانی**: 2024  
**نسخه**: 1.0.0 