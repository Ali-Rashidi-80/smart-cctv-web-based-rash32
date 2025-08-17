"""
Shared configuration and constants for the spy_servo system.
This file contains all the constants and functions that are shared across core modules.
"""

import os
import time
import logging
import asyncio
import functools
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
from pydantic import BaseModel, Field

# Setup logger
logger = logging.getLogger("config")

# ============================================================================
# SYSTEM CONSTANTS
# ============================================================================

# Frame Processing Constants
FRAME_QUEUE_SIZE = int(os.getenv("FRAME_QUEUE_SIZE", "100"))
FRAME_BUFFER_SIZE = int(os.getenv("FRAME_BUFFER_SIZE", "50"))
FRAME_PROCESSING_TIMEOUT = float(os.getenv("FRAME_PROCESSING_TIMEOUT", "5.0"))
REALTIME_FRAME_PROCESSING = os.getenv("REALTIME_FRAME_PROCESSING", "true").lower() == "true"
ADAPTIVE_QUALITY = os.getenv("ADAPTIVE_QUALITY", "true").lower() == "true"
VIDEO_QUALITY = int(os.getenv("VIDEO_QUALITY", "80"))
FRAME_PROCESSING_ENABLED = os.getenv("FRAME_PROCESSING_ENABLED", "true").lower() == "true"
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "30"))
FRAME_DROP_RATIO = float(os.getenv("FRAME_DROP_RATIO", "0.1"))
FRAME_LATENCY_THRESHOLD = float(os.getenv("FRAME_LATENCY_THRESHOLD", "0.5"))
FRAME_COMPRESSION_THRESHOLD = int(os.getenv("FRAME_COMPRESSION_THRESHOLD", str(1024 * 1024)))  # 1MB
MIN_FRAME_INTERVAL = float(os.getenv("MIN_FRAME_INTERVAL", "0.033"))  # 30 FPS
MIN_VALID_FRAMES = int(os.getenv("MIN_VALID_FRAMES", "10"))
MAX_FRAME_SIZE = int(os.getenv("MAX_FRAME_SIZE", str(2 * 1024 * 1024)))  # 2MB
FRAME_SKIP_THRESHOLD = int(os.getenv("FRAME_SKIP_THRESHOLD", "3"))  # Number of frames that can be skipped

# WebSocket Constants
MAX_WEBSOCKET_CLIENTS = int(os.getenv("MAX_WEBSOCKET_CLIENTS", "100"))
MAX_WEBSOCKET_MESSAGE_SIZE = int(os.getenv("MAX_WEBSOCKET_MESSAGE_SIZE", str(2 * 1024 * 1024)))  # 2MB
INACTIVE_CLIENT_TIMEOUT = int(os.getenv("INACTIVE_CLIENT_TIMEOUT", "300"))  # 5 minutes
WEBSOCKET_ERROR_THRESHOLD = int(os.getenv("WEBSOCKET_ERROR_THRESHOLD", "10"))

# Performance Constants
PERFORMANCE_MONITORING = os.getenv("PERFORMANCE_MONITORING", "true").lower() == "true"
PERFORMANCE_UPDATE_INTERVAL = int(os.getenv("PERFORMANCE_UPDATE_INTERVAL", "30"))
MEMORY_THRESHOLD = int(os.getenv("MEMORY_THRESHOLD", "85"))
PROCESSING_OVERHEAD_THRESHOLD = float(os.getenv("PROCESSING_OVERHEAD_THRESHOLD", "0.3"))
ERROR_RESET_INTERVAL = int(os.getenv("ERROR_RESET_INTERVAL", "3600"))

# File Upload Constants
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(512 * 1024)))  # 512KB
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(25 * 1024 * 1024)))  # 25MB

# Video File Constants
MAX_VIDEO_FILE_SIZE = int(os.getenv("MAX_VIDEO_FILE_SIZE", str(2 * 1024 * 1024 * 1024)))  # 2GB
VIDEO_STREAMING_THRESHOLD = int(os.getenv("VIDEO_STREAMING_THRESHOLD", str(100 * 1024 * 1024)))  # 100MB

# Database Constants
DB_FILE = os.getenv("DB_FILE", "smart_camera_system.db")
DB_TIMEOUT = int(os.getenv("DB_TIMEOUT", "60"))
BACKUP_DIR = os.getenv("BACKUP_DIR", "./backups")
BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))
BACKUP_INTERVAL = int(os.getenv("BACKUP_INTERVAL", "86400"))  # 24 hours

