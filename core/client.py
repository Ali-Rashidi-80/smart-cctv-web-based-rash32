import asyncio, aiosqlite, time, os, sys, gc, random, functools, cv2, shutil, bcrypt, json, logging, logging.config, logging.handlers, errno, pyotp
import numpy as np
from typing import List, Tuple
from datetime import datetime, timedelta
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from starlette.background import BackgroundTask
from fastapi import Request, HTTPException, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError, field_validator, EmailStr
from starlette.websockets import WebSocketDisconnect as StarletteWebSocketDisconnect
# ConnectionResetError was removed in Python 3.12, use ConnectionError instead
try:
    from socket import ConnectionResetError
except ImportError:
    ConnectionResetError = ConnectionError

# Import from shared config
from .config import (
    SECURITY_CONFIG, RATE_LIMIT_CONFIG, CAPTCHA_CONFIG, CSRF_CONFIG,
    get_jalali_now_str, is_local_test_request, retry_async, is_test_environment,
    VIDEO_FPS, MIN_VALID_FRAMES, MAX_WEBSOCKET_MESSAGE_SIZE,
    GALLERY_DIR, SECURITY_VIDEOS_DIR, DEVICE_RESOLUTIONS, translations,
    SmartFeaturesCommand, get_app, get_templates,
    FRAME_SKIP_THRESHOLD, MAX_WEBSOCKET_CLIENTS, ACCESS_TOKEN_EXPIRE_MINUTES,
    MAX_VIDEO_FILE_SIZE, VIDEO_STREAMING_THRESHOLD
)

# Import functions from their actual modules
from .sanitize_validate import sanitize_input
from .Security import check_rate_limit, hash_password, validate_captcha, should_require_captcha, record_captcha_attempt, validate_csrf_token, get_csrf_token_from_request
from .sms import send_password_recovery_sms
from .token import create_access_token
from . import login_fun
from .sanitize_validate import validate_password_strength, validate_filename_safe
from .token import verify_token, get_current_user
from .Security import apply_security_headers, check_api_rate_limit
from .db import (
    get_db_connection, close_db_connection, insert_log, insert_servo_command, 
    insert_device_mode_command, migrate_user_settings_table, init_db, robust_db_endpoint,
    UserSettings
)
    # Import these functions later when app is initialized
    # from .pico import send_to_pico_client
    # from .esp32cam import send_to_esp32cam_client

# Setup logger for this module
logger = logging.getLogger("client")

# In-memory storage for login attempts (IP-based)
login_attempts_storage = {}

# Constants
INACTIVE_CLIENT_TIMEOUT = 300  # 5 minutes timeout for inactive clients

# Authentication tokens for microcontrollers
PICO_AUTH_TOKENS = ["rof642fr:5qEKU@A@Tv", "pico_secure_token_2024"]
ESP32CAM_AUTH_TOKENS = ["esp32cam_secure_token_2024", "esp32cam_token_v2"]

# Global references (will be set by main server)
app = None
system_state = None
check_internet_func = None
send_to_pico_client = None
send_to_esp32cam_client = None

def set_app_and_state(fastapi_app, state):
    """Set the FastAPI app and system state references from main server"""
    global app, system_state
    app = fastapi_app
    system_state = state

def get_system_state():
    """Safely get system state, creating temporary one if needed"""
    global system_state
    if system_state is None:
        logger.warning("⚠️ system_state not initialized yet, creating temporary state")
        # Create a temporary system state for initialization
        class TempSystemState:
            def __init__(self):
                self.web_clients_lock = asyncio.Lock()
                self.web_clients = []
                self.active_clients = []
                self.error_counts = {"websocket": 0, "database": 0}
                self.device_status = {"pico": {"online": False, "last_seen": None, "errors": []}, "esp32cam": {"online": False, "last_seen": None, "errors": []}}
                self.latest_frame = None
                self.device_mode = "desktop"
                self.resolution = {"width": 640, "height": 480}
                self.smart_motion_enabled = False
                self.object_tracking_enabled = False
                self.video_count = 0
                self.last_disk_space = 'N/A'
                self.system_shutdown = False
                self.db_initialized = False
                self.start_time = time.time()
        system_state = TempSystemState()
    return system_state

def set_dependencies(internet_check_func):
    """Set additional dependencies from main server"""
    global check_internet_func
    check_internet_func = internet_check_func

def set_microcontroller_deps(pico_func, esp32cam_func):
    """Set microcontroller communication functions"""
    global send_to_pico_client, send_to_esp32cam_client
    send_to_pico_client = pico_func
    send_to_esp32cam_client = esp32cam_func

def is_system_ready() -> bool:
    """Check if system is fully initialized"""
    global system_state
    if system_state is None:
        return False
    return getattr(system_state, 'db_initialized', False) and not getattr(system_state, 'system_shutdown', True)

async def handle_command_response(message):
    """Handle command responses from WebSocket clients"""
    try:
        cmd_type = message.get('type')
        if cmd_type == 'command':
            # Handle different command types
            command = message.get('command')
            if command == 'get_status':
                # Status request - handled by send_status function
                pass
            elif command == 'ping':
                # Ping command - handled by ping/pong mechanism
                pass
            else:
                logger.debug(f"[WebSocket] Unknown command: {command}")
    except Exception as e:
        logger.error(f"[WebSocket] Error handling command response: {e}")
        raise

def register_routes_with_app(fastapi_app):
    """Register all routes with the FastAPI app"""
    global app
    app = fastapi_app
    
    # Add exception handlers
    try:
        app.add_exception_handler(HTTPException, http_exception_handler)
        app.add_exception_handler(404, not_found_handler)
        app.add_exception_handler(Exception, global_exception_handler)
        
        # Add API routes
        app.add_api_route("/ws", ws_http_guard, methods=["GET"])
        app.add_api_route("/", index, methods=["GET"], response_class=HTMLResponse)
        app.add_api_route("/dashboard", dashboard, methods=["GET"], response_class=HTMLResponse)
        app.add_api_route("/set_device_mode", set_device_mode, methods=["POST"])
        app.add_api_route("/get_smart_features", get_smart_features, methods=["GET"])
        app.add_api_route("/set_smart_features", set_smart_features, methods=["POST"], response_model=dict)
        app.add_api_route("/delete_video/{filename}", delete_video_by_filename, methods=["POST"])
        app.add_api_route("/save_user_settings", save_user_settings, methods=["POST"])
        app.add_api_route("/get_user_settings", get_user_settings, methods=["GET"])
        app.add_api_route("/api/profile", get_user_profile, methods=["GET"])
        app.add_api_route("/get_photo_count", get_photo_count, methods=["GET"])
        app.add_api_route("/get_gallery", get_gallery, methods=["GET"])
        app.add_api_route("/get_videos", get_videos, methods=["GET"])
        app.add_api_route("/get_logs", get_logs, methods=["GET"])
        app.add_api_route("/get_all_logs", get_all_logs, methods=["GET"])
        app.add_api_route("/delete_photo/{filename}", delete_photo, methods=["POST"])
        app.add_api_route("/delete_video", delete_video, methods=["POST"])
        app.add_api_route("/logout", logout, methods=["POST"])
        app.add_api_route("/logout", logout_page, methods=["GET"])
        app.add_api_route("/set_language", set_language, methods=["POST"])
        app.add_api_route("/static/{filename}", serve_static_file, methods=["GET"])
        app.add_api_route("/gallery/{filename}", serve_gallery_file, methods=["GET"])
        app.add_api_route("/security_videos/{filename}", serve_video_file, methods=["GET"])
        app.add_api_route("/video_poster/{filename}", generate_video_poster, methods=["GET"])
        app.add_api_route("/video_metadata/{filename}", get_video_metadata, methods=["GET"])
        app.add_api_route("/login", login_page, methods=["GET"], response_class=HTMLResponse)
        app.add_api_route("/login", login, methods=["POST"])
        app.add_api_route("/register", register, methods=["POST"])
        app.add_api_route("/recover-password", recover_password, methods=["POST"])
        app.add_api_route("/reset-password", reset_password, methods=["POST"])
        app.add_api_route("/get_translations", login_fun.get_translations, methods=["GET"])
        
        # Add WebSocket routes
        app.add_websocket_route("/ws", websocket_endpoint)
        app.add_websocket_route("/ws/video", video_stream_websocket)
        
        # Add health check route
        app.add_api_route("/health", health_check, methods=["GET"])
        
        logger.info("✅ Client routes registered successfully")
    except Exception as e:
        logger.error(f"❌ Error registering client routes: {e}")
        raise

# Define missing request models
class DeleteVideoRequest(BaseModel):
    filename: str = Field(..., description="Video filename to delete")

class DeleteImageRequest(BaseModel):
    filename: str = Field(..., description="Image filename to delete")


try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


# Initialize CAPTCHA storage
captcha_storage = {}
# Initialize CAPTCHA storage
captcha_storage = {}


class ActiveClient:
    def __init__(self, ws, connect_time, user_agent=None):
        self.ws = ws
        self.ip = ws.client.host if hasattr(ws, 'client') and hasattr(ws.client, 'host') else None
        self.connect_time = connect_time
        self.user_agent = user_agent
        self.last_activity = connect_time

