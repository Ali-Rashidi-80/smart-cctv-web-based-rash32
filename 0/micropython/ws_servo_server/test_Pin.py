from machine import Pin
import time

pins = [12, 11, 10, 9, 8, 7]
touch_pins = [Pin(pin, Pin.IN, Pin.PULL_UP) for pin in pins]

while True:
    for i, pin in enumerate(touch_pins):
        print(f"Pin {pins[i]}: {pin.value()}")
    time.sleep_ms(100)