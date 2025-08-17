#!/usr/bin/env python3
"""
Spy Servo FastAPI Server
Main entry point for the spy servo system with comprehensive device management,
authentication, WebSocket support, and security features.
"""

import os
import sys
import asyncio
import logging
import logging.config
import signal
import socket
import psutil
import subprocess
import time
import uvicorn
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from datetime import datetime

# Setup basic logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("server_fastapi")

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("✅ Environment variables loaded from .env file")
except ImportError:
    logger.warning("⚠️ python-dotenv not installed, using system environment variables")
except Exception as e:
    logger.warning(f"⚠️ Error loading .env file: {e}")

# FastAPI imports
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Import core modules
from core import (
    config, db, Security, sms, token, sanitize_validate, status,
    pico, esp32cam, OTP, google_auth, login_fun, websocket_manager,
    utils, system_manager, server_manager, client, error_handler,
    memory_manager
)
from core.config import set_templates, get_templates, is_test_environment, translations
from core.translations_ui import UI_TRANSLATIONS
from core.Security import set_dependencies as set_security_dependencies
from core.db import get_db_connection, close_db_connection

set_security_dependencies(
    log_func=None,  # اگر تابع لاگ دارید اینجا قرار دهید
    get_csrf_func=None,
    store_csrf_func=None,
    db_conn_func=get_db_connection,
    db_close_func=close_db_connection
)

# Import update_credentials function
from core.update_credentials import main as update_admin_credentials

# Import tools modules
from core.tools import JalaliFormatter, DynamicPortManager, port_router
from core.tools.config.jalali_log_config import LOGGING_CONFIG

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Setup environment variables
def setup_environment():
    """Setup and validate environment variables"""
    # Admin credentials are now handled by config.py automatically
    
    # Set default values for optional variables
    if not os.getenv('HOST'):
        os.environ['HOST'] = '0.0.0.0'
    # Note: PORT is now handled dynamically by the port manager (3000-9000)
    if not os.getenv('ALGORITHM'):
        os.environ['ALGORITHM'] = 'HS256'
    if not os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES'):
        os.environ['ACCESS_TOKEN_EXPIRE_MINUTES'] = '60'
    
    # Check for Google OAuth configuration
    google_client_id = os.getenv('GOOGLE_CLIENT_ID')
    google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    
    if not google_client_id or not google_client_secret:
        logger.warning("⚠️ Google OAuth not configured - GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables are optional")
    elif google_client_id == 'your-google-client-id' or google_client_secret == 'your-google-client-secret':
        logger.warning("⚠️ Google OAuth using default values - please configure proper credentials")
    else:
        logger.info("✅ Google OAuth configuration validated")
    
    # Log dynamic port configuration
    logger.info("🔧 Dynamic port management enabled - ports 3000-9000")
    logger.info("⚠️ PORT environment variable is ignored - using dynamic port allocation")

def update_server_credentials():
    """Update admin credentials using the update_credentials module"""
    try:
        logger.info("🔄 Checking and updating admin credentials...")
        update_admin_credentials()
        logger.info("✅ Admin credentials update completed")
    except Exception as e:
        logger.warning(f"⚠️ Admin credentials update failed: {e}")
        logger.info("ℹ️ Server will continue with existing credentials")

# Setup environment variables
setup_environment()



# Setup logging with Jalali formatter
try:
    logging.config.dictConfig(LOGGING_CONFIG)
    # Update the existing logger with Jalali configuration
    logger.info("✅ Jalali logging configured successfully")
except Exception as e:
    # Fallback to basic logging if Jalali config fails
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/server.log'),
            logging.StreamHandler()
        ]
    )
    logger.warning(f"⚠️ Jalali logging config failed, using basic logging: {e}")

# Global variables
app: Optional[FastAPI] = None
system_state: Optional[Any] = None
shutdown_event = asyncio.Event()
port_manager: Optional[DynamicPortManager] = None
templates: Optional[Jinja2Templates] = None
system_initialized = False
temp_state_warning_shown = False
current_server_port: Optional[int] = None

# تعریف کلاس BasicSystemState در سطح ماژول
class BasicSystemState:
    def __init__(self):
        self.start_time = time.time()
        # Locks will be initialized during async startup (lifespan)
        self.web_clients_lock = None
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
        self.server_processes = {}
        self.port_assignments = {}
        self.server_status = {}
        # Additional state fields initialized in lifespan
        self.frame_lock = None
        self.frame_buffer_lock = None
        self.performance_lock = None
        self.pico_client_lock = None
        self.esp32cam_client_lock = None
        self.frame_buffer = []
        self.frame_count = 0
        self.frame_drop_count = 0
        self.websocket_error_count = 0
        self.performance_metrics = {
            "avg_frame_latency": 0.0,
            "frame_drop_rate": 0.0,
            "frame_processing_overhead": 0.0
        }
        self.adaptive_quality = False
        self.current_quality = 80
        self.last_error_reset = time.time()
        # Add missing client attributes
        self.pico_client = None
        self.esp32cam_client = None
        self.sensor_data_buffer = []
        
        # ESP32CAM specific attributes
        self.processing_enabled = True
        self.invalid_frame_count = 0
        self.frame_skip_count = 0
        self.last_frame_time = time.time()
        self.video_quality = 80
        self.realtime_enabled = False
        self.frame_processing_times = []
        self.frame_cache = {}
        self.memory_warning_sent = False
        self.last_performance_update = time.time()
        self.last_backup_time = time.time()
        self.last_frame_cache_cleanup = time.time()
        self.last_cleanup_time = None
        
        # Performance monitoring attributes
        self.frame_latency_sum = 0.0
        self.processing_timeout = 5.0  # 5 seconds timeout for frame processing
        
        # Additional ESP32CAM attributes
        self.esp32cam_client_lock = None
        self.esp32cam_client = None
        self.pico_client_lock = None
        self.pico_client = None
        self.sensor_data_buffer = []
        
        # Additional performance attributes
        self.websocket_error_count = 0
        self.last_disk_space = 'N/A'
        self.memory_warning_sent = False
        self.last_performance_update = time.time()
        self.last_backup_time = time.time()
        self.last_frame_cache_cleanup = time.time()
        self.last_cleanup_time = None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def is_system_ready() -> bool:
    """Check if system is fully initialized"""
    global system_initialized, system_state
    return system_initialized and system_state is not None

# تابع helper برای دسترسی امن به system_state
def get_system_state_safe():
    global system_state
    if system_state is None:
        system_state = BasicSystemState()
    return ensure_system_state_attributes(system_state)

def ensure_system_state_attributes(system_state_obj):
    """Ensure all required attributes are present in system state"""
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
        'processing_enabled': True,
        'websocket_error_count': 0,
        'memory_warning_sent': False,
        'last_performance_update': time.time(),
        'last_backup_time': time.time(),
        'last_frame_cache_cleanup': time.time(),
        'last_cleanup_time': None,
        'pico_client': None,
        'esp32cam_client': None,
        'sensor_data_buffer': [],
        'pico_client_lock': None,
        'esp32cam_client_lock': None
    }
    
    for attr_name, default_value in required_attributes.items():
        if not hasattr(system_state_obj, attr_name):
            setattr(system_state_obj, attr_name, default_value)
            logger.info(f"Initialized missing attribute: {attr_name}")
    
    return system_state_obj

# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def tools_background_tasks():
    """Background tasks for tools management"""
    global port_manager
    while not shutdown_event.is_set():
        try:
            # Update port manager state periodically
            if port_manager:
                port_manager.background_refresh()
            
            # Log system status with Jalali timestamp
            if 'JalaliFormatter' in globals():
                jalali_logger = logging.getLogger("jalali_system")
                if is_system_ready():
                    jalali_logger.info("System status check - Tools background task running")
                else:
                    jalali_logger.info("System status check - Tools background task running (system initializing)")
            
            await asyncio.sleep(60)  # Run every minute
            
        except Exception as e:
            logger.error(f"Error in tools background tasks: {e}")
            await asyncio.sleep(30)  # Wait shorter time on error

# ============================================================================
# LIFECYCLE MANAGEMENT
# ============================================================================

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting up Spy Servo System...")
    try:
        # ایجاد دایرکتوری‌های لازم
        os.makedirs("logs", exist_ok=True)
        os.makedirs("static", exist_ok=True)
        os.makedirs("templates", exist_ok=True)
        # مقداردهی Jinja2Templates و ثبت global
        templates = Jinja2Templates(directory="templates")
        set_templates(templates)
        templates.env.filters['datetimeformat'] = datetimeformat  # افزودن فیلتر به محیط Jinja2
        templates.env.filters['translate_log_level'] = translate_log_level  # افزودن فیلتر ترجمه سطح لاگ
        logger.info("✅ Jinja2 templates initialized")
        # Initialize global system state and required locks/attributes
        global system_state, system_initialized
        if system_state is None:
            system_state = BasicSystemState()
            system_initialized = True
        
        # Ensure all required attributes are present
        system_state = ensure_system_state_attributes(system_state)
        
        # Initialize asyncio locks in async context if missing
        import asyncio as _asyncio
        if system_state.web_clients_lock is None:
            system_state.web_clients_lock = _asyncio.Lock()
        if system_state.frame_lock is None:
            system_state.frame_lock = _asyncio.Lock()
        if system_state.frame_buffer_lock is None:
            system_state.frame_buffer_lock = _asyncio.Lock()
        if system_state.performance_lock is None:
            system_state.performance_lock = _asyncio.Lock()
        if system_state.pico_client_lock is None:
            system_state.pico_client_lock = _asyncio.Lock()
        if system_state.esp32cam_client_lock is None:
            system_state.esp32cam_client_lock = _asyncio.Lock()

        # Wire system state into submodules and set cross-module deps (best-effort)
        try:
            from core import client as _client, pico as _pico, esp32cam as _esp32cam, db as _db, status as _status
            # Provide shared system state
            if hasattr(_pico, 'set_system_state'):
                _pico.set_system_state(system_state)
            if hasattr(_esp32cam, 'set_system_state'):
                _esp32cam.set_system_state(system_state)
            # Ensure client has comm functions
            if hasattr(_client, 'set_microcontroller_deps'):
                # Use functions provided by submodules if available
                pico_send = getattr(_pico, 'send_to_pico_client', None)
                esp_send = getattr(_esp32cam, 'send_to_esp32cam_client', None)
                if pico_send or esp_send:
                    _client.set_microcontroller_deps(pico_send, esp_send)
            # Ensure DB and status modules see the same state
            if hasattr(_db, 'set_system_state'):
                _db.set_system_state(system_state)
            if hasattr(_status, 'set_system_state'):
                _status.set_system_state(system_state)
        except Exception as dep_err:
            logger.warning(f"Dependency wiring warning: {dep_err}")

        # ... سایر مقداردهی‌ها ...
        logger.info("✅ Startup completed")
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        raise

    yield

    logger.info("🛑 Shutting down Spy Servo System...")
    try:
        # ... cleanup ...
        logger.info("✅ Shutdown completed")
    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")

# مقداردهی app در سطح ماژول
app = FastAPI(
    title="Spy Servo System",
    version="1.0.0",
    lifespan=lifespan
)

# ============================================================================
# FASTAPI APPLICATION SETUP
# ============================================================================

def datetimeformat(value, lang="fa"):
    from datetime import datetime
    if not value:
        return ""
    try:
        dt = value
        if not isinstance(dt, datetime):
            dt = datetime.fromisoformat(str(value))
        if lang == "fa":
            return dt.strftime("%Y-%m-%d %H:%M")
        else:
            return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)

def translate_log_level(level, lang="fa"):
    """Translate log level to the target language (default: fa)"""
    translations = {
        "fa": {
            "info": "اطلاعات",
            "warning": "هشدار",
            "error": "خطا",
            "critical": "بحرانی",
            "debug": "اشکال‌زدایی",
            "success": "موفقیت",
        },
        "en": {
            "info": "Info",
            "warning": "Warning",
            "error": "Error",
            "critical": "Critical",
            "debug": "Debug",
            "success": "Success",
        }
    }
    level = (level or "").lower()
    return translations.get(lang, translations["en"]).get(level, level)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    global app
    
    # Create FastAPI app with lifespan
    app = FastAPI(
        title="Spy Servo System",
        description="Comprehensive surveillance and device management system",
        version="1.0.0",
        docs_url="/docs" if is_test_environment() else None,
        redoc_url="/redoc" if is_test_environment() else None,
        lifespan=lifespan
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configure appropriately for production
    )
    
    # Mount static files
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # Setup templates
    global templates
    templates = Jinja2Templates(directory="templates")
    templates.env.filters['datetimeformat'] = datetimeformat
    templates.env.filters['translate_log_level'] = translate_log_level
    
    # Add template context processor
    @app.middleware("http")
    async def add_template_context(request: Request, call_next):
        request.state.templates = templates
        response = await call_next(request)
        return response
    
    # Add Jalali logging middleware
    @app.middleware("http")
    async def jalali_logging_middleware(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log with Jalali timestamp if available
        try:
            if 'JalaliFormatter' in globals():
                jalali_logger = logging.getLogger("jalali_access")
                jalali_logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
            else:
                logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
        except Exception as e:
            logger.warning(f"Error in Jalali logging middleware: {e}")
        
        return response
    
    # Register exception handlers (if functions exist)
    if hasattr(error_handler, 'http_exception_handler'):
        app.add_exception_handler(HTTPException, error_handler.http_exception_handler)
    if hasattr(error_handler, 'validation_exception_handler'):
        app.add_exception_handler(RequestValidationError, error_handler.validation_exception_handler)
    if hasattr(error_handler, 'starlette_http_exception_handler'):
        app.add_exception_handler(StarletteHTTPException, error_handler.starlette_http_exception_handler)
    if hasattr(error_handler, 'global_exception_handler'):
        app.add_exception_handler(Exception, error_handler.global_exception_handler)
    
    # Register routes
    register_all_routes(app, templates)
    
    # Create application routes
    create_routes(app)
    
    return app

def create_camera_app() -> FastAPI:
    """Create and configure the camera FastAPI application"""
    
    # Create FastAPI app for camera server
    camera_app = FastAPI(
        title="Camera Server",
        description="Camera streaming and control server",
        version="1.0.0",
        docs_url="/docs" if is_test_environment() else None,
        redoc_url="/redoc" if is_test_environment() else None
    )
    
    # Initialize ESP32CAM module with system state and dependencies
    try:
        from core.esp32cam import set_system_state as _set_cam_state, get_system_state as _get_cam_state, set_dependencies as _set_cam_deps
        from core.client import get_system_state as _get_client_state
        from core.db import insert_log
        from core.client import create_security_video_async

        # Prefer the main client's shared system_state if available so both servers share the same state
        try:
            shared_state = _get_client_state()
        except Exception:
            shared_state = None

        current_system_state = shared_state or _get_cam_state()

        # Ensure critical locks and attributes exist to avoid race conditions on first frames
        try:
            import asyncio
            if not hasattr(current_system_state, 'frame_lock') or current_system_state.frame_lock is None:
                current_system_state.frame_lock = asyncio.Lock()
            if not hasattr(current_system_state, 'frame_buffer_lock') or current_system_state.frame_buffer_lock is None:
                current_system_state.frame_buffer_lock = asyncio.Lock()
            if not hasattr(current_system_state, 'web_clients_lock') or current_system_state.web_clients_lock is None:
                current_system_state.web_clients_lock = asyncio.Lock()
            if not hasattr(current_system_state, 'web_clients') or current_system_state.web_clients is None:
                current_system_state.web_clients = []
            if not hasattr(current_system_state, 'active_clients') or current_system_state.active_clients is None:
                current_system_state.active_clients = []
            if not hasattr(current_system_state, 'device_status') or current_system_state.device_status is None:
                current_system_state.device_status = {"esp32cam": {"online": False, "last_seen": None, "errors": []}}
            
            # Ensure ESP32CAM specific attributes exist
            if not hasattr(current_system_state, 'processing_enabled'):
                current_system_state.processing_enabled = True
            if not hasattr(current_system_state, 'invalid_frame_count'):
                current_system_state.invalid_frame_count = 0
            if not hasattr(current_system_state, 'frame_skip_count'):
                current_system_state.frame_skip_count = 0
            if not hasattr(current_system_state, 'last_frame_time'):
                current_system_state.last_frame_time = time.time()
            if not hasattr(current_system_state, 'video_quality'):
                current_system_state.video_quality = 80
            if not hasattr(current_system_state, 'realtime_enabled'):
                current_system_state.realtime_enabled = False
            if not hasattr(current_system_state, 'frame_processing_times'):
                current_system_state.frame_processing_times = []
            if not hasattr(current_system_state, 'frame_cache'):
                current_system_state.frame_cache = {}
            if not hasattr(current_system_state, 'memory_warning_sent'):
                current_system_state.memory_warning_sent = False
            if not hasattr(current_system_state, 'last_performance_update'):
                current_system_state.last_performance_update = time.time()
            if not hasattr(current_system_state, 'last_backup_time'):
                current_system_state.last_backup_time = time.time()
            if not hasattr(current_system_state, 'last_frame_cache_cleanup'):
                current_system_state.last_frame_cache_cleanup = time.time()
            if not hasattr(current_system_state, 'last_cleanup_time'):
                current_system_state.last_cleanup_time = None
                
        except Exception as _e:
            logger.warning(f"⚠️ Failed to ensure shared locks/state for camera server: {_e}")

        _set_cam_state(current_system_state)
        _set_cam_deps(insert_log, create_security_video_async)
        logger.info("✅ ESP32CAM module initialized with shared system state and dependencies")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize ESP32CAM module: {e}")
    
    # Add middleware for camera server
    camera_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    camera_app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]
    )
    
    # Import WebSocket dependencies
    from fastapi import WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse
    
    # Add camera-specific routes
    @camera_app.get("/")
    async def camera_root():
        return {"message": "Camera Server is running", "port": 3001}
    
    @camera_app.get("/status")
    async def camera_status():
        return {"status": "active", "server": "camera", "port": 3001}
    
    @camera_app.get("/stream")
    async def camera_stream():
        # Placeholder for camera streaming endpoint
        return {"message": "Camera stream endpoint", "status": "ready"}
    
    @camera_app.get("/capture")
    async def camera_capture():
        # Placeholder for camera capture endpoint
        return {"message": "Camera capture endpoint", "status": "ready"}
    
    @camera_app.get("/ws-test")
    async def websocket_test():
        """Test endpoint to check WebSocket availability"""
        return {
            "message": "WebSocket endpoints available",
            "endpoints": [
                "/ws/esp32cam",
                "/ws/camera"
            ],
            "status": "ready"
        }
    
    @camera_app.get("/esp32cam-status")
    async def esp32cam_status():
        """Get ESP32CAM device status"""
        try:
            from core.esp32cam import get_system_state
            system_state = get_system_state()
            return {
                "device": "ESP32CAM",
                "status": system_state.device_status.get("esp32cam", {}),
                "online": system_state.device_status.get("esp32cam", {}).get("online", False),
                "last_seen": system_state.device_status.get("esp32cam", {}).get("last_seen"),
                "errors": system_state.device_status.get("esp32cam", {}).get("errors", [])
            }
        except Exception as e:
            return {
                "device": "ESP32CAM",
                "status": "error",
                "error": str(e)
            }
    
    # WebSocket endpoint for ESP32CAM - Integrated with core/esp32cam.py
    @camera_app.websocket("/ws/esp32cam")
    async def websocket_esp32cam(websocket: WebSocket):
        # Import ESP32CAM functions
        try:
            from core.esp32cam import esp32cam_websocket_endpoint, set_system_state, get_system_state
            
            # Get current system state and set it for ESP32CAM module
            current_system_state = get_system_state()
            set_system_state(current_system_state)
            
            # Use the original ESP32CAM WebSocket handler
            await esp32cam_websocket_endpoint(websocket)
            
        except ImportError as e:
            logger.error(f"❌ Failed to import ESP32CAM module: {e}")
            await websocket.close(code=1000, reason="ESP32CAM module not available")
        except Exception as e:
            logger.error(f"❌ ESP32CAM WebSocket error: {e}")
            await websocket.close(code=1000, reason="Internal server error")
    
    # WebSocket endpoint for general camera connections
    @camera_app.websocket("/ws/camera")
    async def websocket_camera(websocket: WebSocket):
        await websocket.accept()
        logger.info("📷 Camera WebSocket connection established")
        
        try:
            while True:
                # Receive message from camera client
                data = await websocket.receive_text()
                logger.info(f"📷 Received from camera client: {data}")
                
                # Echo back for testing
                await websocket.send_text(f"Camera server received: {data}")
                
        except WebSocketDisconnect:
            logger.info("📷 Camera WebSocket disconnected")
        except Exception as e:
            logger.error(f"❌ Camera WebSocket error: {e}")
    
    return camera_app

