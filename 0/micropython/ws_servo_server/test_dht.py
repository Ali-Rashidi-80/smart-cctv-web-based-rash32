from machine import Pin, UART
import dht
import time
import uasyncio as asyncio

# تنظیمات پین‌ها
DHT_PIN = 6  # پین سنسور DHT22
POWER_RELAY_PIN = 3  # رله قدرت
PUMP_RELAY_PIN = 4   # رله پمپ
MOTOR_RELAY_PIN = 5  # رله موتور
FAN_SPEED_RELAY_PIN = 6  # رله سرعت فن (دور کند/تند)
UART_TX_PIN = 0  # پین TX برای ارتباط سریال
UART_RX_PIN = 1  # پین RX برای ارتباط سریال

# تنظیمات UART
UART_ID = 0
BAUD_RATE = 9600

# تنظیمات تایمر و بازه‌های به‌روزرسانی
TEMP_HUMIDITY_UPDATE_INTERVAL = 2  # به‌روزرسانی دما/رطوبت هر 2 ثانیه
TIMER_UPDATE_INTERVAL = 1  # به‌روزرسانی تایمر هر 1 ثانیه
MAX_TIMER_MINUTES = 999  # حداکثر زمان تایمر
TEMP_THRESHOLD = 25  # آستانه دما برای کنترل خودکار
HUMIDITY_THRESHOLD = 60  # آستانه رطوبت برای کنترل خودکار

