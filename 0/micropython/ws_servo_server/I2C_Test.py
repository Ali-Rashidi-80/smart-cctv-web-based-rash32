from machine import I2C, Pin

SDA_PIN = 8
SCL_PIN = 9
I2C_ID = 0
i2c = I2C(I2C_ID, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=400000)

devices = i2c.scan()
print("I2C devices found:", [hex(addr) for addr in devices])