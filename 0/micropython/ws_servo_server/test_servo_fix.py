"""
تست عملکرد سرووها - برای دیباگ مشکل زاویه‌ها
"""

import uasyncio as asyncio
from machine import Pin, PWM
import ujson
import time

# تنظیمات سروو
SERVO1_PIN = 17
SERVO2_PIN = 16
SERVO1_FILE = "servo1.json"
SERVO2_FILE = "servo2.json"

# تنظیمات ایمن
SAFE_MIN_ANGLE = 5
SAFE_MAX_ANGLE = 175
SAFE_MIN_PULSE = 1000
SAFE_MAX_PULSE = 2000
SERVO_FREQ = 50

class TestServoController:
    def __init__(self, pin_num, angle_file):
        self.pin = PWM(Pin(pin_num))
        self.pin.freq(SERVO_FREQ)
        self.angle_file = angle_file
        self.current_angle = self.load_angle()
        self.target_angle = self.current_angle
        self.moving = False
        self.last_move_time = 0
        
        # محاسبه پیش‌فرض duty cycle
        self.period = 1000000 / SERVO_FREQ  # us
        self.pulse_range = SAFE_MAX_PULSE - SAFE_MIN_PULSE
        self.angle_range = SAFE_MAX_ANGLE - SAFE_MIN_ANGLE
        
        # تنظیم زاویه اولیه
        self.set_angle(self.current_angle, immediate=True)
        print(f"🎯 سروو {pin_num} راه‌اندازی شد: {self.current_angle}°")
    
    def save_angle(self, angle):
        try:
            with open(self.angle_file, 'w') as f:
                ujson.dump({"angle": angle, "timestamp": str(time.time())}, f)
        except Exception as e:
            print(f"⚠️ خطا در ذخیره زاویه: {e}")
    
    def load_angle(self):
        try:
            with open(self.angle_file, 'r') as f:
                data = ujson.load(f)
                return data.get("angle", 90)
        except:
            return 90
    
    def angle_to_duty(self, angle):
        """تبدیل زاویه به duty cycle"""
        safe_angle = max(SAFE_MIN_ANGLE, min(SAFE_MAX_ANGLE, angle))
        pulse = SAFE_MIN_PULSE + (safe_angle - SAFE_MIN_ANGLE) * (self.pulse_range / self.angle_range)
        duty = int((pulse / self.period) * 65535)
        return max(0, min(65535, duty))
    
    def set_angle(self, target, immediate=False):
        """تنظیم زاویه سروو"""
        if self.moving and not immediate:
            print(f"⚠️ سروو در حال حرکت است")
            return self.current_angle
            
        target = max(SAFE_MIN_ANGLE, min(SAFE_MAX_ANGLE, target))
        
        duty = self.angle_to_duty(target)
        self.pin.duty_u16(duty)
        self.current_angle = target
        self.target_angle = target
        self.save_angle(target)
        print(f"🎯 سروو {self.pin} به زاویه {target}° تنظیم شد")
        return target
    
    def get_status(self):
        """دریافت وضعیت سروو"""
        return {
            "current_angle": self.current_angle,
            "target_angle": self.target_angle,
            "moving": self.moving,
            "pin": str(self.pin)
        }

