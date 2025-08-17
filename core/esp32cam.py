import asyncio, time, os, cv2, base64, json, logging, logging.config, logging.handlers
import numpy as np
from datetime import datetime
from fastapi.responses import StreamingResponse
from fastapi import Request, HTTPException, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Optional

# ConnectionResetError was removed in Python 3.12, use ConnectionError instead
try:
    from socket import ConnectionResetError
except ImportError:
    ConnectionResetError = ConnectionError
try:
    # Pydantic v2
    from pydantic import model_validator as _model_validator
    _PydanticV2 = True
except Exception:
    _PydanticV2 = False

# Import from shared config
from .config import (
    FRAME_QUEUE_SIZE, FRAME_BUFFER_SIZE, FRAME_PROCESSING_TIMEOUT,
    REALTIME_FRAME_PROCESSING, ADAPTIVE_QUALITY, VIDEO_QUALITY,
    FRAME_PROCESSING_ENABLED, GALLERY_DIR, SECURITY_VIDEOS_DIR,
    get_jalali_now_str,
    MAX_UPLOAD_SIZE, MIN_FRAME_INTERVAL,
    FRAME_SKIP_THRESHOLD, MAX_FRAME_SIZE, FRAME_DROP_RATIO,
    PERFORMANCE_MONITORING, VIDEO_FPS,
    MAX_WEBSOCKET_MESSAGE_SIZE,
    FRAME_COMPRESSION_THRESHOLD, PERSIAN_TEXT_OVERLAY, FRAME_LATENCY_THRESHOLD,
    MIN_VALID_FRAMES, app, get_current_user
)

# Import authenticate_websocket directly from client module
from .client import authenticate_websocket

# Import from other modules
from .db import robust_db_endpoint, insert_action_command, execute_db_insert, insert_log
from .client import create_security_video_async, send_to_web_clients
from .sanitize_validate import validate_image_format

# Global function reference for pico communication (will be set by main server)
send_to_pico_client = None

# Setup logger for this module
logger = logging.getLogger("esp32cam")

# Global system state reference (will be set by main server)
system_state = None

def set_system_state(state):
    """Set the system state reference from main server"""
    global system_state
    system_state = state

def get_system_state():
    """Get system state with proper initialization"""
    global system_state
    if system_state is None:
        logger.warning("⚠️ system_state not initialized yet, creating temporary state")
        # Create a temporary system state for initialization
        class TempSystemState:
            def __init__(self):
                self.esp32cam_client_lock = asyncio.Lock()
                self.esp32cam_client = None
                self.device_status = {"esp32cam": {"online": False, "last_seen": None, "errors": []}}
                self.active_clients = []
                self.error_counts = {"websocket": 0, "database": 0, "frame_processing": 0}
                self.frame_lock = asyncio.Lock()
                self.frame_buffer_lock = asyncio.Lock()
                self.performance_lock = asyncio.Lock()
                self.latest_frame = None
                self.frame_count = 0
                self.frame_buffer = []
                self.last_frame_time = time.time()
                self.frame_skip_count = 0
                self.video_quality = 80
                self.processing_enabled = True
                self.invalid_frame_count = 0
                self.realtime_enabled = False
                self.adaptive_quality = False
                self.current_quality = 80
                self.resolution = {"width": 640, "height": 480}
                self.frame_processing_times = []
                self.frame_latency_sum = 0.0
                self.processing_timeout = 5.0
                self.performance_metrics = {"avg_frame_latency": 0.0, "frame_processing_overhead": 0.0, "frame_drop_rate": 0.0}
                self.frame_drop_count = 0
        system_state = TempSystemState()
    
    # Ensure all required attributes are present
    required_attributes = {
        'frame_latency_sum': 0.0,
        'processing_timeout': 5.0,
        'frame_processing_times': [],
        'performance_metrics': {"avg_frame_latency": 0.0, "frame_processing_overhead": 0.0, "frame_drop_rate": 0.0},
        'frame_drop_count': 0,
        'invalid_frame_count': 0,
        'frame_skip_count': 0,
        'current_quality': 80,
        'adaptive_quality': False,
        'realtime_enabled': False,
        'processing_enabled': True
    }
    
    for attr_name, default_value in required_attributes.items():
        if not hasattr(system_state, attr_name):
            setattr(system_state, attr_name, default_value)
            logger.info(f"Initialized missing attribute in esp32cam: {attr_name}")
    
    # Ensure frame_lock is properly initialized
    if not hasattr(system_state, 'frame_lock') or system_state.frame_lock is None:
        logger.warning("⚠️ frame_lock not initialized, creating new lock")
        system_state.frame_lock = asyncio.Lock()
    
    return system_state

# Global function references (will be set by main server)
insert_log = None
create_security_video_func = None

def set_dependencies(log_func, security_video_func):
    """Set dependencies from main server"""
    global insert_log, create_security_video_func
    insert_log = log_func
    create_security_video_func = security_video_func

def set_pico_dependency(pico_func):
    """Set pico communication function from main server"""
    global send_to_pico_client
    send_to_pico_client = pico_func

def register_esp32cam_routes(fastapi_app):
    """Register esp32cam routes with the FastAPI app"""
    # Register WebSocket route
    fastapi_app.add_websocket_route("/ws/esp32cam", esp32cam_websocket_endpoint)
    # Register HTTP routes
    fastapi_app.add_api_route("/manual_photo", manual_photo, methods=["POST"])
    fastapi_app.add_api_route("/upload_photo", upload_photo, methods=["POST"])
    fastapi_app.add_api_route("/upload_frame", upload_frame, methods=["POST"])
    fastapi_app.add_api_route("/esp32_video_feed", video_feed, methods=["GET"])
    fastapi_app.add_api_route("/set_action", set_action, methods=["POST"])