# Directory Constants
GALLERY_DIR = os.getenv("GALLERY_DIR", "./gallery")
SECURITY_VIDEOS_DIR = os.getenv("SECURITY_VIDEOS_DIR", "./security_videos")

# Disk Constants
DISK_THRESHOLD = float(os.getenv("DISK_THRESHOLD", "10.0"))  # 10% free disk space threshold

# Authentication Constants
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# JWT Algorithm
ALGORITHM = os.getenv("ALGORITHM", "HS256")

# Secret key for JWT tokens (from environment variable)
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-this-in-production")

# Persian text overlay configuration
PERSIAN_TEXT_OVERLAY = os.getenv("PERSIAN_TEXT_OVERLAY", "true").lower() == "true"

# Global storage for rate limiting
API_RATE_LIMIT_STORAGE = {}

# Initialize CAPTCHA storage
CAPTCHA_STORAGE = {}

# ============================================================================
# ADMIN CREDENTIALS MANAGEMENT
# ============================================================================

import secrets
import string
import re
from pathlib import Path

def generate_safe_admin_credentials():
    """Generate safe admin credentials without problematic characters"""
    # Characters that are safe for microcontrollers and can be quoted
    # Avoid: " ' \ / | % & $ # @ ! ~ ` ^ * ( ) [ ] { } < > ; : , . ? = + -
    safe_chars = string.ascii_letters + string.digits
    
    # Generate username (8-12 characters)
    username = ''.join(secrets.choice(safe_chars) for _ in range(secrets.choice([8, 9, 10, 11, 12])))
    
    # Generate password (12-16 characters)
    password = ''.join(secrets.choice(safe_chars) for _ in range(secrets.choice([12, 13, 14, 15, 16])))
    
    return username, password

def generate_safe_secret_key():
    """Generate a safe secret key without problematic characters"""
    # Use only alphanumeric characters for maximum compatibility
    safe_chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(safe_chars) for _ in range(64))

def validate_credential_safety(credential):
    """Validate that a credential doesn't contain problematic characters"""
    if not credential:
        return False
    
    # Check for problematic characters
    problematic_chars = r'["\'\\/|%&$#@!~`^*()\[\]{}<>;:,.?=+-]'
    if re.search(problematic_chars, credential):
        return False
    
    # Check length
    if len(credential) < 8:
        return False
    
    return True

def load_or_generate_admin_credentials():
    """Load existing admin credentials or generate new ones if needed"""
    credentials_file = Path("core/admin_credentials.txt")
    fallback_file = Path("admin_credentials.txt")
    
    # Try to load from core directory first, then root directory
    for file_path in [credentials_file, fallback_file]:
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                # Parse the file content
                credentials = {}
                for line in content.split('\n'):
                    line = line.strip()
                    if '=' in line:
                        key, value = line.split('=', 1)
                        credentials[key.strip()] = value.strip()
                
                # Validate existing credentials
                admin_username = credentials.get('ADMIN_USERNAME', '')
                admin_password = credentials.get('ADMIN_PASSWORD', '')
                secret_key = credentials.get('SECRET_KEY', '')
                
                # Check if all credentials are safe and valid
                if (validate_credential_safety(admin_username) and 
                    validate_credential_safety(admin_password) and 
                    validate_credential_safety(secret_key)):
                    
                    logger.info(f"✅ Loaded existing safe credentials from {file_path}")
                    return admin_username, admin_password, secret_key
                else:
                    logger.warning(f"⚠️ Existing credentials in {file_path} contain problematic characters, will regenerate")
                    break
                    
            except Exception as e:
                logger.warning(f"⚠️ Error reading {file_path}: {e}")
                continue
    
    # Generate new safe credentials
    logger.warning("⚠️ Missing or invalid credentials, generating new safe ones...")
    
    admin_username, admin_password = generate_safe_admin_credentials()
    secret_key = generate_safe_secret_key()
    
    # Save to both locations for redundancy
    credentials_content = f"""SECRET_KEY={secret_key}
ADMIN_USERNAME={admin_username}
ADMIN_PASSWORD={admin_password}
"""
    
    try:
        # Save to core directory
        credentials_file.parent.mkdir(parents=True, exist_ok=True)
        with open(credentials_file, 'w', encoding='utf-8') as f:
            f.write(credentials_content)
        logger.info(f"✅ Generated and saved new credentials to {credentials_file}")
    except Exception as e:
        logger.warning(f"⚠️ Error saving to {credentials_file}: {e}")
    
    try:
        # Save to root directory as backup
        with open(fallback_file, 'w', encoding='utf-8') as f:
            f.write(credentials_content)
        logger.info(f"✅ Generated and saved new credentials to {fallback_file}")
    except Exception as e:
        logger.warning(f"⚠️ Error saving to {fallback_file}: {e}")
    
    return admin_username, admin_password, secret_key