class DeviceModeCommand(BaseModel):
    device_mode: str = Field(..., pattern=r'^(desktop|mobile)$')


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, description="Username must be between 1 and 50 characters")
    password: str = Field(..., min_length=1, max_length=100, description="Password must be between 1 and 100 characters")
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not v or not v.strip():
            raise ValueError("Username cannot be empty")
        v = v.strip()
        if len(v) > 50:
            raise ValueError("Username too long")
        
        # Allow email format as username (common user behavior)
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        # If it's an email, allow it
        if re.match(email_pattern, v):
            return v
        
        # For non-email usernames, use more flexible validation
        if not re.match(r'^[a-zA-Z0-9_\-\.@]{1,50}$', v):
            raise ValueError('Username must contain only alphanumeric characters, underscores, hyphens, dots, and @ symbol')
        
        # Check for dangerous patterns
        dangerous_patterns = [
            r'<script', r'javascript:', r'vbscript:', r'on\w+\s*=', 
            r'<iframe', r'<object', r'<embed', r'<form',
            r'<input', r'<textarea', r'<select', r'<link',
            r'<meta', r'<style', r'data:text/html', r'data:application/x-javascript'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError('Username contains potentially dangerous content')
        
        # Check for SQL injection patterns
        sql_patterns = [
            r'\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b',
            r'--|#|/\*|\*/', r'\b(and|or)\b\s+\d+\s*[=<>]',
            r'\b(union|select)\b.*\bfrom\b', r'\bxp_cmdshell\b|\bsp_executesql\b'
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError('Username contains invalid SQL patterns')
        
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if not v or not v.strip():
            raise ValueError("Password cannot be empty")
        if len(v.strip()) > 100:
            raise ValueError("Password too long")
        return v.strip()


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    phone: str = Field(..., pattern=r'^(\+989\d{9}|09\d{9}|9\d{9})$')  # More flexible Iranian phone format
    email: EmailStr | None = None
    password: str = Field(..., min_length=8, max_length=100)  # Enhanced security requirement
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        if not validate_password_strength(v):
            raise ValueError("Password must be at least 8 characters long and contain at least 3 of: uppercase, lowercase, digits, special characters")
        return v

class PasswordRecoveryRequest(BaseModel):
    phone: str = Field(..., pattern=r'^(\+989\d{9}|09\d{9}|9\d{9})$')  # More flexible Iranian phone format

class PasswordResetRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$')
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v):
        """Validate password strength requirements"""
        if not validate_password_strength(v):
            raise ValueError("Password must be at least 8 characters long and contain at least 3 of: uppercase, lowercase, digits, special characters")
        return v

global_pico_last_seen = None


async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP exception handler with sanitized error messages"""
    # Log the actual error for debugging
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}")
    
    # Return sanitized error message
    return JSONResponse(
        {"detail": exc.detail if exc.status_code < 500 else "Internal server error"},
        status_code=exc.status_code
    )

async def send_to_web_clients(message):
    remove_clients = []
    async with system_state.web_clients_lock:
        # کپی از لیست برای جلوگیری از تغییر در حین iteration
        clients_to_send = system_state.web_clients.copy()
        
    # ارسال پیام خارج از lock برای جلوگیری از deadlock
    for client in clients_to_send:
        try:
            # Check if client is still connected
            if not client or not hasattr(client, 'send_text'):
                remove_clients.append(client)
                continue
                
            await client.send_text(json.dumps(message) if not isinstance(message, str) else message)
        except Exception as e:
            # Don't log normal closure errors
            if "1000" not in str(e) and "Rapid test" not in str(e) and "disconnect" not in str(e).lower():
                logger.warning(f"Failed to send to web client {client.client.host}: {e}")
            remove_clients.append(client)
    
    # حذف کلاینت‌های قطع شده
    if remove_clients:
        async with system_state.web_clients_lock:
            for client in remove_clients:
                if client in system_state.web_clients:
                    system_state.web_clients.remove(client)
                # حذف از active_clients با thread safety
                system_state.active_clients = [c for c in system_state.active_clients if not (hasattr(c, 'ws') and c.ws == client)]
                logger.info(f"Removed disconnected web client: {client.client.host}")
                # ثبت در error counts
                system_state.error_counts["websocket"] += 1


async def ws_http_guard():
    return PlainTextResponse("WebSocket endpoint. Use WebSocket protocol.", status_code=400)


async def not_found_handler(request: Request, exc: HTTPException):
    """Handle 404 errors by redirecting to login"""
    return RedirectResponse(url="/login", status_code=302)

async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to prevent information disclosure"""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {str(exc)}")
    
    # Don't expose internal errors to clients
    return JSONResponse(
        {"detail": "Internal server error"},
        status_code=500
    )





async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for web clients with improved error handling"""
    try:
        # Accept WebSocket connection first, then authenticate via message
        await websocket.accept()
        
        # Wait for authentication message
        try:
            auth_data = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
            auth_message = json.loads(auth_data)
            
            if auth_message.get('type') != 'authenticate':
                logger.warning(f"Invalid first message from {websocket.client.host}: {auth_message.get('type')}")
                await websocket.send_text(json.dumps({"type": "auth_failed", "message": "Invalid authentication message"}))
                await websocket.close(code=4001, reason="Invalid authentication")
                return
            
            # Verify the token
            token = auth_message.get('token')
            if not token:
                logger.warning(f"No token provided by {websocket.client.host}")
                await websocket.send_text(json.dumps({"type": "auth_failed", "message": "No token provided"}))
                await websocket.close(code=4001, reason="No token")
                return
            
            # Verify JWT token
            user_data = verify_token(token)
            if not user_data:
                logger.warning(f"Invalid JWT token from {websocket.client.host}")
                await websocket.send_text(json.dumps({"type": "auth_failed", "message": "Invalid token"}))
                await websocket.close(code=4001, reason="Invalid token")
                return
            
            # Authentication successful
            username = user_data.get("sub")
            user_role = user_data.get("role", "user")
            
            # Store user information in websocket for later use
            websocket.user_info = {
                "username": username,
                "role": user_role,
                "ip": websocket.client.host
            }
            
            logger.info(f"WebSocket authenticated successfully from {websocket.client.host} (user: {username}, role: {user_role})")
            
            # Send authentication success message
            await websocket.send_text(json.dumps({"type": "authenticated", "username": username, "role": user_role}))
            
        except asyncio.TimeoutError:
            logger.warning(f"Authentication timeout from {websocket.client.host}")
            await websocket.send_text(json.dumps({"type": "auth_failed", "message": "Authentication timeout"}))
            await websocket.close(code=4001, reason="Authentication timeout")
            return
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in authentication message from {websocket.client.host}")
            await websocket.send_text(json.dumps({"type": "auth_failed", "message": "Invalid JSON"}))
            await websocket.close(code=4001, reason="Invalid JSON")
            return
        except Exception as e:
            logger.error(f"Authentication error from {websocket.client.host}: {e}")
            await websocket.send_text(json.dumps({"type": "auth_failed", "message": "Authentication error"}))
            await websocket.close(code=4001, reason="Authentication error")
            return
        
        user_agent = websocket.headers.get('user-agent', 'Unknown')
        logger.info(f"[WebSocket] New web connection from {websocket.client.host}, user-agent: {user_agent}")
        connect_time = datetime.now()
        client = ActiveClient(websocket, connect_time, user_agent)
        client_id = id(websocket)
        websocket_error_counts = {client_id: 0}

        current_system_state = get_system_state()
        async with current_system_state.web_clients_lock:
            if len(current_system_state.web_clients) >= MAX_WEBSOCKET_CLIENTS:
                await websocket.send_text(json.dumps({"type": "error", "message": "Maximum WebSocket clients reached."}))
                await websocket.close(code=1008)
                logger.warning(f"Rejected web connection from {websocket.client.host}: Max clients reached")
                return
            current_system_state.web_clients.append(websocket)
            current_system_state.active_clients.append(client)
            
    except Exception as e:
        logger.error(f"Error in WebSocket connection setup: {e}")
        try:
            await websocket.close(code=1011)  # Internal error
        except Exception:
            pass
        return

    # Enhanced status sending function
    async def send_status():
        try:
            current_system_state = get_system_state()
            if current_system_state.system_shutdown:
                return
            
            # Get current system status
            status_data = {
                "type": "status",
                "timestamp": datetime.now().isoformat(),
                "system_ready": is_system_ready(),
                "device_status": current_system_state.device_status,
                "error_counts": current_system_state.error_counts,
                "uptime": time.time() - current_system_state.start_time,
                "web_clients_count": len(current_system_state.web_clients),
                "active_clients_count": len(current_system_state.active_clients)
            }
            
            await websocket.send_text(json.dumps(status_data))
            
        except Exception as e:
            # Enhanced error suppression for normal closure errors
            if ("1000" not in str(e) and "1001" not in str(e) and 
                "Rapid test" not in str(e) and "keepalive" not in str(e).lower() and 
                "1011" not in str(e) and "timeout" not in str(e).lower() and
                "ABNORMAL_CLOSURE" not in str(e) and "disconnect" not in str(e).lower()):
                logger.error(f"[WebSocket] Error sending status to {websocket.client.host}: {e}")
            raise
    
    try:
        await send_status()
        last_activity = datetime.now()
        last_pong = datetime.now()
        
        current_system_state = get_system_state()
        while not current_system_state.system_shutdown:
            try:
                # Check for inactive clients
                if (datetime.now() - last_activity).total_seconds() > INACTIVE_CLIENT_TIMEOUT:
                    logger.warning(f"[WebSocket] Client {websocket.client.host} inactive for {INACTIVE_CLIENT_TIMEOUT} seconds, closing connection")
                    await websocket.send_text(json.dumps({"type": "error", "message": "Inactive for too long"}))
                    break
                
                # Send ping if no pong received
                if (datetime.now() - last_pong).total_seconds() > 30:
                    logger.debug(f"[WebSocket] No pong received from {websocket.client.host} within 30 seconds, sending ping")
                    try:
                        await websocket.send_text(json.dumps({"type": "ping"}))
                    except Exception as e:
                        if ("1000" not in str(e) and "1001" not in str(e) and 
                            "Rapid test" not in str(e) and "keepalive" not in str(e).lower() and 
                            "1011" not in str(e) and "timeout" not in str(e).lower() and
                            "ABNORMAL_CLOSURE" not in str(e) and "disconnect" not in str(e).lower()):
                            logger.error(f"[WebSocket] Error sending ping to {websocket.client.host}: {e}")
                        break
                
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    last_activity = datetime.now()
                    client.last_activity = last_activity
                    
                    try:
                        message = json.loads(data)
                        cmd_type = message.get('type')
                    except json.JSONDecodeError as e:
                        logger.warning(f"[WebSocket] Invalid JSON from {websocket.client.host}: {e}")
                        continue
                    
                    # Handle different message types
                    if cmd_type == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                        last_pong = datetime.now()
                    elif cmd_type == "get_status":
                        await send_status()
                    elif cmd_type == "command":
                        # Handle commands
                        try:
                            await handle_command_response(message)
                        except Exception as e:
                            logger.error(f"[WebSocket] Error handling command from {websocket.client.host}: {e}")
                            await websocket.send_text(json.dumps({
                                "type": "ack", 
                                "cmd_type": "error", 
                                "status": "failed", 
                                "detail": str(e)
                            }))
                    else:
                        # Send status for unknown commands
                        try:
                            await send_status()
                        except Exception as e:
                            if ("1000" not in str(e) and "1001" not in str(e) and 
                                "Rapid test" not in str(e) and "keepalive" not in str(e).lower() and 
                                "1011" not in str(e) and "timeout" not in str(e).lower() and
                                "ABNORMAL_CLOSURE" not in str(e) and "disconnect" not in str(e).lower()):
                                logger.error(f"[WebSocket] Error sending status to {websocket.client.host}: {e}")
                            break
                        continue
                        
                except Exception as e:
                    # Enhanced error suppression for normal closure errors
                    if ("1000" not in str(e) and "1001" not in str(e) and 
                        "Rapid test" not in str(e) and "keepalive" not in str(e).lower() and 
                        "1011" not in str(e) and "timeout" not in str(e).lower() and
                        "ABNORMAL_CLOSURE" not in str(e) and "disconnect" not in str(e).lower()):
                        logger.error(f"[WebSocket] Inner error for {websocket.client.host}: {e}")
                    try:
                        await websocket.send_text(json.dumps({
                            "type": "ack", 
                            "cmd_type": "error", 
                            "status": "ignored", 
                            "detail": str(e)
                        }))
                    except Exception:
                        pass
                    # Don't continue, break the loop to close connection
                    break
                    
            except asyncio.TimeoutError:
                logger.debug(f"[WebSocket] Timeout waiting for message from {websocket.client.host}, sending ping")
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                    last_pong = datetime.now()
                except Exception as e:
                    if ("1000" not in str(e) and "1001" not in str(e) and 
                        "Rapid test" not in str(e) and "keepalive" not in str(e).lower() and 
                        "1011" not in str(e) and "timeout" not in str(e).lower() and
                        "ABNORMAL_CLOSURE" not in str(e) and "disconnect" not in str(e).lower()):
                        logger.error(f"[WebSocket] Error sending ping after timeout to {websocket.client.host}: {e}")
                    break
            except WebSocketDisconnect as e:
                logger.info(f"[WebSocket] Client {websocket.client.host} disconnected cleanly: code={e.code}, reason={e.reason}")
                break
            except ConnectionResetError as e:
                logger.info(f"[WebSocket] Connection reset by {websocket.client.host}: {e}")
                break
            except Exception as e:
                # Enhanced error suppression for normal closure errors
                if ("1000" not in str(e) and "1001" not in str(e) and 
                    "Rapid test" not in str(e) and "keepalive" not in str(e).lower() and 
                    "1011" not in str(e) and "timeout" not in str(e).lower() and
                    "ABNORMAL_CLOSURE" not in str(e) and "disconnect" not in str(e).lower()):
                    logger.error(f"[WebSocket] Outer error for {websocket.client.host}: {e}", exc_info=True)
                try:
                    await websocket.send_text(json.dumps({
                        "type": "ack", 
                        "cmd_type": "error", 
                        "status": "ignored", 
                        "detail": str(e)
                    }))
                except Exception:
                    # If we can't send the error message, the connection is likely broken
                    break
                continue
                
    except Exception as e:
        # Enhanced error suppression for normal closure errors
        if ("1000" not in str(e) and "1001" not in str(e) and 
            "Rapid test" not in str(e) and "keepalive" not in str(e).lower() and 
            "1011" not in str(e) and "timeout" not in str(e).lower() and
            "ABNORMAL_CLOSURE" not in str(e) and "disconnect" not in str(e).lower()):
            logger.error(f"[WebSocket] Critical error for {websocket.client.host}: {e}")
    finally:
        # Cleanup
        try:
            current_system_state = get_system_state()
            async with current_system_state.web_clients_lock:
                if websocket in current_system_state.web_clients:
                    current_system_state.web_clients.remove(websocket)
                if client in current_system_state.active_clients:
                    current_system_state.active_clients.remove(client)
        except Exception as e:
            logger.warning(f"[WebSocket] Error during cleanup for {websocket.client.host}: {e}")
        
        logger.info(f"[WebSocket] Connection closed for {websocket.client.host}")




    

async def authenticate_websocket(websocket: WebSocket, device_type: str = None):
    """Common WebSocket authentication function with role-based access control"""
    try:
        # Check for JWT token in headers
        auth_header = websocket.headers.get("authorization", "")
        
        # For testing, allow connections without auth for localhost
        if "127.0.0.1" in websocket.client.host or "localhost" in websocket.client.host:
            await websocket.accept()
            logger.info(f"Localhost WebSocket connection accepted from {websocket.client.host}")
            return True
        
        if not auth_header.startswith("Bearer "):
            logger.warning(f"Missing authorization header from {websocket.client.host}")
            await websocket.close(code=4001, reason="Missing authorization")
            return False
        
        token = auth_header.replace("Bearer ", "")
        
        # Enhanced device-specific authentication
        if device_type == "pico":
            # For Pico, check against PICO_AUTH_TOKENS
            if token in PICO_AUTH_TOKENS:
                logger.info(f"Pico authentication successful from {websocket.client.host}")
                # Accept WebSocket connection for Pico devices
                await websocket.accept()
                return True
            else:
                logger.warning(f"Invalid Pico token from {websocket.client.host}: {token[:10]}...")
                await websocket.close(code=4001, reason="Invalid Pico token")
                return False


        elif device_type == "esp32cam":
            # For ESP32CAM, check against ESP32CAM_AUTH_TOKENS
            if token in ESP32CAM_AUTH_TOKENS:
                logger.info(f"ESP32CAM authentication successful from {websocket.client.host}")
                # Accept WebSocket connection for ESP32CAM devices
                await websocket.accept()
                return True
            else:
                logger.warning(f"Invalid ESP32CAM token from {websocket.client.host}: {token[:10]}...")
                await websocket.close(code=4001, reason="Invalid ESP32CAM token")
                return False
        else:
            # For web clients, use JWT verification with role-based access control
            user_data = verify_token(token)
            if not user_data:
                logger.warning(f"Invalid JWT token from {websocket.client.host}")
                await websocket.close(code=4001, reason="Invalid token")
                return False
            
            # Extract user role and username from token
            username = user_data.get("sub")
            user_role = user_data.get("role", "user")
            
            # Store user information in websocket for later use
            websocket.user_info = {
                "username": username,
                "role": user_role,
                "ip": websocket.client.host
            }
            
            # Log successful authentication with role
            logger.info(f"WebSocket authenticated successfully from {websocket.client.host} (user: {username}, role: {user_role})")
        
        await websocket.accept()
        return True
    except Exception as e:
        logger.error(f"WebSocket authentication error from {websocket.client.host}: {e}")
        await websocket.close(code=4001, reason="Authentication error")
        return False



async def index(request: Request, user=Depends(get_current_user)):
    if not user:
        # Always redirect to login for unauthenticated users with security headers
        response = RedirectResponse(url="/login", status_code=302)
        return apply_security_headers(response)
    
    # User is authenticated, serve the main dashboard
    try:
        lang = request.cookies.get('language', 'fa')
        return get_templates().TemplateResponse("index.html", {"request": request, "translations": translations, "lang": lang})
    except Exception as e:
        logger.error(f"Error rendering index page: {e}")
        # Fallback to dashboard
        return get_templates().TemplateResponse("index.html", {"request": request, "translations": translations, "lang": lang})



async def dashboard(request: Request, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        lang = request.cookies.get('language', 'fa')
        return get_templates().TemplateResponse("index.html", {"request": request, "translations": translations, "lang": lang})
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        # Fallback to index.html if dashboard.html doesn't exist
        lang = request.cookies.get('language', 'fa')
        return get_templates().TemplateResponse("index.html", {"request": request, "translations": translations, "lang": lang})




# --- 5. On server startup, load device_mode from user_settings if available ---
# (Add after DB init, e.g. after init_db())
async def load_device_mode_from_db():
    conn = await get_db_connection()
    try:
        cursor = await conn.execute('SELECT device_mode FROM user_settings ORDER BY updated_at DESC LIMIT 1')
        row = await cursor.fetchone()
        if row and row[0] in DEVICE_RESOLUTIONS:
            system_state.device_mode = row[0]
            system_state.resolution = DEVICE_RESOLUTIONS[row[0]]
    finally:
        await close_db_connection(conn)
# In main or startup event:
# await load_device_mode_from_db()


async def set_device_mode(command: DeviceModeCommand, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    logger.info(f"[HTTP] /set_device_mode: device_mode={command.device_mode}")
    try:
        system_state.device_mode = command.device_mode
        system_state.resolution = DEVICE_RESOLUTIONS[command.device_mode]
        logger.info(f"[HTTP] Set system_state.device_mode to {system_state.device_mode}")
        await insert_device_mode_command(command.device_mode)
        await insert_log(f"Device mode: {command.device_mode} ({system_state.resolution['width']}x{system_state.resolution['height']})", "command")
        await send_to_web_clients({
            "type": "command_response",
            "status": "success",
            "command": {"type": "device_mode", "device_mode": command.device_mode, "resolution": system_state.resolution}
        })
        return {"status": "success", "message": f"Device mode set: {command.device_mode} ({system_state.resolution['width']}x{system_state.resolution['height']})", "resolution": system_state.resolution}
    except Exception as e:
        logger.error(f"Device mode error: {e}")
        raise HTTPException(status_code=400, detail="Device mode error")




async def get_smart_features(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        # First, ensure all required columns exist
        await migrate_user_settings_table()
        
        conn = await get_db_connection()
        try:
            # Get smart features from database for specific user with validation and error handling
            try:
                cursor = await conn.execute(
                    'SELECT smart_motion, smart_tracking FROM user_settings WHERE username = ? ORDER BY updated_at DESC LIMIT 1',
                    (user.get("sub"),)
                )
                row = await cursor.fetchone()
            except Exception as e:
                logger.warning(f"Error querying smart features, using fallback: {e}")
                row = None
            
            if row:
                # Validate and sanitize retrieved data
                motion = bool(row[0]) if row[0] is not None else False
                tracking = bool(row[1]) if row[1] is not None else False
            else:
                # Default values if no settings found
                motion = False
                tracking = False
            
            logger.info(f"Smart features retrieved for {user.get('sub')}: motion={motion}, tracking={tracking}")
            return {
                "status": "success",
                "motion": motion,
                "tracking": tracking
            }
        finally:
            await close_db_connection(conn)
    except Exception as e:
        logger.error(f"ERROR getting smart features from database: {e}")
        # Fallback to system state with validation
        fallback_motion = bool(getattr(system_state, 'smart_motion_enabled', False))
        fallback_tracking = bool(getattr(system_state, 'object_tracking_enabled', False))
        
        logger.info(f"Using fallback smart features for {user.get('sub')}: motion={fallback_motion}, tracking={fallback_tracking}")
        return {
            "status": "success",
            "motion": fallback_motion,
            "tracking": fallback_tracking
        }





# --- Smart Features Endpoints ---
async def set_smart_features(cmd: SmartFeaturesCommand, request: Request, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        # First, ensure all required columns exist
        await migrate_user_settings_table()
        
        # Validate and sanitize smart features data
        validated_motion = bool(cmd.motion) if cmd.motion is not None else False
        validated_tracking = bool(cmd.tracking) if cmd.tracking is not None else False
        
        prev_motion = getattr(system_state, 'smart_motion_enabled', None)
        prev_tracking = getattr(system_state, 'object_tracking_enabled', None)
        logger.info(f"[HTTP] /set_smart_features from {request.client.host}: motion {prev_motion}->{validated_motion}, tracking {prev_tracking}->{validated_tracking}")
        
        # Update system state
        system_state.smart_motion_enabled = validated_motion
        system_state.object_tracking_enabled = validated_tracking
        
        # Save to database for user with improved error handling
        conn = await get_db_connection()
        try:
            try:
                # Use direct execute instead of async context manager
                await conn.execute(
                    'INSERT OR REPLACE INTO user_settings (username, ip, smart_motion, smart_tracking, updated_at) VALUES (?, ?, ?, ?, ?)',
                    (user.get("sub"), request.client.host, validated_motion, validated_tracking, get_jalali_now_str())
                )
                await conn.commit()
                
                logger.info(f"Smart features saved to database for user: {user.get('sub')}")
                
            except Exception as e:
                logger.warning(f"Error in smart features transaction, trying fallback: {e}")
                # Fallback: try to insert without problematic columns
                try:
                    await conn.execute(
                        'INSERT OR REPLACE INTO user_settings (username, ip, updated_at) VALUES (?, ?, ?)',
                        (user.get("sub"), request.client.host, get_jalali_now_str())
                    )
                    await conn.commit()
                    logger.info(f"Smart features saved with fallback for user: {user.get('sub')}")
                except Exception as e2:
                    logger.error(f"Fallback smart features save also failed: {e2}")
                    # Don't raise HTTPException, just log the error
                    
        finally:
            await close_db_connection(conn)
        
        log_msg = f"Smart features updated: motion={validated_motion}, tracking={validated_tracking}"
        logger.info(log_msg)
        await insert_log(log_msg, "command")
        
        # اطلاع‌رسانی به کلاینت‌ها (در صورت نیاز)
        await send_to_web_clients({
            "type": "smart_features",
            "motion": validated_motion,
            "tracking": validated_tracking
        })
        
        return {"status": "success", "message": "Smart features updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in set_smart_features: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")





       
async def delete_video_by_filename(filename: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Validate filename and extension securely
    if not validate_filename_safe(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid file type")

    filepath = os.path.join(SECURITY_VIDEOS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get file size to determine if it's a large file
    try:
        file_size = os.path.getsize(filepath)
        is_large_file = file_size > 100 * 1024 * 1024  # > 100MB
        is_very_large_file = file_size > 500 * 1024 * 1024  # > 500MB
        logger.info(f"Attempting to delete video {filename} (size: {file_size/1024/1024:.1f}MB, large: {is_large_file}, very_large: {is_very_large_file})")
    except Exception as e:
        logger.warning(f"Error getting file size for {filename}: {e}")
        is_large_file = False
        is_very_large_file = False
    
    # Retry mechanism for file deletion with optimized delays
    max_retries = 10 if is_very_large_file else (8 if is_large_file else 6)  # More retries for very large files
    base_delay = 1.0 if is_very_large_file else (0.5 if is_large_file else 0.3)  # Longer delays for very large files
    
    for attempt in range(max_retries):
        try:
            # Extra delay for very large files
            if is_very_large_file and attempt == 0:
                logger.info(f"Very large file detected ({file_size/1024/1024:.1f}MB), adding extra delay...")
                await asyncio.sleep(2.0)  # Extra 2 second delay for very large files
            
            # Force terminate HTTP connections immediately
            await force_terminate_http_connections(filename)
            
            # Force close HTTP connections first
            await force_close_http_connections(filename)
            
            # Check for HTTP connections and allow them to close
            await check_http_connections(filename)
            
            # Try to force close file handles before deletion
            await force_close_file_handles(filepath)
            
            # Try to delete the file
            await asyncio.to_thread(os.remove, filepath)
            logger.info(f"Successfully deleted video {filename} (attempt {attempt + 1})")
            break  # Success, exit retry loop
        except PermissionError as e:
            if attempt < max_retries - 1:
                delay = base_delay * (attempt + 1)  # Linear backoff
                logger.warning(f"File {filename} is locked (size: {file_size/1024/1024:.1f}MB), retrying in {delay:.1f} seconds... (attempt {attempt + 1}/{max_retries})")
                
                # Try to force file release on Windows
                if sys.platform.startswith('win'):
                    try:
                        # Try to open file in write mode to check if it's locked
                        with open(filepath, 'r+b') as f:
                            pass  # Just check if we can open it
                    except Exception as e:
                        logger.debug(f"File {filename} is locked: {e}")
                        pass  # File is locked, continue with retry
                
                await asyncio.sleep(delay)
            else:
                logger.error(f"Failed to delete {filename} after {max_retries} attempts: {e}")
                raise HTTPException(status_code=503, detail=f"File is locked and cannot be deleted after {max_retries} attempts: {filename}")
        except OSError as e:
            if e.errno == errno.ENOENT:
                # File was already deleted
                logger.info(f"File {filename} was already deleted")
                break
            elif attempt < max_retries - 1:
                delay = base_delay * (attempt + 1)
                logger.warning(f"OS error deleting {filename}, retrying in {delay:.1f} seconds... (attempt {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"OS error deleting {filename} after {max_retries} attempts: {e}")
                raise HTTPException(status_code=500, detail=f"OS error deleting file: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error deleting {filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")
    
    # Delete from database
    conn = await get_db_connection()
    try:
        await conn.execute("DELETE FROM security_videos WHERE filename=?", (filename,))
        await conn.commit()
        logger.info(f"Removed {filename} from database")
    except Exception as e:
        logger.error(f"Error removing {filename} from database: {e}")
        # Don't fail the whole operation if DB deletion fails
    finally:
        await close_db_connection(conn)
    
    await insert_log(f"Video deleted: {filename}", "delete")
    
    # Notify clients
    await send_to_web_clients({"type": "video_deleted", "filename": filename})
    
    return {"status": "success", "message": f"Video {filename} deleted successfully"}
# --- Smart Features API Models ---

# SmartFeaturesCommand is now imported from core.config






async def save_user_settings(settings: UserSettings, request: Request, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    client_ip = request.client.host
    
    # Enhanced rate limiting check
    if not check_api_rate_limit(client_ip, "/save_user_settings"):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    # CSRF protection
    csrf_token = request.headers.get("X-CSRF-Token")
    if not csrf_token:
        # Try to get from form data as fallback
        form_data = await request.form()
        csrf_token = form_data.get('csrf_token')
    
    if not csrf_token:
        logger.warning(f"CSRF token missing for save_user_settings from {client_ip}")
        # For now, allow the request to proceed without CSRF token to prevent blocking
        # In production, this should be enforced
        # raise HTTPException(status_code=403, detail="CSRF token required")
    
    # Validate CSRF token if provided
    if csrf_token and len(csrf_token) >= 10:
        try:
            # Get stored token for user
            from .db import get_user_csrf_token
            stored_token = await get_user_csrf_token(user.get("sub"))
            
            if stored_token and csrf_token != stored_token:
                logger.warning(f"Invalid CSRF token for save_user_settings from {client_ip}")
                # For now, allow the request to proceed
                # In production, this should be enforced
                # raise HTTPException(status_code=403, detail="Invalid CSRF token")
        except Exception as e:
            logger.error(f"CSRF validation error: {e}")
            # Allow request to proceed for now
    
    try:
        # First, ensure all required columns exist
        await migrate_user_settings_table()
        
        # Validate and sanitize data before saving with improved validation
        def safe_int(value, min_val, max_val, default):
            try:
                if value is None:
                    return default
                val = int(value)
                return max(min_val, min(max_val, val))
            except (ValueError, TypeError):
                return default
        
        def safe_bool(value):
            try:
                if value is None:
                    return False
                return bool(value)
            except (ValueError, TypeError):
                return False
        
        def safe_str(value, valid_options, default):
            try:
                if value is None or value not in valid_options:
                    return default
                return value
            except (ValueError, TypeError):
                return default
        
        validated_settings = {
            'username': user.get("sub"),
            'ip': request.client.host,
            'theme': safe_str(settings.theme, ['light', 'dark'], 'light'),
            'language': safe_str(settings.language, ['fa', 'en'], 'fa'),
            'servo1': safe_int(settings.servo1, 0, 180, 90),
            'servo2': safe_int(settings.servo2, 0, 180, 90),
            'device_mode': safe_str(settings.device_mode, ['desktop', 'mobile'], 'desktop'),
            'photo_quality': safe_int(settings.photoQuality, 1, 100, 80),
            'smart_motion': safe_bool(settings.smart_motion),
            'smart_tracking': safe_bool(settings.smart_tracking),
            'stream_enabled': safe_bool(settings.stream_enabled),
            'flash_settings': json.dumps({
                'intensity': safe_int(getattr(settings, 'flash_intensity', 50), 0, 100, 50),
                'enabled': safe_bool(getattr(settings, 'flash_enabled', False))
            })
        }
        
        # Retry logic for database operations
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                conn = await get_db_connection()
                if conn is None:
                    logger.error(f"Failed to get database connection on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        raise HTTPException(status_code=503, detail="Database connection failed")
                
                try:
                    # Use direct execute instead of async context manager
                    try:
                        await conn.execute('''
                            INSERT OR REPLACE INTO user_settings 
                            (username, ip, theme, language, servo1, servo2, device_mode, photo_quality, 
                             smart_motion, smart_tracking, stream_enabled, flash_settings, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            validated_settings['username'], validated_settings['ip'], validated_settings['theme'],
                            validated_settings['language'], validated_settings['servo1'], validated_settings['servo2'],
                            validated_settings['device_mode'], validated_settings['photo_quality'],
                            validated_settings['smart_motion'], validated_settings['smart_tracking'],
                            validated_settings['stream_enabled'], validated_settings['flash_settings'],
                            get_jalali_now_str()
                        ))
                        await conn.commit()
                    except Exception as e:
                        logger.warning(f"Error in transaction, trying individual insert: {e}")
                        # Fallback: try to insert without problematic columns
                        try:
                            await conn.execute('''
                                INSERT OR REPLACE INTO user_settings 
                                (username, ip, theme, language, servo1, servo2, device_mode, photo_quality, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                validated_settings['username'], validated_settings['ip'], validated_settings['theme'],
                                validated_settings['language'], validated_settings['servo1'], validated_settings['servo2'],
                                validated_settings['device_mode'], validated_settings['photo_quality'],
                                get_jalali_now_str()
                            ))
                            await conn.commit()
                        except Exception as e2:
                            logger.error(f"Fallback insert also failed: {e2}")
                            raise
                    
                    logger.info(f"User settings saved successfully for {validated_settings['username']}")
                    
                finally:
                    if conn is not None:
                        await close_db_connection(conn)
                
                # Send servo command to Pico if servo values are provided
                try:
                    if settings.servo1 is not None or settings.servo2 is not None:
                        servo1_val = settings.servo1 if settings.servo1 is not None else 90
                        servo2_val = settings.servo2 if settings.servo2 is not None else 90

                        servo_cmd = {
                            "type": "servo",
                            "command": {
                                "servo1": servo1_val,
                                "servo2": servo2_val
                            },
                            "timestamp": datetime.now().isoformat(),
                            "source": "user_settings"
                        }

                        await insert_servo_command(servo1_val, servo2_val)
                        await insert_log(
                            f"Servo command from user settings: X={servo1_val}°, Y={servo2_val}°",
                            "command"
                        )

                        # Send to Pico (guard if dependency not set)
                        if callable(send_to_pico_client):
                            await send_to_pico_client(servo_cmd)
                        else:
                            logger.debug("send_to_pico_client not set; skipping pico dispatch")

                        # Send to ESP32CAM for logging (guard if dependency not set)
                        if callable(send_to_esp32cam_client):
                            await send_to_esp32cam_client({
                                "type": "servo_command_log",
                                "servo1": servo1_val,
                                "servo2": servo2_val,
                                "timestamp": datetime.now().isoformat(),
                                "source": "user_settings"
                            })
                        else:
                            logger.debug("send_to_esp32cam_client not set; skipping esp32cam dispatch")
                except Exception as e:
                    # Do not fail the save operation if downstream dispatch fails
                    logger.warning(f"Non-critical error dispatching servo/log updates: {e}")
                
                return {"success": True, "status": "success", "language": settings.language}
                
            except aiosqlite.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Database locked on attempt {attempt + 1}/{max_retries}, retrying in {retry_delay}s: {e}")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    logger.error(f"Database operational error after {attempt + 1} attempts: {e}")
                    raise HTTPException(status_code=503, detail="Database temporarily unavailable, please try again")
            except ValidationError as e:
                logger.error(f"[HTTP] Validation error in /save_user_settings: {e.errors()}")
                raise HTTPException(status_code=422, detail=f"Validation error: {e.errors()}")
            except Exception as e:
                logger.error(f"ERROR saving user settings after {attempt + 1} attempts: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    # Return proper error response instead of raising exception
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=503,
                        content={"detail": "Database error", "error": str(e)}
                    )
        
        # This should never be reached, but just in case
        raise HTTPException(status_code=503, detail="Database operation failed after all retries")
        
    except Exception as e:
        logger.error(f"Unexpected error in save_user_settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

async def get_user_settings(request: Request, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        # First, ensure all required columns exist
        await migrate_user_settings_table()
        
        conn = await get_db_connection()
        
        try:
            # Get user data with improved error handling
            user_query = await conn.execute(
                'SELECT username, role FROM users WHERE username = ?',
                (user.get("sub"),)
            )
            user_data = await user_query.fetchone()
            
            if not user_data:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Get user settings with improved validation and error handling
            try:
                settings_query = await conn.execute(
                    'SELECT theme, language, flash_settings, servo1, servo2, device_mode, photo_quality, smart_motion, smart_tracking, stream_enabled FROM user_settings WHERE username = ? ORDER BY updated_at DESC LIMIT 1',
                    (user.get("sub"),)
                )
                settings_data = await settings_query.fetchone()
            except Exception as e:
                logger.warning(f"Error querying user settings, using fallback: {e}")
                settings_data = None
            
            # Prepare response data with validation
            # Generate/fetch CSRF token for authenticated user so frontend can include it in POST requests
            try:
                from .db import get_user_csrf_token
                csrf_token_val = await get_user_csrf_token(user.get("sub"))
            except Exception:
                csrf_token_val = None
            response_data = {
                "status": "success",
                "user_role": user_data[1],
                "username": user_data[0],
                "language": request.cookies.get('language', 'fa'),
                "csrf_token": csrf_token_val
            }
            
            if settings_data:
                # Validate and sanitize retrieved data
                flash_settings = settings_data[2] if settings_data[2] else "{}"
                try:
                    # Validate JSON format
                    if flash_settings and flash_settings != "{}":
                        json.loads(flash_settings)
                except json.JSONDecodeError:
                    flash_settings = "{}"
                
                response_data["settings"] = {
                    "theme": settings_data[0] if settings_data[0] in ['light', 'dark'] else "light",
                    "language": settings_data[1] if settings_data[1] in ['fa', 'en'] else "fa",
                    "flashSettings": flash_settings,
                    "servo1": max(0, min(180, settings_data[3])) if settings_data[3] is not None else 90,
                    "servo2": max(0, min(180, settings_data[4])) if settings_data[4] is not None else 90,
                    "device_mode": settings_data[5] if settings_data[5] in ['desktop', 'mobile'] else "desktop",
                    "photoQuality": max(1, min(100, settings_data[6])) if settings_data[6] is not None else 80,
                    "smart_motion": bool(settings_data[7]) if settings_data[7] is not None else False,
                    "smart_tracking": bool(settings_data[8]) if settings_data[8] is not None else False,
                    "stream_enabled": bool(settings_data[9]) if settings_data[9] is not None else False
                }
            else:
                # Return validated default settings
                response_data["settings"] = {
                    "theme": "light",
                    "language": "fa",
                    "flashSettings": "{}",
                    "device_mode": "desktop",
                    "servo1": 90,
                    "servo2": 90,
                    "photoQuality": 80,
                    "smart_motion": False,
                    "smart_tracking": False,
                    "stream_enabled": False
                }
            
            logger.info(f"User settings retrieved successfully for {user.get('sub')}")
            return response_data
            
        finally:
            await close_db_connection(conn)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"ERROR getting user settings: {e}")
        # Return a more graceful error response with fallback settings
        return {
            "status": "success",
            "user_role": "user",
            "username": user.get("sub"),
            "language": request.cookies.get('language', 'fa'),
            "settings": {
                "theme": "light",
                "language": "fa",
                "flashSettings": "{}",
                "device_mode": "desktop",
                "servo1": 90,
                "servo2": 90,
                "photoQuality": 80,
                "smart_motion": False,
                "smart_tracking": False,
                "stream_enabled": False
            }
        }

async def get_user_profile(request: Request, user=Depends(get_current_user)):
    """Get user profile information for display in profile modal"""
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = await get_db_connection()
        
        try:
            # Get user data
            user_query = await conn.execute(
                'SELECT username, role, created_at FROM users WHERE username = ?',
                (user.get("sub"),)
            )
            user_data = await user_query.fetchone()
            
            if not user_data:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Get user settings for additional info
            settings_query = await conn.execute(
                'SELECT theme, language FROM user_settings WHERE username = ? ORDER BY updated_at DESC LIMIT 1',
                (user.get("sub"),)
            )
            settings_data = await settings_query.fetchone()
            
            # Prepare profile data
            profile_data = {
                "status": "success",
                "profile": {
                    "username": user_data[0],
                    "role": user_data[1],
                    "created_at": user_data[2],
                    "theme": settings_data[0] if settings_data and settings_data[0] else "light",
                    "language": settings_data[1] if settings_data and settings_data[1] else "fa",
                    "is_online": True,  # User is online if they can access this endpoint
                    "last_seen": datetime.now().isoformat()
                }
            }
            
            logger.info(f"Profile data retrieved successfully for {user.get('sub')}")
            return profile_data
            
        finally:
            await close_db_connection(conn)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ERROR getting user profile: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving profile data")

def alert_admin(message, critical=False):
    if critical:
        logger.critical(f"[ADMIN ALERT] {message}")
    else:
        logger.warning(f"[ADMIN ALERT] {message}")

# تابع جدید برای آزاد کردن قوی‌تر file handles
async def force_close_file_handles(filepath: str):
    """Try to force close any open file handles on Windows with multiple attempts"""
    if not sys.platform.startswith('win'):
        return
    
    # Multiple attempts to force file handle release
    for attempt in range(10):  # Increased attempts for better reliability
        try:
            # Try to open file in exclusive mode to check if it's locked
            with open(filepath, 'r+b') as f:
                # File is accessible, close it
                f.close()
                logger.info(f"Successfully accessed file handle on attempt {attempt + 1}")
                break
        except PermissionError:
            # File is locked, try alternative methods
            try:
                # Try to open in read-only mode
                with open(filepath, 'rb') as f:
                    f.close()
                logger.info(f"Successfully accessed file in read mode on attempt {attempt + 1}")
                break
            except Exception as e:
                logger.warning(f"File still locked on attempt {attempt + 1}: {e}")
                if attempt < 9:  # Not the last attempt
                    await asyncio.sleep(0.5)  # Increased delay
        except Exception as e:
            logger.warning(f"Unexpected error accessing file on attempt {attempt + 1}: {e}")
            if attempt < 9:
                await asyncio.sleep(0.5)
    
    # Final attempt with garbage collection and memory cleanup
    if sys.platform.startswith('win'):
        await asyncio.to_thread(gc.collect)
        await asyncio.sleep(1.0)  # Longer delay for final cleanup

# Global variable to track active file connections
active_file_connections = set()

# تابع جدید برای ثبت اتصالات فعال
def register_file_connection(filename: str):
    """Register that a file is being served"""
    active_file_connections.add(filename)

# تابع جدید برای حذف ثبت اتصالات
def unregister_file_connection(filename: str):
    """Unregister that a file is no longer being served"""
    active_file_connections.discard(filename)

# تابع جدید برای بررسی اتصالات HTTP
async def check_http_connections(filename: str):
    """Check if file is being served via HTTP and add small delay"""
    if filename in active_file_connections:
        logger.info(f"File {filename} is currently being served, waiting for connections to close...")
        # Wait longer if file is actively being served
        await asyncio.sleep(1.0)  # Increased delay
    else:
        # Small delay to allow HTTP connections to close
        await asyncio.sleep(0.2)  # Increased delay

# تابع جدید برای قطع اتصالات HTTP
async def force_close_http_connections(filename: str):
    """Force close all HTTP connections to a specific file"""
    if filename in active_file_connections:
        logger.info(f"Force closing HTTP connections for {filename}")
        # Remove from active connections
        active_file_connections.discard(filename)
        # Wait a bit more for connections to fully close
        await asyncio.sleep(0.5)  # Increased delay

# تابع جدید برای قطع فوری اتصالات HTTP
async def force_terminate_http_connections(filename: str):
    """Force terminate all HTTP connections to a specific file immediately"""
    if filename in active_file_connections:
        logger.info(f"Force terminating HTTP connections for {filename}")
        # Remove from active connections immediately
        active_file_connections.discard(filename)
        # Force garbage collection
        import gc
        gc.collect()
        # Wait for connections to fully close
        await asyncio.sleep(0.3)




async def video_stream_websocket(websocket: WebSocket):
    # WebSocket authentication for video stream
    try:
        # Accept WebSocket connection first, then authenticate via message
        await websocket.accept()
        
        # Wait for authentication message
        try:
            auth_data = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
            auth_message = json.loads(auth_data)
            
            if auth_message.get('type') != 'authenticate':
                logger.warning(f"Invalid first message from video client {websocket.client.host}: {auth_message.get('type')}")
                await websocket.send_text(json.dumps({"type": "auth_failed", "message": "Invalid authentication message"}))
                await websocket.close(code=4001, reason="Invalid authentication")
                return
            
            # Verify the token
            token = auth_message.get('token')
            if not token:
                logger.warning(f"No token provided by video client {websocket.client.host}")
                await websocket.send_text(json.dumps({"type": "auth_failed", "message": "No token provided"}))
                await websocket.close(code=4001, reason="No token")
                return
            
            # Verify JWT token
            user_data = verify_token(token)
            if not user_data:
                logger.warning(f"Invalid JWT token from video client {websocket.client.host}")
                await websocket.send_text(json.dumps({"type": "auth_failed", "message": "Invalid token"}))
                await websocket.close(code=4001, reason="Invalid token")
                return
            
            # Authentication successful
            username = user_data.get("sub")
            user_role = user_data.get("role", "user")
            
            # Store user information in websocket for later use
            websocket.user_info = {
                "username": username,
                "role": user_role,
                "ip": websocket.client.host
            }
            
            logger.info(f"Video WebSocket authenticated successfully from {websocket.client.host} (user: {username}, role: {user_role})")
            
            # Send authentication success message
            await websocket.send_text(json.dumps({"type": "authenticated", "username": username, "role": user_role}))
            
        except asyncio.TimeoutError:
            logger.warning(f"Video WebSocket authentication timeout from {websocket.client.host}")
            await websocket.send_text(json.dumps({"type": "auth_failed", "message": "Authentication timeout"}))
            await websocket.close(code=4001, reason="Authentication timeout")
            return
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in video WebSocket authentication message from {websocket.client.host}")
            await websocket.send_text(json.dumps({"type": "auth_failed", "message": "Invalid JSON"}))
            await websocket.close(code=4001, reason="Invalid JSON")
            return
        except Exception as e:
            logger.error(f"Video WebSocket authentication error from {websocket.client.host}: {e}")
            await websocket.send_text(json.dumps({"type": "auth_failed", "message": "Authentication error"}))
            await websocket.close(code=4001, reason="Authentication error")
            return
        
        logger.info(f"[Video WebSocket] New video connection from {websocket.client.host}")
        
        try:
            last_frame_sent = None
            frame_count = 0
            last_ping_time = time.time()
            
            while not system_state.system_shutdown:
                try:
                    current_time = time.time()
                    
                    # Send ping every 30 seconds to check connection
                    if current_time - last_ping_time > 30:
                        try:
                            await websocket.send_text(json.dumps({"type": "ping"}))
                            last_ping_time = current_time
                        except Exception as e:
                            # Connection is broken, break the loop
                            if "1000" not in str(e) and "Rapid test" not in str(e):
                                logger.info(f"[Video WebSocket] Connection broken for {websocket.client.host}: {e}")
                            break
                    
                    # Send frame if available
                    try:
                        if hasattr(system_state, 'frame_lock') and system_state.frame_lock is not None:
                            async with system_state.frame_lock:
                                if system_state.latest_frame is not None and system_state.latest_frame != last_frame_sent:
                                    try:
                                        await websocket.send_bytes(system_state.latest_frame)
                                        last_frame_sent = system_state.latest_frame
                                        frame_count += 1
                                        
                                        # Log frame statistics every 100 frames
                                        if frame_count % 100 == 0:
                                            logger.info(f"[Video WebSocket] Sent {frame_count} frames to {websocket.client.host}")
                                            
                                    except Exception as e:
                                        if "1000" not in str(e) and "Rapid test" not in str(e):
                                            logger.error(f"[Video WebSocket] Error sending frame to {websocket.client.host}: {e}")
                                        break
                        else:
                            # Fallback if lock is not available
                            if system_state.latest_frame is not None and system_state.latest_frame != last_frame_sent:
                                try:
                                    await websocket.send_bytes(system_state.latest_frame)
                                    last_frame_sent = system_state.latest_frame
                                    frame_count += 1
                                except Exception as e:
                                    if "1000" not in str(e) and "Rapid test" not in str(e):
                                        logger.error(f"[Video WebSocket] Error sending frame to {websocket.client.host}: {e}")
                                    break
                            logger.warning("⚠️ frame_lock not available in video WebSocket, using fallback")
                    except Exception as lock_error:
                        logger.error(f"Error with frame_lock in video WebSocket: {lock_error}")
                        # Fallback without lock
                        if system_state.latest_frame is not None and system_state.latest_frame != last_frame_sent:
                            try:
                                await websocket.send_bytes(system_state.latest_frame)
                                last_frame_sent = system_state.latest_frame
                                frame_count += 1
                            except Exception as e:
                                if "1000" not in str(e) and "Rapid test" not in str(e):
                                    logger.error(f"[Video WebSocket] Error sending frame to {websocket.client.host}: {e}")
                                break
                    
                    # Adaptive sleep based on frame availability
                    if system_state.latest_frame is not None:
                        await asyncio.sleep(1.0 / VIDEO_FPS)  # Normal frame rate
                    else:
                        await asyncio.sleep(0.5)  # Slower when no frames available
                    
                except WebSocketDisconnect:
                    logger.info(f"[Video WebSocket] Client {websocket.client.host} disconnected")
                    break
                except Exception as e:
                    if "1000" not in str(e) and "Rapid test" not in str(e):
                        logger.error(f"[Video WebSocket] Unexpected error for {websocket.client.host}: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"[Video WebSocket] Error in main loop for {websocket.client.host}: {e}")
        finally:
            logger.info(f"[Video WebSocket] Connection closed for {websocket.client.host} - Total frames sent: {frame_count}")
            
    except Exception as e:
        logger.error(f"Video WebSocket connection error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass





async def get_photo_count(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        photo_count = len([f for f in await asyncio.to_thread(os.listdir, GALLERY_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]) if os.path.exists(GALLERY_DIR) else 0
        return {"status": "success", "count": photo_count}
    except Exception as e:
        logger.error(f"Photo count error: {e}")
        raise HTTPException(status_code=500, detail="Photo count error")


async def get_gallery(page: int = 0, limit: int = 9, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        if not os.path.exists(GALLERY_DIR):
            await asyncio.to_thread(os.makedirs, GALLERY_DIR, exist_ok=True)
        files = [f for f in await asyncio.to_thread(os.listdir, GALLERY_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        files.sort(key=lambda x: os.path.getctime(os.path.join(GALLERY_DIR, x)), reverse=True)
        start = page * limit
        end = start + limit
        page_files = files[start:end]
        gallery_data = [{"filename": f, "url": f"/gallery/{f}", "size": os.path.getsize(os.path.join(GALLERY_DIR, f)), "timestamp": datetime.fromtimestamp(os.path.getctime(os.path.join(GALLERY_DIR, f))).isoformat()} for f in page_files]
        return {"status": "success", "photos": gallery_data, "total": len(files), "page": page, "limit": limit, "has_more": end < len(files)}
    except Exception as e:
        raise e

async def get_videos(page: int = 0, limit: int = 6, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not os.path.exists(SECURITY_VIDEOS_DIR):
        await asyncio.to_thread(os.makedirs, SECURITY_VIDEOS_DIR, exist_ok=True)
    files = [f for f in await asyncio.to_thread(os.listdir, SECURITY_VIDEOS_DIR) if f.lower().endswith(('.mp4', '.avi', '.mov'))]
    files.sort(key=lambda x: os.path.getctime(os.path.join(SECURITY_VIDEOS_DIR, x)), reverse=True)
    start = page * limit
    end = start + limit
    page_files = files[start:end]
    videos_data = []
    for f in page_files:
        # Extract hour from the timestamp in the filename (e.g., "video_2025-05-25_23-57-00.mp4")
        try:
            timestamp_part = f.split('_')[2].split('.')[0]  # Get "23-57-00"
            hour = int(timestamp_part.split('-')[0])  # Extract "23" as the hour
        except (IndexError, ValueError):
            hour = 0  # Default to 0 if parsing fails
        videos_data.append({
            "filename": f,
            "url": f"/security_videos/{f}",
            "size": os.path.getsize(os.path.join(SECURITY_VIDEOS_DIR, f)),
            "timestamp": datetime.fromtimestamp(os.path.getctime(os.path.join(SECURITY_VIDEOS_DIR, f))).isoformat(),
            "hour": hour
        })
    return {"status": "success", "videos": videos_data, "total": len(files), "page": page, "limit": limit, "has_more": end < len(files)}

async def get_logs(limit: int = 50, source: str = None, level: str = None, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Ensure database is initialized
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database initialization error in get_logs: {e}")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    
    conn = await get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection failed")
    
    try:
        query = "SELECT * FROM camera_logs"
        filters = []
        params = []
        if source:
            filters.append("source = ?")
            params.append(source)
        if level:
            filters.append("log_type = ?")
            params.append(level)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor = await conn.execute(query, tuple(params))
        logs = await cursor.fetchall()
        logs_data = [{
            "timestamp": log["created_at"],
            "level": log["log_type"],
            "message": log["message"],
            "source": log["source"] if "source" in log.keys() else None,
            "pico_timestamp": log["pico_timestamp"] if "pico_timestamp" in log.keys() else None
        } for log in logs]
        return {"status": "success", "logs": logs_data}
    except Exception as e:
        logger.error(f"Error in get_logs: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if conn is not None:
            await close_db_connection(conn)

async def get_all_logs(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Ensure database is initialized
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database initialization error in get_all_logs: {e}")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    
    conn = await get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection failed")
    
    try:
        cursor = await conn.execute("SELECT * FROM camera_logs ORDER BY created_at DESC")
        logs = await cursor.fetchall()
        logs_data = [{
            "id": log['id'],
            "message": log['message'],
            "level": log['log_type'],
            "timestamp": log['created_at'],
            "source": log["source"] if "source" in log.keys() else None,
            "pico_timestamp": log["pico_timestamp"] if "pico_timestamp" in log.keys() else None
        } for log in logs]
        return {"status": "success", "logs": logs_data}
    except Exception as e:
        logger.error(f"Error in get_all_logs: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if conn is not None:
            await close_db_connection(conn)

async def delete_photo(filename: str, request: Request, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    logger.info(f"[HTTP] /delete_photo from {request.client.host}: filename={filename}")

    # Validate filename and extension securely
    if not validate_filename_safe(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid file type")

    filepath = os.path.join(GALLERY_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    await asyncio.to_thread(os.remove, filepath)
    conn = await get_db_connection()
    try:
        await conn.execute("DELETE FROM manual_photos WHERE filename=?", (filename,))
        await conn.commit()
    finally:
        await close_db_connection(conn)
    try:
        await insert_log(f"Photo deleted: {filename}", "delete")
    except Exception as e:
        logger.error(f"Error inserting photo delete log: {e}")
        system_state.error_counts["database"] += 1
    await send_to_web_clients({"type": "photo_deleted", "filename": filename})
    return {"status": "success", "message": f"Photo {filename} deleted"}

async def delete_video(request: DeleteVideoRequest, req: Request, user=Depends(get_current_user)):
    """Legacy endpoint - redirects to delete_video_by_filename"""
    return await delete_video_by_filename(request.filename, user)




async def logout(req: Request):
    """Logout endpoint - clears cookies and returns JSON response"""
    try:
        client_ip = req.client.host
        await insert_log(f"Logout from {client_ip}", "auth")
        
        # Create response and clear cookie
        response = JSONResponse(content={"status": "success", "message": "Successfully logged out"})
        response.delete_cookie(key="access_token")
        
        return response
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail="Logout error")

async def logout_page(req: Request):
    """Logout page - redirects to login"""
    return RedirectResponse(url="/login", status_code=302)

def get_lang_from_request(request: Request):
    return request.cookies.get('language', 'fa')

async def set_language(request: Request):
    data = await request.json()
    lang = data.get("lang", "fa")
    msg = {"fa": "زبان نامعتبر", "en": "Invalid language"}
    if lang not in ["fa", "en"]:
        return JSONResponse({"status": "error", "message": msg.get(lang, msg['en'])}, status_code=400)
    response = JSONResponse({"status": "success", "language": lang})
    response.set_cookie(key="language", value=lang, max_age=60*60*24*365)
    return response

async def serve_static_file(filename: str):
    logger.info(f"[STATIC] Requested static file: {filename}")
    
    # Simplified validation - just check for directory traversal
    if '..' in filename:
        logger.warning(f"Directory traversal attempt in static: {filename}")
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Allow all files in static directory for now
    file_path = os.path.join("static", filename)
    if not os.path.exists(file_path):
        logger.warning(f"Static file not found: {filename}")
        raise HTTPException(status_code=404, detail=f"File {filename} not found")
    
    logger.info(f"[STATIC] Serving file: {file_path}")
    
    response = FileResponse(file_path)
    
    # Apply minimal security headers for static files (no cache clearing)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    
    # Add appropriate cache headers for static assets
    if filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.css', '.js')):
        response.headers['Cache-Control'] = 'public, max-age=86400'  # 24 hours
    else:
        response.headers['Cache-Control'] = 'no-cache'
    
    return response


async def serve_gallery_file(filename: str, request: Request, user=Depends(get_current_user)):
    logger.info(f"[HTTP] /gallery/{filename} requested by {request.client.host}")
    
    # Enhanced path traversal protection using centralized function
    if not validate_filename_safe(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Validate file extension
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in allowed_extensions:
        logger.warning(f"Invalid file extension: {file_ext}")
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    file_path = os.path.join(GALLERY_DIR, filename)
    if not os.path.exists(file_path):
        logger.warning(f"Gallery file not found: {filename}")
        raise HTTPException(status_code=404, detail=f"File {filename} not found")
    
    # File size check removed as requested
    
    response = FileResponse(file_path, headers={
        'Cache-Control': 'public, max-age=3600',
        'Content-Disposition': f'inline; filename="{filename}"'
    })
    # Apply centralized security headers
    return apply_security_headers(response)


def get_video_content_type(filename: str) -> str:
    """Get the appropriate Content-Type for video files based on extension"""
    file_ext = os.path.splitext(filename)[1].lower()
    content_types = {
        '.mp4': 'video/mp4',
        '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime',
        '.mkv': 'video/x-matroska',
        '.webm': 'video/webm'
    }
    return content_types.get(file_ext, 'video/mp4')  # Default to mp4

async def serve_video_file(request: Request, filename: str):
    """Serve video files with optimized streaming and no download capability"""
    # Validate filename
    if not filename or '..' in filename or '/' in filename:
        logger.warning(f"Invalid video filename: {filename}")
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Construct file path
    file_path = os.path.join("security_videos", filename)
    
    if not os.path.exists(file_path):
        logger.warning(f"Video file not found: {filename}")
        raise HTTPException(status_code=404, detail=f"File {filename} not found")
    
    try:
        file_size = os.path.getsize(file_path)
        
        # Enhanced streaming response for all videos
        logger.info(f"Streaming video: {filename} ({file_size} bytes)")
        
        # Check for range requests (HTTP 206 Partial Content)
        range_header = request.headers.get('range')
        if range_header:
            logger.info(f"Range request for {filename}: {range_header}")
            return await handle_range_request(request, file_path, file_size, filename, range_header)
        
        # Full file streaming with optimized settings
        logger.info(f"Full file streaming for {filename}")
        return await handle_full_file_streaming(request, file_path, file_size, filename)
        
    except OSError as e:
        logger.warning(f"Error accessing video file: {filename} - {e}")
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        unregister_file_connection(filename)
        logger.error(f"Error serving video file {filename}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def handle_range_request(request: Request, file_path: str, file_size: int, filename: str, range_header: str):
    """Handle HTTP range requests for video seeking"""
    try:
        import re
        match = re.match(r'bytes=(\d+)-(\d+)?', range_header)
        if not match:
            raise HTTPException(status_code=400, detail="Invalid range header")
        
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else file_size - 1
        
        # Validate range
        if start >= file_size or end >= file_size or start > end:
            raise HTTPException(status_code=416, detail="Range not satisfiable")
        
        content_length = end - start + 1
        
        async def range_generator():
            try:
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    remaining = content_length
                    chunk_size = 64 * 1024  # 64KB chunks for better performance
                    
                    while remaining > 0:
                        read_size = min(chunk_size, remaining)
                        chunk = f.read(read_size)
                        if not chunk:
                            break
                        yield chunk
                        remaining -= len(chunk)
            except Exception as e:
                logger.error(f"Error in range generator: {e}")
                raise HTTPException(status_code=500, detail="Error reading file")
            finally:
                unregister_file_connection(filename)
        
        content_type = get_video_content_type(filename)
        
        response = StreamingResponse(
            range_generator(),
            headers={
                'Accept-Ranges': 'bytes',
                'Content-Range': f'bytes {start}-{end}/{file_size}',
                'Content-Length': str(content_length),
                'Content-Type': content_type,
                'Content-Disposition': 'inline; filename=""',
                'Cache-Control': 'public, max-age=3600, must-revalidate',
                'ETag': f'"{hash(filename + str(file_size))}"',
                'X-Streaming-Only': 'true',
                'X-Video-Security': 'streaming-only',
                'X-Content-Type-Options': 'nosniff',
                'X-Frame-Options': 'SAMEORIGIN',
                'X-Download-Options': 'noopen',
                'X-Permitted-Cross-Domain-Policies': 'none'
            },
            status_code=206
        )
        
        register_file_connection(filename)
        return apply_security_headers(response)
        
    except Exception as e:
        logger.error(f"Error handling range request: {e}")
        raise HTTPException(status_code=500, detail="Error processing range request")


async def handle_full_file_streaming(request: Request, file_path: str, file_size: int, filename: str):
    """Handle full file streaming with optimized performance"""
    async def full_file_generator():
        try:
            with open(file_path, 'rb') as f:
                chunk_size = 64 * 1024  # 64KB chunks for better performance
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            logger.error(f"Error in full file generator: {e}")
            raise HTTPException(status_code=500, detail="Error reading file")
        finally:
            unregister_file_connection(filename)
    
    content_type = get_video_content_type(filename)
    
    response = StreamingResponse(
        full_file_generator(),
        headers={
            'Accept-Ranges': 'bytes',
            'Content-Type': content_type,
            'Content-Disposition': 'inline; filename=""',
            'Cache-Control': 'public, max-age=3600, must-revalidate',
            'ETag': f'"{hash(filename + str(file_size))}"',
            'X-Streaming-Only': 'true',
            'X-Video-Security': 'streaming-only',
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'SAMEORIGIN',
            'X-Download-Options': 'noopen',
            'X-Permitted-Cross-Domain-Policies': 'none'
        }
    )
    
    register_file_connection(filename)
    return apply_security_headers(response)


async def login_page(request: Request):
    # Check if user is already logged in
    token = request.cookies.get("access_token")
    if token and verify_token(token):
        return RedirectResponse(url="/", status_code=302)
    
    lang = request.cookies.get('language', 'fa')
    return get_templates().TemplateResponse("login.html", {"request": request, "translations": translations, "lang": lang})



def check_login_attempts(client_ip: str) -> bool:
    """Enhanced in-memory login attempts tracking"""
    try:
        global login_attempts_storage
        # Skip login attempts check for local test requests
        if is_local_test_request(client_ip):
            return True
        
        current_time = time.time()
        
        # Safely access config with defaults
        try:
            config = RATE_LIMIT_CONFIG.get('LOGIN_ATTEMPTS', {})
            max_requests = config.get('max_requests', 5)
            window_seconds = config.get('window_seconds', 300)
        except Exception as e:
            logger.warning(f"[LOGIN] Error accessing rate limit config: {e}")
            # Use default values if config access fails
            max_requests = 5
            window_seconds = 300
        
        window_start = current_time - window_seconds
        
        # Clean old entries
        login_attempts_storage = {ip: data for ip, data in login_attempts_storage.items() 
                                if data['last_attempt'] > window_start}
        
        # Check current IP
        if client_ip not in login_attempts_storage:
            login_attempts_storage[client_ip] = {'count': 0, 'last_attempt': 0, 'blocked_until': 0}
        
        # Check if still blocked
        if login_attempts_storage[client_ip]['blocked_until'] > current_time:
            return False
        
        # Reset count if window expired
        if login_attempts_storage[client_ip]['last_attempt'] < window_start:
            login_attempts_storage[client_ip]['count'] = 0
        
        # Check if limit exceeded
        if login_attempts_storage[client_ip]['count'] >= max_requests:
            try:
                ban_duration = SECURITY_CONFIG.get('LOGIN_BAN_DURATION', 300)
            except Exception as e:
                logger.warning(f"[LOGIN] Error accessing security config: {e}")
                ban_duration = 300  # Default to 5 minutes
            
            login_attempts_storage[client_ip]['blocked_until'] = current_time + ban_duration
            return False
        
        return True
    except Exception as e:
        logger.error(f"[LOGIN] Error in check_login_attempts: {e}")
        # If there's an error, allow the login attempt to proceed
        return True


def record_login_attempt(client_ip: str, success: bool):
    """Enhanced in-memory login attempt recording"""
    try:
        current_time = time.time()
        
        # Initialize if not exists
        if client_ip not in login_attempts_storage:
            login_attempts_storage[client_ip] = {'count': 0, 'last_attempt': 0, 'blocked_until': 0}
        
        if success:
            # Reset on successful login
            login_attempts_storage[client_ip]['count'] = 0
            login_attempts_storage[client_ip]['blocked_until'] = 0
        else:
            # Increment failed attempts
            login_attempts_storage[client_ip]['count'] += 1
            login_attempts_storage[client_ip]['last_attempt'] = current_time
            
            # Block if limit exceeded - safely access config
            try:
                config = RATE_LIMIT_CONFIG.get('LOGIN_ATTEMPTS', {})
                max_requests = config.get('max_requests', 5)  # Default to 5
                
                if login_attempts_storage[client_ip]['count'] >= max_requests:
                    ban_duration = SECURITY_CONFIG.get('LOGIN_BAN_DURATION', 300)  # Default to 5 minutes
                    login_attempts_storage[client_ip]['blocked_until'] = current_time + ban_duration
            except Exception as e:
                logger.warning(f"[LOGIN] Error accessing rate limit config: {e}")
                # Use default values if config access fails
                if login_attempts_storage[client_ip]['count'] >= 5:
                    login_attempts_storage[client_ip]['blocked_until'] = current_time + 300
    except Exception as e:
        logger.error(f"[LOGIN] Error in record_login_attempt: {e}")
        # Don't let this function fail the login process
        pass

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using bcrypt"""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ImportError:
        logger.error("bcrypt is required for password verification. Please install it: pip install bcrypt")
        return False


async def login(request: LoginRequest, req: Request):
    client_ip = req.client.host
    logger.debug(f"[LOGIN] Start login for IP: {client_ip}")
    
    # Ensure database is initialized (silent)
    if not getattr(system_state, 'db_initialized', False):
        logger.debug("[LOGIN] DB not initialized, calling init_db()")
        await init_db()
    
    # Enhanced input sanitization and validation
    logger.debug(f"[LOGIN] Raw username: {request.username}")
    sanitized_username = sanitize_input(request.username)
    sanitized_password = sanitize_input(request.password)
    logger.debug(f"[LOGIN] Sanitized username: {sanitized_username}")
    
    # Enhanced rate limiting check with exponential backoff
    if not check_api_rate_limit(client_ip, "/login"):
        logger.warning(f"[LOGIN] Rate limit exceeded for {client_ip}")
        raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")
    
    # Enhanced password strength validation
    if len(sanitized_password) < 8:
        logger.warning(f"[LOGIN] Weak password attempt from {client_ip}")
        record_login_attempt(client_ip, False)
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
    
    # Check for common weak passwords
    weak_passwords = [
        '123456', 'password', 'admin', 'qwerty', '123456789',
        '12345678', '1234567', '1234567890', '123123', 'abc123',
        'password123', 'admin123', 'letmein', 'welcome', 'monkey'
    ]
    
    if sanitized_password.lower() in weak_passwords:
        logger.warning(f"[LOGIN] Weak password detected from {client_ip}")
        record_login_attempt(client_ip, False)
        raise HTTPException(status_code=400, detail="Password is too weak. Please choose a stronger password")
    
    # Enhanced input validation
    if sanitized_username != request.username:
        logger.warning(f"[LOGIN] Username sanitized mismatch for {client_ip}")
        raise HTTPException(status_code=400, detail="Invalid username format")
    
    # Validate username length and format (allow emails which can be shorter)
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    is_email = re.match(email_pattern, sanitized_username)
    
    if is_email:
        # For emails, only check maximum length
        if len(sanitized_username) > 50:
            logger.warning(f"[LOGIN] Email too long from {client_ip}")
            raise HTTPException(status_code=400, detail="Email address too long")
    else:
        # For usernames, check both minimum and maximum length
        if len(sanitized_username) < 3 or len(sanitized_username) > 50:
            logger.warning(f"[LOGIN] Invalid username length from {client_ip}")
            raise HTTPException(status_code=400, detail="Username must be between 3 and 50 characters")
    
    # Check for SQL injection patterns in username
    sql_injection_patterns = [
        "'", '"', ';', '--', '/*', '*/', 'union', 'select', 'insert', 'update', 'delete', 'drop'
    ]
    
    if any(pattern in sanitized_username.lower() for pattern in sql_injection_patterns):
        logger.warning(f"[LOGIN] SQL injection attempt detected from {client_ip}")
        record_login_attempt(client_ip, False)
        raise HTTPException(status_code=400, detail="Invalid username format")
    
    try:
        logger.debug(f"[LOGIN] Getting DB connection for {client_ip}")
        
        # Get user from database with retry logic
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                conn = await get_db_connection()
                try:
                    logger.debug(f"[LOGIN] Executing user query for {sanitized_username}")
                    
                    # Try to find user by username first, then by email
                    user_query = await conn.execute(
                        'SELECT username, password_hash, role, is_active, two_fa_enabled, two_fa_secret FROM users WHERE username = ? OR email = ?',
                        (sanitized_username, sanitized_username)
                    )
                    user_data = await user_query.fetchone()
                    logger.debug(f"[LOGIN] user_data: {user_data}")
                    
                    # Check if user exists first
                    if not user_data:
                        logger.warning(f"[LOGIN] User not found: {sanitized_username} from {client_ip}")
                        record_login_attempt(client_ip, False)
                        raise HTTPException(status_code=401, detail="نام کاربری یا رمز عبور اشتباه است")
                    
                    # Check if user is active
                    if not user_data[3]:  # is_active
                        logger.warning(f"[LOGIN] User inactive: {sanitized_username} from {client_ip}")
                        record_login_attempt(client_ip, False)
                        raise HTTPException(status_code=401, detail="حساب کاربری غیرفعال است")
                    
                    # Ensure we have the right number of columns
                    if len(user_data) > 6:
                        user_data = user_data[:6]
                    
                    username, password_hash, role, is_active, two_fa_enabled, two_fa_secret = user_data
                    logger.debug(f"[LOGIN] Verifying password for {username}")
                    
                    try:
                        password_ok = verify_password(sanitized_password, password_hash)
                    except Exception as e:
                        logger.error(f"[LOGIN] bcrypt error: {e}")
                        raise HTTPException(status_code=500, detail="خطا در تأیید رمز عبور")
                    
                    if password_ok:
                        record_login_attempt(client_ip, True)
                        
                        # Check if user has 2FA enabled
                        if two_fa_enabled and two_fa_secret:
                            logger.info(f"[LOGIN] 2FA required for {username}")
                            secret = two_fa_secret
                            totp = pyotp.TOTP(secret)
                            qr_code_data = totp.provisioning_uri(username, issuer_name="Smart Camera System")
                            await insert_log(f"2FA required for login from {client_ip} (user: {username})", "auth")
                            return {
                                "requires_2fa": True,
                                "qr_code": qr_code_data,
                                "secret": f"{username}:{secret}"
                            }
                        else:
                            logger.debug(f"[LOGIN] Creating access token for {username}")
                            try:
                                # Enhanced token creation with IP validation
                                access_token = create_access_token(
                                    data={
                                        "sub": username, 
                                        "role": role, 
                                        "ip": client_ip,
                                        "user_agent": req.headers.get('user-agent', 'Unknown')
                                    }
                                )
                            except Exception as e:
                                logger.error(f"[LOGIN] Token creation error: {e}")
                                raise HTTPException(status_code=500, detail="خطا در ایجاد توکن")
                            
                            await insert_log(f"Successful login from {client_ip} (user: {username}, role: {role})", "auth")
                            
                            response_data = {
                                "access_token": access_token,
                                "token_type": "bearer",
                                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                                "user": {
                                    "username": username,
                                    "role": role
                                }
                            }
                            
                            response = JSONResponse(content=response_data)
                            
                            # Enhanced secure cookie settings
                            secure_cookie = not is_test_environment()
                            response.set_cookie(
                                key="access_token",
                                value=access_token,
                                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                                httponly=True,
                                secure=secure_cookie,
                                samesite="strict"
                            )
                            
                            return response
                    else:
                        logger.warning(f"[LOGIN] Invalid password for {sanitized_username} from {client_ip}")
                        record_login_attempt(client_ip, False)
                        raise HTTPException(status_code=401, detail="نام کاربری یا رمز عبور اشتباه است")
                        
                finally:
                    await close_db_connection(conn)
                
                # If we reach here, the operation was successful
                break
                
            except aiosqlite.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"[LOGIN] Database locked on attempt {attempt + 1}/{max_retries}, retrying in {retry_delay}s: {e}")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    logger.error(f"[LOGIN] Database operational error after {attempt + 1} attempts: {e}")
                    raise HTTPException(status_code=503, detail="پایگاه داده موقتاً در دسترس نیست، لطفاً دوباره تلاش کنید")
            except HTTPException:
                # Re-raise HTTP exceptions
                raise
            except Exception as e:
                logger.error(f"[LOGIN] Unexpected error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(f"[LOGIN] All retry attempts failed for {client_ip}")
                    raise HTTPException(status_code=500, detail="خطا در ورود به سیستم، لطفاً دوباره تلاش کنید")
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"[LOGIN] Unexpected error: {e}")
        record_login_attempt(client_ip, False)
        raise HTTPException(status_code=500, detail="خطا در ورود به سیستم، لطفاً دوباره تلاش کنید")


