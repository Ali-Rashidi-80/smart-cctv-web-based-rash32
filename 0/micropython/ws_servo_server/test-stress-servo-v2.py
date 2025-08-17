import uasyncio as asyncio
from machine import Pin, PWM
import random
import math

SERVO1_PIN = 17
SERVO2_PIN = 16

SAFE_MIN_ANGLE = 20
SAFE_MAX_ANGLE = 160

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

async def move_servo_gradually(pwm, current, target, label="", step=5, delay=0.03):
    if current == target:
        return
    step = abs(step) if target > current else -abs(step)
    for angle in range(current, target, step):
        duty, pulse = angle_to_duty(angle)
        pwm.duty_u16(duty)
        print(f"{label} زاویه: {angle}° | پالس: {pulse:.1f}us | duty: {duty}")
        await asyncio.sleep(delay)
    # آخرین زاویه
    duty, pulse = angle_to_duty(target)
    pwm.duty_u16(duty)
    print(f"{label} زاویه: {target}° | پالس: {pulse:.1f}us | duty: {duty}")
    await asyncio.sleep(delay)

async def test_wave_motion(pwm1, pwm2, current1, current2, label1, label2, rounds=2, delay=0.02):
    print("تست حرکت موجی (سینوسی)...")
    for r in range(rounds):
        for t in range(0, 360, 4):
            # موج سینوسی بین بازه ایمن
            angle1 = int((SAFE_MAX_ANGLE - SAFE_MIN_ANGLE) / 2 * (1 + math.sin(math.radians(t))) + SAFE_MIN_ANGLE)
            angle2 = int((SAFE_MAX_ANGLE - SAFE_MIN_ANGLE) / 2 * (1 + math.cos(math.radians(t))) + SAFE_MIN_ANGLE)
            duty1, pulse1 = angle_to_duty(angle1)
            duty2, pulse2 = angle_to_duty(angle2)
            pwm1.duty_u16(duty1)
            pwm2.duty_u16(duty2)
            print(f"{label1} موجی: {angle1}° | {label2} موجی: {angle2}°")
            await asyncio.sleep(delay)
    return angle1, angle2

async def test_shock_motion(pwm1, pwm2, current1, current2, label1, label2, shocks=5):
    print("تست شوک مکانیکی (پرش سریع)...")
    for _ in range(shocks):
        a1 = random.choice([SAFE_MIN_ANGLE, SAFE_MAX_ANGLE])
        a2 = random.choice([SAFE_MIN_ANGLE, SAFE_MAX_ANGLE])
        await move_servo_gradually(pwm1, current1, a1, label1, step=20, delay=0.01)
        await move_servo_gradually(pwm2, current2, a2, label2, step=20, delay=0.01)
        current1, current2 = a1, a2
        await asyncio.sleep(0.2)
    return current1, current2

async def test_random_gradual(pwm1, pwm2, current1, current2, label1, label2, count=10):
    print("تست تصادفی تدریجی (ایمن)...")
    for _ in range(count):
        a1 = random.randint(SAFE_MIN_ANGLE, SAFE_MAX_ANGLE)
        a2 = random.randint(SAFE_MIN_ANGLE, SAFE_MAX_ANGLE)
        await move_servo_gradually(pwm1, current1, a1, label1, step=5, delay=0.03)
        await move_servo_gradually(pwm2, current2, a2, label2, step=5, delay=0.03)
        current1, current2 = a1, a2
        await asyncio.sleep(0.1)
    return current1, current2

async def test_speed_variation(pwm1, pwm2, current1, current2, label1, label2):
    print("تست سرعت‌های مختلف...")
    for step, delay in [(1, 0.05), (5, 0.02), (10, 0.01)]:
        print(f"حرکت با گام {step} و تاخیر {delay} ثانیه")
        for angle in range(SAFE_MIN_ANGLE, SAFE_MAX_ANGLE+1, 20):
            await move_servo_gradually(pwm1, current1, angle, label1, step=step, delay=delay)
            await move_servo_gradually(pwm2, current2, angle, label2, step=step, delay=delay)
            current1, current2 = angle, angle
    return current1, current2

async def stress_test_servos():
    pwm1 = PWM(Pin(SERVO1_PIN))
    pwm2 = PWM(Pin(SERVO2_PIN))
    pwm1.freq(SERVO_FREQ)
    pwm2.freq(SERVO_FREQ)

    iteration = 0
    print("شروع تست فوق استرسی و عملیاتی MG90S ...")
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

        # 1. تست سرعت‌های مختلف
        current1, current2 = await test_speed_variation(pwm1, pwm2, current1, current2, "Servo1", "Servo2")

        # 2. تست موجی (سینوسی)
        current1, current2 = await test_wave_motion(pwm1, pwm2, current1, current2, "Servo1", "Servo2", rounds=2, delay=0.01)

        # 3. تست تصادفی تدریجی
        current1, current2 = await test_random_gradual(pwm1, pwm2, current1, current2, "Servo1", "Servo2", count=10)

        # 4. تست شوک مکانیکی (پرش سریع)
        current1, current2 = await test_shock_motion(pwm1, pwm2, current1, current2, "Servo1", "Servo2", shocks=5)

        # 5. بازگشت به مرکز و استراحت
        await move_servo_gradually(pwm1, current1, 90, "Servo1")
        await move_servo_gradually(pwm2, current2, 90, "Servo2")
        current1 = 90
        current2 = 90
        await asyncio.sleep(1)

        print(f"دور {iteration} با موفقیت انجام شد. اگر رفتار غیرعادی دیدی، مقدار زاویه و پالس را یادداشت کن و گزارش بده.")
        await asyncio.sleep(1)

try:
    asyncio.run(stress_test_servos())
except KeyboardInterrupt:
    print("تست متوقف شد.")