def regenerate_admin_credentials():
    """Force regeneration of admin credentials"""
    logger.warning("🔄 Forcing regeneration of admin credentials...")
    
    admin_username, admin_password = generate_safe_admin_credentials()
    secret_key = generate_safe_secret_key()
    
    # Save to both locations for redundancy
    credentials_content = f"""SECRET_KEY={secret_key}
ADMIN_USERNAME={admin_username}
ADMIN_PASSWORD={admin_password}
"""
    
    credentials_file = Path("core/admin_credentials.txt")
    fallback_file = Path("admin_credentials.txt")
    
    try:
        # Save to core directory
        credentials_file.parent.mkdir(parents=True, exist_ok=True)
        with open(credentials_file, 'w', encoding='utf-8') as f:
            f.write(credentials_content)
        logger.info(f"✅ Regenerated and saved new credentials to {credentials_file}")
    except Exception as e:
        logger.warning(f"⚠️ Error saving to {credentials_file}: {e}")
    
    try:
        # Save to root directory as backup
        with open(fallback_file, 'w', encoding='utf-8') as f:
            f.write(credentials_content)
        logger.info(f"✅ Regenerated and saved new credentials to {fallback_file}")
    except Exception as e:
        logger.warning(f"⚠️ Error saving to {fallback_file}: {e}")
    
    # Update environment variables
    os.environ['SECRET_KEY'] = secret_key
    os.environ['ADMIN_USERNAME'] = admin_username
    os.environ['ADMIN_PASSWORD'] = admin_password
    
    return admin_username, admin_password, secret_key

# Load or generate admin credentials
ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY = load_or_generate_admin_credentials()

# Set environment variables if not already set
if not os.getenv('SECRET_KEY'):
    os.environ['SECRET_KEY'] = SECRET_KEY
if not os.getenv('ADMIN_USERNAME'):
    os.environ['ADMIN_USERNAME'] = ADMIN_USERNAME
if not os.getenv('ADMIN_PASSWORD'):
    os.environ['ADMIN_PASSWORD'] = ADMIN_PASSWORD

# ============================================================================
# DEVICE AUTHENTICATION TOKENS
# ============================================================================

# Device Authentication Tokens (from environment variables)
PICO_AUTH_TOKENS = os.getenv("PICO_AUTH_TOKENS", "rof642fr:5qEKU@A@Tv,pico_secure_token_2024").split(",")
ESP32CAM_AUTH_TOKENS = os.getenv("ESP32CAM_AUTH_TOKENS", "esp32cam_secure_token_2024,esp32cam_token_v2").split(",")

# SMS Constants (from environment variables)
SMS_USERNAME = os.getenv("SMS_USERNAME", "9204963846")
SMS_PASSWORD = os.getenv("SMS_PASSWORD", "3TZ95")
SMS_SENDER_NUMBER = os.getenv("SMS_SENDER_NUMBER", "50002710063846")

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