async def test_angle_auto_adjustment():
    """تست تنظیم خودکار زاویه‌های خارج از محدوده"""
    print("\n🔄 تست تنظیم خودکار زاویه‌ها...")
    
    servo1 = TestServoController(SERVO1_PIN, SERVO1_FILE)
    servo2 = TestServoController(SERVO2_PIN, SERVO2_FILE)
    
    # تست زاویه‌های خارج از محدوده
    test_angles = [
        (0, 0),      # زاویه 0 (معتبر)
        (3, 3),      # کمتر از حداقل
        (180, 180),  # بیشتر از حداکثر
        (5, 5),      # حداقل
        (175, 175),  # حداکثر
        (90, 90),    # مرکز
    ]
    
    for servo1_target, servo2_target in test_angles:
        print(f"\n📥 دستور اصلی: servo1={servo1_target}°, servo2={servo2_target}°")
        
        # شبیه‌سازی تابع validate_servo_angle
        def validate_angle(angle):
            if angle == 0:
                return True, "valid"
            elif angle < SAFE_MIN_ANGLE:
                return True, f"adjusted_to_min_{SAFE_MIN_ANGLE}"
            elif angle > SAFE_MAX_ANGLE:
                return True, f"adjusted_to_max_{SAFE_MAX_ANGLE}"
            else:
                return True, "valid"
        
        # اعتبارسنجی زاویه‌ها
        valid1, result1 = validate_angle(servo1_target)
        valid2, result2 = validate_angle(servo2_target)
        
        # تنظیم خودکار
        if result1.startswith("adjusted_to_min_"):
            adjusted_angle = int(result1.split("_")[-1])
            print(f"🔄 servo1: {servo1_target}° → {adjusted_angle}° (حداقل)")
            servo1_target = adjusted_angle
        elif result1.startswith("adjusted_to_max_"):
            adjusted_angle = int(result1.split("_")[-1])
            print(f"🔄 servo1: {servo1_target}° → {adjusted_angle}° (حداکثر)")
            servo1_target = adjusted_angle
        else:
            print(f"✅ servo1: {servo1_target}° (معتبر)")
            
        if result2.startswith("adjusted_to_min_"):
            adjusted_angle = int(result2.split("_")[-1])
            print(f"🔄 servo2: {servo2_target}° → {adjusted_angle}° (حداقل)")
            servo2_target = adjusted_angle
        elif result2.startswith("adjusted_to_max_"):
            adjusted_angle = int(result2.split("_")[-1])
            print(f"🔄 servo2: {servo2_target}° → {adjusted_angle}° (حداکثر)")
            servo2_target = adjusted_angle
        else:
            print(f"✅ servo2: {servo2_target}° (معتبر)")
        
        # اجرای دستور
        servo1.set_angle(servo1_target)
        servo2.set_angle(servo2_target)
        
        print(f"📊 نتیجه: servo1={servo1.current_angle}°, servo2={servo2.current_angle}°")
        await asyncio.sleep(0.5)
    
    print("\n✅ تست تنظیم خودکار زاویه‌ها تکمیل شد")

async def test_servo_angles():
    """تست زاویه‌های مختلف سروو"""
    print("🧪 شروع تست سرووها...")
    
    # راه‌اندازی سرووها
    servo1 = TestServoController(SERVO1_PIN, SERVO1_FILE)
    servo2 = TestServoController(SERVO2_PIN, SERVO2_FILE)
    
    # تست زاویه‌های مختلف (با محدوده جدید)
    test_angles = [90, 45, 135, 5, 175, 90]
    
    for angle in test_angles:
        print(f"\n🎯 تست زاویه {angle}°")
        print(f"📊 قبل: servo1={servo1.current_angle}°, servo2={servo2.current_angle}°")
        
        # تنظیم زاویه
        servo1.set_angle(angle)
        servo2.set_angle(angle)
        
        print(f"📊 بعد: servo1={servo1.current_angle}°, servo2={servo2.current_angle}°")
        
        # انتظار
        await asyncio.sleep(1)
    
    print("\n✅ تست سرووها تکمیل شد")

async def test_duplicate_detection():
    """تست تشخیص دستورات تکراری"""
    print("\n🔄 تست تشخیص دستورات تکراری...")
    
    servo1 = TestServoController(SERVO1_PIN, SERVO1_FILE)
    servo2 = TestServoController(SERVO2_PIN, SERVO2_FILE)
    
    current_angle1 = servo1.current_angle
    current_angle2 = servo2.current_angle
    
    # تست دستورات مشابه
    test_commands = [
        (90, 90),   # همان زاویه فعلی
        (91, 91),   # نزدیک به زاویه فعلی
        (88, 88),   # نزدیک به زاویه فعلی
        (100, 100), # زاویه متفاوت
        (90, 90),   # بازگشت به زاویه اولیه
    ]
    
    for servo1_target, servo2_target in test_commands:
        print(f"\n📥 دستور: servo1={servo1_target}°, servo2={servo2_target}°")
        print(f"📊 فعلی: X={current_angle1}°, Y={current_angle2}°")
        
        # بررسی دستور تکراری
        angle_tolerance = 2
        servo1_same = abs(servo1_target - current_angle1) <= angle_tolerance
        servo2_same = abs(servo2_target - current_angle2) <= angle_tolerance
        
        if servo1_same and servo2_same:
            print(f"🔄 دستور تکراری تشخیص داده شد!")
        else:
            print(f"✅ دستور جدید - اجرا می‌شود")
            servo1.set_angle(servo1_target)
            servo2.set_angle(servo2_target)
            current_angle1 = servo1.current_angle
            current_angle2 = servo2.current_angle
        
        await asyncio.sleep(0.5)
    
    print("\n✅ تست تشخیص دستورات تکراری تکمیل شد")

async def main():
    """تابع اصلی تست"""
    print("🚀 شروع تست‌های سروو...")
    print("=" * 50)
    
    try:
        await test_servo_angles()
        await test_duplicate_detection()
        await test_angle_auto_adjustment()
        
        print("\n🎉 تمام تست‌ها با موفقیت تکمیل شدند!")
        
    except Exception as e:
        print(f"❌ خطا در تست: {e}")
    
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main()) 