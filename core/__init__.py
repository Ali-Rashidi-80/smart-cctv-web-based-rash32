# Core package initialization
# This file makes the core directory a Python package

# Import commonly used modules to make them available at package level
from . import config
from . import db
from . import Security
from . import sms
from . import token
from . import sanitize_validate
from . import status
from . import pico
from . import esp32cam
from . import OTP
from . import google_auth
from . import login_fun
from . import websocket_manager
from . import utils
from . import system_manager
from . import server_manager

# Version information
__version__ = "1.0.0"
__author__ = "Spy Servo Team"

# Package description
__doc__ = """
Core package for Spy Servo application containing:
- Configuration management
- Database operations
- Security functions
- SMS functionality
- Token management
- Input validation and sanitization
- Status monitoring
- Device management (Pico, ESP32CAM)
- OTP functionality
- Google authentication
- Login functions
- WebSocket management
- Utility functions
- System management
- Server management
""" 