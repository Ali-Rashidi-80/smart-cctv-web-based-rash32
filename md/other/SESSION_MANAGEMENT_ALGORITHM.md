# الگوریتم مدیریت نشست (Session Management Algorithm)

## 🔐 **مروری کلی**

سیستم مدیریت نشست در این پروژه از یک الگوریتم چندلایه و پیشرفته استفاده می‌کند که شامل مدیریت توکن‌های JWT، بررسی منقضی شدن نشست، و هدایت خودکار به صفحه لاگین است.

## ⏰ **مدت زمان نشست**

### **تنظیمات اصلی**
```python
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 60 دقیقه (1 ساعت)
```

### **توکن‌های بازیابی**
```python
# توکن‌های بازیابی رمز عبور: 5 دقیقه
# محدودیت تلاش: 3 بار در ساعت
```

## 🔄 **الگوریتم مدیریت نشست**

### **1. ایجاد توکن (Token Creation)**
```python
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(utc) + expires_delta
    else:
        expire = datetime.now(utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
```

### **2. بررسی توکن (Token Verification)**
```python
def verify_token(token: str):
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # توکن منقضی شده
    except (jwt.exceptions.DecodeError, jwt.exceptions.PyJWTError):
        return None  # توکن نامعتبر
```

### **3. Middleware احراز هویت**
```python
@app.middleware("http")
async def auth_and_security_middleware(request: Request, call_next):
    # بررسی endpoint های عمومی
    public_endpoints = ["/login", "/logout", "/register", "/recover-password", ...]
    is_public = any(request.url.path.startswith(p) for p in public_endpoints)
    
    if is_public:
        return await call_next(request)
    
    # بررسی احراز هویت برای endpoint های محافظت شده
    token = request.cookies.get("access_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    user_info = verify_token(token) if token else None
    
    if not user_info:
        # درخواست API - بازگشت 401
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Unauthorized", "redirect": "/login"}, status_code=401)
        # درخواست HTML - هدایت به لاگین
        return RedirectResponse(url="/login", status_code=302)
    
    # توکن معتبر - ادامه درخواست
    return await call_next(request)
```

## 🎯 **الگوریتم هدایت به لاگین**

### **شرایط هدایت به لاگین**

#### **1. توکن منقضی شده**
```python
except jwt.ExpiredSignatureError:
    return None  # Middleware هدایت می‌کند
```

#### **2. توکن نامعتبر**
```python
except (jwt.exceptions.DecodeError, jwt.exceptions.PyJWTError):
    return None  # Middleware هدایت می‌کند
```

#### **3. عدم وجود توکن**
```python
token = request.cookies.get("access_token")
if not token:
    return RedirectResponse(url="/login", status_code=302)
```

#### **4. درخواست‌های API بدون احراز هویت**
```python
if request.url.path.startswith("/api/"):
    return JSONResponse({"detail": "Unauthorized", "redirect": "/login"}, status_code=401)
```

### **نحوه هدایت**

#### **درخواست‌های HTML**
```python
return RedirectResponse(url="/login", status_code=302)
```

#### **درخواست‌های API**
```python
return JSONResponse({
    "detail": "Unauthorized", 
    "redirect": "/login"
}, status_code=401)
```

## 🔍 **مدیریت نشست در Frontend**

### **1. بررسی نشست موجود**
```javascript
function checkExistingSession() {
    const token = localStorage.getItem('access_token');
    const expires = localStorage.getItem('token_expires');
    
    if (token && expires && Date.now() < parseInt(expires)) {
        window.location.href = '/';  // هدایت به داشبورد
    } else {
        localStorage.removeItem('access_token');
        localStorage.removeItem('token_expires');
        sessionStorage.clear();
    }
}
```

