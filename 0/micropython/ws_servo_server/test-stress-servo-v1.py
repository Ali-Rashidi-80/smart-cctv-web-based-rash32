import uasyncio as asyncio
from machine import Pin, PWM
import random

SERVO1_PIN = 17
SERVO2_PIN = 16

SAFE_MIN_ANGLE = 5
SAFE_MAX_ANGLE = 175

SAFE_MIN_PULSE = 1000   # 1ms
SAFE_MAX_PULSE = 2000   # 2ms
SERVO_FREQ = 50         # 50Hz

def angle_to_duty(angle):
    safe_angle = max(SAFE_MIN_ANGLE, min(SAFE_MAX_ANGLE, angle))
    pulse = SAFE_MIN_PULSE + (safe_angle / 180) * (SAFE_MAX_PULSE - SAFE_MIN_PULSE)
    period = 1000000 / SERVO_FREQ  # us
    duty = int((pulse / period) * 65535)
    duty = max(0, min(65535, duty))
    return duty, pulse

async def move_servo_gradually(pwm, current, target, label=""):
    step = 5 if target > current else -5
    for angle in range(current, target, step):
        duty, pulse = angle_to_duty(angle)
        pwm.duty_u16(duty)
        print(f"{label} زاویه: {angle}° | پالس: {pulse:.1f}us | duty: {duty}")
        await asyncio.sleep(0.03)
    # آخرین زاویه
    duty, pulse = angle_to_duty(target)
    pwm.duty_u16(duty)
    print(f"{label} زاویه: {target}° | پالس: {pulse:.1f}us | duty: {duty}")
    await asyncio.sleep(0.03)

async def stress_test_servos():
    pwm1 = PWM(Pin(SERVO1_PIN))
    pwm2 = PWM(Pin(SERVO2_PIN))
    pwm1.freq(SERVO_FREQ)
    pwm2.freq(SERVO_FREQ)

    iteration = 0
    print("شروع تست فوق ایمن MG90S (حرکت تدریجی تصادفی)...")
    current1 = 90
    current2 = 90
    await move_servo_gradually(pwm1, current1, 90, "Servo1")
    await move_servo_gradually(pwm2, current2, 90, "Servo2")
    await asyncio.sleep(1)
    current1 = 90
    current2 = 90

    while True:
        iteration += 1
        print(f"\n===== دور {iteration} =====")

        # 1. تست رفت و برگشتی ایمن
        for angle in range(SAFE_MIN_ANGLE, SAFE_MAX_ANGLE+1, 10):
            await move_servo_gradually(pwm1, current1, angle, "Servo1")
            await move_servo_gradually(pwm2, current2, SAFE_MAX_ANGLE-angle+SAFE_MIN_ANGLE, "Servo2")
            current1 = angle
            current2 = SAFE_MAX_ANGLE-angle+SAFE_MIN_ANGLE
        for angle in range(SAFE_MAX_ANGLE, SAFE_MIN_ANGLE-1, -10):
            await move_servo_gradually(pwm1, current1, angle, "Servo1")
            await move_servo_gradually(pwm2, current2, SAFE_MAX_ANGLE-angle+SAFE_MIN_ANGLE, "Servo2")
            current1 = angle
            current2 = SAFE_MAX_ANGLE-angle+SAFE_MIN_ANGLE

        # 2. تست پرش ناگهانی به لبه‌ها و مرکز (اما باز هم تدریجی)
        for angle in [SAFE_MIN_ANGLE, 90, SAFE_MAX_ANGLE, 90]:
            await move_servo_gradually(pwm1, current1, angle, "Servo1")
            await move_servo_gradually(pwm2, current2, angle, "Servo2")
            current1 = angle
            current2 = angle
            await asyncio.sleep(0.2)

        # 3. تست تصادفی (Random) - حرکت تدریجی
        print("تست تصادفی (ایمن و تدریجی)...")
        for _ in range(10):
            a1 = random.randint(SAFE_MIN_ANGLE, SAFE_MAX_ANGLE)
            a2 = random.randint(SAFE_MIN_ANGLE, SAFE_MAX_ANGLE)
            await move_servo_gradually(pwm1, current1, a1, "Servo1")
            await move_servo_gradually(pwm2, current2, a2, "Servo2")
            current1 = a1
            current2 = a2
            await asyncio.sleep(0.1)

        # 4. بازگشت به مرکز و استراحت
        await move_servo_gradually(pwm1, current1, 90, "Servo1")
        await move_servo_gradually(pwm2, current2, 90, "Servo2")
        current1 = 90
        current2 = 90
        await asyncio.sleep(1)

        print(f"دور {iteration} با موفقیت انجام شد.")
        await asyncio.sleep(1)

try:
    asyncio.run(stress_test_servos())
except KeyboardInterrupt:
    print("تست متوقف شد.")