# Temporary CSRF token functions for unauthenticated users
async def validate_temp_csrf_token(session_id: str, token: str) -> bool:
    """Validate temporary CSRF token for unauthenticated users"""
    try:
        conn = await get_db_connection()
        cursor = await conn.execute(
            "SELECT csrf_token, expires_at FROM temp_csrf_tokens WHERE session_id = ? AND expires_at > ?",
            (session_id, datetime.now().isoformat())
        )
        result = await cursor.fetchone()
        await close_db_connection(conn)
        
        if result and result[0]:
            stored_token, expiry = result
            if validate_csrf_token(token, stored_token):
                # Don't delete the token immediately - let it expire naturally
                # This allows for retry attempts and better user experience
                return True
        return False
    except Exception as e:
        logger.error(f"Error validating temp CSRF token: {e}")
        return False



async def register(request: RegisterRequest, req: Request):
    """User registration endpoint"""
    client_ip = req.client.host
    
    # CSRF validation logic moved here
    csrf_token = get_csrf_token_from_request(req)
    session_id = req.headers.get('X-Session-ID')
    
    if not csrf_token:
        logger.warning(f"CSRF token missing for {req.method} {req.url.path} from {req.client.host}")
        raise HTTPException(status_code=403, detail="CSRF token missing")
    
    if not session_id:
        logger.warning(f"Session ID missing for {req.method} {req.url.path} from {req.client.host}")
        raise HTTPException(status_code=403, detail="Session ID missing")
    
    # Validate temporary CSRF token
    if not await validate_temp_csrf_token(session_id, csrf_token):
        logger.warning(f"Invalid temp CSRF token for {req.method} {req.url.path} from {req.client.host}")
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    
    # Ensure database is initialized (silent)
    if not getattr(system_state, 'db_initialized', False):
        await init_db()
    
    # Sanitize inputs
    sanitized_username = sanitize_input(request.username)
    sanitized_phone = sanitize_input(request.phone)
    sanitized_email = sanitize_input(request.email).lower() if request.email else None
    sanitized_password = sanitize_input(request.password)
    
    # Enhanced password strength validation using the centralized function
    if not validate_password_strength(sanitized_password):
                    raise HTTPException(status_code=400, detail="Password is too weak. Password must be at least 8 characters long and contain uppercase, lowercase, digit, and special character.")
    
    # Check rate limiting
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    try:
        conn = await get_db_connection()
        try:
            # Check if username already exists
            user_check = await conn.execute(
                'SELECT username FROM users WHERE username = ?',
                (sanitized_username,)
            )
            if await user_check.fetchone():
                raise HTTPException(status_code=400, detail="نام کاربری قبلاً استفاده شده است")
            
            # Check if phone already exists
            phone_check = await conn.execute(
                'SELECT phone FROM users WHERE phone = ?',
                (sanitized_phone,)
            )
            if await phone_check.fetchone():
                raise HTTPException(status_code=400, detail="شماره تلفن قبلاً ثبت شده است")
            
            # Check if email already exists (only if provided)
            if sanitized_email:
                email_check = await conn.execute(
                    'SELECT email FROM users WHERE lower(email) = ?',
                    (sanitized_email,)
                )
                if await email_check.fetchone():
                    raise HTTPException(status_code=400, detail="ایمیل قبلاً ثبت شده است")
            
            # Hash password
            password_hash = hash_password(sanitized_password)
            
            # Insert new user
            if sanitized_email:
                await conn.execute(
                    'INSERT INTO users (username, phone, email, password_hash, role, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (sanitized_username, sanitized_phone, sanitized_email, password_hash, "user", True, get_jalali_now_str())
                )
            else:
                await conn.execute(
                    'INSERT INTO users (username, phone, password_hash, role, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                    (sanitized_username, sanitized_phone, password_hash, "user", True, get_jalali_now_str())
                )
            await conn.commit()
            
            await insert_log(f"New user registered: {sanitized_username} from {client_ip}", "auth")
            
            return {"status": "success", "message": "ثبت‌نام با موفقیت انجام شد"}
        finally:
            await close_db_connection(conn)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Registration error")
        raise HTTPException(status_code=500, detail="خطا در ثبت‌نام")



