import asyncio, shutil, socket, logging, logging.config, logging.handlers
from datetime import datetime
from fastapi import HTTPException


# Global app reference (will be set by main server)
app = None

def set_app(fastapi_app):
    """Set the FastAPI app reference from main server"""
    global app
    app = fastapi_app

def register_status_routes(fastapi_app):
    """Register status routes with the FastAPI app"""
    global app
    app = fastapi_app
    
    # Register status routes
    fastapi_app.add_api_route("/devices/status", all_devices_status, methods=["GET"])
    fastapi_app.add_api_route("/esp32cam/status", esp32cam_status, methods=["GET"])
    fastapi_app.add_api_route("/pico/status", pico_status, methods=["GET"])
    fastapi_app.add_api_route("/get_status", get_status, methods=["GET"])
    
    # Add the missing endpoint that the client is calling
    fastapi_app.add_api_route("/api/device_status", all_devices_status, methods=["GET"])

# Setup logger for this module
logger = logging.getLogger("status")

# Global system state reference (will be set by main server)
system_state = None

# Global dependencies (will be set by main server)
get_current_user_func = None
pico_auth_tokens = None

def set_system_state(state):
    """Set the system state reference from main server"""
    global system_state
    system_state = state

def get_system_state():
    """Safely get system state, creating temporary one if needed"""
    global system_state
    if system_state is None:
        logger.warning("⚠️ system_state not initialized yet, creating temporary state")
        # Create a temporary system state for initialization
        class TempSystemState:
            def __init__(self):
                self.device_status = {"pico": {"online": False, "last_seen": None, "errors": []}, "esp32cam": {"online": False, "last_seen": None, "errors": []}}
                self.system_shutdown = False
        system_state = TempSystemState()
    return system_state

def set_dependencies(current_user_func, auth_tokens):
    """Set the dependencies from main server"""
    global get_current_user_func, pico_auth_tokens
    get_current_user_func = current_user_func
    pico_auth_tokens = auth_tokens


try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False




async def all_devices_status():
    """All devices status endpoint"""
    current_system_state = get_system_state()
    return {
        "timestamp": datetime.now().isoformat(),
        "devices": current_system_state.device_status
    }




async def esp32cam_status():
    """ESP32CAM status endpoint"""
    current_system_state = get_system_state()
    return {
        "status": "ready" if current_system_state.device_status["esp32cam"]["online"] else "offline",
        "timestamp": datetime.now().isoformat(),
        "service": "ESP32CAM",
        "port": "8080",
        "online": current_system_state.device_status["esp32cam"]["online"],
        "last_seen": current_system_state.device_status["esp32cam"]["last_seen"].isoformat() if current_system_state.device_status["esp32cam"]["last_seen"] else None,
        "recent_errors": current_system_state.device_status["esp32cam"]["errors"][-5:]  # آخرین 5 خطا
    }







async def pico_status():
    """Pico status endpoint"""
    current_system_state = get_system_state()
    return {
        "status": "ready" if current_system_state.device_status["pico"]["online"] else "offline",
        "timestamp": datetime.now().isoformat(),
        "service": "Pico",
        "online": current_system_state.device_status["pico"]["online"],
        "last_seen": current_system_state.device_status["pico"]["last_seen"].isoformat() if current_system_state.device_status["pico"]["last_seen"] else None,
        "recent_errors": current_system_state.device_status["pico"]["errors"][-5:],  # آخرین 5 خطا
        "current_token": pico_auth_tokens[0][:10] + "..." if pico_auth_tokens else None
    }




def check_internet():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return "online"
    except Exception:
        return "offline"

async def get_status(user=None):
    # Check if user authentication is required and available
    if get_current_user_func:
        try:
            user = await get_current_user_func()
        except Exception as e:
            logger.warning(f"User authentication failed: {e}")
            user = None
    
    if not user and get_current_user_func:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        # Get system state safely
        current_system_state = get_system_state()
        
        ram_percent = psutil.virtual_memory().percent if PSUTIL_AVAILABLE else None
        cpu_percent = psutil.cpu_percent(interval=0.2) if PSUTIL_AVAILABLE else None
        total, used, free = await asyncio.to_thread(shutil.disk_usage, '.')
        free_percent = (free / total) * 100
        storage_str = f"{free_percent:.1f}% free"
        
        system_info = {
            "server_status": "online" if not current_system_state.system_shutdown else "offline",
            "camera_status": "online" if current_system_state.device_status["esp32cam"]["online"] else "offline",
            "pico_status": "online" if current_system_state.device_status["pico"]["online"] else "offline",
            "pico_last_seen": current_system_state.device_status["pico"]["last_seen"],
            "ram_percent": ram_percent,
            "cpu_percent": cpu_percent,
            "internet": await asyncio.to_thread(check_internet),
            "storage": storage_str
        }
        return {"status": "success", "data": system_info}
    except Exception as e:
        logger.exception("Status retrieval error")
        return {"status": "error", "error": str(e)}