SECURITY_CONFIG = {
    'MAX_LOGIN_ATTEMPTS': 5,
    'LOGIN_BAN_DURATION': 300,  # 5 minutes
    'PASSWORD_MIN_LENGTH': 12,
    'PASSWORD_MAX_LENGTH': 128,
    'SESSION_TIMEOUT': 1800,  # 30 minutes
    'TOKEN_EXPIRY': 1800,  # 30 minutes
    'RATE_LIMIT_WINDOW': 100,  # 1 minute
    'RATE_LIMIT_MAX_REQUESTS': 100,
    'LOGIN_RATE_LIMIT_MAX': 50,
    'API_RATE_LIMIT_MAX': 100,
    'ALLOWED_FILE_EXTENSIONS': {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.avi', '.mov'},
    'MAX_FILE_SIZE': 25 * 1024 * 1024,  # 25MB
    'CSRF_TOKEN_EXPIRY': 3600,  # 1 hour
    'CONCURRENT_SESSIONS_MAX': 3,
    'MAX_TOKEN_AGE_HOURS': 1,
    'ENABLE_IP_VALIDATION': True,
    'ENABLE_ALGORITHM_VERIFICATION': True,
    'ENABLE_REPLAY_PROTECTION': True,
}

RATE_LIMIT_CONFIG = {
    'WINDOW_SIZE': 60,  # 1 minute
    'MAX_REQUESTS': 100,
    'LOGIN_MAX_REQUESTS': 5,
    'OTP_MAX_REQUESTS': 3,
    'API_MAX_REQUESTS': 100,
    'LOGIN_ATTEMPTS': {
        'max_requests': 5,
        'window_seconds': 300
    },
}

CSRF_CONFIG = {
    'TOKEN_EXPIRY': 3600,  # 1 hour
    'REQUIRED_ENDPOINTS': ['/login', '/register', '/recover-password', '/reset-password'],
    'EXEMPT_ENDPOINTS': ['/static', '/favicon.ico'],
}

CAPTCHA_CONFIG = {
    'ENABLED': True,
    'LENGTH': 6,
    'EXPIRY': 300,  # 5 minutes
    'MAX_ATTEMPTS': 3,
    'BLOCK_DURATION': 1800,  # 30 minutes
}

# ============================================================================
# TEST MODE CONFIGURATION
# ============================================================================

TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'

# ============================================================================
# EXTERNAL LIBRARY AVAILABILITY
# ============================================================================

# Check for psutil availability
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Check for Persian tools availability
try:
    from persiantools.jdatetime import JalaliDateTime
    PERSIANTOOLS_AVAILABLE = True
except ImportError:
    PERSIANTOOLS_AVAILABLE = False

# Check for Arabic text reshaping support
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_RESHAPER_AVAILABLE = True
except ImportError:
    ARABIC_RESHAPER_AVAILABLE = False

# Check for bleach availability
try:
    import bleach
    BLEACH_AVAILABLE = True
    BLEACH_CONFIG = {
        'tags': ['b', 'i', 'u', 'em', 'strong', 'a'],
        'attributes': {'a': ['href']},
        'strip': True
    }
except ImportError:
    BLEACH_AVAILABLE = False
    BLEACH_CONFIG = {}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_jalali_now_str():
    """Get current Jalali datetime as string"""
    try:
        if PERSIANTOOLS_AVAILABLE:
            return JalaliDateTime.now().strftime('%Y-%m-%d %H:%M:%S')
        else:
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logger.warning(f"Error getting Jalali datetime: {e}")
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def is_local_test_request(client_ip: str) -> bool:
    """Check if request is from localhost for testing"""
    return client_ip in ['127.0.0.1', 'localhost', '::1']

def is_test_environment() -> bool:
    """Check if running in test environment"""
    return TEST_MODE or os.getenv('ENVIRONMENT') == 'test'

async def retry_async(func, retries=7, delay=1, backoff=2, exceptions=(Exception,)):
    """Retry async function with exponential backoff"""
    for attempt in range(retries):
        try:
            return await func()
        except exceptions as e:
            if attempt == retries - 1:
                raise e
            await asyncio.sleep(delay)
            delay *= backoff

# ============================================================================
# DEVICE RESOLUTIONS
# ============================================================================

DEVICE_RESOLUTIONS = {
    "desktop": {"width": 1072, "height": 603},
    "mobile": {"width": 536, "height": 301}
}

# ============================================================================
# TRANSLATIONS
# ============================================================================

translations = {
    'en': {
        'login': 'Login',
        'register': 'Register',
        'username': 'Username',
        'password': 'Password',
        'submit': 'Submit',
        'error': 'Error',
        'success': 'Success',
    },
    'fa': {
        'login': 'ورود',
        'register': 'ثبت نام',
        'username': 'نام کاربری',
        'password': 'رمز عبور',
        'submit': 'ارسال',
        'error': 'خطا',
        'success': 'موفقیت',
    }
}

# Override UI translations with comprehensive set for templates/index.html
try:
    from .translations_ui import UI_TRANSLATIONS as _UI_TRANSLATIONS
    translations = _UI_TRANSLATIONS
    logger.info("✅ UI translations loaded from core/translations_ui.py")
except Exception as _e:
    logger.warning(f"⚠️ Failed to load UI translations, using fallback minimal set: {_e}")

# ============================================================================
# SMART FEATURES COMMAND MODEL
# ============================================================================

class SmartFeaturesCommand(BaseModel):
    motion: bool = Field(default=False, description="Enable/disable motion detection")
    tracking: bool = Field(default=False, description="Enable/disable object tracking")

# ============================================================================
# SYSTEM STATE CLASS
# ============================================================================

class SystemState:
    def __init__(self):
        self.db_initialized = False
        self.system_shutdown = False
        self.esp32cam_client_lock = asyncio.Lock()
        self.pico_client_lock = asyncio.Lock()
        self.web_clients_lock = asyncio.Lock()
        self.frame_cache_lock = asyncio.Lock()
        self.rate_limit_lock = asyncio.Lock()
        self.security_lock = asyncio.Lock()
        self.otp_lock = asyncio.Lock()
        self.login_lock = asyncio.Lock()
        self.sms_lock = asyncio.Lock()
        self.token_lock = asyncio.Lock()
        self.google_auth_lock = asyncio.Lock()
        self.sanitize_lock = asyncio.Lock()
        self.client_app_lock = asyncio.Lock()

# ============================================================================
# GLOBAL SYSTEM STATE INSTANCE
# ============================================================================

system_state = SystemState()

# ============================================================================
# GLOBAL REFERENCES (set by main server)
# ============================================================================

# Global references for FastAPI app and templates (set by main server)
app = None
templates = None

def set_app(fastapi_app):
    """Set the FastAPI app reference"""
    global app
    app = fastapi_app

def set_templates(jinja_templates):
    """Set the Jinja2 templates reference"""
    global templates
    templates = jinja_templates

def get_app():
    """Safely get the FastAPI app reference"""
    global app
    if app is None:
        raise RuntimeError("FastAPI app not initialized yet. Call set_app() first.")
    return app

def get_templates():
    """Safely get the Jinja2 templates reference"""
    global templates
    if templates is None:
        raise RuntimeError("Jinja2 templates not initialized yet. Call set_templates() first.")
    return templates

# ============================================================================
# FUNCTION PLACEHOLDERS (will be set by main server)
# ============================================================================

# These functions will be set by the main server during initialization
insert_log = None
get_db_connection = None
close_db_connection = None
send_to_web_clients = None
send_to_pico_client = None
send_to_esp32cam_client = None
create_security_video_async = None
authenticate_websocket = None
get_current_user = None
robust_db_endpoint = None
init_db = None
migrate_all_tables = None
periodic_backup_and_reset = None
periodic_cleanup = None
monitor_system_health = None
set_db_system_state = None
set_utils_system_state = None
set_esp32cam_system_state = None
set_pico_system_state = None
set_status_system_state = None
set_security_system_state = None
set_otp_system_state = None
set_login_system_state = None
set_sms_system_state = None
set_token_system_state = None
set_google_auth_system_state = None
set_sanitize_system_state = None
set_client_app_and_state = None
alert_admin = None
check_rate_limit = None
hash_password = None
send_password_recovery_sms = None
validate_captcha = None
should_require_captcha = None
record_captcha_attempt = None
create_access_token = None
validate_csrf_token = None
get_csrf_token_from_request = None
generate_csrf_token = None
log_security_event = None
validate_image_format = None
validate_iranian_mobile = None
process_mobile_number = None
detect_embedded_malicious_content = None
insert_action_command = None
insert_photo_to_db = None
execute_db_insert = None
DailyCleanupFileHandler = None

def set_global_functions(**kwargs):
    """Set global function references from main server"""
    global app, templates, insert_log, get_db_connection, close_db_connection
    global send_to_web_clients, send_to_pico_client, send_to_esp32cam_client
    global create_security_video_async, authenticate_websocket, get_current_user
    global robust_db_endpoint, init_db, migrate_all_tables, periodic_backup_and_reset
    global periodic_cleanup, monitor_system_health, set_db_system_state
    global set_utils_system_state, set_esp32cam_system_state, set_pico_system_state
    global set_status_system_state, set_security_system_state, set_otp_system_state
    global set_login_system_state, set_sms_system_state, set_token_system_state
    global set_google_auth_system_state, set_sanitize_system_state, set_client_app_and_state
    global alert_admin, check_rate_limit, hash_password, send_password_recovery_sms
    global validate_captcha, should_require_captcha, record_captcha_attempt
    global create_access_token, validate_csrf_token, get_csrf_token_from_request
    global generate_csrf_token, log_security_event, validate_image_format
    global validate_iranian_mobile, process_mobile_number, detect_embedded_malicious_content
    global insert_action_command, insert_photo_to_db, execute_db_insert, DailyCleanupFileHandler
    global SECRET_KEY
    
    for key, value in kwargs.items():
        if key in globals():
            globals()[key] = value
        else:
            logger.warning(f"Unknown function key: {key}") 