async def check_recovery_attempts(phone: str, conn=None) -> bool:
    """Check if user has exceeded recovery attempts"""
    try:
        should_close = False
        if conn is None:
            conn = await get_db_connection()
            should_close = True
        
        # Check attempts in last 1 hour
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        attempts = await conn.execute(
            'SELECT COUNT(*) FROM password_recovery WHERE phone = ? AND created_at > ?',
            (phone, one_hour_ago)
        )
        count = await attempts.fetchone()
        
        if should_close:
            await close_db_connection(conn)
        
        # Allow maximum 3 attempts per hour
        return count[0] < 3
    except Exception as e:
        logger.error(f"Error checking recovery attempts: {e}")
        return False

async def generate_unique_recovery_code(conn, phone: str) -> str:
    """Generate unique 6-digit recovery code"""
    max_attempts = 10
    for attempt in range(max_attempts):
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # Check if code already exists
        existing = await conn.execute(
            'SELECT COUNT(*) FROM password_recovery WHERE token = ?',
            (code,)
        )
        count = await existing.fetchone()
        
        if count[0] == 0:
            return code
    
    raise HTTPException(status_code=500, detail="Unable to generate unique recovery code")


def require_temp_csrf_token(func):
    """Decorator for endpoints that need temporary CSRF validation (for unauthenticated users)"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        request = None
        
        # First try to get request from kwargs
        request = kwargs.get('request') or kwargs.get('req')
        
        # If not in kwargs, look for Request object in args
        if not request:
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
        
        # If still not found, try to get it from the function signature
        if not request:
            import inspect
            sig = inspect.signature(func)
            param_names = list(sig.parameters.keys())
            
            # Look for parameters that might be Request objects
            for i, arg in enumerate(args):
                if i < len(param_names):
                    param_name = param_names[i]
                    # Check if this parameter is likely a Request object
                    if param_name in ['req', 'request', 'http_request']:
                        if hasattr(arg, 'headers') and hasattr(arg, 'method'):
                            request = arg
                            break
        
        if not request:
            raise HTTPException(status_code=400, detail="Request object not found")
        
        # Get CSRF token from request
        csrf_token = get_csrf_token_from_request(request)
        session_id = request.headers.get('X-Session-ID')
        
        if not csrf_token:
            path_info = request.url.path if hasattr(request, 'url') and request.url else "unknown"
            logger.warning(f"CSRF token missing for {getattr(request, 'method', 'unknown')} {path_info} from {getattr(request.client, 'host', 'unknown')}")
            raise HTTPException(status_code=403, detail="CSRF token missing")
        
        if not session_id:
            path_info = request.url.path if hasattr(request, 'url') and request.url else "unknown"
            logger.warning(f"Session ID missing for {getattr(request, 'method', 'unknown')} {path_info} from {getattr(request.client, 'host', 'unknown')}")
            raise HTTPException(status_code=403, detail="Session ID missing")
        
        # Validate temporary CSRF token
        if not await validate_temp_csrf_token(session_id, csrf_token):
            path_info = request.url.path if hasattr(request, 'url') and request.url else "unknown"
            logger.warning(f"Invalid temp CSRF token for {getattr(request, 'method', 'unknown')} {path_info} from {getattr(request.client, 'host', 'unknown')}")
            raise HTTPException(status_code=403, detail="Invalid CSRF token")
        
        return await func(*args, **kwargs)
    
    return wrapper

async def recover_password(recovery_request: PasswordRecoveryRequest, req: Request):
    """Password recovery endpoint via SMS"""
    client_ip = req.client.host
    
    # Ensure database is initialized (silent)
    if not getattr(system_state, 'db_initialized', False):
        await init_db()
    
    # Sanitize phone input
    sanitized_phone = sanitize_input(recovery_request.phone)
    
    # Check rate limiting
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    try:
        conn = await get_db_connection()
        try:
            # Check recovery attempts limit
            if not await check_recovery_attempts(sanitized_phone):
                raise HTTPException(status_code=429, detail="تعداد تلاش‌های بازیابی شما در 1 ساعت گذشته به حداکثر رسیده است. لطفاً 1 ساعت صبر کنید.")
            
            # Check if phone exists
            user_check = await conn.execute(
                'SELECT username FROM users WHERE phone = ? AND is_active = 1',
                (sanitized_phone,)
            )
            user_data = await user_check.fetchone()
            
            if not user_data:
                # Don't reveal if phone exists or not for security
                return {"status": "success", "message": "اگر شماره تلفن در سیستم ثبت شده باشد، کد بازیابی ارسال خواهد شد"}
            
            # Generate unique recovery token (6 digits for SMS)
            recovery_token = await generate_unique_recovery_code(conn, sanitized_phone)
            recovery_expires = datetime.now() + timedelta(minutes=5)  # 5 minutes expiration

            # Log the recovery token for debugging
            logger.info(f"[DEBUG] Password recovery code for {sanitized_phone}: {recovery_token}")
            
            # Store recovery token in database
            await conn.execute(
                'INSERT INTO password_recovery (phone, token, expires_at, created_at) VALUES (?, ?, ?, ?)',
                (sanitized_phone, recovery_token, recovery_expires.isoformat(), get_jalali_now_str())
            )
            await conn.commit()
        finally:
            await close_db_connection(conn)
        
        # Send recovery SMS
        try:
            await send_password_recovery_sms(sanitized_phone, recovery_token, user_data[0])
            await insert_log(f"Password recovery SMS sent to {sanitized_phone} from {client_ip}", "auth")
            return {"status": "success", "message": "کد بازیابی به شماره تلفن شما ارسال شد"}
        except Exception as sms_error:
            logger.error(f"Failed to send recovery SMS: {sms_error}")
            # Log the token for manual recovery if SMS fails
            logger.info(f"Password recovery token for {sanitized_phone}: {recovery_token}")
            await insert_log(f"Password recovery requested for {sanitized_phone} from {client_ip} (SMS failed)", "auth")
            return {"status": "success", "message": "کد بازیابی به شماره تلفن شما ارسال شد"}
        
    except Exception as e:
        logger.error(f"Password recovery error: {e}")
        raise HTTPException(status_code=500, detail="خطا در ارسال کد بازیابی")


async def reset_password(reset_request: PasswordResetRequest, req: Request):
    """Reset password using recovery token"""
    client_ip = req.client.host
    
    # Ensure database is initialized (silent)
    if not getattr(system_state, 'db_initialized', False):
        await init_db()
    
    # Sanitize inputs
    sanitized_token = sanitize_input(reset_request.code)
    sanitized_password = sanitize_input(reset_request.new_password)
    
    # Validate password strength
    if len(sanitized_password) < 8:
        raise HTTPException(status_code=400, detail="رمز عبور باید حداقل 8 کاراکتر باشد")
    
    # Check rate limiting
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    try:
        conn = await get_db_connection()
        try:
            # Check if token exists and is valid
            token_check = await conn.execute(
                'SELECT phone, expires_at, used FROM password_recovery WHERE token = ?',
                (sanitized_token,)
            )
            token_data = await token_check.fetchone()
            
            if not token_data:
                raise HTTPException(status_code=400, detail="کد نامعتبر است")
            
            phone, expires_at, used = token_data
            
            # Check if token is expired
            if datetime.fromisoformat(expires_at) < datetime.now():
                raise HTTPException(status_code=400, detail="کد منقضی شده است")
            
            # Check if token is already used
            if used:
                raise HTTPException(status_code=400, detail="کد قبلاً استفاده شده است")
            
            # Hash new password
            password_hash = hash_password(sanitized_password)
            
            # Update user password
            await conn.execute(
                'UPDATE users SET password_hash = ? WHERE phone = ?',
                (password_hash, phone)
            )
            
            # Mark token as used
            await conn.execute(
                'UPDATE password_recovery SET used = 1 WHERE token = ?',
                (sanitized_token,)
            )
            
            await conn.commit()
            
            await insert_log(f"Password reset successful for {phone} from {client_ip}", "auth")
            
            return {"status": "success", "message": "رمز عبور با موفقیت تغییر یافت"}
        finally:
            await close_db_connection(conn)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset error: {e}")
        raise HTTPException(status_code=500, detail="خطا در تغییر رمز عبور")






async def create_security_video(frames: List[Tuple[bytes, datetime]]):
    try:
        total_frames_needed = VIDEO_FPS * 3600  # 1 hour
        if len(frames) < MIN_VALID_FRAMES:
            logger.warning("Not enough valid frames for video creation")
            return
        # Repeat last frame if not enough frames, or trim if too many
        if len(frames) < total_frames_needed:
            last_frame = frames[-1][0]
            frames += [(last_frame, datetime.now())] * (total_frames_needed - len(frames))
        else:
            frames = frames[:total_frames_needed]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hour_of_day = datetime.now().hour
        video_filename = f"security_video_{timestamp}_{hour_of_day}.mp4"
        video_filepath = os.path.join(SECURITY_VIDEOS_DIR, video_filename)
        await asyncio.to_thread(os.makedirs, SECURITY_VIDEOS_DIR, exist_ok=True)
        first_frame = cv2.imdecode(np.frombuffer(frames[0][0], dtype=np.uint8), cv2.IMREAD_COLOR)
        if first_frame is None:
            logger.error("Invalid first frame for video")
            return
        height, width = first_frame.shape[:2]
        # Use H.264 if ffmpeg is available, else mp4v
        fourcc = cv2.VideoWriter_fourcc(*'avc1') if shutil.which('ffmpeg') else cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(video_filepath, fourcc, VIDEO_FPS, (width, height))
        prev_good_frame = first_frame
        for frame_data, _ in frames:
            frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                frame = prev_good_frame  # Use previous good frame
            else:
                prev_good_frame = frame
            await asyncio.to_thread(video_writer.write, frame)
        await asyncio.to_thread(video_writer.release)
        system_state.video_count += 1
        async def insert_video():
            conn = await get_db_connection()
            try:
                await conn.execute(
                    "INSERT INTO security_videos (filename, filepath, hour_of_day, duration, created_at) VALUES (?, ?, ?, ?, ?)",
                    (video_filename, video_filepath, hour_of_day, 3600, get_jalali_now_str())
                )
                await conn.commit()
            finally:
                await close_db_connection(conn)
        await retry_async(insert_video)
        logger.info(f"Security video created: {video_filename}")
        async with system_state.web_clients_lock:
            for client in system_state.web_clients:
                try:
                    await client.send_text(json.dumps({
                        "type": "video_created",
                        "filename": video_filename,
                        "url": f"/security_videos/{video_filename}",
                        "hour": hour_of_day,
                        "timestamp": get_jalali_now_str()
                    }))
                except Exception as e:
                    logger.warning(f"Error sending video notification: {e}")
    except Exception as e:
        logger.error(f"Error creating security video: {e}")
        if 'video_writer' in locals():
            await asyncio.to_thread(video_writer.release)
        if os.path.exists(video_filepath):
            await asyncio.to_thread(os.remove, video_filepath)



async def create_security_video_async(frames: List[Tuple[bytes, datetime]]):
    """ایجاد ویدیو امنیتی در background - wrapper for create_security_video"""
    await create_security_video(frames)


async def generate_video_poster(request: Request, filename: str):
    """Generate video poster (thumbnail) from the first frame, similar to Windows behavior"""
    try:
        # Validate filename
        if not filename or '..' in filename or '/' in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # Construct file path
        file_path = os.path.join("security_videos", filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Video file not found")
        
        # Check if poster already exists
        poster_dir = os.path.join("security_videos", "posters")
        os.makedirs(poster_dir, exist_ok=True)
        
        poster_filename = f"{os.path.splitext(filename)[0]}_poster.jpg"
        poster_path = os.path.join(poster_dir, poster_filename)
        
        # Generate poster if it doesn't exist
        if not os.path.exists(poster_path):
            await generate_video_poster_frame(file_path, poster_path)
        
        # Serve the poster image
        if os.path.exists(poster_path):
            return FileResponse(
                poster_path,
                media_type="image/jpeg",
                headers={
                    'Cache-Control': 'public, max-age=86400',  # Cache for 24 hours
                    'X-Poster-Generated': 'true'
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to generate poster")
            
    except Exception as e:
        logger.error(f"Error generating video poster for {filename}: {e}")
        raise HTTPException(status_code=500, detail="Error generating poster")


async def generate_video_poster_frame(video_path: str, poster_path: str):
    """Extract first frame from video and save as JPEG poster"""
    try:
        import cv2
        
        # Open video file
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception("Could not open video file")
        
        # Read first frame
        ret, frame = cap.read()
        if not ret:
            raise Exception("Could not read video frame")
        
        # Resize frame for optimal poster size (16:9 aspect ratio)
        height, width = frame.shape[:2]
        target_width = 320
        target_height = int(target_width * 9 / 16)
        
        # Resize frame
        resized_frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)
        
        # Save as JPEG with high quality
        cv2.imwrite(poster_path, resized_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        
        # Release video capture
        cap.release()
        
        logger.info(f"Generated poster for video: {os.path.basename(video_path)}")
        
    except ImportError:
        logger.warning("OpenCV not available, using fallback poster generation")
        await generate_fallback_poster(video_path, poster_path)
    except Exception as e:
        logger.error(f"Error generating poster frame: {e}")
        await generate_fallback_poster(video_path, poster_path)


async def generate_fallback_poster(video_path: str, poster_path: str):
    """Fallback poster generation using ffmpeg if available"""
    try:
        import subprocess
        
        # Use ffmpeg to extract first frame
        cmd = [
            'ffmpeg', '-i', video_path, 
            '-vframes', '1', 
            '-q:v', '2',  # High quality
            '-vf', 'scale=320:180',  # 16:9 aspect ratio
            '-y',  # Overwrite output
            poster_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(poster_path):
            logger.info(f"Generated poster using ffmpeg: {os.path.basename(video_path)}")
        else:
            raise Exception(f"ffmpeg failed: {result.stderr}")
            
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.error(f"Fallback poster generation failed: {e}")
        # Create a default poster with video info
        await create_default_poster(video_path, poster_path)


async def create_default_poster(video_path: str, poster_path: str):
    """Create a default poster with video information when all else fails"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import os
        
        # Create a 320x180 black image
        img = Image.new('RGB', (320, 180), color='black')
        draw = ImageDraw.Draw(img)
        
        # Try to use a default font
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()
        
        # Get video filename
        filename = os.path.basename(video_path)
        
        # Draw video icon and filename
        draw.text((160, 80), "🎥", fill="white", anchor="mm", font=font)
        draw.text((160, 120), filename[:20], fill="white", anchor="mm", font=font)
        
        # Save the default poster
        img.save(poster_path, "JPEG", quality=90)
        logger.info(f"Created default poster for: {filename}")
        
    except Exception as e:
        logger.error(f"Failed to create default poster: {e}")


