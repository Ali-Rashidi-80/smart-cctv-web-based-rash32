import time
from machine import I2C, Pin
import pcf8575


# =======================
# کلاس کنترل I2C Multiplexer (PCA9548A)
# =======================
class I2CMultiplexer:
    def __init__(self, i2c, address=0x70):
        self.i2c = i2c
        self.address = address
        self._check_presence()

    def _check_presence(self):
        devices = self.i2c.scan()
        if self.address not in devices:
            raise Exception(f"PCA9548A at address 0x{self.address:02X} not found.")
        print(f"PCA9548A found at address 0x{self.address:02X}.")

    def select_channel(self, channel):
        if not 0 <= channel <= 7:
            raise ValueError("Channel must be between 0 and 7.")
        channel_mask = 1 << channel
        self.i2c.writeto(self.address, bytes([channel_mask]))
        time.sleep(0.01)
        print(f"Selected channel {channel} on PCA9548A.")

# =======================
# کلاس کنترل PCF8575 برای رله‌ها
# =======================
class RelayModule:
    def __init__(self, i2c, address=0x20, init_state=0xFFFF):
        """
        :param i2c: I2C object
        :param address: PCF8575 I2C address
        :param init_state: Initial state for all pins (0xFFFF = all HIGH, relays OFF)
        """
        self.i2c = i2c
        self.address = address
        self.init_state = init_state
        self._check_presence()
        self.expander = pcf8575.PCF8575(i2c, address)
        self.reset_relays()

    def _check_presence(self):
        devices = self.i2c.scan()
        if self.address not in devices:
            raise Exception(f"PCF8575 at address 0x{self.address:02X} not found.")
        print(f"PCF8575 found at address 0x{self.address:02X}.")

    def reset_relays(self):
        """Set all relays to OFF (all pins HIGH)."""
        self.expander.port = self.init_state
        time.sleep(0.02)

    def set_relay(self, relay, state):
        """
        Control a single relay.
        :param relay: Relay number (0 to 15, corresponding to P00 to P17)
        :param state: True (ON, LOW) or False (OFF, HIGH)
        """
        if not 0 <= relay <= 15:
            raise ValueError("Relay number must be between 0 and 15.")
        current_state = self.expander.port
        if state:  # Turn ON (set pin to LOW)
            new_state = current_state & ~(1 << relay)
        else:  # Turn OFF (set pin to HIGH)
            new_state = current_state | (1 << relay)
        self.expander.port = new_state
        time.sleep(0.02)
        print(f"Relay {relay} set to {'ON' if state else 'OFF'} (Port: {bin(new_state)})")

    def set_all_relays(self, states):
        """
        Control all 16 relays at once.
        :param states: 16-bit integer (e.g., 0x0000 = all ON, 0xFFFF = all OFF)
        """
        if not 0 <= states <= 0xFFFF:
            raise ValueError("States must be a 16-bit value (0 to 0xFFFF).")
        # Invert bits because relays are active LOW
        self.expander.port = states
        time.sleep(0.02)
        print(f"All relays set to {bin(states)}")

    def read_relay_status(self):
        """Read the current state of all relays."""
        return self.expander.port

# =======================
# تنظیمات I2C برای Raspberry Pi Pico
# =======================
SDA_PIN = 4
SCL_PIN = 5
I2C_FREQ = 400000
I2C_ID = 0

# ایجاد شیء I2C
i2c = I2C(I2C_ID, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=I2C_FREQ)

# =======================
# تنظیمات Multiplexer و Relay Module
# =======================
MUX_ADDRESS = 0x70
MUX_CHANNEL = 0  # Channel 0 for PCF8575
RELAY_ADDRESS = 0x20
INIT_STATE = 0xFFFF  # All relays OFF (all pins HIGH)

# Initialize Multiplexer
multiplexer = I2CMultiplexer(i2c, address=MUX_ADDRESS)
multiplexer.select_channel(MUX_CHANNEL)

# Initialize Relay Module
relay_module = RelayModule(i2c, address=RELAY_ADDRESS, init_state=INIT_STATE)

# =======================
# حلقه اصلی برای تست
# =======================

    
#while True:
try:
    # Test: Turn each relay ON and OFF one by one
    for relay in range(16):
        print(f"\nTesting Relay {relay}")
        relay_module.set_relay(relay, True)  # Turn ON
        time.sleep(0.5)
        relay_module.set_relay(relay, False)  # Turn OFF
        time.sleep(0.5)

    # Test: Turn all relays ON
    print("\nTurning all relays ON")
    relay_module.set_all_relays(0x0000)  # All LOW (relays ON)
    time.sleep(2)

    # Test: Turn all relays OFF
    print("Turning all relays OFF")
    relay_module.set_all_relays(0xFFFF)  # All HIGH (relays OFF)
    time.sleep(2)

except KeyboardInterrupt:
    print("Program stopped by user.")
    relay_module.reset_relays()  # Ensure all relays are OFF before exiting