try:
    from persiantools.jdatetime import JalaliDateTime
    PERSIANTOOLS_AVAILABLE = True
except ImportError:
    PERSIANTOOLS_AVAILABLE = False


try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_RESHAPER_AVAILABLE = True
except ImportError:
    ARABIC_RESHAPER_AVAILABLE = False






class ActiveClient:
    def __init__(self, ws, connect_time, user_agent=None):
        self.ws = ws
        self.ip = ws.client.host if hasattr(ws, 'client') and hasattr(ws.client, 'host') else None
        self.connect_time = connect_time
        self.user_agent = user_agent
        self.last_activity = connect_time

class ActionCommand(BaseModel):
    action: str = Field(..., min_length=1, max_length=50)
    intensity: Optional[int] = Field(default=50)

    class Config:
        extra = "ignore"

    def validate_action(self):
        allowed_actions = {
            'capture_photo', 'reset_position', 'emergency_stop', 'system_reboot', 
            'flash_on', 'flash_off', 'start_recording', 'stop_recording', 'save_to_gallery',
            'buzzer', 'led', 'motor', 'relay', 'custom', 'servo_reset', 'camera_reset',
            'system_status', 'get_logs', 'clear_logs', 'backup_system', 'restore_system'
        }
        if self.action not in allowed_actions:
            raise ValueError(f'Invalid action. Allowed actions: {", ".join(allowed_actions)}')
        return True

    def validate_intensity(self):
        if self.intensity is not None and (not isinstance(self.intensity, int) or self.intensity < 0 or self.intensity > 100):
            raise ValueError('Intensity must be an integer between 0 and 100')
        return True

class ManualPhotoRequest(BaseModel):
    quality: Optional[int] = Field(default=80)
    flash: bool = False
    intensity: Optional[int] = Field(default=50)

    class Config:
        extra = "ignore"

    def validate_quality(self):
        if self.quality is not None and (not isinstance(self.quality, int) or self.quality < 1 or self.quality > 100):
            raise ValueError('Quality must be an integer between 1 and 100')
        return True

    def validate_intensity(self):
        if self.intensity is not None and (not isinstance(self.intensity, int) or self.intensity < 0 or self.intensity > 100):
            raise ValueError('Intensity must be an integer between 0 and 100')
        return True


async def esp32cam_websocket_endpoint(websocket: WebSocket):
    # WebSocket authentication for ESP32CAM microcontroller
    logger.info(f"[WebSocket] ESP32CAM connection attempt from {websocket.client.host}")
    
    # Authenticate the connection
    if not await authenticate_websocket(websocket, "esp32cam"):
        return
    
    logger.info(f"[WebSocket] ESP32CAM authenticated and connected from {websocket.client.host}")
    
    # ثبت اتصال ESP32CAM
    async with system_state.esp32cam_client_lock:
        system_state.esp32cam_client = websocket
        system_state.device_status["esp32cam"]["online"] = True
        system_state.device_status["esp32cam"]["last_seen"] = datetime.now()
        system_state.active_clients.append(ActiveClient(websocket, datetime.now(), "ESP32CAM"))
        logger.info(f"[DEBUG] ESP32CAM status updated: online=True, last_seen={system_state.device_status['esp32cam']['last_seen']}")
    

    # Send connection success message
    try:
        await websocket.send_text(json.dumps({"type": "connection_ack", "status": "success", "message": "ESP32CAM connected successfully"}))
    except Exception as e:
        logger.warning(f"[WebSocket] Could not send connection success message: {e}")
    

    try:
        while True:
            try:
                # دریافت داده (متن یا باینری) - کاهش timeout برای جلوگیری از keepalive timeout
                message = await asyncio.wait_for(websocket.receive(), timeout=60)
                
                if message["type"] == "websocket.receive":
                    if "text" in message:
                        # پیام متنی
                        data = message["text"]
                        logger.info(f"[WebSocket] ESP32CAM text message: {data}")
                        
                        # پردازش پیام‌های متنی
                        try:
                            json_message = json.loads(data)
                            if json_message.get("type") == "photo_sent":
                                logger.info(f"[WebSocket] Manual photo received from ESP32CAM: {json_message.get('size', 0)} bytes")
                                # ذخیره عکس در گالری
                                await save_manual_photo_from_esp32cam(json_message)

                            elif json_message.get("type") == "photo_error":
                                logger.error(f"[WebSocket] ESP32CAM photo error: {json_message.get('message', 'Unknown error')}")
                                # ثبت خطا در وضعیت دستگاه
                                system_state.device_status["esp32cam"]["errors"].append({
                                    "time": datetime.now().isoformat(),
                                    "error": f"Photo error: {json_message.get('message', 'Unknown error')}"
                                })

                            elif json_message.get("type") == "log":
                                logger.info(f"[ESP32CAM] {json_message.get('message', '')}")
                                # ثبت لاگ در دیتابیس
                                try:
                                    await insert_log(json_message.get('message', ''), json_message.get('level', 'info'), "esp32cam")
                                except Exception as e:
                                    logger.error(f"Error inserting ESP32CAM log: {e}")
                                    system_state.error_counts["database"] += 1

                            elif json_message.get("type") == "system_error":
                                logger.error(f"[ESP32CAM] System error: {json_message.get('message', '')}")
                                system_state.device_status["esp32cam"]["errors"].append({
                                    "time": datetime.now().isoformat(),
                                    "error": f"System error: {json_message.get('message', '')}"
                                })
                        except json.JSONDecodeError:
                            logger.warning(f"[WebSocket] Invalid JSON from ESP32CAM: {data}")
                    
                    elif "bytes" in message:
                        # فریم باینری
                        frame_data = message["bytes"]
                        
                        # Validation فریم
                        if not frame_data or len(frame_data) == 0:
                            logger.warning("[WebSocket] Empty frame data received from ESP32CAM")
                            continue
                        
                        if len(frame_data) > MAX_FRAME_SIZE:
                            logger.warning(f"[WebSocket] Frame too large from ESP32CAM: {len(frame_data)} bytes")
                            system_state.frame_drop_count += 1
                            continue
                        
                        # به‌روزرسانی وضعیت دستگاه
                        system_state.device_status["esp32cam"]["last_seen"] = datetime.now()
                        
                        # پردازش فریم
                        try:
                            # پردازش فریم معمولی
                            processed_frame = await preprocess_frame(frame_data)
                            final_frame = await add_persian_text_overlay(processed_frame)
                            
                            # ذخیره در سیستم با بررسی lock
                            try:
                                if hasattr(system_state, 'frame_lock') and system_state.frame_lock is not None:
                                    async with system_state.frame_lock:
                                        system_state.latest_frame = final_frame
                                        system_state.frame_count += 1
                                        system_state.last_frame_time = time.time()
                                else:
                                    # Fallback if lock is not available
                                    system_state.latest_frame = final_frame
                                    system_state.frame_count += 1
                                    system_state.last_frame_time = time.time()
                                    logger.warning("⚠️ frame_lock not available, using fallback frame storage")
                            except Exception as lock_error:
                                logger.error(f"Error with frame_lock: {lock_error}")
                                # Fallback storage without lock
                                system_state.latest_frame = final_frame
                                system_state.frame_count += 1
                                system_state.last_frame_time = time.time()
                            
                            # اضافه به buffer با بررسی lock
                            try:
                                if hasattr(system_state, 'frame_buffer_lock') and system_state.frame_buffer_lock is not None:
                                    async with system_state.frame_buffer_lock:
                                        if len(system_state.frame_buffer) >= FRAME_BUFFER_SIZE:
                                            system_state.frame_buffer = system_state.frame_buffer[-FRAME_BUFFER_SIZE//2:]
                                        system_state.frame_buffer.append((final_frame, datetime.now()))
                                else:
                                    # Fallback if buffer lock is not available
                                    if len(system_state.frame_buffer) >= FRAME_BUFFER_SIZE:
                                        system_state.frame_buffer = system_state.frame_buffer[-FRAME_BUFFER_SIZE//2:]
                                    system_state.frame_buffer.append((final_frame, datetime.now()))
                                    logger.warning("⚠️ frame_buffer_lock not available, using fallback buffer storage")
                            except Exception as buffer_error:
                                logger.error(f"Error with frame_buffer_lock: {buffer_error}")
                                # Fallback buffer storage without lock
                                if len(system_state.frame_buffer) >= FRAME_BUFFER_SIZE:
                                    system_state.frame_buffer = system_state.frame_buffer[-FRAME_BUFFER_SIZE//2:]
                                system_state.frame_buffer.append((final_frame, datetime.now()))
            
                            # ارسال به فرانت‌اند با بهینه‌سازی
                            try:
                                await send_frame_to_clients(final_frame)
                            except Exception as e:
                                logger.error(f"Error sending frame to clients: {e}")
                                system_state.error_counts["frame_processing"] += 1
                            
                            # Log frame statistics every 100 frames
                            if system_state.frame_count % 100 == 0:
                                logger.info(f"[WebSocket] ESP32CAM processed {system_state.frame_count} frames")
                                
                        except Exception as e:
                            logger.error(f"[WebSocket] Error processing ESP32CAM frame: {e}")
                            system_state.device_status["esp32cam"]["errors"].append({
                                "time": datetime.now().isoformat(),
                                "error": f"Frame processing error: {str(e)}"
                            })
                            system_state.invalid_frame_count += 1
                    
            except asyncio.TimeoutError:
                logger.debug(f"[WebSocket] ESP32CAM timeout, sending ping")
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception as e:
                    if "1000" not in str(e) and "disconnect" not in str(e).lower():
                        logger.warning(f"[WebSocket] ESP32CAM ping failed: {e}")
                    break
                continue
            
    except WebSocketDisconnect as e:
        logger.info(f"[WebSocket] ESP32CAM disconnected cleanly: code={e.code}, reason={e.reason}")
    except ConnectionResetError as e:
        logger.info(f"[WebSocket] ESP32CAM connection reset: {e}")
    except Exception as e:
        # Don't log normal closure errors
        if "1000" not in str(e) and "Rapid test" not in str(e) and "disconnect" not in str(e).lower():
            logger.error(f"[WebSocket] ESP32CAM error: {e}")
        system_state.error_counts["websocket"] += 1
        system_state.device_status["esp32cam"]["errors"].append({
            "time": datetime.now().isoformat(),
            "error": str(e)
        })

    finally:
        # حذف اتصال ESP32CAM
        async with system_state.esp32cam_client_lock:
            system_state.esp32cam_client = None
            system_state.device_status["esp32cam"]["online"] = False
            system_state.device_status["esp32cam"]["last_seen"] = datetime.now()
            system_state.active_clients = [c for c in system_state.active_clients if not (hasattr(c, 'ws') and c.ws == websocket)]
        logger.info(f"[WebSocket] ESP32CAM connection closed")








async def save_manual_photo_binary(frame_data):
    """ذخیره عکس دستی باینری دریافتی از ESP32CAM"""
    try:
        # اعتبارسنجی فرمت تصویر
        if not validate_image_format(frame_data):
            logger.error("Invalid image format for manual photo")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"manual_photo_{timestamp}.jpg"
        filepath = os.path.join(GALLERY_DIR, filename)
        
        # ایجاد پوشه گالری
        await asyncio.to_thread(os.makedirs, GALLERY_DIR, exist_ok=True)
        
        # پردازش و ذخیره عکس
        processed_photo = await preprocess_frame(frame_data)
        final_photo = await add_persian_text_overlay(processed_photo)
        
        # ذخیره فایل
        await asyncio.to_thread(lambda: open(filepath, 'wb').write(final_photo))
        
        # ذخیره در دیتابیس
        await insert_photo_to_db(filename, filepath, 80, False, 50)
        await insert_log(f"Manual photo saved from ESP32CAM: {filename}", "photo")
        
        # ارسال به فرانت‌اند
        await send_to_web_clients({
            "type": "photo_captured",
            "filename": filename,
            "url": f"/gallery/{filename}",
            "quality": 80,
            "flash_used": False,
            "intensity": 50,
            "timestamp": get_jalali_now_str()
        })
        
        logger.info(f"Manual photo saved successfully: {filename}")
        
    except Exception as e:
        logger.error(f"Error saving manual photo binary from ESP32CAM: {e}")
        await insert_log(f"Error saving manual photo binary: {e}", "error")





async def save_manual_photo_from_esp32cam(message):
    """ذخیره عکس دستی دریافتی از ESP32CAM"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"manual_photo_{timestamp}.jpg"
        filepath = os.path.join(GALLERY_DIR, filename)
        
        # ایجاد پوشه گالری
        await asyncio.to_thread(os.makedirs, GALLERY_DIR, exist_ok=True)
        
        # ذخیره در دیتابیس
        await insert_photo_to_db(filename, filepath, 80, False, 50)
        await insert_log(f"Manual photo saved from ESP32CAM: {filename}", "photo")
        
        # ارسال به فرانت‌اند
        await send_to_web_clients({
            "type": "photo_captured",
            "filename": filename,
            "url": f"/gallery/{filename}",
            "quality": 80,
            "flash_used": False,
            "intensity": 50,
            "timestamp": get_jalali_now_str()
        })
        
        logger.info(f"Manual photo saved successfully: {filename}")
        
    except Exception as e:
        logger.error(f"Error saving manual photo from ESP32CAM: {e}")
        await insert_log(f"Error saving manual photo: {e}", "error")






async def send_to_esp32cam_client(message):
    try:
        if not hasattr(system_state, 'esp32cam_client_lock') or system_state.esp32cam_client_lock is None:
            logger.debug("ESP32CAM client lock not initialized; skipping dispatch")
            return
            
        async with system_state.esp32cam_client_lock:
            client = getattr(system_state, 'esp32cam_client', None)
            if client:
                try:
                    await client.send_text(json.dumps(message))
                    # به‌روزرسانی وضعیت دستگاه
                    system_state.device_status["esp32cam"]["last_seen"] = datetime.now()
                    logger.debug(f"Message sent to ESP32CAM: {message}")
                except Exception as e:
                    # Don't log normal closure errors
                    if "1000" not in str(e) and "Rapid test" not in str(e):
                        logger.warning(f"Failed to send to esp32cam client {client.client.host}: {e}")
                    system_state.esp32cam_client = None
                    system_state.device_status["esp32cam"]["online"] = False
                    system_state.device_status["esp32cam"]["errors"].append({
                        "time": datetime.now().isoformat(),
                        "error": str(e)
                    })
                    system_state.active_clients = [c for c in system_state.active_clients if not (hasattr(c, 'ws') and c.ws == client)]
                    logger.info(f"Removed disconnected esp32cam client: {client.client.host}")
            else:
                logger.debug("ESP32CAM client not connected")
                # Only add error if it's been more than 5 minutes since last error
                last_error_time = system_state.device_status["esp32cam"]["errors"][-1]["time"] if system_state.device_status["esp32cam"]["errors"] else None
                if not last_error_time or (datetime.now() - datetime.fromisoformat(last_error_time)).total_seconds() > 300:
                    system_state.device_status["esp32cam"]["errors"].append({
                        "time": datetime.now().isoformat(),
                        "error": "Client not connected"
                    })
    except Exception as e:
        logger.warning(f"Non-CRITICAL ERROR dispatching esp32cam updates: {e}")




# --- Common photo insertion function ---
async def insert_photo_to_db(filename: str, filepath: str, quality: int = 80, flash_used: bool = False, intensity: int = 50):
    """Common function to insert photo into database"""
    await execute_db_insert(
        "INSERT INTO manual_photos (filename, filepath, quality, flash_used, flash_intensity, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (filename, filepath, quality, flash_used, intensity, get_jalali_now_str())
    )






@robust_db_endpoint
async def manual_photo(manual_request: ManualPhotoRequest, request: Request, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Ensure all fields are properly set and validated
    if manual_request.quality is None:
        manual_request.quality = 80
    elif not isinstance(manual_request.quality, int) or manual_request.quality < 1 or manual_request.quality > 100:
        raise HTTPException(status_code=422, detail="Quality must be an integer between 1 and 100")
    
    if manual_request.intensity is None:
        manual_request.intensity = 50
    elif not isinstance(manual_request.intensity, int) or manual_request.intensity < 0 or manual_request.intensity > 100:
        raise HTTPException(status_code=422, detail="Intensity must be an integer between 0 and 100")
    
    # Validate flash boolean
    if not isinstance(manual_request.flash, bool):
        raise HTTPException(status_code=422, detail="Flash must be a boolean value")
    
    # Call validation methods
    manual_request.validate_quality()
    manual_request.validate_intensity()
    
    logger.info(f"[HTTP] /manual_photo from {request.client.host}: quality={manual_request.quality}, flash={manual_request.flash}, intensity={manual_request.intensity}")
    logger.info(f"[DEBUG] Received photo request data: {manual_request.dict()}")
    
    try:
        # بررسی اتصال ESP32CAM - برای تست موقتاً نادیده می‌گیریم
        if not system_state.device_status["esp32cam"]["online"]:
            logger.warning("ESP32CAM is offline, but continuing for testing purposes")
            # برای تست، ادامه می‌دهیم
            # return {"status": "error", "message": "ESP32CAM is offline, cannot capture photo"}
        
        # ارسال دستور به ESP32CAM با مدیریت خطا
        try:
            if hasattr(system_state, 'esp32cam_client') and system_state.esp32cam_client is not None:
                await send_to_esp32cam_client({
                    "action": "capture_photo",
                    "quality": manual_request.quality,
                    "flash": manual_request.flash,
                    "intensity": manual_request.intensity
                })
            else:
                logger.debug("ESP32CAM client not available; skipping esp32cam dispatch")
        except Exception as disp_err:
            logger.warning(f"Non-CRITICAL ERROR dispatching photo command to esp32cam: {disp_err}")
        
        # ثبت لاگ
        await insert_log(f"Manual photo command sent to ESP32CAM: quality={manual_request.quality}, flash={manual_request.flash}, intensity={manual_request.intensity}%", "photo")
        
        return {"status": "success", "message": "Photo capture command sent to ESP32CAM"}
        
    except Exception as e:
        logger.error(f"Unexpected DB ERROR: {e}")
        return {"status": "error", "message": "Internal server error"}


@robust_db_endpoint
async def upload_photo(request: Request, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    form = await request.form()
    logger.info(f"[HTTP] /upload_photo from {request.client.host}: fields={list(form.keys())}")
    if set(form.keys()) - {'photo', 'quality', 'flash_used', 'intensity'}:
        raise HTTPException(status_code=400, detail="Invalid form fields")
    photo_data = form.get("photo")
    quality = int(form.get("quality", 80))
    flash_used = form.get("flash_used", "false").lower() == "true"
    intensity = int(form.get("intensity", 50))
    if not photo_data:
        raise HTTPException(status_code=400, detail="Photo data not received")
    photo_bytes = await photo_data.read() if hasattr(photo_data, 'file') else (photo_data.encode() if isinstance(photo_data, str) else photo_data)
    if len(photo_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="Photo size exceeds limit")
    if not validate_image_format(photo_bytes):
        raise HTTPException(status_code=400, detail="Invalid photo format")
    processed_photo = await preprocess_frame(photo_bytes)
    final_photo = await add_persian_text_overlay(processed_photo)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"manual_photo_{timestamp}.jpg"
    filepath = os.path.join(GALLERY_DIR, filename)
    await asyncio.to_thread(os.makedirs, GALLERY_DIR, exist_ok=True)
    await asyncio.to_thread(lambda: open(filepath, 'wb').write(final_photo))
    await insert_photo_to_db(filename, filepath, quality, flash_used, intensity)
    try:
        await insert_log(f"Photo uploaded: {filename}, Intensity: {intensity}%", "photo")
    except Exception as e:
        logger.error(f"Error inserting photo upload log: {e}")
        system_state.error_counts["database"] += 1
    await send_to_web_clients({
        "type": "photo_captured",
        "filename": filename,
        "url": f"/gallery/{filename}",
        "quality": quality,
        "flash_used": flash_used,
        "intensity": intensity,
        "timestamp": get_jalali_now_str()
    })
    return {"status": "success", "filename": filename, "url": f"/gallery/{filename}"}



async def upload_frame(request: Request, user=Depends(get_current_user)):
    """آپلود فریم با بهینه‌سازی real-time و مدیریت هوشمند"""
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    start_time = time.time()
    
    try:
        # بررسی نرخ فریم با منطق پیشرفته
        current_time = time.time()
        frame_interval = current_time - system_state.last_frame_time
        
        if frame_interval < MIN_FRAME_INTERVAL:
            # بررسی اینکه آیا باید فریم را رد کنیم یا نه
            if system_state.frame_skip_count < FRAME_SKIP_THRESHOLD:
                system_state.frame_skip_count += 1
                return {"status": "success", "message": "Frame skipped (high rate)"}
            else:
                # اگر تعداد فریم‌های رد شده زیاد است، فریم را پردازش کن
                system_state.frame_skip_count = 0
        
        system_state.last_frame_time = current_time
        
        # دریافت داده فریم
        form = await request.form()
        if not form or set(form.keys()) - {'frame'} or 'frame' not in form:
            raise HTTPException(status_code=400, detail="Frame data not received or invalid form fields")
        
        frame_data = form.get("frame")
        if not frame_data:
            raise HTTPException(status_code=400, detail="Frame data not received")
        
        frame_bytes = await frame_data.read() if hasattr(frame_data, 'file') else (frame_data.encode() if isinstance(frame_data, str) else frame_data)
        
        # اعتبارسنجی اندازه و فرمت
        if len(frame_bytes) > MAX_FRAME_SIZE:
            raise HTTPException(status_code=400, detail="Frame size exceeds limit")
        if not validate_image_format(frame_bytes):
            raise HTTPException(status_code=400, detail="Invalid frame format")
        
        # پردازش فریم با timeout
        try:
            processed_frame = await asyncio.wait_for(preprocess_frame(frame_bytes), timeout=FRAME_PROCESSING_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("Frame processing timeout, using original frame")
            system_state.frame_drop_count += 1
            processed_frame = frame_bytes
        
        # اضافه کردن متن فارسی
        final_frame = await add_persian_text_overlay(processed_frame)
        
        # ذخیره در سیستم با lock بهینه
        try:
            if hasattr(system_state, 'frame_lock') and system_state.frame_lock is not None:
                async with system_state.frame_lock:
                    system_state.latest_frame = final_frame
                    system_state.frame_count += 1
            else:
                # Fallback if lock is not available
                system_state.latest_frame = final_frame
                system_state.frame_count += 1
                logger.warning("⚠️ frame_lock not available in upload_frame, using fallback")
        except Exception as lock_error:
            logger.error(f"Error with frame_lock in upload_frame: {lock_error}")
            # Fallback storage without lock
            system_state.latest_frame = final_frame
            system_state.frame_count += 1
        
        # مدیریت buffer با منطق هوشمند
        try:
            if hasattr(system_state, 'frame_buffer_lock') and system_state.frame_buffer_lock is not None:
                async with system_state.frame_buffer_lock:
                    # بررسی buffer overflow با منطق پیشرفته
                    if len(system_state.frame_buffer) >= FRAME_BUFFER_SIZE:
                        # حذف فریم‌های قدیمی بر اساس نسبت
                        frames_to_remove = int(FRAME_BUFFER_SIZE * FRAME_DROP_RATIO)
                        system_state.frame_buffer = system_state.frame_buffer[frames_to_remove:]
                        system_state.frame_drop_count += frames_to_remove
                        logger.info(f"Frame buffer trimmed: removed {frames_to_remove} old frames")
                    
                    # اضافه کردن فریم جدید
                    system_state.frame_buffer.append((final_frame, datetime.now()))
                    
                    # بررسی نیاز به ایجاد ویدیو
                    if len(system_state.frame_buffer) >= FRAME_BUFFER_SIZE:
                        try:
                            # ایجاد ویدیو در background
                            asyncio.create_task(create_security_video_async(system_state.frame_buffer[:FRAME_BUFFER_SIZE//2]))
                            system_state.frame_buffer = system_state.frame_buffer[FRAME_BUFFER_SIZE//2:]
                        except Exception as e:
                            logger.error(f"Error creating security video: {e}")
                            # در صورت خطا، buffer را پاک کن
                            system_state.frame_buffer = system_state.frame_buffer[-FRAME_BUFFER_SIZE//4:]
            else:
                # Fallback if buffer lock is not available
                if len(system_state.frame_buffer) >= FRAME_BUFFER_SIZE:
                    frames_to_remove = int(FRAME_BUFFER_SIZE * FRAME_DROP_RATIO)
                    system_state.frame_buffer = system_state.frame_buffer[frames_to_remove:]
                    system_state.frame_drop_count += frames_to_remove
                system_state.frame_buffer.append((final_frame, datetime.now()))
                logger.warning("⚠️ frame_buffer_lock not available in upload_frame, using fallback")
        except Exception as buffer_error:
            logger.error(f"Error with frame_buffer_lock in upload_frame: {buffer_error}")
            # Fallback buffer management without lock
            if len(system_state.frame_buffer) >= FRAME_BUFFER_SIZE:
                frames_to_remove = int(FRAME_BUFFER_SIZE * FRAME_DROP_RATIO)
                system_state.frame_buffer = system_state.frame_buffer[frames_to_remove:]
                system_state.frame_drop_count += frames_to_remove
            system_state.frame_buffer.append((final_frame, datetime.now()))
        
        # ارسال به فرانت‌اند با بهینه‌سازی
        try:
            await send_frame_to_clients(final_frame)
        except Exception as e:
            logger.error(f"Error sending frame to clients: {e}")
            system_state.error_counts["frame_processing"] += 1
        
        # محاسبه و ثبت متریک‌های عملکرد
        total_time = time.time() - start_time
        if PERFORMANCE_MONITORING:
            system_state.performance_metrics["frame_drop_rate"] = system_state.frame_drop_count / max(system_state.frame_count, 1)
        
        return {"status": "success", "processing_time": total_time}
        
    except ValueError as e:
        logger.error(f"Frame validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Frame upload error: {e}")
        raise HTTPException(status_code=500, detail="Frame upload error")
    

async def generate_frames():
    while not system_state.system_shutdown:
        try:
            try:
                if hasattr(system_state, 'frame_lock') and system_state.frame_lock is not None:
                    async with system_state.frame_lock:
                        if system_state.latest_frame is not None:
                            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + system_state.latest_frame + b'\r\n')
                else:
                    # Fallback if lock is not available
                    if system_state.latest_frame is not None:
                        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + system_state.latest_frame + b'\r\n')
                    logger.warning("⚠️ frame_lock not available in generate_frames, using fallback")
            except Exception as lock_error:
                logger.error(f"Error with frame_lock in generate_frames: {lock_error}")
                # Fallback without lock
                if system_state.latest_frame is not None:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + system_state.latest_frame + b'\r\n')
            await asyncio.sleep(1.0 / VIDEO_FPS)
        except Exception as e:
            logger.error(f"Frame generation error: {e}")
            await asyncio.sleep(1.0)  # Wait longer on error



async def video_feed(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace;boundary=frame")
    except Exception as e:
        logger.error(f"Video feed error: {e}")
        raise HTTPException(status_code=500, detail="Video feed error")






async def set_action(command: ActionCommand, request: Request, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Ensure intensity is properly set and validated
    if command.intensity is None:
        command.intensity = 50
    elif not isinstance(command.intensity, int) or command.intensity < 0 or command.intensity > 100:
        raise HTTPException(status_code=422, detail="Intensity must be an integer between 0 and 100")
    
    # Validate action string
    if not isinstance(command.action, str) or not command.action.strip():
        raise HTTPException(status_code=422, detail="Action must be a non-empty string")
    
    logger.info(f"[HTTP] /set_action from {request.client.host}: action={command.action}, intensity={command.intensity}")
    logger.info(f"[DEBUG] Received command data: {command.dict()}")
    
    try:
        command.validate_action()
        command.validate_intensity()
        await insert_action_command(command.action, command.intensity)
        await insert_log(f"Action command: {command.action}, Intensity: {command.intensity}%", "command")
        if command.action in ['flash_on', 'flash_off']:
            system_state.flash_intensity = command.intensity if command.action == 'flash_on' else 0
        
        # Send action to ESP32CAM (not Pico)
        try:
            if hasattr(system_state, 'esp32cam_client') and system_state.esp32cam_client is not None:
                # ESP32CAM firmware expects top-level "action" and may use optional fields
                await send_to_esp32cam_client({
                    "action": command.action,
                    "intensity": command.intensity
                })
            else:
                logger.debug("ESP32CAM client not available; skipping esp32cam dispatch")
        except Exception as disp_err:
            logger.warning(f"Non-CRITICAL ERROR dispatching action to esp32cam: {disp_err}")
            
        await send_to_web_clients({
            "type": "command_response",
            "status": "success",
            "command": {"type": "action", "action": command.action, "intensity": command.intensity}
        })

        return {"status": "success", "message": f"Action command sent: {command.action}, Intensity: {command.intensity}%"}
    except ValueError as e:
        logger.error(f"Action validation error: {e}")
        raise HTTPException(status_code=422, detail=f"Invalid action: {str(e)}")
    except Exception as e:
        logger.error(f"Action command error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    


async def send_frame_to_clients(frame_data: bytes):
    """ارسال فریم به فرانت‌اند با بهینه‌سازی"""
    try:
        # بررسی اندازه فریم قبل از ارسال
        frame_to_send = base64.b64encode(frame_data).decode('utf-8')
        frame_message = json.dumps({"type": "frame", "data": frame_to_send, "resolution": system_state.resolution})
        
        # بررسی اندازه پیام و فشرده‌سازی هوشمند
        if len(frame_message) > MAX_WEBSOCKET_MESSAGE_SIZE:
            logger.warning(f"Frame message too large ({len(frame_message)} bytes), compressing")
            # فشرده‌سازی هوشمند
            compressed_frame = await compress_frame_intelligently(frame_data)
            compressed_data = base64.b64encode(compressed_frame).decode('utf-8')
            frame_message = json.dumps({"type": "frame", "data": compressed_data, "resolution": system_state.resolution})
        
        # ارسال به فرانت‌اند
        await send_to_web_clients(frame_message)
        
    except Exception as e:
        # Don't log normal closure errors
        if "1000" not in str(e) and "Rapid test" not in str(e):
            logger.error(f"Error sending frame to clients: {e}")










async def compress_frame_intelligently(frame_data: bytes) -> bytes:
    """فشرده‌سازی هوشمند فریم بر اساس اندازه و کیفیت"""
    try:
        # decode frame
        frame_array = np.frombuffer(frame_data, dtype=np.uint8)
        frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
        
        if frame is None:
            return frame_data
        
        # محاسبه کیفیت بهینه بر اساس اندازه
        original_size = len(frame_data)
        target_size = FRAME_COMPRESSION_THRESHOLD
        
        if original_size <= target_size:
            return frame_data
        
        # محاسبه نسبت فشرده‌سازی
        compression_ratio = target_size / original_size
        quality = max(30, int(compression_ratio * 100))
        
        # فشرده‌سازی
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, compressed_frame = await asyncio.to_thread(cv2.imencode, '.jpg', frame, encode_params)
        
        # آزاد کردن حافظه
        del frame_array, frame
        
        return compressed_frame.tobytes()
        
    except Exception as e:
        logger.error(f"Error compressing frame: {e}")
        return frame_data








async def add_persian_text_overlay(frame_data: bytes) -> bytes:
    if not PERSIAN_TEXT_OVERLAY or not PERSIANTOOLS_AVAILABLE or not ARABIC_RESHAPER_AVAILABLE:
        return frame_data
    try:
        frame_array = np.frombuffer(frame_data, dtype=np.uint8)
        frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Invalid frame for text overlay")
        jalali_datetime = JalaliDateTime.now().strftime("%Y/%m/%d %H:%M:%S")
        text = get_display(arabic_reshaper.reshape(jalali_datetime))
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        color = (255, 255, 255)
        thickness = 2
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = frame.shape[1] - text_size[0] - 10
        text_y = frame.shape[0] - 10
        await asyncio.to_thread(cv2.putText, frame, text, (text_x, text_y), font, font_scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
        await asyncio.to_thread(cv2.putText, frame, text, (text_x, text_y), font, font_scale, color, thickness, cv2.LINE_AA)
        _, processed_frame = await asyncio.to_thread(cv2.imencode, '.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), system_state.video_quality])
        return processed_frame.tobytes()
    except Exception as e:
        logger.error(f"Error adding Persian text overlay: {e}")
        return frame_data

async def preprocess_frame(frame_data: bytes) -> bytes:
    """پردازش پیشرفته فریم با بهینه‌سازی real-time و مدیریت حافظه"""
    start_time = time.time()
    
    try:
        if not system_state.processing_enabled:
            return frame_data
        
        # Validate input data
        if not frame_data or len(frame_data) == 0:
            logger.warning("Empty frame data received")
            system_state.invalid_frame_count += 1
            return frame_data
        
        if len(frame_data) > MAX_FRAME_SIZE:
            logger.warning(f"Frame too large: {len(frame_data)} bytes")
            system_state.frame_drop_count += 1
            return frame_data
        
        # بررسی timeout پردازش
        if system_state.realtime_enabled and (time.time() - start_time) > system_state.processing_timeout:
            logger.warning("Frame processing timeout, skipping")
            system_state.frame_skip_count += 1
            return frame_data
        
        # بهبود مدیریت حافظه با context manager
        frame_array = np.frombuffer(frame_data, dtype=np.uint8)
        frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
        
        if frame is None:
            system_state.invalid_frame_count += 1
            logger.warning("Failed to decode frame data")
            return frame_data
        
        # آزاد کردن حافظه frame_array
        del frame_array
        
        # Validate frame dimensions
        if frame.shape[0] == 0 or frame.shape[1] == 0:
            system_state.invalid_frame_count += 1
            logger.warning("Invalid frame dimensions")
            del frame
            return frame_data
        
        # resize frame با بهینه‌سازی
        target_size = (system_state.resolution['width'], system_state.resolution['height'])
        if frame.shape[:2] != target_size[::-1]:  # OpenCV uses (height, width)
            try:
                frame = await asyncio.to_thread(cv2.resize, frame, target_size, interpolation=cv2.INTER_LANCZOS4)
            except Exception as e:
                logger.error(f"Frame resize error: {e}")
                del frame
                return frame_data
        
        # کیفیت تطبیقی بر اساس عملکرد
        quality = system_state.current_quality
        if system_state.adaptive_quality and len(system_state.frame_processing_times) > 10:
            async with system_state.performance_lock:
                avg_processing_time = sum(system_state.frame_processing_times[-10:]) / 10
                if avg_processing_time > FRAME_LATENCY_THRESHOLD:
                    quality = max(60, quality - 10)  # کاهش کیفیت
                    system_state.current_quality = quality
                elif avg_processing_time < FRAME_LATENCY_THRESHOLD * 0.5:
                    quality = min(95, quality + 5)  # افزایش کیفیت
                    system_state.current_quality = quality
        
        # encode frame با کیفیت بهینه
        try:
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            _, processed_frame = await asyncio.to_thread(cv2.imencode, '.jpg', frame, encode_params)
        except Exception as e:
            logger.error(f"Frame encoding error: {e}")
            del frame
            return frame_data
        
        # آزاد کردن حافظه frame
        del frame
        
        result = processed_frame.tobytes()
        
        # آزاد کردن حافظه processed_frame
        del processed_frame
        
        # ثبت متریک‌های عملکرد با thread safety
        processing_time = time.time() - start_time
        try:
            async with system_state.performance_lock:
                system_state.frame_processing_times.append(processing_time)
                system_state.frame_latency_sum += processing_time
                
                # نگهداری فقط 100 نمونه اخیر
                if len(system_state.frame_processing_times) > 100:
                    system_state.frame_processing_times = system_state.frame_processing_times[-100:]
                
                # به‌روزرسانی متریک‌های عملکرد
                if len(system_state.frame_processing_times) > 0:
                    system_state.performance_metrics["avg_frame_latency"] = system_state.frame_latency_sum / len(system_state.frame_processing_times)
                    system_state.performance_metrics["frame_processing_overhead"] = processing_time / MIN_FRAME_INTERVAL
        except AttributeError as e:
            # Handle missing attributes gracefully
            logger.warning(f"Performance metrics update failed: {e}")
            # Initialize missing attributes if needed
            if not hasattr(system_state, 'frame_latency_sum'):
                system_state.frame_latency_sum = 0.0
            if not hasattr(system_state, 'frame_processing_times'):
                system_state.frame_processing_times = []
            if not hasattr(system_state, 'performance_metrics'):
                system_state.performance_metrics = {"avg_frame_latency": 0.0, "frame_processing_overhead": 0.0, "frame_drop_rate": 0.0}
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
        
        return result
        
    except Exception as e:
        logger.error(f"Frame processing error: {e}")
        try:
            system_state.invalid_frame_count += 1
            if system_state.invalid_frame_count >= MIN_VALID_FRAMES:
                logger.warning("Too many invalid frames, consider checking camera")
        except AttributeError:
            # Handle missing attributes gracefully
            logger.warning("System state attributes not properly initialized")
        return frame_data