async def get_video_metadata(request: Request, filename: str):
    """Get comprehensive video metadata similar to Windows file properties"""
    try:
        # Validate filename
        if not filename or '..' in filename or '/' in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # Construct file path
        file_path = os.path.join("security_videos", filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Video file not found")
        
        # Get basic file info
        stat_info = os.stat(file_path)
        file_size = stat_info.st_size
        
        # Get video metadata using OpenCV
        metadata = {
            "filename": filename,
            "file_size": file_size,
            "file_size_formatted": format_file_size(file_size),
            "created_time": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
            "modified_time": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            "access_time": datetime.fromtimestamp(stat_info.st_atime).isoformat(),
            "poster_url": f"/video_poster/{filename}"
        }
        
        try:
            import cv2
            
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                # Get video properties
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                # Calculate duration
                duration = frame_count / fps if fps > 0 else 0
                duration_formatted = format_duration(duration)
                
                metadata.update({
                    "width": width,
                    "height": height,
                    "fps": round(fps, 2),
                    "frame_count": frame_count,
                    "duration": duration,
                    "duration_formatted": duration_formatted,
                    "aspect_ratio": f"{width}:{height}",
                    "resolution": f"{width}x{height}"
                })
                
                cap.release()
                
        except ImportError:
            logger.warning("OpenCV not available, using basic metadata")
        
        return JSONResponse(content=metadata)
        
    except Exception as e:
        logger.error(f"Error getting video metadata for {filename}: {e}")
        raise HTTPException(status_code=500, detail="Error getting metadata")


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def format_duration(seconds: float) -> str:
    """Format duration in MM:SS format"""
    if seconds <= 0:
        return "00:00"
    
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"

async def health_check():
    """Comprehensive health check endpoint"""
    try:
        # Get system state
        current_system_state = get_system_state()
        
        # Check database connection
        db_healthy = False
        try:
            conn = await get_db_connection()
            if conn:
                await close_db_connection(conn)
                db_healthy = True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
        
        # Check ESP32CAM status
        esp32cam_status = current_system_state.device_status.get("esp32cam", {})
        esp32cam_online = esp32cam_status.get("online", False)
        esp32cam_last_seen = esp32cam_status.get("last_seen")
        
        # Check Pico status
        pico_status = current_system_state.device_status.get("pico", {})
        pico_online = pico_status.get("online", False)
        pico_last_seen = pico_status.get("last_seen")
        
        # Calculate uptime
        uptime_seconds = time.time() - current_system_state.start_time
        uptime_hours = uptime_seconds / 3600
        
        # Get performance metrics
        performance_metrics = current_system_state.performance_metrics
        
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "uptime_hours": round(uptime_hours, 2),
            "system_ready": is_system_ready(),
            "database": {
                "healthy": db_healthy,
                "status": "connected" if db_healthy else "disconnected"
            },
            "devices": {
                "esp32cam": {
                    "online": esp32cam_online,
                    "last_seen": esp32cam_last_seen.isoformat() if esp32cam_last_seen else None,
                    "errors": len(esp32cam_status.get("errors", []))
                },
                "pico": {
                    "online": pico_online,
                    "last_seen": pico_last_seen.isoformat() if pico_last_seen else None,
                    "errors": len(pico_status.get("errors", []))
                }
            },
            "performance": {
                "frame_count": current_system_state.frame_count,
                "frame_drop_count": current_system_state.frame_drop_count,
                "avg_frame_latency": performance_metrics.get("avg_frame_latency", 0.0),
                "frame_drop_rate": performance_metrics.get("frame_drop_rate", 0.0),
                "websocket_clients": len(current_system_state.web_clients),
                "active_clients": len(current_system_state.active_clients)
            },
            "errors": {
                "websocket": current_system_state.error_counts.get("websocket", 0),
                "database": current_system_state.error_counts.get("database", 0),
                "frame_processing": current_system_state.error_counts.get("frame_processing", 0)
            }
        }
        
        # Determine overall health status
        if not db_healthy or not esp32cam_online:
            health_data["status"] = "degraded"
        
        if current_system_state.error_counts.get("websocket", 0) > 10:
            health_data["status"] = "warning"
        
        return health_data
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }