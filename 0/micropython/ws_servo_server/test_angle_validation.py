"""
تست منطق جدید اعتبارسنجی زاویه سروو
"""

# تنظیمات ایمن
SAFE_MIN_ANGLE = 11
SAFE_MAX_ANGLE = 169

def validate_servo_angle(angle):
    """
    اعتبارسنجی زاویه سروو با منطق جدید:
    - اگر زاویه بین 0 تا 11 باشد، به SAFE_MIN_ANGLE تنظیم می‌شود
    - اگر زاویه بین 169 تا 180 باشد، به SAFE_MAX_ANGLE تنظیم می‌شود
    - زاویه‌های بین 11 تا 169 بدون تغییر باقی می‌مانند
    """
    try:
        angle = int(angle)
        
        if 0 <= angle <= 11:
            print(f"🔄 زاویه {angle}° به {SAFE_MIN_ANGLE}° تنظیم شد (حداقل ایمن)")
            return SAFE_MIN_ANGLE
        elif 169 <= angle <= 180:
            print(f"🔄 زاویه {angle}° به {SAFE_MAX_ANGLE}° تنظیم شد (حداکثر ایمن)")
            return SAFE_MAX_ANGLE
        elif SAFE_MIN_ANGLE <= angle <= SAFE_MAX_ANGLE:
            return angle
        else:
            # برای زاویه‌های خارج از محدوده 0-180، از منطق قبلی استفاده می‌کنیم
            safe_angle = max(SAFE_MIN_ANGLE, min(SAFE_MAX_ANGLE, angle))
            print(f"🔄 زاویه {angle}° به {safe_angle}° تنظیم شد (خارج از محدوده)")
            return safe_angle
            
    except (ValueError, TypeError):
        print(f"⚠️ زاویه نامعتبر: {angle}، استفاده از مقدار پیش‌فرض 90°")
        return 90

def test_angle_validation():
    """تست منطق اعتبارسنجی زاویه"""
    print("🧪 شروع تست اعتبارسنجی زاویه سروو")
    print("=" * 50)
    
    # تست زاویه‌های بین 0 تا 11
    print("\n📋 تست زاویه‌های بین 0 تا 11:")
    for angle in [0, 5, 10, 11]:
        result = validate_servo_angle(angle)
        expected = SAFE_MIN_ANGLE
        status = "✅" if result == expected else "❌"
        print(f"{status} ورودی: {angle}° -> خروجی: {result}° (انتظار: {expected}°)")
    
    # تست زاویه‌های بین 169 تا 180
    print("\n📋 تست زاویه‌های بین 169 تا 180:")
    for angle in [169, 175, 180]:
        result = validate_servo_angle(angle)
        expected = SAFE_MAX_ANGLE
        status = "✅" if result == expected else "❌"
        print(f"{status} ورودی: {angle}° -> خروجی: {result}° (انتظار: {expected}°)")
    
    # تست زاویه‌های معتبر
    print("\n📋 تست زاویه‌های معتبر (12 تا 168):")
    for angle in [12, 50, 90, 150, 168]:
        result = validate_servo_angle(angle)
        expected = angle
        status = "✅" if result == expected else "❌"
        print(f"{status} ورودی: {angle}° -> خروجی: {result}° (انتظار: {expected}°)")
    
    # تست زاویه‌های خارج از محدوده
    print("\n📋 تست زاویه‌های خارج از محدوده:")
    for angle in [-10, 200, 300]:
        result = validate_servo_angle(angle)
        if angle < 0:
            expected = SAFE_MIN_ANGLE
        else:
            expected = SAFE_MAX_ANGLE
        status = "✅" if result == expected else "❌"
        print(f"{status} ورودی: {angle}° -> خروجی: {result}° (انتظار: {expected}°)")
    
    # تست مقادیر نامعتبر
    print("\n📋 تست مقادیر نامعتبر:")
    for value in ["abc", None, "90.5"]:
        result = validate_servo_angle(value)
        expected = 90
        status = "✅" if result == expected else "❌"
        print(f"{status} ورودی: {value} -> خروجی: {result}° (انتظار: {expected}°)")
    
    print("\n" + "=" * 50)
    print("✅ تست اعتبارسنجی زاویه سروو تکمیل شد")

if __name__ == "__main__":
    test_angle_validation() 