### **2. مدیریت منقضی شدن نشست**
```javascript
setupSessionManagement() {
    // بررسی منقضی شدن نشست هر دقیقه
    setInterval(() => {
        const expires = localStorage.getItem('token_expires');
        if (expires && Date.now() > parseInt(expires)) {
            this.handleSessionExpired();
        }
    }, 60000); // هر دقیقه
}

handleSessionExpired() {
    if (localStorage.getItem('user_role') === 'admin') {
        // ادمین - نمایش هشدار
        this.showNotification('Admin session expired. Please refresh the page.', 'warning');
    } else {
        // کاربر عادی - خروج اجباری
        this.forceLogout();
    }
}

forceLogout() {
    localStorage.clear();
    sessionStorage.clear();
    this.showNotification('Session expired. Please login again.', 'warning');
    window.location.href = '/login';  // هدایت به لاگین
}
```

### **3. مدیریت چند تب (Multi-tab)**
```javascript
window.addEventListener('storage', (e) => {
    if (e.key === 'access_token' && !e.newValue) {
        // توکن در تب دیگر پاک شده
        this.handleSessionExpired();
    }
});
```

## 🛡️ **امنیت نشست**

### **1. تنظیمات Cookie**
```python
response.set_cookie(
    key="access_token",
    value=access_token,
    max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    httponly=True,  # جلوگیری از دسترسی JavaScript
    secure=os.getenv("ENVIRONMENT") == "production",  # HTTPS در production
    samesite="lax"  # محافظت در برابر CSRF
)
```

### **2. بررسی IP**
```python
# توکن شامل IP کاربر است
access_token = create_access_token(
    data={"sub": username, "role": role, "ip": client_ip}
)
```

### **3. Rate Limiting**
```python
MAX_LOGIN_ATTEMPTS = 6
LOGIN_BLOCK_DURATION = 1800  # 30 دقیقه
RATE_LIMIT_REQUESTS = 15
RATE_LIMIT_WINDOW = 60  # 1 دقیقه
```

## 📊 **نمودار جریان نشست**

```
کاربر وارد می‌شود
        ↓
   ایجاد توکن JWT
        ↓
   ذخیره در Cookie
        ↓
   درخواست‌های بعدی
        ↓
   Middleware بررسی می‌کند
        ↓
   توکن معتبر؟ ──نه──→ هدایت به /login
        ↓ بله
   ادامه درخواست
        ↓
   بررسی منقضی شدن (هر دقیقه)
        ↓
   منقضی شده؟ ──بله──→ handleSessionExpired()
        ↓ نه
   ادامه نشست
```

## 🔄 **سناریوهای مختلف**

### **1. نشست عادی**
- کاربر لاگین می‌کند
- توکن 60 دقیقه معتبر است
- درخواست‌ها بدون مشکل پردازش می‌شوند

### **2. منقضی شدن نشست**
- توکن منقضی می‌شود
- Middleware تشخیص می‌دهد
- کاربر به `/login` هدایت می‌شود

### **3. Hard Reload**
- کاربر صفحه را refresh می‌کند
- توکن از Cookie خوانده می‌شود
- اگر معتبر باشد، ادامه نشست

### **4. چند تب**
- توکن در یک تب پاک می‌شود
- سایر تب‌ها تشخیص می‌دهند
- همه تب‌ها به لاگین هدایت می‌شوند

### **5. درخواست API**
- توکن نامعتبر در API
- پاسخ 401 با `redirect: "/login"`
- Frontend هدایت می‌کند

## 🎯 **نتیجه‌گیری**

الگوریتم مدیریت نشست این سیستم:

1. **امن**: از JWT با امضای دیجیتال استفاده می‌کند
2. **کارآمد**: بررسی خودکار منقضی شدن
3. **قابل اعتماد**: هدایت خودکار به لاگین
4. **چندلایه**: Middleware + Frontend + Cookie
5. **مقاوم**: مدیریت خطا و استثناها

**پاسخ به سوال شما**: بله، بعد از منقضی شدن نشست، کاربر به طور خودکار به صفحه لاگین هدایت می‌شود. این فرآیند در چندین لایه (Backend Middleware، Frontend JavaScript، و Cookie Management) پیاده‌سازی شده است.

---

**تاریخ ایجاد**: 30 تیر 1404  
**وضعیت**: ✅ **تکمیل شده**  
**سطح امنیت**: 🛡️ **عالی** 