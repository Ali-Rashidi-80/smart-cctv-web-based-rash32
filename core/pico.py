import asyncio, time, os, sys, gc, psutil, logging, json, random, string
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import WebSocket, WebSocketDisconnect, HTTPException, Request, Depends
from pydantic import BaseModel, Field, ValidationError

# Import required functions from other modules
from .token import get_current_user
from .Security import check_rate_limit
from .utils import send_to_web_clients_wrapper
from .client import authenticate_websocket
from .db import insert_log, insert_servo_command, insert_action_command

# Global function reference for esp32cam communication (will be set by main server)
send_to_esp32cam_client = None

# Setup logger for this module
logger = logging.getLogger("pico")

# Constants
WEBSOCKET_ERROR_THRESHOLD = 10
CONNECTION_TIMEOUT = 30
PICO_AUTH_TOKENS = [
    "pico_auth_token_2024_secure_001",
    "pico_auth_token_2024_secure_002",
    "pico_auth_token_2024_secure_003"
]
SERVO_MIN_ANGLE = 0
SERVO_MAX_ANGLE = 180
SERVO_DEFAULT_SPEED = 50
ACTION_INTENSITY_RANGE = (1, 100)

# Global system state reference (will be set by main server)
system_state = None

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
                self.pico_client_lock = asyncio.Lock()
                self.pico_client = None
                self.device_status = {"pico": {"online": False, "last_seen": None, "errors": []}}
                self.active_clients = []
                self.error_counts = {"websocket": 0, "database": 0}
                self.sensor_data_buffer = []
                self.message_counter = 0
                self.pico_connected = False
        system_state = TempSystemState()
    return system_state

# Global function references (will be set by main server)
insert_log = None
insert_servo_command = None
insert_action_command = None

def set_dependencies(log_func, servo_cmd_func, action_cmd_func):
    """Set dependencies from main server"""
    global insert_log, insert_servo_command, insert_action_command
    insert_log = log_func
    insert_servo_command = servo_cmd_func
    insert_action_command = action_cmd_func

def set_esp32cam_dependency(esp32cam_func):
    """Set esp32cam communication function from main server"""
    global send_to_esp32cam_client
    send_to_esp32cam_client = esp32cam_func

def register_pico_routes(fastapi_app):
    """Register pico routes with the FastAPI app"""
    # Register WebSocket route
    fastapi_app.add_websocket_route("/ws/pico", pico_websocket_endpoint)
    # Register HTTP route
    fastapi_app.add_api_route("/set_servo", set_servo, methods=["POST"])

class ActiveClient:
    def __init__(self, ws, connect_time, user_agent=None):
        self.ws = ws
        self.ip = ws.client.host if hasattr(ws, 'client') and hasattr(ws.client, 'host') else None
        self.connect_time = connect_time
        self.user_agent = user_agent
        self.last_activity = connect_time

class ServoCommand(BaseModel):
    servo1: int = Field(default=90, ge=0, le=180)
    servo2: int = Field(default=90, ge=0, le=180)


async def send_to_pico_client(message):
    try:
        if not hasattr(system_state, 'pico_client_lock') or system_state.pico_client_lock is None:
            logger.debug("Pico client lock not initialized; skipping dispatch")
            return
            
        async with system_state.pico_client_lock:
            client = getattr(system_state, 'pico_client', None)
            if client:
                try:
                    await client.send_text(json.dumps(message))
                    # به‌روزرسانی وضعیت دستگاه
                    system_state.device_status["pico"]["last_seen"] = datetime.now()
                    logger.debug(f"Message sent to Pico: {message}")
                except Exception as e:
                    # Don't log normal closure errors
                    if "1000" not in str(e) and "Rapid test" not in str(e):
                        logger.warning(f"Failed to send to pico client {client.client.host}: {e}")
                    system_state.pico_client = None
                    system_state.device_status["pico"]["online"] = False
                    system_state.device_status["pico"]["errors"].append({
                        "time": datetime.now().isoformat(),
                        "error": str(e)
                    })
                    system_state.active_clients = [c for c in system_state.active_clients if not (hasattr(c, 'ws') and c.ws == client)]
                    logger.info(f"Removed disconnected pico client: {client.client.host}")
            else:
                logger.debug("Pico client not connected")
                system_state.device_status["pico"]["errors"].append({
                    "time": datetime.now().isoformat(),
                    "error": "Client not connected"
                })
    except Exception as e:
        logger.warning(f"Non-CRITICAL ERROR dispatching servo/log updates: {e}")




