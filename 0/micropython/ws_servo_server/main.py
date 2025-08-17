import network, time, uos, gc, math, ujson
import uasyncio as asyncio
from machine import Pin, PWM, reset
import client as ws_client

# ================================
# تنظیمات سرور و پورت
# ================================
# آدرس WebSocket
WS_URL = "wss://smart-cctv-rash32.chbk.app/ws/pico"

# ================================
# تنظیمات احراز هویت
# ================================
# توکن احراز هویت
AUTH_TOKEN = "rof642fr:5qEKU@A@Tv"
AUTH_HEADER = ("Authorization", f"Bearer {AUTH_TOKEN}")

# ================================
# اتصال به WiFi
# ================================
WIFI_CONFIGS = [
    {"ssid": "SAMSUNG", "password": "panzer790"},
    {"ssid": "Galaxy_A25_5G", "password": "88888888"}
]

# تنظیمات WiFi
WIFI_TIMEOUT = 20  # ثانیه
WIFI_RETRY_DELAY = 5  # ثانیه
WIFI_MAX_ATTEMPTS = 3
ERROR_THRESHOLD = 5
MAX_WS_ERRORS = 5
error_counter = 0
ws_error_count = 0
LOG_INTERVAL = 60
last_log_time = 0
last_pong = 0
global_pico_last_seen = 0
sent_error_messages = set()

# ================================
# تنظیمات سروو
# ================================
SERVO1_PIN = 17
SERVO2_PIN = 16
SERVO1_FILE = "servo1.json"
SERVO2_FILE = "servo2.json"

# --- Safe angle and pulse for MG90S ---
SAFE_MIN_ANGLE = 20
SAFE_MAX_ANGLE = 160
SAFE_MIN_PULSE = 1000   # 1ms
SAFE_MAX_PULSE = 2000   # 2ms
SERVO_FREQ = 50         # 50Hz

# --- تنظیمات حرکت نرم سروو ---
SMOOTH_MOVEMENT_CONFIG = {
    "min_step": 1,           # حداقل گام حرکت (درجه)
    "max_step": 3,           # حداکثر گام حرکت (درجه)
    "min_delay": 0.008,      # حداقل تاخیر بین گام‌ها (ثانیه)
    "max_delay": 0.025,      # حداکثر تاخیر بین گام‌ها (ثانیه)
    "acceleration_steps": 10, # تعداد گام‌های شتاب
    "deceleration_steps": 10, # تعداد گام‌های کاهش سرعت
    "small_movement_threshold": 3,  # آستانه حرکت کوچک (درجه)
    "medium_movement_threshold": 15, # آستانه حرکت متوسط (درجه)
    "large_movement_threshold": 45   # آستانه حرکت بزرگ (درجه)
}

# ================================
# متغیرهای سراسری
# ================================
current_angle1 = 90
current_angle2 = 90
servo1 = None
servo2 = None
connection_ack_sent = False
connection_confirmed = False

# ================================
# تابع اعتبارسنجی زاویه سروو
# ================================
def validate_servo_angle(angle):
    """
    اعتبارسنجی زاویه سروو با منطق جدید:
    - اگر زاویه بین 0 تا 11 باشد، به SAFE_MIN_ANGLE تنظیم می‌شود
    - اگر زاویه بین 169 تا 180 باشد، به SAFE_MAX_ANGLE تنظیم می‌شود
    - زاویه‌های بین 11 تا 169 بدون تغییر باقی می‌مانند
    """
    try:
        angle = int(angle)
        
        if 0 <= angle <= SAFE_MIN_ANGLE:
            return SAFE_MIN_ANGLE
        elif SAFE_MAX_ANGLE <= angle <= 180:
            return SAFE_MAX_ANGLE
        elif SAFE_MIN_ANGLE <= angle <= SAFE_MAX_ANGLE:
            return angle
        else:
            # برای زاویه‌های خارج از محدوده 0-180، از منطق قبلی استفاده می‌کنیم
            safe_angle = max(SAFE_MIN_ANGLE, min(SAFE_MAX_ANGLE, angle))
            return safe_angle
            
    except (ValueError, TypeError):
        print(f"⚠️ زاویه نامعتبر: {angle}، استفاده از مقدار پیش‌فرض 90°")
        return 90