def register_all_routes(app: FastAPI, templates: Jinja2Templates):
    """Register all application routes"""
    
    # Initialize system state for all modules
    global system_state, system_initialized
    if system_state is None:
        logger.info("🔧 Initializing system state for modules...")
        system_state = BasicSystemState()
        system_initialized = True
    
    # Set system state for all modules
    try:
        client.set_app_and_state(app, system_state)
        db.set_system_state(system_state)
        status.set_system_state(system_state)
        # Ensure OTP module receives the shared system state and dependencies
        try:
            if hasattr(OTP, 'set_system_state'):
                OTP.set_system_state(system_state)
        except Exception as otp_state_err:
            logger.warning(f"⚠️ Error setting OTP system state: {otp_state_err}")
        logger.info("✅ System state set for all modules")
    except Exception as e:
        logger.warning(f"⚠️ Error setting system state for modules: {e}")
    
    # Register core module routes
    client.register_routes_with_app(app)
    
    # Wire dependent functions for Pico module (DB inserts, logging, and ESP32CAM dispatch)
    try:
        if hasattr(pico, 'set_dependencies'):
            pico.set_dependencies(db.insert_log, db.insert_servo_command, db.insert_action_command)
        if hasattr(pico, 'set_esp32cam_dependency') and hasattr(esp32cam, 'send_to_esp32cam_client'):
            pico.set_esp32cam_dependency(esp32cam.send_to_esp32cam_client)
        logger.info("✅ Pico dependencies wired successfully")
    except Exception as dep_err:
        logger.warning(f"⚠️ Pico dependency wiring failed: {dep_err}")

    # Register device routes (if functions exist)
    if hasattr(pico, 'register_pico_routes'):
        pico.register_pico_routes(app)
    if hasattr(esp32cam, 'register_esp32cam_routes'):
        esp32cam.register_esp32cam_routes(app)
    if hasattr(status, 'register_status_routes'):
        status.register_status_routes(app)
    
    # Register authentication routes (if functions exist)
    if hasattr(login_fun, 'register_auth_routes'):
        login_fun.register_auth_routes(app)
    if hasattr(google_auth, 'register_google_auth_routes'):
        # Wire Google Auth system state and dependencies before registering routes
        try:
            if hasattr(google_auth, 'set_system_state'):
                google_auth.set_system_state(system_state)
            if hasattr(db, 'insert_log') and hasattr(google_auth, 'set_dependencies'):
                # create_user_func and verify_password_hash_func are not needed currently
                google_auth.set_dependencies(db.insert_log, None, None)
        except Exception as ga_err:
            logger.warning(f"⚠️ Could not set Google Auth dependencies: {ga_err}")
        google_auth.register_google_auth_routes(app)
    if hasattr(OTP, 'register_otp_routes'):
        # Best-effort to wire OTP dependencies (logging) before route registration
        try:
            if hasattr(db, 'insert_log') and hasattr(OTP, 'set_dependencies'):
                OTP.set_dependencies(db.insert_log, None)
        except Exception as otp_dep_err:
            logger.warning(f"⚠️ Could not set OTP dependencies: {otp_dep_err}")
        OTP.register_otp_routes(app)
    
    # Register security routes (if function exists)
    if hasattr(Security, 'register_security_routes'):
        Security.register_security_routes(app)
    
    # Register utility routes (if function exists)
    if hasattr(utils, 'register_utility_routes'):
        utils.register_utility_routes(app)
    
    # Register system management routes (if function exists)
    if hasattr(system_manager, 'register_system_routes'):
        system_manager.register_system_routes(app)
    
    # Register database routes (if function exists)
    if hasattr(db, 'register_db_routes'):
        db.register_db_routes(app)
    
    # Register SMS routes (if function exists)
    if hasattr(sms, 'register_sms_routes'):
        sms.register_sms_routes(app)
    
    # Register token routes (if function exists)
    if hasattr(token, 'register_token_routes'):
        token.register_token_routes(app)
    
    # Register validation routes (if function exists)
    if hasattr(sanitize_validate, 'register_validation_routes'):
        sanitize_validate.register_validation_routes(app)
    
    # Register WebSocket routes (if function exists)
    if hasattr(websocket_manager, 'register_websocket_routes'):
        websocket_manager.register_websocket_routes(app)
    
    # Register memory management routes (if function exists)
    if hasattr(memory_manager, 'register_memory_routes'):
        memory_manager.register_memory_routes(app)
    
    # Register error handling routes (if function exists)
    if hasattr(error_handler, 'register_error_routes'):
        error_handler.register_error_routes(app)
    
    # Register tools routes
    app.include_router(port_router, prefix="/api/v1/ports", tags=["Port Management"])


# ============================================================================
# ROUTE DEFINITIONS
# ============================================================================

def create_routes(app: FastAPI):
    """Create and register all application routes"""
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        current_system_state = get_system_state_safe()
        return {
            "status": "healthy" if is_system_ready() else "initializing",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "uptime": time.time() - current_system_state.start_time if current_system_state else 0,
            "port_manager_status": "active" if port_manager else "inactive",
            "system_ready": is_system_ready()
        }
    
    # Tools integration endpoints
    @app.get("/api/v1/tools/port/pick")
    async def pick_port():
        """Pick a free port using dynamic port manager"""
        if not port_manager:
            raise HTTPException(status_code=503, detail="Port manager not available")
        try:
            port = port_manager.pick_port()
            return {"port": port, "status": "success"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to pick port: {e}")
    
    @app.get("/api/v1/tools/port/release")
    async def release_port():
        """Release the current port"""
        if not port_manager:
            raise HTTPException(status_code=503, detail="Port manager not available")
        try:
            port_manager.release_port()
            return {"status": "success", "message": "Port released"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to release port: {e}")
    
    @app.get("/api/v1/tools/port/state")
    async def get_port_state():
        """Get current port manager state"""
        if not port_manager:
            raise HTTPException(status_code=503, detail="Port manager not available")
        try:
            return port_manager.get_state()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get port state: {e}")
    
    @app.get("/api/v1/tools/jalali/now")
    async def get_jalali_now():
        """Get current Jalali date and time"""
        try:
            from persiantools.jdatetime import JalaliDateTime
            dt = datetime.now()
            jdt = JalaliDateTime.to_jalali(dt)
            return {
                "jalali_date": jdt.strftime('%Y/%m/%d'),
                "jalali_time": jdt.strftime('%H:%M:%S'),
                "jalali_datetime": jdt.strftime('%Y/%m/%d %H:%M:%S'),
                "gregorian_date": dt.strftime('%Y-%m-%d'),
                "gregorian_time": dt.strftime('%H:%M:%S'),
                "system_ready": is_system_ready()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get Jalali date: {e}")
    
    @app.get("/api/v1/tools/jalali/status")
    async def get_jalali_status():
        """Get Jalali system status"""
        try:
            from persiantools.jdatetime import JalaliDateTime
            dt = datetime.now()
            jdt = JalaliDateTime.to_jalali(dt)
            return {
                "jalali_system": "active",
                "current_jalali": jdt.strftime('%Y/%m/%d %H:%M:%S'),
                "current_gregorian": dt.strftime('%Y-%m-%d %H:%M:%S'),
                "system_ready": is_system_ready(),
                "jalali_logging_active": "JalaliFormatter" in globals(),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "jalali_system": "error",
                "error": str(e),
                "system_ready": is_system_ready(),
                "timestamp": datetime.now().isoformat()
            }
    
    @app.get("/api/v1/tools/info")
    async def get_tools_info():
        """Get information about available tools"""
        return {
            "available_tools": {
                "jalali_formatter": "Persian/Jalali date formatting",
                "dynamic_port_manager": "Dynamic port allocation and management",
                "port_router": "Port management API endpoints",
                "jalali_logging": "Persian date logging configuration",
                "credentials_update": "Admin credentials management and update"
            },
            "port_manager_status": "active" if port_manager else "inactive",
            "jalali_logging": "active" if "JalaliFormatter" in globals() else "inactive",
            "system_status": "ready" if is_system_ready() else "inactive"
        }
    
    @app.post("/api/v1/tools/credentials/update")
    async def update_credentials_endpoint():
        """Manually trigger admin credentials update"""
        try:
            update_server_credentials()
            return {
                "status": "success",
                "message": "Admin credentials updated successfully",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to update credentials: {str(e)}"
            )
    
    @app.get("/api/v1/system/status")
    async def get_system_status():
        """Get detailed system status"""
        current_system_state = get_system_state_safe()
        return {
            "system_ready": is_system_ready(),
            "initialization_status": "complete" if is_system_ready() else "in_progress",
            "uptime": time.time() - current_system_state.start_time if current_system_state else 0,
            "port_manager_active": port_manager is not None,
            "database_initialized": getattr(current_system_state, 'db_initialized', False),
            "websocket_manager_active": hasattr(websocket_manager, 'initialize_websocket_manager'),
            "background_tasks_active": hasattr(system_manager, 'start_background_tasks'),
            "credentials_manager_active": True,
            "timestamp": datetime.now().isoformat()
        }
    
    # Root endpoint
    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request):
        """Root endpoint - redirects to login or dashboard
        Note: The actual index/login routing is also registered in core.client.register_routes_with_app.
        This root keeps backward compatibility and passes translations config.
        """
        try:
            user = await token.get_current_user(request)
            lang = request.cookies.get('language', 'fa')
            context = {"request": request, "translations": translations, "lang": lang}
            return templates.TemplateResponse("index.html" if user else "login.html", context)
        except Exception:
            lang = request.cookies.get('language', 'fa')
            return templates.TemplateResponse("login.html", {"request": request, "translations": translations, "lang": lang})
    
    # System overview endpoint
    @app.get("/api/v1/system/overview")
    async def get_system_overview():
        """Get comprehensive system overview"""
        current_system_state = get_system_state_safe()
        return {
            "server_status": "running",
            "system_ready": is_system_ready(),
            "initialization_status": "complete" if is_system_ready() else "in_progress",
            "uptime_seconds": time.time() - current_system_state.start_time if current_system_state else 0,
            "uptime_formatted": f"{(time.time() - current_system_state.start_time) / 3600:.1f} hours" if current_system_state else "N/A",
            "components": {
                "database": "active",
                "port_manager": "active" if port_manager else "inactive",
                "jalali_logging": "active" if "JalaliFormatter" in globals() else "inactive",
                "websocket_manager": "active" if hasattr(websocket_manager, 'initialize_websocket_manager') else "inactive",
                "background_tasks": "active" if hasattr(system_manager, 'start_background_tasks') else "inactive",
                "credentials_manager": "active"
            },
            "jalali_timestamp": "1404/05/20" if "JalaliFormatter" in globals() else "N/A",
            "timestamp": datetime.now().isoformat()
        }
    
    @app.get("/api/v1/server/port")
    async def get_server_port():
        """Get current server port information"""
        try:
            if port_manager:
                current_port = port_manager.get_current_port()
                port_state = port_manager.get_state()
                return {
                    "current_port": current_port or current_server_port,
                    "port_manager_status": "active",
                    "port_range": {
                        "start": port_manager.start,
                        "end": port_manager.end
                    },
                    "available_ports": len(port_state.get("available_ports", [])),
                    "used_ports": len(port_state.get("used_ports", [])),
                    "port_state": port_state,
                    "server_port": current_server_port,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "current_port": current_server_port,
                    "port_manager_status": "inactive",
                    "error": "Port manager not available",
                    "server_port": current_server_port,
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            return {
                "current_port": current_server_port,
                "port_manager_status": "error",
                "error": str(e),
                "server_port": current_server_port,
                "timestamp": datetime.now().isoformat()
            }
    
    @app.post("/api/v1/server/port/change")
    async def change_server_port():
        """Manually change server port using dynamic port manager"""
        global current_server_port
        
        try:
            if not port_manager:
                raise HTTPException(status_code=503, detail="Port manager not available")
            
            # Release current port
            old_port = current_server_port
            if old_port:
                try:
                    port_manager.release_port()
                    logger.info(f"🔄 Released old port: {old_port}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to release old port {old_port}: {e}")
            
            # Pick new port
            new_port = port_manager.pick_port()
            current_server_port = new_port
            
            logger.info(f"🔄 Server port changed from {old_port} to {new_port}")
            
            return {
                "status": "success",
                "message": f"Port changed from {old_port} to {new_port}",
                "old_port": old_port,
                "new_port": new_port,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to change port: {str(e)}"
            )

    @app.get("/csrf-token")
    async def csrf_token_endpoint(request: Request):
        from core.Security import get_csrf_token
        return await get_csrf_token(request)

# ============================================================================
# SIGNAL HANDLERS
# ============================================================================

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if hasattr(signal, 'SIGBREAK'):  # Windows
        signal.signal(signal.SIGBREAK, signal_handler)

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point for the server"""
    # Declare variables that might be used in exception handlers
    global system_state, port_manager, current_server_port, system_initialized
    app = None
    port = 3000
    
    try:
        # Setup signal handlers
        setup_signal_handlers()
        
        # Create application
        try:
            app = create_app()
            logger.info("✅ FastAPI application created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create FastAPI application: {e}")
            raise
        
        # Get server configuration
        host = os.getenv("HOST", "0.0.0.0")
        reload = os.getenv("RELOAD", "false").lower() == "true"
        
        # Initialize basic system state immediately
        if system_state is None:
            logger.info("🔧 Initializing basic system state...")
            system_state = BasicSystemState()
            system_initialized = True
            logger.info("✅ Basic system state initialized")
        
        # Initialize port manager if not available
        if port_manager is None:
            try:
                logger.info("🔧 Initializing port manager...")
                os.makedirs("core/tools/port_state", exist_ok=True)
                port_manager = DynamicPortManager(
                    start=3000, 
                    end=9000, 
                    json_path="core/tools/port_state/dynamic_ports.json",
                    refresh_interval=60, 
                    enable_background_logging=False
                )
                logger.info("✅ Port manager initialized in main function")
            except Exception as e:
                logger.warning(f"⚠️ Port manager initialization failed: {e}")
                logger.info("ℹ️ Server will continue with fallback port management")
                port_manager = None
        
        # Enhanced port selection with conflict resolution and Windows compatibility
        port = select_available_port_sync(host, port_manager)
        current_server_port = port
        
        # Kill existing server processes if running
        try:
            if hasattr(server_manager, 'kill_existing_server'):
                server_manager.kill_existing_server()
                logger.info("✅ Existing server processes cleaned up")
            else:
                logger.warning("⚠️ server_manager.kill_existing_server method not found")
        except Exception as e:
            logger.warning(f"⚠️ Failed to kill existing server: {e}")
            logger.info("ℹ️ Continuing with server startup...")
        
        # Additional Windows-specific port cleanup
        if os.name == 'nt':  # Windows
            try:
                import subprocess
                # Kill any processes using the selected port
                result = subprocess.run(
                    ['netstat', '-ano'], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if f":{port}" in line and "LISTENING" in line:
                            parts = line.split()
                            if len(parts) >= 5:
                                pid = parts[-1]
                                try:
                                    subprocess.run(
                                        ['taskkill', '/PID', pid, '/F'], 
                                        capture_output=True, 
                                        timeout=10
                                    )
                                    logger.info(f"✅ Killed Windows process (PID: {pid}) using port {port}")
                                except Exception as e:
                                    logger.warning(f"⚠️ Failed to kill Windows process: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Windows port cleanup failed: {e}")
        
        # Final health check before starting server
        logger.info("🔍 Performing final health check...")
        if system_state and system_initialized:
            logger.info("✅ System state: Ready")
        else:
            logger.warning("⚠️ System state: Not fully ready, but continuing...")
        
        if port_manager:
            logger.info("✅ Port manager: Active")
        else:
            logger.warning("⚠️ Port manager: Inactive, using fallback")
        
        # Start server with enhanced error handling
        logger.info(f"🚀 Starting server on {host}:{port}")
        logger.info(f"📊 Port manager status: {'active' if port_manager else 'inactive'}")
        logger.info(f"🔧 Dynamic port range: 3000-9000")
        logger.info(f"🎯 Current server port: {current_server_port}")
        logger.info("🎉 System initialization completed successfully!")
        
        # Start camera server on port 3001 first
        try:
            logger.info("📷 Starting camera server on port 3001...")
            camera_app = create_camera_app()
            logger.info("✅ Camera FastAPI application created successfully")
            
            # Start camera server in background thread
            import threading
            def run_camera_server():
                try:
                    logger.info("📷 Camera server thread started")
                    uvicorn.run(
                        camera_app,
                        host=host,
                        port=3001,
                        reload=False,  # Camera server with reload=False
                        log_level="info",
                        access_log=True,
                        workers=1,
                        loop="asyncio",
                        timeout_keep_alive=30,
                        timeout_graceful_shutdown=30
                    )
                except Exception as e:
                    logger.error(f"❌ Camera server error: {e}")
            
            camera_thread = threading.Thread(target=run_camera_server, daemon=True)
            camera_thread.start()
            logger.info("✅ Camera server thread started successfully on port 3001")
            
        except Exception as e:
            logger.error(f"❌ Failed to start camera server: {e}")
            logger.warning("⚠️ Camera server failed to start, but main server continues...")
        
        # Wait a moment for camera server to start
        import time
        time.sleep(2)
        
        try:
            logger.info(f"🎯 Attempting to start main uvicorn server on {host}:{port}")
            logger.info(f"🔧 App object type: {type(app)}")
            logger.info(f"🔧 App ready: {app is not None}")
            
            # Enhanced uvicorn configuration with reload=False for background operation
            uvicorn.run(
                app,
                host=host,
                port=port,
                reload=False,  # Set to False for background operation
                log_level="info",
                access_log=True,
                workers=1,
                loop="asyncio",
                timeout_keep_alive=30,
                timeout_graceful_shutdown=30
            )
        except Exception as e:
            logger.error(f"❌ Failed to start uvicorn server: {e}")
            logger.error(f"❌ Error type: {type(e)}")
            logger.error(f"❌ Error details: {str(e)}")
            import traceback
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            raise
        
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
        # Release the port when stopping
        if port_manager:
            try:
                port_manager.release_port()
                logger.info("✅ Port released successfully")
            except Exception as e:
                logger.warning(f"⚠️ Failed to release port: {e}")
        else:
            logger.info("ℹ️ No port manager to release port from")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        # Release the port on error
        if port_manager:
            try:
                port_manager.release_port()
                logger.info("✅ Port released on error")
            except Exception as release_error:
                logger.warning(f"⚠️ Failed to release port on error: {release_error}")
        else:
            logger.info("ℹ️ No port manager to release port from on error")
        #sys.exit(1)
        pass

def select_available_port_sync(host: str, port_manager) -> int:
    """
    Enhanced port selection with conflict resolution and port freeing (synchronous version)
    """
    # Priority ports to try first
    priority_ports = [3000, 8000, 8080, 5000, 3001, 3002]
    
    # First, try to free port 3000 if it's occupied
    if is_port_occupied_sync(3000):
        logger.warning(f"⚠️ Port 3000 is occupied, attempting to free it...")
        if free_port_sync(3000):
            logger.info(f"✅ Port 3000 freed successfully")
        else:
            logger.warning(f"⚠️ Could not free port 3000, will try alternative ports")
    
    # Try priority ports first
    for port in priority_ports:
        if is_port_available_sync(host, port):
            logger.info(f"✅ Priority port {port} is available")
            # Update port manager state if available
            if port_manager:
                try:
                    port_manager.state["پورت_فعلی"] = port
                    port_manager.state["پورت_های_آزاد"] = [p for p in port_manager.state.get("پورت_های_آزاد", []) if p != port]
                    used_ports = port_manager.state.get("پورت_های_اشغال", [])
                    if port not in used_ports:
                        used_ports.append(port)
                    port_manager.state["پورت_های_اشغال"] = used_ports
                    port_manager._save_state()
                except Exception as e:
                    logger.warning(f"⚠️ Could not update port manager state: {e}")
            return port
    
    # If no priority ports available, try dynamic port selection
    if port_manager:
        try:
            # Force refresh of port manager state
            port_manager.find_free_ports(count=50)
            port = port_manager.pick_port()
            logger.info(f"🎯 Dynamic port manager selected port: {port}")
            return port
        except Exception as e:
            logger.warning(f"⚠️ Dynamic port manager failed: {e}")
    
    # Fallback: scan for any available port
    for port in range(3000, 9000):
        if is_port_available_sync(host, port):
            logger.info(f"🔍 Found available fallback port: {port}")
            return port
    
    # Last resort: use a random high port
    import random
    fallback_port = random.randint(8000, 9000)
    logger.warning(f"⚠️ No ports available in range 3000-9000, using fallback: {fallback_port}")
    return fallback_port

async def select_available_port(host: str, port_manager) -> int:
    """
    Enhanced port selection with conflict resolution and port freeing (async version)
    """

    
    # Priority ports to try first
    priority_ports = [3000, 8000, 8080, 5000, 3001, 3002]
    
    # First, try to free port 3000 if it's occupied
    if await is_port_occupied(3000):
        logger.warning(f"⚠️ Port 3000 is occupied, attempting to free it...")
        if await free_port(3000):
            logger.info(f"✅ Port 3000 freed successfully")
        else:
            logger.warning(f"⚠️ Could not free port 3000, will try alternative ports")
    
    # Try priority ports first
    for port in priority_ports:
        if await is_port_available(host, port):
            logger.info(f"✅ Priority port {port} is available")
            # Update port manager state if available
            if port_manager:
                try:
                    port_manager.state["پورت_فعلی"] = port
                    port_manager.state["پورت_های_آزاد"] = [p for p in port_manager.state.get("پورت_های_آزاد", []) if p != port]
                    used_ports = port_manager.state.get("پورت_های_اشغال", [])
                    if port not in used_ports:
                        used_ports.append(port)
                    port_manager.state["پورت_های_اشغال"] = used_ports
                    port_manager._save_state()
                except Exception as e:
                    logger.warning(f"⚠️ Could not update port manager state: {e}")
            return port
    
    # If no priority ports available, try dynamic port selection
    if port_manager:
        try:
            # Force refresh of port manager state
            port_manager.find_free_ports(count=50)
            port = port_manager.pick_port()
            logger.info(f"🎯 Dynamic port manager selected port: {port}")
            return port
        except Exception as e:
            logger.warning(f"⚠️ Dynamic port manager failed: {e}")
    
    # Fallback: scan for any available port
    for port in range(3000, 9000):
        if await is_port_available(host, port):
            logger.info(f"🔍 Found available fallback port: {port}")
            return port
    
    # Last resort: use a random high port
    import random
    fallback_port = random.randint(8000, 9000)
    logger.warning(f"⚠️ No ports available in range 3000-9000, using fallback: {fallback_port}")
    return fallback_port

def is_port_available_sync(host: str, port: int) -> bool:
    """Check if a port is available for binding (synchronous version)"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            return True
    except Exception:
        return False

async def is_port_available(host: str, port: int) -> bool:
    """Check if a port is available for binding (async version)"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            return True
    except Exception:
        return False

def is_port_occupied_sync(port: int) -> bool:
    """Check if a port is occupied by any process (synchronous version)"""
    try:
        import psutil
        for conn in psutil.net_connections():
            if conn.laddr.port == port:
                return True
        return False
    except ImportError:
        # Fallback method without psutil
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("", port))
                sock.close()
                return False
        except OSError:
            return True
        except Exception:
            return True

async def is_port_occupied(port: int) -> bool:
    """Check if a port is occupied by any process (async version)"""
    try:
        import psutil
        for conn in psutil.net_connections():
            if conn.laddr.port == port:
                return True
        return False
    except ImportError:
        # Fallback method without psutil
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("", port))
                sock.close()
                return False
        except OSError:
            return True
        except Exception:
            return True

def free_port_sync(port: int) -> bool:
    """Attempt to free a port by killing processes using it (synchronous version)"""
    try:
        import psutil
        import subprocess
        import platform
        
        # Find processes using the port
        processes_to_kill = []
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    processes_to_kill.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        
        # Kill processes using the port
        killed_count = 0
        for proc in processes_to_kill:
            try:
                proc_name = proc.name()
                proc.terminate()
                proc.wait(timeout=5)
                logger.info(f"✅ Terminated process {proc_name} (PID: {proc.pid}) using port {port}")
                killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                try:
                    proc.kill()
                    logger.info(f"✅ Force killed process (PID: {proc.pid}) using port {port}")
                    killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        
        if killed_count > 0:
            # Wait a bit for the port to be freed
            time.sleep(1)
            
            # Verify port is now free
            if is_port_available_sync("0.0.0.0", port):
                logger.info(f"✅ Port {port} is now available after freeing")
                return True
            else:
                logger.warning(f"⚠️ Port {port} still not available after freeing")
                return False
        
        # If no processes found, try system-specific commands
        if platform.system() == "Windows":
            try:
                # Windows: use netstat to find and kill processes
                result = subprocess.run(
                    ["netstat", "-ano"], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if f":{port}" in line and "LISTENING" in line:
                            parts = line.split()
                            if len(parts) >= 5:
                                pid = parts[-1]
                                try:
                                    subprocess.run(
                                        ["taskkill", "/PID", pid, "/F"], 
                                        capture_output=True, 
                                        timeout=10
                                    )
                                    logger.info(f"✅ Killed Windows process (PID: {pid}) using port {port}")
                                    time.sleep(1)
                                    if is_port_available_sync("0.0.0.0", port):
                                        return True
                                except Exception as e:
                                    logger.warning(f"⚠️ Failed to kill Windows process: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Windows port freeing failed: {e}")
        
        elif platform.system() == "Linux":
            try:
                # Linux: try multiple methods to kill processes using the port
                port_freed = False
                
                # Method 1: Use fuser with more aggressive flags
                try:
                    result = subprocess.run(
                        ["fuser", "-k", "-9", str(port)], 
                        capture_output=True, 
                        timeout=10
                    )
                    if result.returncode == 0:
                        logger.info(f"✅ Killed Linux processes using fuser -k -9 on port {port}")
                        port_freed = True
                except Exception as e:
                    logger.debug(f"fuser -k -9 failed: {e}")
                
                # Method 2: Use lsof to find and kill processes
                if not port_freed:
                    try:
                        result = subprocess.run(
                            ["lsof", "-ti", f":{port}"], 
                            capture_output=True, 
                            text=True, 
                            timeout=10
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            pids = result.stdout.strip().split('\n')
                            for pid in pids:
                                if pid.strip():
                                    try:
                                        subprocess.run(
                                            ["kill", "-9", pid.strip()], 
                                            capture_output=True, 
                                            timeout=5
                                        )
                                        logger.info(f"✅ Killed process {pid.strip()} using lsof on port {port}")
                                        port_freed = True
                                    except Exception as e:
                                        logger.debug(f"Failed to kill PID {pid}: {e}")
                    except Exception as e:
                        logger.debug(f"lsof method failed: {e}")
                
                # Method 3: Use ss to find and kill processes
                if not port_freed:
                    try:
                        result = subprocess.run(
                            ["ss", "-tlnp", f"|", "grep", f":{port}"], 
                            shell=True,
                            capture_output=True, 
                            text=True, 
                            timeout=10
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            lines = result.stdout.strip().split('\n')
                            for line in lines:
                                if f":{port}" in line and "pid=" in line:
                                    # Extract PID from ss output
                                    import re
                                    pid_match = re.search(r'pid=(\d+)', line)
                                    if pid_match:
                                        pid = pid_match.group(1)
                                        try:
                                            subprocess.run(
                                                ["kill", "-9", pid], 
                                                capture_output=True, 
                                                timeout=5
                                            )
                                            logger.info(f"✅ Killed process {pid} using ss on port {port}")
                                            port_freed = True
                                        except Exception as e:
                                            logger.debug(f"Failed to kill PID {pid}: {e}")
                    except Exception as e:
                        logger.debug(f"ss method failed: {e}")
                
                # Method 4: Use netstat as fallback
                if not port_freed:
                    try:
                        result = subprocess.run(
                            ["netstat", "-tlnp"], 
                            capture_output=True, 
                            text=True, 
                            timeout=10
                        )
                        if result.returncode == 0:
                            lines = result.stdout.split('\n')
                            for line in lines:
                                if f":{port}" in line and "LISTEN" in line:
                                    parts = line.split()
                                    if len(parts) >= 7:
                                        pid_part = parts[-1]
                                        if '/' in pid_part:
                                            pid = pid_part.split('/')[0]
                                            try:
                                                subprocess.run(
                                                    ["kill", "-9", pid], 
                                                    capture_output=True, 
                                                    timeout=5
                                                )
                                                logger.info(f"✅ Killed process {pid} using netstat on port {port}")
                                                port_freed = True
                                            except Exception as e:
                                                logger.debug(f"Failed to kill PID {pid}: {e}")
                    except Exception as e:
                        logger.debug(f"netstat method failed: {e}")
                
                if port_freed:
                    # Wait a bit for the port to be freed
                    time.sleep(2)
                    if is_port_available_sync("0.0.0.0", port):
                        logger.info(f"✅ Port {port} is now available after aggressive freeing")
                        return True
                    else:
                        logger.warning(f"⚠️ Port {port} still not available after aggressive freeing")
                        return False
                else:
                    logger.warning(f"⚠️ No processes found using port {port} or failed to kill them")
                    return False
                    
            except Exception as e:
                logger.warning(f"⚠️ Linux port freeing failed: {e}")
                return False
        
    except Exception as e:
        logger.error(f"❌ Error freeing port {port}: {e}")
        return False

async def free_port(port: int) -> bool:
    """Attempt to free a port by killing processes using it (async version)"""
    try:
        import psutil
        import subprocess
        import platform
        
        # Find processes using the port
        processes_to_kill = []
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    processes_to_kill.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        
        # Kill processes using the port
        killed_count = 0
        for proc in processes_to_kill:
            try:
                proc_name = proc.name()
                proc.terminate()
                proc.wait(timeout=5)
                logger.info(f"✅ Terminated process {proc_name} (PID: {proc.pid}) using port {port}")
                killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                try:
                    proc.kill()
                    logger.info(f"✅ Force killed process (PID: {proc.pid}) using port {port}")
                    killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        
        if killed_count > 0:
            # Wait a bit for the port to be freed
            import asyncio
            await asyncio.sleep(1)
            
            # Verify port is now free
            if await is_port_available("0.0.0.0", port):
                logger.info(f"✅ Port {port} is now available after freeing")
                return True
            else:
                logger.warning(f"⚠️ Port {port} still not available after freeing")
                return False
        
        # If no processes found, try system-specific commands
        if platform.system() == "Windows":
            try:
                # Windows: use netstat to find and kill processes
                result = subprocess.run(
                    ["netstat", "-ano"], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if f":{port}" in line and "LISTENING" in line:
                            parts = line.split()
                            if len(parts) >= 5:
                                pid = parts[-1]
                                try:
                                    subprocess.run(
                                        ["taskkill", "/PID", pid, "/F"], 
                                        capture_output=True, 
                                        timeout=10
                                    )
                                    logger.info(f"✅ Killed Windows process (PID: {pid}) using port {port}")
                                    await asyncio.sleep(1)
                                    if await is_port_available("0.0.0.0", port):
                                        return True
                                except Exception as e:
                                    logger.warning(f"⚠️ Failed to kill Windows process: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Windows port freeing failed: {e}")
        
        elif platform.system() == "Linux":
            try:
                # Linux: try multiple methods to kill processes using the port
                port_freed = False
                
                # Method 1: Use fuser with more aggressive flags
                try:
                    result = subprocess.run(
                        ["fuser", "-k", "-9", str(port)], 
                        capture_output=True, 
                        timeout=10
                    )
                    if result.returncode == 0:
                        logger.info(f"✅ Killed Linux processes using fuser -k -9 on port {port}")
                        port_freed = True
                except Exception as e:
                    logger.debug(f"fuser -k -9 failed: {e}")
                
                # Method 2: Use lsof to find and kill processes
                if not port_freed:
                    try:
                        result = subprocess.run(
                            ["lsof", "-ti", f":{port}"], 
                            capture_output=True, 
                            text=True, 
                            timeout=10
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            pids = result.stdout.strip().split('\n')
                            for pid in pids:
                                if pid.strip():
                                    try:
                                        subprocess.run(
                                            ["kill", "-9", pid.strip()], 
                                            capture_output=True, 
                                            timeout=5
                                        )
                                        logger.info(f"✅ Killed process {pid.strip()} using lsof on port {port}")
                                        port_freed = True
                                    except Exception as e:
                                        logger.debug(f"Failed to kill PID {pid}: {e}")
                    except Exception as e:
                        logger.debug(f"lsof method failed: {e}")
                
                # Method 3: Use ss to find and kill processes
                if not port_freed:
                    try:
                        result = subprocess.run(
                            ["ss", "-tlnp", f"|", "grep", f":{port}"], 
                            shell=True,
                            capture_output=True, 
                            text=True, 
                            timeout=10
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            lines = result.stdout.strip().split('\n')
                            for line in lines:
                                if f":{port}" in line and "pid=" in line:
                                    # Extract PID from ss output
                                    import re
                                    pid_match = re.search(r'pid=(\d+)', line)
                                    if pid_match:
                                        pid = pid_match.group(1)
                                        try:
                                            subprocess.run(
                                                ["kill", "-9", pid], 
                                                capture_output=True, 
                                                timeout=5
                                            )
                                            logger.info(f"✅ Killed process {pid} using ss on port {port}")
                                            port_freed = True
                                        except Exception as e:
                                            logger.debug(f"Failed to kill PID {pid}: {e}")
                    except Exception as e:
                        logger.debug(f"ss method failed: {e}")
                
                # Method 4: Use netstat as fallback
                if not port_freed:
                    try:
                        result = subprocess.run(
                            ["netstat", "-tlnp"], 
                            capture_output=True, 
                            text=True, 
                            timeout=10
                        )
                        if result.returncode == 0:
                            lines = result.stdout.split('\n')
                            for line in lines:
                                if f":{port}" in line and "LISTEN" in line:
                                    parts = line.split()
                                    if len(parts) >= 7:
                                        pid_part = parts[-1]
                                        if '/' in pid_part:
                                            pid = pid_part.split('/')[0]
                                            try:
                                                subprocess.run(
                                                    ["kill", "-9", pid], 
                                                    capture_output=True, 
                                                    timeout=5
                                                )
                                                logger.info(f"✅ Killed process {pid} using netstat on port {port}")
                                                port_freed = True
                                            except Exception as e:
                                                logger.debug(f"Failed to kill PID {pid}: {e}")
                    except Exception as e:
                        logger.debug(f"netstat method failed: {e}")
                
                if port_freed:
                    # Wait a bit for the port to be freed
                    await asyncio.sleep(2)
                    if await is_port_available("0.0.0.0", port):
                        logger.info(f"✅ Port {port} is now available after aggressive freeing")
                        return True
                    else:
                        logger.warning(f"⚠️ Port {port} still not available after aggressive freeing")
                        return False
                else:
                    logger.warning(f"⚠️ No processes found using port {port} or failed to kill them")
                    return False
                    
            except Exception as e:
                logger.warning(f"⚠️ Linux port freeing failed: {e}")
                return False
        
    except Exception as e:
        logger.warning(f"⚠️ Port freeing failed: {e}")
        return False

if __name__ == "__main__":
    main()