async def pico_websocket_endpoint(websocket: WebSocket):
    logger.info(f"[WebSocket] Pico connection attempt from {websocket.client.host}")
    try:
        # Authenticate the connection
        if not await authenticate_websocket(websocket, "pico"):
            logger.warning(f"[WebSocket] Pico authentication failed from {websocket.client.host}")
            try:
                await websocket.send_text(json.dumps({"type": "error", "message": "Authentication failed"}))
            except Exception:
                pass
            return

        # WebSocket connection is already accepted in authenticate_websocket
        logger.info(f"[WebSocket] Pico WebSocket ready for communication from {websocket.client.host}")

        logger.info(f"[WebSocket] Pico authenticated and connected from {websocket.client.host}")
        async with system_state.pico_client_lock:
            system_state.pico_client = websocket
            system_state.device_status["pico"]["online"] = True
            system_state.device_status["pico"]["last_seen"] = datetime.now()
            system_state.active_clients.append(ActiveClient(websocket, datetime.now(), "Pico"))
            logger.info(f"[DEBUG] Pico status updated: online=True, last_seen={system_state.device_status['pico']['last_seen']}")

        # Send connection success message
        try:
            await websocket.send_text(json.dumps({"type": "connection_ack", "status": "success", "message": "Pico connected successfully"}))
            logger.info(f"[WebSocket] Connection success message sent to Pico")
        except Exception as e:
            logger.warning(f"[WebSocket] Could not send connection success message: {e}")
        

        # Create periodic ping task with improved stability
        ping_task = None
        last_ping_time = datetime.now()
        ping_interval = 60  # Increased from 15 to 60 seconds to reduce network usage
        

        async def periodic_ping():
            """Send periodic pings to Pico to keep connection alive with improved error handling"""
            nonlocal last_ping_time
            last_activity = datetime.now()
            consecutive_inactive_periods = 0
            
            while True:
                try:
                    await asyncio.sleep(ping_interval)
                    current_time = datetime.now()
                    
                    # Check if connection is still active
                    if system_state.pico_client != websocket:
                        logger.debug(f"[WebSocket] Pico connection changed, stopping ping task")
                        break
                    
                    # Enhanced ping logic for continuous sensor data:
                    # - During active sensor data transmission: minimal ping (every 5 minutes)
                    # - During low activity: adaptive ping
                    # - During no activity: frequent ping
                    inactive_duration = (current_time - last_activity).total_seconds()
                    
                    # Check if we're receiving sensor data
                    sensor_data_active = False
                    if hasattr(system_state, 'sensor_data_buffer') and system_state.sensor_data_buffer:
                        # Check if we received sensor data in last 60 seconds (more lenient)
                        try:
                            recent_sensor_data = [data for data in system_state.sensor_data_buffer 
                                                if (current_time - datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))).total_seconds() < 60]
                            sensor_data_active = len(recent_sensor_data) > 0
                        except:
                            # If timestamp parsing fails, assume active
                            sensor_data_active = True
                    
                    # Adaptive ping strategy for continuous data:
                    if sensor_data_active:
                        # During active sensor data transmission, minimal ping
                        ping_threshold = 300  # 5 minutes
                    elif inactive_duration > 900:  # 15+ minutes
                        ping_threshold = 60  # 1 minute
                    elif inactive_duration > 300:  # 5-15 minutes
                        ping_threshold = 120  # 2 minutes
                    else:
                        ping_threshold = 999999  # No ping for first 5 minutes
                    
                    if inactive_duration > ping_threshold:
                        consecutive_inactive_periods += 1
                        # Send ping with timestamp
                        ping_message = {
                            "type": "ping", 
                            "timestamp": current_time.isoformat(),
                            "server_time": current_time.timestamp(),
                            "inactive_duration": int(inactive_duration)
                        }
                        await websocket.send_text(json.dumps(ping_message))
                        last_ping_time = current_time
                        logger.debug(f"[WebSocket] Smart ping sent to Pico at {current_time} (inactive for {inactive_duration:.0f}s, period #{consecutive_inactive_periods})")
                    else:
                        consecutive_inactive_periods = 0  # Reset counter if activity detected
                    
                except asyncio.CancelledError:
                    logger.debug(f"[WebSocket] Ping task cancelled for Pico")
                    break
                except Exception as e:
                    # Don't log normal closure errors
                    if "1000" not in str(e) and "Rapid test" not in str(e) and "ABNORMAL_CLOSURE" not in str(e):
                        logger.warning(f"[WebSocket] Error sending periodic ping to Pico: {e}")
                    break
        
        # Start periodic ping task
        ping_task = asyncio.create_task(periodic_ping())
        
        # Main message handling loop with improved error handling
        try:
            while True:
                try:
                    # Increased timeout for better stability
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=300)  # 5 minutes timeout
                    # Only log every 100th message to reduce overhead
                    if hasattr(system_state, 'message_counter'):
                        system_state.message_counter += 1
                    else:
                        system_state.message_counter = 1
                    
                    if system_state.message_counter % 100 == 0:
                        logger.info(f"[WebSocket] Pico message #{system_state.message_counter}: {data[:100]}...")
                    else:
                        logger.debug(f"[WebSocket] Pico message #{system_state.message_counter}")
                    
                    try:
                        message = json.loads(data)
                        message_type = message.get("type")
                        
                        # Update last seen for any message
                        current_time = datetime.now()
                        system_state.device_status["pico"]["last_seen"] = current_time
                        last_activity = current_time  # Update activity for smart ping
                        
                        if message_type == "pong":
                            logger.info(f"[PICO] Pong received, updating last_seen")
                            # Reset ping interval if we get a pong
                            last_ping_time = datetime.now()
                            
                        elif message_type == "ping":
                            # پاسخ به ping پیکو با timestamp
                            try:
                                pong_message = {
                                    "type": "pong",
                                    "timestamp": datetime.now().isoformat(),
                                    "server_time": datetime.now().timestamp()
                                }
                                await websocket.send_text(json.dumps(pong_message))
                                logger.info(f"[PICO] Ping received, sent pong response")
                            except Exception as e:
                                if "1000" not in str(e) and "Rapid test" not in str(e):
                                    logger.error(f"Error sending pong to Pico: {e}")
                                    
                        elif message_type == "connect":
                            # پیام اتصال اولیه پیکو
                            logger.info(f"[PICO] Connection message received: device={message.get('device')}, version={message.get('version')}")
                            # ارسال تایید اتصال فقط یک بار
                            if not hasattr(system_state, 'pico_connected'):
                                try:
                                    await websocket.send_text(json.dumps({
                                        "type": "connection_ack",
                                        "status": "success",
                                        "message": "Pico connection acknowledged",
                                        "timestamp": datetime.now().isoformat()
                                    }))
                                    system_state.pico_connected = True
                                except Exception as e:
                                    if "1000" not in str(e) and "Rapid test" not in str(e):
                                        logger.error(f"Error sending connection ack: {e}")
                            else:
                                logger.debug(f"[PICO] Connection already acknowledged, skipping")
                                    
                        elif message_type == "servo":
                            # پردازش دستورات سروو از پیکو
                            servo_data = message.get('command', {})
                            servo1_target = servo_data.get('servo1', 90)
                            servo2_target = servo_data.get('servo2', 90)
                            
                            logger.info(f"[PICO] Servo command received: servo1={servo1_target}°, servo2={servo2_target}°")
                            
                            # ارسال ACK برای دستور سروو
                            try:
                                ack_message = {
                                    "type": "ack",
                                    "command_type": "servo",
                                    "status": "success",
                                    "detail": f"servo1={servo1_target}°, servo2={servo2_target}°",
                                    "timestamp": datetime.now().isoformat()
                                }
                                await websocket.send_text(json.dumps(ack_message))
                                logger.info(f"[PICO] Servo command acknowledged")
                            except Exception as e:
                                if "1000" not in str(e) and "Rapid test" not in str(e):
                                    logger.error(f"Error sending servo ack: {e}")
                                    
                        elif message_type == "log":
                            logger.info(f"[PICO] {message.get('message', '')}")
                            try:
                                await insert_log(message.get('message', ''), message.get('level', 'info'), "pico")
                            except Exception as e:
                                logger.error(f"Error inserting Pico log: {e}")
                                system_state.error_counts["database"] += 1
                                
                        elif message_type == "ack":
                            logger.info(f"[PICO] ACK received: {message}")
                            
                        elif message_type == "test":
                            # پیام تست - فقط لاگ کن
                            logger.info(f"[PICO] Test message received: {message.get('message', '')}")
                            
                        elif message_type == "sensor_data":
                            # پردازش داده‌های سنسور برای استفاده مداوم
                            sensor_type = message.get("sensor_type", "unknown")
                            sensor_data = message.get("data", {})
                            sequence = sensor_data.get("sequence", 0)
                            
                            # ارسال ACK سریع برای داده‌های سنسور (بدون لاگ اضافی)
                            try:
                                ack_message = {
                                    "type": "ack",
                                    "command_type": "sensor_data",
                                    "status": "success",
                                    "sensor_type": sensor_type,
                                    "sequence": sequence,
                                    "timestamp": datetime.now().isoformat(),
                                    "server_time": datetime.now().timestamp()
                                }
                                await websocket.send_text(json.dumps(ack_message))
                                
                                # ذخیره داده‌های سنسور در حافظه برای پردازش
                                if not hasattr(system_state, 'sensor_data_buffer'):
                                    system_state.sensor_data_buffer = []
                                
                                system_state.sensor_data_buffer.append({
                                    "sensor_type": sensor_type,
                                    "data": sensor_data,
                                    "timestamp": datetime.now().isoformat(),
                                    "sequence": sequence
                                })
                                
                                # محدود کردن اندازه buffer
                                if len(system_state.sensor_data_buffer) > 1000:
                                    system_state.sensor_data_buffer = system_state.sensor_data_buffer[-500:]
                                
                                # Update activity for smart ping
                                last_activity = datetime.now()
                                
                                # Log only every 1000th sensor data for performance
                                if sequence % 1000 == 0:
                                    logger.info(f"[PICO] Sensor data processed: {sensor_type}, sequence: {sequence}")
                                
                            except Exception as e:
                                # Don't log normal WebSocket closure errors
                                if "1000" not in str(e) and "OK" not in str(e) and "ABNORMAL_CLOSURE" not in str(e):
                                    logger.error(f"Error processing sensor data: {e}")
                                else:
                                    logger.debug(f"Normal WebSocket operation: {e}")
                            
                        else:
                            logger.warning(f"[WebSocket] Unknown message type from Pico: {message}")
                            try:
                                await websocket.send_text(json.dumps({
                                    "type": "error", 
                                    "message": "Unknown message type",
                                    "timestamp": datetime.now().isoformat()
                                }))
                            except Exception:
                                pass
                                
                    except json.JSONDecodeError:
                        logger.warning(f"[WebSocket] Invalid JSON from Pico: {data}")
                        try:
                            await websocket.send_text(json.dumps({
                                "type": "error", 
                                "message": "Invalid JSON format",
                                "timestamp": datetime.now().isoformat()
                            }))
                        except Exception:
                            pass
                            
                except asyncio.TimeoutError:
                    # Send ping on timeout to check connection health
                    try:
                        ping_message = {
                            "type": "ping",
                            "timestamp": datetime.now().isoformat(),
                            "server_time": datetime.now().timestamp()
                        }
                        await websocket.send_text(json.dumps(ping_message))
                        logger.debug(f"[WebSocket] Timeout ping sent to Pico")
                    except Exception as e:
                        if "1000" not in str(e) and "Rapid test" not in str(e) and "ABNORMAL_CLOSURE" not in str(e):
                            logger.error(f"[WebSocket] Error sending timeout ping to Pico: {e}")
                        break
                    continue
        except Exception as e:
            # Don't log normal closure errors
            if "1000" not in str(e) and "Rapid test" not in str(e) and "ABNORMAL_CLOSURE" not in str(e):
                logger.error(f"[WebSocket] Pico error: {e}")
            try:
                await websocket.send_text(json.dumps({
                    "type": "error", 
                    "message": f"Server error: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }))
            except Exception:
                pass
            system_state.error_counts["websocket"] += 1
            system_state.device_status["pico"]["errors"].append({
                "time": datetime.now().isoformat(),
                "error": str(e)
            })
        finally:
            # Cancel periodic ping task
            if ping_task:
                ping_task.cancel()
                try:
                    await ping_task
                except asyncio.CancelledError:
                    pass
            async with system_state.pico_client_lock:
                system_state.pico_client = None
                system_state.device_status["pico"]["online"] = False
                system_state.device_status["pico"]["last_seen"] = datetime.now()
                system_state.active_clients = [c for c in system_state.active_clients if not (hasattr(c, 'ws') and c.ws == websocket)]
                # Reset connection flag
                if hasattr(system_state, 'pico_connected'):
                    delattr(system_state, 'pico_connected')
            logger.info(f"[WebSocket] Pico connection closed")
    except Exception as e:
        logger.error(f"[WebSocket] Fatal error in pico_websocket_endpoint: {e}")
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": f"Fatal server error: {str(e)}"}))
        except Exception:
            pass


 
async def set_servo(command: ServoCommand, request: Request, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    client_ip = request.client.host
    
    # Check rate limiting
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    # Sanitize and validate input
    command.servo1 = max(0, min(180, command.servo1))
    command.servo2 = max(0, min(180, command.servo2))
    
    logger.info(f"[HTTP] /set_servo from {client_ip}: servo1={command.servo1}, servo2={command.servo2}")
    
    # اعتبارسنجی ورودی
    if not isinstance(command.servo1, int) or not (0 <= command.servo1 <= 180):
        logger.error("Invalid servo1 value")
        raise HTTPException(status_code=400, detail="Invalid servo1 value")
    if not isinstance(command.servo2, int) or not (0 <= command.servo2 <= 180):
        logger.error("Invalid servo2 value")
        raise HTTPException(status_code=400, detail="Invalid servo2 value")
    
    try:
        await insert_servo_command(command.servo1, command.servo2)
        await insert_log(f"Servo command: X={command.servo1}°, Y={command.servo2}°", "command")
        
        # بررسی اتصال پیکو
        if not system_state.device_status["pico"]["online"]:
            logger.warning("Pico is offline, servo command will be queued")
            await send_to_web_clients_wrapper({
                "type": "command_response",
                "status": "warning",
                "message": "Pico is offline, command will be sent when connected",
                "command": {"type": "servo", "servo1": command.servo1, "servo2": command.servo2}
            })
            return {"status": "warning", "message": "Pico is offline, command will be sent when connected"}
        
        # Send servo command to Pico with proper format
        servo_message = {
            "type": "servo", 
            "command": {
                "servo1": command.servo1, 
                "servo2": command.servo2
            },
            "timestamp": datetime.now().isoformat(),
            "source": "web_interface"
        }
        
        # Guard dispatch if function is not available yet
        try:
            if hasattr(system_state, 'pico_client') and system_state.pico_client is not None:
                await send_to_pico_client(servo_message)
            else:
                logger.debug("Pico client not available; skipping pico dispatch")
        except Exception as disp_err:
            logger.warning(f"Non-CRITICAL ERROR dispatching servo/log updates: {disp_err}")
        
        # Also send to ESP32CAM for logging/status updates
        try:
            if hasattr(system_state, 'esp32cam_client') and system_state.esp32cam_client is not None:
                await send_to_esp32cam_client({
                    "type": "servo_command_log",
                    "servo1": command.servo1,
                    "servo2": command.servo2,
                    "timestamp": datetime.now().isoformat()
                })
            else:
                logger.debug("ESP32CAM client not available; skipping esp32cam dispatch")
        except Exception as disp_err:
            logger.warning(f"Non-CRITICAL ERROR dispatching servo/log updates: {disp_err}")
        
        await send_to_web_clients_wrapper({
            "type": "command_response",
            "status": "success",
            "command": {"type": "servo", "servo1": command.servo1, "servo2": command.servo2}
        })
        return {"status": "success", "message": f"Servo command sent: X={command.servo1}°, Y={command.servo2}°"}
    except ValueError as e:
        logger.error(f"Servo validation error from {request.client.host}: {e}, input: servo1={command.servo1}, servo2={command.servo2}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Servo command error from {request.client.host}: {e}, input: servo1={command.servo1}, servo2={command.servo2}")
        raise HTTPException(status_code=500, detail="Servo command error")