# ================================
# کلاس کنترل سروو
# ================================
class ServoController:
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
        
        # تنظیم اولیه سروو
        duty = self.angle_to_duty(self.current_angle)
        self.pin.duty_u16(duty)
    
    def save_angle(self, angle):
        try:
            with open(self.angle_file, 'w') as f:
                ujson.dump({"angle": angle, "timestamp": get_now_str()}, f)
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
        """تبدیل زاویه به duty cycle با بهینه‌سازی"""
        safe_angle = validate_servo_angle(angle)
        # محاسبه بهینه‌شده
        pulse = SAFE_MIN_PULSE + (safe_angle - SAFE_MIN_ANGLE) * (self.pulse_range / self.angle_range)
        duty = int((pulse / self.period) * 65535)
        return max(0, min(65535, duty))
    
    async def set_angle(self, current, target, immediate=False):
        if self.moving and not immediate:
            print(f"⚠️ سروو در حال حرکت است، دستور نادیده گرفته شد")
            return current
            
        target = validate_servo_angle(target)
        
        # حرکت مستقیم برای تغییرات بسیار کوچک یا دستورات فوری
        if immediate or abs(target - current) <= SMOOTH_MOVEMENT_CONFIG["small_movement_threshold"]:
            duty = self.angle_to_duty(target)
            self.pin.duty_u16(duty)
            self.current_angle = target
            self.target_angle = target
            self.save_angle(target)
            return target
        
        # حرکت نرم با الگوریتم پیشرفته
        self.moving = True
        movement_distance = abs(target - current)
        direction = 1 if target > current else -1
        
        try:
            # محاسبه پارامترهای حرکت بر اساس فاصله
            if movement_distance <= SMOOTH_MOVEMENT_CONFIG["medium_movement_threshold"]:
                # حرکت متوسط - سرعت ثابت
                step_size = SMOOTH_MOVEMENT_CONFIG["min_step"]
                step_delay = SMOOTH_MOVEMENT_CONFIG["min_delay"]
                movement_type = "متوسط"
            elif movement_distance <= SMOOTH_MOVEMENT_CONFIG["large_movement_threshold"]:
                # حرکت بزرگ - شتاب و کاهش سرعت ساده
                step_size = SMOOTH_MOVEMENT_CONFIG["max_step"]
                step_delay = SMOOTH_MOVEMENT_CONFIG["max_delay"]
                movement_type = "بزرگ"
            else:
                # حرکت بسیار بزرگ - شتاب و کاهش سرعت پیشرفته
                step_size = SMOOTH_MOVEMENT_CONFIG["max_step"]
                step_delay = SMOOTH_MOVEMENT_CONFIG["max_delay"]
                movement_type = "بسیار بزرگ"
            
            print(f"🎯 شروع حرکت {movement_type}: {current}° → {target}°")
            
            # محاسبه تعداد گام‌ها
            if step_size <= 0:
                step_size = 1
            total_steps = int(movement_distance / step_size)
            if total_steps == 0:
                total_steps = 1
            
            # حرکت با شتاب و کاهش سرعت پیشرفته
            current_pos = current
            acceleration_steps = min(SMOOTH_MOVEMENT_CONFIG["acceleration_steps"], total_steps // 3)
            deceleration_steps = min(SMOOTH_MOVEMENT_CONFIG["deceleration_steps"], total_steps // 3)
            constant_steps = total_steps - acceleration_steps - deceleration_steps
            
            # فاز شتاب
            for i in range(acceleration_steps):
                if not self.moving:
                    break
                current_pos += direction * step_size
                safe_angle = validate_servo_angle(current_pos)
                duty = self.angle_to_duty(safe_angle)
                self.pin.duty_u16(duty)
                self.current_angle = safe_angle
                
                # تاخیر متغیر - شتاب
                dynamic_delay = step_delay * (1.0 - (i / acceleration_steps) * 0.5)
                await asyncio.sleep(dynamic_delay)
            
            # فاز سرعت ثابت
            for i in range(constant_steps):
                if not self.moving:
                    break
                current_pos += direction * step_size
                safe_angle = validate_servo_angle(current_pos)
                duty = self.angle_to_duty(safe_angle)
                self.pin.duty_u16(duty)
                self.current_angle = safe_angle
                await asyncio.sleep(step_delay)
            
            # فاز کاهش سرعت
            for i in range(deceleration_steps):
                if not self.moving:
                    break
                current_pos += direction * step_size
                safe_angle = validate_servo_angle(current_pos)
                duty = self.angle_to_duty(safe_angle)
                self.pin.duty_u16(duty)
                self.current_angle = safe_angle
                
                # تاخیر متغیر - کاهش سرعت
                dynamic_delay = step_delay * (1.0 + (i / deceleration_steps) * 0.5)
                await asyncio.sleep(dynamic_delay)
            
            # تنظیم دقیق زاویه نهایی
            final_duty = self.angle_to_duty(target)
            self.pin.duty_u16(final_duty)
            self.current_angle = target
            self.target_angle = target
            self.save_angle(target)
            
            print(f"✅ سروو {self.pin} به زاویه {target}° تنظیم شد")
            
        except Exception as e:
            print(f"❌ خطا در حرکت سروو: {e}")
            # بازگشت به موقعیت ایمن
            safe_duty = self.angle_to_duty(current)
            self.pin.duty_u16(safe_duty)
            self.current_angle = current
        finally:
            self.moving = False
            self.last_move_time = time.time()
        
        return self.current_angle
    
    def emergency_stop(self):
        """توقف اضطراری سروو"""
        self.moving = False
        current_duty = self.angle_to_duty(self.current_angle)
        self.pin.duty_u16(current_duty)
        print(f"🛑 توقف اضطراری سروو {self.pin}")
    
    async def emergency_stop_smooth(self):
        """توقف اضطراری نرم سروو"""
        if not self.moving:
            return
            
        print(f"🛑 توقف اضطراری نرم سروو {self.pin}")
        self.moving = False
        
        # توقف نرم با کاهش تدریجی سرعت
        try:
            current_pos = self.current_angle
            target_pos = self.current_angle  # توقف در موقعیت فعلی
            
            # کاهش سرعت در 5 گام
            for i in range(5):
                if not self.moving:
                    break
                    
                # محاسبه موقعیت با کاهش سرعت
                progress = i / 5.0
                smooth_progress = progress * progress * (3 - 2 * progress)
                stop_pos = current_pos + (target_pos - current_pos) * smooth_progress
                
                safe_angle = validate_servo_angle(stop_pos)
                duty = self.angle_to_duty(safe_angle)
                self.pin.duty_u16(duty)
                self.current_angle = safe_angle
                
                await asyncio.sleep(0.01)  # تاخیر کوتاه
            
            # تنظیم نهایی
            final_duty = self.angle_to_duty(target_pos)
            self.pin.duty_u16(final_duty)
            self.current_angle = target_pos
            
        except Exception as e:
            print(f"❌ خطا در توقف نرم: {e}")
            # توقف فوری
            current_duty = self.angle_to_duty(self.current_angle)
            self.pin.duty_u16(current_duty)
    
    def get_status(self):
        """دریافت وضعیت سروو"""
        return {
            "current_angle": self.current_angle,
            "target_angle": self.target_angle,
            "moving": self.moving,
            "last_move_time": self.last_move_time,
            "pin": str(self.pin)
        }
    
    def _calculate_movement_params(self, current, target):
        """محاسبه پارامترهای حرکت بر اساس شرایط سیستم"""
        movement_distance = abs(target - current)
        
        # بررسی حافظه آزاد
        memory_free = gc.mem_free()
        if memory_free < 5000:  # کمتر از 5KB
            # کاهش تعداد گام‌ها برای صرفه‌جویی در حافظه
            total_steps = max(10, int(movement_distance * 1.5))
            base_delay = SMOOTH_MOVEMENT_CONFIG["max_delay"]
        elif memory_free < 10000:  # کمتر از 10KB
            total_steps = max(15, int(movement_distance * 1.8))
            base_delay = SMOOTH_MOVEMENT_CONFIG["max_delay"] * 0.8
        else:
            # حافظه کافی - استفاده از تنظیمات بهینه
            total_steps = max(20, int(movement_distance * 2))
            base_delay = SMOOTH_MOVEMENT_CONFIG["min_delay"]
        
        # تنظیم بر اساس فاصله حرکت
        if movement_distance <= 10:
            # حرکت کوچک - سرعت بالا
            total_steps = max(8, int(movement_distance * 1.5))
            base_delay = SMOOTH_MOVEMENT_CONFIG["min_delay"]
        elif movement_distance <= 30:
            # حرکت متوسط - تعادل
            total_steps = max(15, int(movement_distance * 1.8))
            base_delay = (SMOOTH_MOVEMENT_CONFIG["min_delay"] + SMOOTH_MOVEMENT_CONFIG["max_delay"]) / 2
        else:
            # حرکت بزرگ - دقت بالا
            total_steps = max(25, int(movement_distance * 2.2))
            base_delay = SMOOTH_MOVEMENT_CONFIG["max_delay"]
        
        return {
            "total_steps": total_steps,
            "base_delay": base_delay,
            "movement_distance": movement_distance
        }
    

    
    async def set_angle_ultra_smooth(self, current, target, immediate=False):
        """حرکت فوق نرم با interpolation پیشرفته"""
        if self.moving and not immediate:
            print(f"⚠️ سروو در حال حرکت است، دستور نادیده گرفته شد")
            return current
            
        target = validate_servo_angle(target)
        
        # حرکت مستقیم برای تغییرات بسیار کوچک
        if immediate or abs(target - current) <= 1:
            duty = self.angle_to_duty(target)
            self.pin.duty_u16(duty)
            self.current_angle = target
            self.target_angle = target
            self.save_angle(target)
            return target
        
        # تنظیم پارامترهای حرکت بر اساس شرایط سیستم
        movement_params = self._calculate_movement_params(current, target)
        
        # حرکت فوق نرم با interpolation
        self.moving = True
        direction = 1 if target > current else -1
        
        try:
            total_steps = movement_params["total_steps"]
            base_delay = movement_params["base_delay"]
            movement_distance = movement_params["movement_distance"]
            
            print(f"🎯 شروع حرکت فوق نرم: {current}° → {target}°")
            
            # حرکت با interpolation نرم
            if total_steps <= 0:
                total_steps = 1
            for i in range(total_steps + 1):
                if not self.moving:
                    break
                
                # محاسبه زاویه با interpolation
                progress = i / total_steps
                # استفاده از تابع نرم برای حرکت طبیعی‌تر
                smooth_progress = progress * progress * (3 - 2 * progress)  # Smoothstep function
                current_pos = current + (target - current) * smooth_progress
                
                safe_angle = validate_servo_angle(current_pos)
                duty = self.angle_to_duty(safe_angle)
                self.pin.duty_u16(duty)
                self.current_angle = safe_angle
                
                # تاخیر متغیر بر اساس پیشرفت و شرایط سیستم
                if progress < 0.2:
                    # شتاب اولیه
                    delay = base_delay * (1.5 - progress * 1.0)
                elif progress < 0.4:
                    # شتاب ادامه‌دار
                    delay = base_delay * (1.0 - (progress - 0.2) * 0.5)
                elif progress > 0.8:
                    # کاهش سرعت نهایی
                    delay = base_delay * (1.0 + (progress - 0.8) * 1.0)
                elif progress > 0.6:
                    # شروع کاهش سرعت
                    delay = base_delay * (1.0 + (progress - 0.6) * 0.5)
                else:
                    # سرعت ثابت
                    delay = base_delay
                
                # محدود کردن تاخیر
                delay = max(SMOOTH_MOVEMENT_CONFIG["min_delay"], 
                           min(SMOOTH_MOVEMENT_CONFIG["max_delay"], delay))
                
                await asyncio.sleep(delay)
            
            # تنظیم دقیق زاویه نهایی
            final_duty = self.angle_to_duty(target)
            self.pin.duty_u16(final_duty)
            self.current_angle = target
            self.target_angle = target
            self.save_angle(target)
            
            print(f"✅ سروو {self.pin} به زاویه {target}° تنظیم شد")
            
        except Exception as e:
            print(f"❌ خطا در حرکت فوق نرم سروو: {e}")
            # بازگشت به موقعیت ایمن
            safe_duty = self.angle_to_duty(current)
            self.pin.duty_u16(safe_duty)
            self.current_angle = current
        finally:
            self.moving = False
            self.last_move_time = time.time()
        
        return self.current_angle

# ================================
# اتصال WiFi
# ================================

def configure_wifi():
    """تنظیم WiFi برای عملکرد بهتر"""
    try:
        wlan = network.WLAN(network.STA_IF)
        print("⚙️ تنظیمات WiFi اعمال شد")
        return True
    except Exception as e:
        print(f"⚠️ خطا در تنظیم WiFi: {e}")
        return False

def test_internet_connection():
    """تست اتصال اینترنت"""
    try:
        import socket
        addr_info = socket.getaddrinfo("8.8.8.8", 80)
        print("✅ اتصال اینترنت برقرار است")
        return True
    except Exception as e:
        print(f"❌ اتصال اینترنت ناموفق: {e}")
        return False

def simple_wifi_connect():
    """اتصال ساده به WiFi بدون async"""
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        
        for config in WIFI_CONFIGS:
            try:
                print(f"🔗 اتصال ساده به {config['ssid']}...")
                
                if wlan.isconnected():
                    wlan.disconnect()
                    time.sleep(1)
                
                wlan.connect(config['ssid'], config['password'])
                
                # انتظار ساده
                for i in range(5):
                    if wlan.isconnected():
                        ip_config = wlan.ifconfig()
                        print(f"✅ اتصال موفق: {config['ssid']}")
                        print(f"📡 IP: {ip_config[0]}")
                        return True
                    time.sleep(1)
                
                print(f"❌ اتصال ناموفق: {config['ssid']}")
                
            except Exception as e:
                print(f"⚠️ خطا: {e}")
                continue
        
        return False
        
    except Exception as e:
        print(f"❌ خطای کلی WiFi: {e}")
        return False

async def connect_wifi():
    """اتصال به WiFi با بهبود مدیریت خطا"""
    global error_counter
    
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    for config in WIFI_CONFIGS:
        try:
            print(f"🔗 تلاش برای اتصال به {config['ssid']}...")
            
            # قطع اتصال قبلی
            if wlan.isconnected():
                wlan.disconnect()
                await asyncio.sleep(0.5)
            
            # تلاش برای اتصال
            wlan.connect(config['ssid'], config['password'])
            print(f"⏳ انتظار برای اتصال...")
            
            # انتظار برای اتصال - ساده‌شده
            for i in range(8):  # حداکثر 8 ثانیه
                if wlan.isconnected():
                    ip_config = wlan.ifconfig()
                    print(f"✅ اتصال WiFi موفق: {config['ssid']}")
                    print(f"📡 IP: {ip_config[0]}")
                    print(f"🌐 Gateway: {ip_config[2]}")
                    print(f"📶 Signal: {wlan.status()}")
                    error_counter = 0
                    return True
                
                # نمایش پیشرفت
                if i % 2 == 0:
                    print(f"⏳ انتظار... {8-i} ثانیه")
                
                await asyncio.sleep(1)
            
            print(f"❌ اتصال به {config['ssid']} ناموفق")
            
        except Exception as e:
            print(f"⚠️ خطا در اتصال به {config['ssid']}: {e}")
            error_counter += 1
            await asyncio.sleep(1)
    
    print("❌ اتصال به هیچ شبکه‌ای موفق نبود")
    error_counter += 1
    
    if error_counter >= ERROR_THRESHOLD:
        print("🔄 ریست سیستم به دلیل خطاهای مکرر...")
        await asyncio.sleep(2)
        reset()
    
    return False

# ================================
# تنظیمات ثابت
# ================================
# این بخش حذف شده - تنظیمات ثابت هستند

# ================================
# ریست سیستم
# ================================
async def do_reboot():
    """ریست سیستم"""
    print("🔄 ریست سیستم در حال انجام...")
    send_log(None, "System reboot initiated", "warning")
    await asyncio.sleep(2)
    reset()

# ================================
# پردازش دستورات (بهبود یافته)
# ================================
async def process_command(cmd, ws=None):
    global current_angle1, current_angle2
    try:
        cmd_type = cmd.get('type')
        
        # به‌روزرسانی زمان آخرین فعالیت
        global global_pico_last_seen
        global_pico_last_seen = time.time()
        
        if cmd_type == 'pong':
            global last_pong
            last_pong = time.time()
            return
            
        if cmd_type == 'ping':
            if ws:
                try:
                    pong_message = {
                        "type": "pong",
                        "timestamp": get_now_str(),
                        "device": "pico",
                        "memory_free": gc.mem_free()
                    }
                    ws.send(ujson.dumps(pong_message))
                except Exception as e:
                    print(f"⚠️ خطا در ارسال pong: {e}")
            return
            
        if cmd_type == 'connection':
            global connection_confirmed
            status = cmd.get('status', 'unknown')
            message = cmd.get('message', '')
            print(f"✅ اتصال تایید شد: {status} - {message}")
            # ارسال ACK فقط یک بار
            if ws and not connection_confirmed:
                send_ack(ws, 'connection', status='success', detail='Connection confirmed')
                connection_confirmed = True
            return
            
        if cmd_type == 'connection_ack':
            global connection_ack_sent
            status = cmd.get('status', 'unknown')
            message = cmd.get('message', '')
            print(f"✅ تایید اتصال دریافت شد: {status} - {message}")
            # ارسال ACK فقط یک بار
            if ws and not connection_ack_sent:
                send_ack(ws, 'connection_ack', status='success', detail='Connection acknowledged')
                connection_ack_sent = True
            return
            
        if cmd_type == 'ack':
            print(f"📥 دریافت پیام ack: {cmd}")
            return
            
        if not cmd_type or cmd_type == '':
            print("⚠️ پیام خالی دریافت شد، نادیده گرفته شد")
            return
            
        if cmd_type == 'status':
            print("📊 دریافت پیام status")
            if ws:
                status_data = {
                    "servo1": servo1.get_status() if servo1 else None,
                    "servo2": servo2.get_status() if servo2 else None,
                    "memory_free": gc.mem_free(),
                    "uptime": time.time(),
                    "wifi_connected": network.WLAN(network.STA_IF).isconnected()
                }
                send_ack(ws, 'status', status='success', detail=status_data)
            return
            
        # دستورات config حذف شده - تنظیمات ثابت هستند
            
        if cmd_type == 'servo':
            servo_data = cmd.get('command', cmd)
            servo1_target = int(servo_data.get('servo1', 90))
            servo2_target = int(servo_data.get('servo2', 90))
            
            # اعتبارسنجی با منطق جدید
            servo1_target = validate_servo_angle(servo1_target)
            servo2_target = validate_servo_angle(servo2_target)
            
            # بررسی دستور تکراری سریع
            if servo1_target == current_angle1 and servo2_target == current_angle2:
                print(f"🔄 دستور تکراری سروو نادیده گرفته شد")
                if ws:
                    send_ack(ws, 'servo', status='ignored', detail='Duplicate command')
                return
                
            print(f"🎯 اجرای دستور سروو: X={servo1_target}°, Y={servo2_target}°")
            
            if servo1 and servo2:
                try:
                    # انتخاب نوع حرکت بر اساس فاصله
                    movement_distance1 = abs(servo1_target - current_angle1)
                    movement_distance2 = abs(servo2_target - current_angle2)
                    
                    # استفاده از حرکت فوق نرم برای تغییرات بزرگ
                    use_ultra_smooth = (movement_distance1 > 20 or movement_distance2 > 20)
                    
                    if use_ultra_smooth:
                        servo1_task = asyncio.create_task(servo1.set_angle_ultra_smooth(current_angle1, servo1_target))
                        servo2_task = asyncio.create_task(servo2.set_angle_ultra_smooth(current_angle2, servo2_target))
                    else:
                        servo1_task = asyncio.create_task(servo1.set_angle(current_angle1, servo1_target))
                        servo2_task = asyncio.create_task(servo2.set_angle(current_angle2, servo2_target))
                    
                    # انتظار برای تکمیل هر دو
                    await asyncio.gather(servo1_task, servo2_task)
                    
                    current_angle1 = servo1.current_angle
                    current_angle2 = servo2.current_angle
                    
                    print(f"✅ دستور سروو تکمیل شد")
                    if ws:
                        send_ack(ws, 'servo', status='success', detail=f'X={current_angle1}°, Y={current_angle2}°')
                        
                except Exception as e:
                    print(f"❌ خطا در اجرای سروو: {e}")
                    # توقف اضطراری نرم
                    try:
                        if servo1:
                            await servo1.emergency_stop_smooth()
                        if servo2:
                            await servo2.emergency_stop_smooth()
                    except:
                        # اگر توقف نرم ناموفق بود، توقف فوری
                        if servo1:
                            servo1.emergency_stop()
                        if servo2:
                            servo2.emergency_stop()
                    if ws:
                        send_ack(ws, 'servo', status='error', detail=str(e))
            else:
                print("❌ سرووها آماده نیستند")
                if ws:
                    send_ack(ws, 'servo', status='error', detail='Servos not initialized')
            return
        if cmd_type == 'action':
            action_data = cmd.get('command', {})
            action = action_data.get('action', '')
            print(f"🎯 اجرای عملیات: {action}")
            if action == 'reset_position':
                if servo1 and servo2:
                    try:
                        await servo1.set_angle(current_angle1, 90, immediate=True)
                        await servo2.set_angle(current_angle2, 90, immediate=True)
                        current_angle1 = 90
                        current_angle2 = 90
                        print("✅ سرووها به موقعیت مرکزی بازگشتند")
                        if ws:
                            send_ack(ws, 'action', status='success', detail='Reset to center position')
                    except Exception as e:
                        print(f"❌ خطا در reset position: {e}")
                        if ws:
                            send_ack(ws, 'action', status='error', detail=str(e))
            elif action == 'emergency_stop':
                if servo1 and servo2:
                    try:
                        await servo1.set_angle(current_angle1, current_angle1, immediate=True)
                        await servo2.set_angle(current_angle2, current_angle2, immediate=True)
                        print("🛑 توقف اضطراری سرووها")
                        if ws:
                            send_ack(ws, 'action', status='success', detail='Emergency stop executed')
                    except Exception as e:
                        print(f"❌ خطا در emergency stop: {e}")
                        if ws:
                            send_ack(ws, 'action', status='error', detail=str(e))
            elif action == 'emergency_stop_smooth':
                if servo1 and servo2:
                    try:
                        await servo1.emergency_stop_smooth()
                        await servo2.emergency_stop_smooth()
                        print("🛑 توقف اضطراری نرم سرووها")
                        if ws:
                            send_ack(ws, 'action', status='success', detail='Smooth emergency stop executed')
                    except Exception as e:
                        print(f"❌ خطا در smooth emergency stop: {e}")
                        if ws:
                            send_ack(ws, 'action', status='error', detail=str(e))
            elif action == 'system_reboot':
                print("🔄 دریافت دستور ریست سخت‌افزاری!")
                send_log(ws, "System reboot command received", "warning")
                asyncio.create_task(do_reboot())
            else:
                print(f"❌ عملیات ناشناخته: {action}")
                if ws:
                    send_ack(ws, 'action', status='error', detail=f'Unknown action: {action}')
            return
        if cmd_type == 'servo_smooth':
            # دستور حرکت فوق نرم سروو
            servo_data = cmd.get('command', cmd)
            servo1_target = int(servo_data.get('servo1', 90))
            servo2_target = int(servo_data.get('servo2', 90))
            
            # اعتبارسنجی با منطق جدید
            servo1_target = validate_servo_angle(servo1_target)
            servo2_target = validate_servo_angle(servo2_target)
            
            # بررسی دستور تکراری سریع
            if servo1_target == current_angle1 and servo2_target == current_angle2:
                print(f"🔄 دستور تکراری سروو نادیده گرفته شد")
                if ws:
                    send_ack(ws, 'servo_smooth', status='ignored', detail='Duplicate command')
                return
                
            print(f"🎯 اجرای دستور حرکت فوق نرم سروو: X={servo1_target}°, Y={servo2_target}°")
            
            if servo1 and servo2:
                try:
                    # همیشه از حرکت فوق نرم استفاده کن
                    servo1_task = asyncio.create_task(servo1.set_angle_ultra_smooth(current_angle1, servo1_target))
                    servo2_task = asyncio.create_task(servo2.set_angle_ultra_smooth(current_angle2, servo2_target))
                    
                    # انتظار برای تکمیل هر دو
                    await asyncio.gather(servo1_task, servo2_task)
                    
                    current_angle1 = servo1.current_angle
                    current_angle2 = servo2.current_angle
                    
                    print(f"✅ دستور حرکت فوق نرم سروو تکمیل شد")
                    if ws:
                        send_ack(ws, 'servo_smooth', status='success', detail=f'X={current_angle1}°, Y={current_angle2}°')
                        
                except Exception as e:
                    print(f"❌ خطا در اجرای حرکت فوق نرم سروو: {e}")
                    # توقف اضطراری نرم
                    try:
                        if servo1:
                            await servo1.emergency_stop_smooth()
                        if servo2:
                            await servo2.emergency_stop_smooth()
                    except:
                        # اگر توقف نرم ناموفق بود، توقف فوری
                        if servo1:
                            servo1.emergency_stop()
                        if servo2:
                            servo2.emergency_stop()
                    if ws:
                        send_ack(ws, 'servo_smooth', status='error', detail=str(e))
            else:
                print("❌ سرووها آماده نیستند")
                if ws:
                    send_ack(ws, 'servo_smooth', status='error', detail='Servos not initialized')
            return
            
        if cmd_type == 'command':
            command_data = cmd.get('command', {})
            if 'servo1' in command_data or 'servo2' in command_data:
                servo1_target = int(command_data.get('servo1', 90))
                servo2_target = int(command_data.get('servo2', 90))
                servo1_target = validate_servo_angle(servo1_target)
                servo2_target = validate_servo_angle(servo2_target)
                print(f"🎯 اجرای دستور command (servo): servo1={servo1_target}°, servo2={servo2_target}°")
                if servo1 and servo2:
                    try:
                        # انتخاب نوع حرکت بر اساس فاصله
                        movement_distance1 = abs(servo1_target - current_angle1)
                        movement_distance2 = abs(servo2_target - current_angle2)
                        
                        # استفاده از حرکت فوق نرم برای تغییرات بزرگ
                        use_ultra_smooth = (movement_distance1 > 20 or movement_distance2 > 20)
                        
                        if use_ultra_smooth:
                            current_angle1 = await servo1.set_angle_ultra_smooth(current_angle1, servo1_target)
                            current_angle2 = await servo2.set_angle_ultra_smooth(current_angle2, servo2_target)
                        else:
                            current_angle1 = await servo1.set_angle(current_angle1, servo1_target)
                            current_angle2 = await servo2.set_angle(current_angle2, servo2_target)
                            
                        print(f"✅ دستور command اجرا شد")
                        if ws:
                            send_ack(ws, 'command', status='success', detail='Processed as servo command')
                    except Exception as e:
                        print(f"❌ خطا در اجرای command: {e}")
                        # توقف اضطراری نرم
                        try:
                            if servo1:
                                await servo1.emergency_stop_smooth()
                            if servo2:
                                await servo2.emergency_stop_smooth()
                        except:
                            # اگر توقف نرم ناموفق بود، توقف فوری
                            if servo1:
                                servo1.emergency_stop()
                            if servo2:
                                servo2.emergency_stop()
                        if ws:
                            send_ack(ws, 'command', status='error', detail=str(e))
                else:
                    if ws:
                        send_ack(ws, 'command', status='error', detail='Servos not initialized')
                return
            elif 'action' in command_data:
                action = command_data.get('action', '')
                print(f"🎯 اجرای دستور command (action): action={action}")
                if action == 'reset_position':
                    if servo1 and servo2:
                        try:
                            await servo1.set_angle(current_angle1, 90, immediate=True)
                            await servo2.set_angle(current_angle2, 90, immediate=True)
                            current_angle1 = 90
                            current_angle2 = 90
                            print("✅ سرووها به موقعیت مرکزی بازگشتند")
                            if ws:
                                send_ack(ws, 'command', status='success', detail='Reset to center position')
                        except Exception as e:
                            print(f"❌ خطا در reset position: {e}")
                            if ws:
                                send_ack(ws, 'command', status='error', detail=str(e))
                elif action == 'emergency_stop':
                    if servo1 and servo2:
                        try:
                            await servo1.set_angle(current_angle1, current_angle1, immediate=True)
                            await servo2.set_angle(current_angle2, current_angle2, immediate=True)
                            print("🛑 توقف اضطراری سرووها")
                            if ws:
                                send_ack(ws, 'command', status='success', detail='Emergency stop executed')
                        except Exception as e:
                            print(f"❌ خطا در emergency stop: {e}")
                            if ws:
                                send_ack(ws, 'command', status='error', detail=str(e))
                elif action == 'emergency_stop_smooth':
                    if servo1 and servo2:
                        try:
                            await servo1.emergency_stop_smooth()
                            await servo2.emergency_stop_smooth()
                            print("🛑 توقف اضطراری نرم سرووها")
                            if ws:
                                send_ack(ws, 'command', status='success', detail='Smooth emergency stop executed')
                        except Exception as e:
                            print(f"❌ خطا در smooth emergency stop: {e}")
                            if ws:
                                send_ack(ws, 'command', status='error', detail=str(e))
                elif action == 'system_reboot':
                    print("🔄 دریافت دستور ریست سخت‌افزاری!")
                    send_log(ws, "System reboot command received", "warning")
                    asyncio.create_task(do_reboot())
                else:
                    print(f"❌ عملیات ناشناخته: {action}")
                    if ws:
                        send_ack(ws, 'command', status='error', detail=f'Unknown action: {action}')
                return
            else:
                print(f"❌ پیام command نامعتبر: {cmd}")
                if ws:
                    send_ack(ws, 'command', status='ignored', detail='Invalid command format')
                return
        print(f"❓ پیام ناشناخته: {cmd}")
        if ws:
            send_ack(ws, 'unknown', status='ignored', detail=str(cmd))
    except Exception as e:
        print(f"❌ خطا در پردازش دستور: {e}")
        if ws:
            send_ack(ws, 'error', status='error', detail=str(e))

# ================================
# WebSocket Client (بهبود یافته)
# ================================
async def websocket_client():
    global error_counter, global_pico_last_seen, ws_error_count, last_pong
    reconnect_attempt = 0
    ws = None
    
    while True:
        try:
            # پاکسازی حافظه قبل از اتصال
            gc.collect()
            
            print(f"🔗 تلاش برای اتصال به WebSocket: {WS_URL}")
            print(f"🔑 استفاده از توکن: {AUTH_TOKEN[:10]}...")
            
            # اتصال به WebSocket با احراز هویت
            try:
                ws = ws_client.connect(WS_URL, headers=[AUTH_HEADER])
            except Exception as e:
                print(f"❌ خطا در اتصال WebSocket: {e}")
                ws = None
            
            if ws and hasattr(ws, 'send') and hasattr(ws, 'recv'):
                print("✅ اتصال WebSocket موفق")
                ws_error_count = 0
                reconnect_attempt = 0
                global_pico_last_seen = time.time()
                
                # ریست کردن متغیرهای اتصال
                global connection_confirmed, connection_ack_sent
                connection_confirmed = False
                connection_ack_sent = False
                
                # ارسال پیام اولیه بهبود یافته
                initial_message = {
                    "type": "connect",
                    "device": "pico",
                    "timestamp": get_now_str(),
                    "version": "2.0",
                    "servo1_angle": current_angle1,
                    "servo2_angle": current_angle2,
                    "auth_token": AUTH_TOKEN[:10] + "...",
                    "memory_free": gc.mem_free(),
                    "wifi_ssid": network.WLAN(network.STA_IF).config('ssid') if network.WLAN(network.STA_IF).isconnected() else "disconnected",
                    "connection_id": int(time.time())  # شناسه یکتا برای اتصال
                }
                ws.send(ujson.dumps(initial_message))
                print("📤 پیام اولیه ارسال شد")
                
                # انتظار برای تایید اتصال
                await asyncio.sleep(1)
                
                # حلقه اصلی WebSocket
                message_count = 0
                last_activity = time.time()
                last_ping = time.time()
                last_memory_check = time.time()
                
                while True:
                    try:
                        current_time = time.time()
                        
                        # بررسی timeout اتصال
                        if current_time - last_activity > 60:
                            print("⏰ timeout اتصال، تلاش مجدد...")
                            break
                        
                        # ارسال ping هر 15 ثانیه
                        if current_time - last_ping > 15:
                            try:
                                ping_message = {
                                    "type": "ping", 
                                    "timestamp": get_now_str(),
                                    "device": "pico",
                                    "memory_free": gc.mem_free()
                                }
                                ws.send(ujson.dumps(ping_message))
                                last_ping = current_time
                                print("📤 ping ارسال شد")
                            except Exception as e:
                                print(f"⚠️ خطا در ارسال ping: {e}")
                                break
                        
                        # بررسی سلامت سیستم هر 30 ثانیه
                        if current_time - last_memory_check > 30:
                            health = check_system_health()
                            if health.get("memory_free", 0) < 5000:  # کمتر از 5KB
                                print(f"⚠️ حافظه کم: {health['memory_free']} bytes")
                                gc.collect()
                                print(f"✅ حافظه آزاد بعد از پاکسازی: {gc.mem_free()} bytes")
                            last_memory_check = current_time
                        
                        # پاکسازی حافظه هر 10 پیام
                        if message_count % 10 == 0:
                            gc.collect()
                        
                        try:
                            message = ws.recv()
                            if message:
                                last_activity = current_time
                                global_pico_last_seen = current_time
                                message_count += 1
                                
                                try:
                                    data = ujson.loads(message)
                                    await process_command(data, ws)
                                    # پاکسازی فوری حافظه بعد از پردازش
                                    del data
                                    gc.collect()
                                except Exception as e:
                                    print(f"❌ خطا در پردازش پیام: {e}")
                                    print(f"📥 پیام دریافتی: {message[:50]}...")
                        except Exception as recv_error:
                            print(f"⚠️ خطا در دریافت پیام: {recv_error}")
                            break
                        
                        # انتظار کوتاه‌تر برای پاسخگویی بهتر
                        await asyncio.sleep(0.005)  # 5ms delay - بهینه‌سازی
                        
                    except Exception as e:
                        print(f"⚠️ خطا در دریافت پیام: {e}")
                        break
                        
            else:
                print("❌ اتصال WebSocket ناموفق")
                ws_error_count += 1
                
        except Exception as e:
            print(f"❌ خطا در WebSocket client: {e}")
            ws_error_count += 1
            error_counter += 1
            
            # ثبت خطا
            append_error_log({
                "type": "websocket_error",
                "error": str(e),
                "timestamp": get_now_str(),
                "ws_error_count": ws_error_count,
                "error_counter": error_counter
            })
            
            # بررسی تعداد خطاها
            if ws_error_count >= MAX_WS_ERRORS:
                print(f"❌ تعداد خطاهای WebSocket به حد مجاز رسید ({MAX_WS_ERRORS})")
                if error_counter >= ERROR_THRESHOLD:
                    print("🔄 ریست سیستم به دلیل خطاهای مکرر...")
                    await asyncio.sleep(2)
                    reset()
                else:
                    print("⏰ انتظار طولانی‌تر قبل از تلاش مجدد...")
                    await asyncio.sleep(30)
                    ws_error_count = 0
            else:
                # انتظار تدریجی با بهبود
                reconnect_delay = min(3 * (reconnect_attempt + 1), 15)  # کاهش تاخیر
                print(f"⏰ انتظار {reconnect_delay} ثانیه قبل از تلاش مجدد...")
                await asyncio.sleep(reconnect_delay)
                reconnect_attempt += 1
                
                # پاکسازی حافظه قبل از تلاش مجدد
                gc.collect()
                
        finally:
            # پاکسازی اتصال
            if ws:
                try:
                    ws.close()
                except:
                    pass
            ws = None

# ================================
# تابع اصلی (بهبود یافته)
# ================================
async def main():
    global servo1, servo2, current_angle1, current_angle2
    
    print("🚀 راه‌اندازی سیستم پیکو v2.0...")
    print("=" * 50)
    
    # نمایش تنظیمات ثابت
    print(f"🔑 توکن: {AUTH_TOKEN[:10]}...")
    print(f"🌐 آدرس: {WS_URL}")
    print("=" * 50)
    
    # پاکسازی حافظه اولیه
    gc.collect()
    initial_memory = gc.mem_free()
    print(f"💾 حافظه آزاد اولیه: {initial_memory} bytes")
    
    # راه‌اندازی سرووها
    try:
        print("🔧 راه‌اندازی سرووها...")
        servo1 = ServoController(SERVO1_PIN, SERVO1_FILE)
        servo2 = ServoController(SERVO2_PIN, SERVO2_FILE)
        current_angle1 = servo1.current_angle
        current_angle2 = servo2.current_angle
        print(f"✅ سرووها راه‌اندازی شدند: X={current_angle1}°, Y={current_angle2}°")
        
        # تست اولیه سرووها
        print("🧪 تست اولیه سرووها...")
        await servo1.set_angle(current_angle1, current_angle1, immediate=True)
        await servo2.set_angle(current_angle2, current_angle2, immediate=True)
        print("✅ تست سرووها موفق")
        
    except Exception as e:
        print(f"❌ خطا در راه‌اندازی سرووها: {e}")
        print("🔄 تلاش برای راه‌اندازی مجدد...")
        await asyncio.sleep(2)
        try:
            servo1 = ServoController(SERVO1_PIN, SERVO1_FILE)
            servo2 = ServoController(SERVO2_PIN, SERVO2_FILE)
            current_angle1 = servo1.current_angle
            current_angle2 = servo2.current_angle
            print(f"✅ سرووها در تلاش دوم راه‌اندازی شدند")
        except Exception as e2:
            print(f"❌ خطا در تلاش دوم: {e2}")
            print("🔄 ریست سیستم...")
            await asyncio.sleep(2)
            reset()
    
    print(f"💾 حافظه آزاد بعد از راه‌اندازی سرووها: {gc.mem_free()} bytes")
    
    # اتصال به WiFi
    print("🌐 اتصال به WiFi...")
    
    # تنظیم WiFi
    print("⚙️ تنظیم WiFi...")
    configure_wifi()
    
    # اتصال ساده به WiFi
    print("🔗 تلاش اتصال WiFi...")
    if simple_wifi_connect():
        wlan = network.WLAN(network.STA_IF)
        print("✅ اتصال WiFi موفق")
    else:
        print("❌ اتصال WiFi ناموفق، ریست سیستم...")
        await asyncio.sleep(2)
        reset()
    
    print("🌐 اتصال WiFi برقرار شد")
    print(f"📡 IP: {wlan.ifconfig()[0]}")
    print(f"🌐 Gateway: {wlan.ifconfig()[2]}")
    print(f"📶 Signal: {wlan.status()}")
    print(f"💾 حافظه آزاد بعد از WiFi: {gc.mem_free()} bytes")
    
    # تست اتصال اینترنت
    print("🌐 تست اتصال اینترنت...")
    test_internet_connection()
    
    # شروع WebSocket client
    print("🌐 شروع WebSocket client...")
    try:
        await websocket_client()
    except Exception as e:
        print(f"❌ خطا در WebSocket client: {e}")
        append_error_log({
            "type": "log",
            "level": "error",
            "message": f"WebSocket client error: {e}",
            "timestamp": get_now_str()
        })
        await asyncio.sleep(5)
        print("🔄 تلاش مجدد...")
        await main()  # تلاش مجدد

# ================================
# توابع کمکی (بهبود یافته)
# ================================
def get_now_str():
    """دریافت زمان فعلی به صورت رشته"""
    try:
        import time
        # استفاده از time.time() و تبدیل به فرمت قابل خواندن
        current_time = time.time()
        # تبدیل به فرمت ساده
        return f"{int(current_time)}"
    except:
        return "unknown"

def append_error_log(error_data):
    """ثبت خطا در فایل با مدیریت بهتر"""
    try:
        # اضافه کردن اطلاعات سیستم
        error_data["memory_free"] = gc.mem_free()
        error_data["uptime"] = time.time()
        error_data["wifi_connected"] = network.WLAN(network.STA_IF).isconnected()
        
        with open("error_log.json", "a") as f:
            f.write(ujson.dumps(error_data) + "\n")
            
        # محدود کردن اندازه فایل لاگ
        try:
            import os
            if os.path.exists("error_log.json"):
                stat = os.stat("error_log.json")
                if stat[6] > 10240:  # بیش از 10KB
                    # نگه داشتن فقط 100 خط آخر
                    with open("error_log.json", "r") as f:
                        lines = f.readlines()
                    with open("error_log.json", "w") as f:
                        f.writelines(lines[-100:])
        except:
            pass
            
    except Exception as e:
        print(f"⚠️ خطا در ثبت لاگ: {e}")

def send_log(ws, message, level="info"):
    """ارسال لاگ به سرور با بهبود مدیریت خطا"""
    try:
        if not ws:
            print(f"[{level.upper()}] {message}")
            return
            
        log_message = {
            "type": "log",
            "message": message,
            "level": level,
            "timestamp": get_now_str(),
            "device": "pico",
            "memory_free": gc.mem_free()
        }
        ws.send(ujson.dumps(log_message))
    except Exception as e:
        print(f"⚠️ خطا در ارسال لاگ: {e}")
        print(f"[{level.upper()}] {message}")

def send_ack(ws, command_type, status="success", detail=""):
    """ارسال تایید به سرور با بهبود مدیریت خطا"""
    try:
        if not ws:
            return
            
        ack_message = {
            "type": "ack",
            "command_type": command_type,
            "status": status,
            "detail": detail,
            "timestamp": get_now_str(),
            "device": "pico",
            "memory_free": gc.mem_free()
        }
        ws.send(ujson.dumps(ack_message))
    except Exception as e:
        print(f"⚠️ خطا در ارسال ACK: {e}")

def get_system_status():
    """دریافت وضعیت کامل سیستم"""
    try:
        wlan = network.WLAN(network.STA_IF)
        return {
            "device": "pico",
            "version": "2.0",
            "uptime": time.time(),
            "memory_free": gc.mem_free(),
            "wifi_connected": wlan.isconnected(),
            "wifi_ssid": wlan.config('ssid') if wlan.isconnected() else None,
            "ip_address": wlan.ifconfig()[0] if wlan.isconnected() else None,
            "servo1_status": servo1.get_status() if servo1 else None,
            "servo2_status": servo2.get_status() if servo2 else None,
            "current_angles": {
                "servo1": current_angle1,
                "servo2": current_angle2
            },
            "error_count": error_counter,
            "ws_error_count": ws_error_count,
            "last_pong": last_pong,
            "global_pico_last_seen": global_pico_last_seen
        }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": get_now_str()
        }

def emergency_shutdown():
    """توقف اضطراری سیستم"""
    print("🛑 توقف اضطراری سیستم...")
    
    # توقف سرووها
    if servo1:
        try:
            servo1.emergency_stop()
        except:
            pass
    if servo2:
        try:
            servo2.emergency_stop()
        except:
            pass
    
    # پاکسازی حافظه
    gc.collect()
    
    print("✅ توقف اضطراری تکمیل شد")

def check_system_health():
    """بررسی سلامت سیستم"""
    try:
        health_status = {
            "memory_free": gc.mem_free(),
            "memory_allocated": gc.mem_alloc(),
            "wifi_connected": network.WLAN(network.STA_IF).isconnected(),
            "servo1_ready": servo1 is not None,
            "servo2_ready": servo2 is not None,
            "error_count": error_counter,
            "ws_error_count": ws_error_count
        }
        
        # بررسی حافظه
        if health_status["memory_free"] < 10000:  # کمتر از 10KB
            print("⚠️ حافظه کم، پاکسازی...")
            gc.collect()
            health_status["memory_free"] = gc.mem_free()
        
        # بررسی خطاها
        if health_status["error_count"] > 10:
            print("⚠️ تعداد خطاها زیاد")
        
        return health_status
    except Exception as e:
        print(f"❌ خطا در بررسی سلامت سیستم: {e}")
        return {"error": str(e)}

def is_websocket_healthy(ws):
    """بررسی سلامت اتصال WebSocket"""
    try:
        if not ws:
            return False
        
        # بررسی وجود متدهای ضروری
        if not hasattr(ws, 'send') or not hasattr(ws, 'recv'):
            return False
        
        return True
    except Exception as e:
        print(f"❌ خطا در بررسی سلامت WebSocket: {e}")
        return False


# ================================
# اجرای برنامه (بهبود یافته)
# ================================
if __name__ == "__main__":
    try:
        print("🚀 شروع سیستم پیکو v2.0...")
        print("📅 تاریخ: " + get_now_str())
        print("💾 حافظه آزاد: " + str(gc.mem_free()) + " bytes")
        print("=" * 50)
        
        # اجرای برنامه اصلی
        asyncio.run(main())
        
    except KeyboardInterrupt:
        print("\n🛑 برنامه توسط کاربر متوقف شد")
        try:
            emergency_shutdown()
        except:
            pass
        print("✅ خروج ایمن")
        
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")
        try:
            emergency_shutdown()
        except:
            pass
        
        # ثبت خطا
        append_error_log({
            "type": "fatal_error",
            "error": str(e),
            "timestamp": get_now_str(),
            "traceback": "main_execution_error"
        })
        
        print("🔄 ریست سیستم در 5 ثانیه...")
        time.sleep(5)
        reset()