# کلاس کنترل کولر
class CoolerControl:
    def __init__(self):
        # مقداردهی اولیه سنسور DHT22
        self.dht_sensor = dht.DHT22(Pin(DHT_PIN))
        
        # مقداردهی اولیه رله‌ها (Active-Low: 0 = روشن، 1 = خاموش)
        self.power_relay = Pin(POWER_RELAY_PIN, Pin.OUT, value=1)
        self.pump_relay = Pin(PUMP_RELAY_PIN, Pin.OUT, value=1)
        self.motor_relay = Pin(MOTOR_RELAY_PIN, Pin.OUT, value=1)
        self.fan_speed_relay = Pin(FAN_SPEED_RELAY_PIN, Pin.OUT, value=1)
        
        # مقداردهی اولیه UART
        self.uart = UART(UART_ID, baudrate=BAUD_RATE, tx=Pin(UART_TX_PIN), rx=Pin(UART_RX_PIN))
        
        # متغیرهای وضعیت
        self.temp = 0
        self.humidity = 0
        self.pump_state = False
        self.motor_state = False
        self.fan_speed = 0  # 0: خاموش، 1: کم، 2: زیاد
        self.timer_active = False
        self.timer_remaining_ms = 0
        self.last_temp_humidity_update = 0
        self.last_timer_update = 0
        
    def read_dht(self):
        """خواندن دما و رطوبت از سنسور DHT22"""
        try:
            self.dht_sensor.measure()
            self.temp = int(self.dht_sensor.temperature())
            self.humidity = int(self.dht_sensor.humidity())
            print(f"DHT22: Temp={self.temp}C, Humidity={self.humidity}%")
            return True
        except Exception as e:
            print(f"DHT22 Error: {e}")
            return False

    def send_serial_command(self, cmd):
        """ارسال دستور سریال به آردوینو"""
        try:
            self.uart.write(cmd)
            print(f"Sent command: {cmd}")
            # انتظار برای بازتاب دستور
            start_time = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start_time) < 100:
                if self.uart.any():
                    echo = self.uart.read(1).decode()
                    if echo == cmd[0]:
                        return True
            print("No echo received")
            return False
        except Exception as e:
            print(f"Serial Error: {e}")
            return False

    def update_display(self):
        """به‌روزرسانی نمایشگر آردوینو با دما، رطوبت، و تایمر"""
        # ارسال دما
        self.send_serial_command(f"T{self.temp}")
        # ارسال رطوبت
        self.send_serial_command(f"H{self.humidity}")
        # ارسال زمان تایمر
        minutes = self.timer_remaining_ms // 60000
        self.send_serial_command(f"R{minutes}")

    def toggle_pump(self):
        """تغییر وضعیت پمپ"""
        self.pump_state = not self.pump_state
        self.pump_relay.value(0 if self.pump_state else 1)
        self.send_serial_command("P")
        print(f"Pump: {'ON' if self.pump_state else 'OFF'}")

    def cycle_fan_speed(self):
        """تغییر سرعت فن (خاموش -> کم -> زیاد -> خاموش)"""
        self.fan_speed = (self.fan_speed + 1) % 3
        self.motor_state = self.fan_speed > 0
        self.motor_relay.value(0 if self.motor_state else 1)
        self.fan_speed_relay.value(0 if self.fan_speed == 2 else 1)  # دور تند = 0، دور کند یا خاموش = 1
        self.send_serial_command("M")
        print(f"Fan Speed: {self.fan_speed} (Motor: {'ON' if self.motor_state else 'OFF'})")

    def set_timer(self, minutes):
        """تنظیم تایمر"""
        if 0 <= minutes <= MAX_TIMER_MINUTES:
            self.timer_remaining_ms = minutes * 60000
            self.timer_active = minutes > 0
            self.send_serial_command(f"R{minutes}")
            print(f"Timer set to {minutes} minutes")
            if self.timer_active:
                self.power_relay.value(0)  # روشن کردن قدرت
        else:
            print(f"Invalid timer value: {minutes}")

    def update_timer(self):
        """به‌روزرسانی تایمر"""
        if self.timer_active and time.ticks_diff(time.ticks_ms(), self.last_timer_update) >= 1000:
            self.last_timer_update = time.ticks_ms()
            if self.timer_remaining_ms >= 1000:
                self.timer_remaining_ms -= 1000
                minutes = self.timer_remaining_ms // 60000
                self.send_serial_command(f"R{minutes}")
            else:
                # پایان تایمر: خاموش کردن همه چیز
                self.timer_remaining_ms = 0
                self.timer_active = False
                self.pump_state = False
                self.motor_state = False
                self.fan_speed = 0
                self.power_relay.value(1)  # خاموش کردن قدرت
                self.pump_relay.value(1)
                self.motor_relay.value(1)
                self.fan_speed_relay.value(1)
                self.send_serial_command("P")  # به‌روزرسانی پمپ
                self.send_serial_command("M")  # به‌روزرسانی فن
                self.send_serial_command("R0")  # غیرفعال کردن تایمر
                print("Timer finished: All components OFF")

    def auto_control(self):
        """کنترل خودکار بر اساس دما و رطوبت"""
        if not self.timer_active:
            if self.temp > TEMP_THRESHOLD and not self.motor_state:
                self.cycle_fan_speed()  # روشن کردن فن
            if self.humidity < HUMIDITY_THRESHOLD and not self.pump_state:
                self.toggle_pump()  # روشن کردن پمپ
        if self.temp <= TEMP_THRESHOLD and self.fan_speed > 0:
            self.cycle_fan_speed()  # خاموش کردن فن اگر دما پایین باشد
        if self.humidity >= HUMIDITY_THRESHOLD and self.pump_state:
            self.toggle_pump()  # خاموش کردن پمپ اگر رطوبت بالا باشد

async def main():
    cooler = CoolerControl()
    
    # تست اولیه: خواندن سنسور و به‌روزرسانی نمایشگر
    cooler.read_dht()
    cooler.update_display()
    
#   while True:
    # به‌روزرسانی دما و رطوبت
    if time.ticks_diff(time.ticks_ms(), cooler.last_temp_humidity_update) >= TEMP_HUMIDITY_UPDATE_INTERVAL * 1000:
        cooler.last_temp_humidity_update = time.ticks_ms()
        if cooler.read_dht():
            cooler.update_display()
            cooler.auto_control()
    
    # به‌روزرسانی تایمر
    cooler.update_timer()
    
    # برای کاهش بار CPU
    await asyncio.sleep_ms(100)

# اجرای برنامه
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Program stopped by user")
    # خاموش کردن همه رله‌ها در هنگام خروج
    for pin in [POWER_RELAY_PIN, PUMP_RELAY_PIN, MOTOR_RELAY_PIN, FAN_SPEED_RELAY_PIN]:
        Pin(pin, Pin.OUT).value(1)
except Exception as e:
    print(f"Error: {e}")