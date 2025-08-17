import network
import time
import uasyncio as asyncio

# WiFi credentials
SSID = "SAMSUNG"
PASSWORD = "panzer790"

# Initialize WLAN
wlan = network.WLAN(network.STA_IF)

def format_timestamp():
    t = time.localtime()
    return f"{t[0]}/{t[1]:02d}/{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"

# Function to check WiFi connection status
def isconnected():
    return wlan.isconnected()

# Function to connect to WiFi
def connect_wifi():
    if isconnected():
        print(f"[{format_timestamp()}] ✅ Already connected. IP Address: {wlan.ifconfig()[0]}")
        return True

    print(f"[{format_timestamp()}] 🔄 Connecting to WiFi...")
    wlan.active(True)  # Ensure WLAN is active
    wlan.connect(SSID, PASSWORD)

    timeout = 15  # Increased timeout to 15 seconds
    start_time = time.time()

    while not isconnected():
        if time.time() - start_time > timeout:
            print(f"[{format_timestamp()}] ❌ Connection timed out!")
            return False
        print(".", end="")
        time.sleep(1)

    wifi_status()
    return True

# Display WiFi status
def wifi_status():
    if isconnected():
        ip, subnet, gateway, dns = wlan.ifconfig()
        print(f"[{format_timestamp()}] 📡 WiFi Info:")
        print(f"  - IP Address: {ip}")
        print(f"  - Subnet Mask: {subnet}")
        print(f"  - Gateway: {gateway}")
        print(f"  - DNS Server: {dns}")
    else:
        print(f"[{format_timestamp()}] ❌ Not connected to WiFi")

# Async function to ensure WiFi connection
async def ensure_wifi():
    wlan.active(True)  # Ensure WLAN is active
    while not isconnected():
        print(f"[{format_timestamp()}] ⚠ WiFi lost! Reconnecting...")
        connect_wifi()
        await asyncio.sleep(2)
    print(f"[{format_timestamp()}] WiFi Connected!✅. IP Address: {wlan.ifconfig()[0]}")
    return True

# Start WiFi connection
def start():
    asyncio.run(ensure_wifi())
    
start()