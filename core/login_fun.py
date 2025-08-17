import asyncio, time, os, sys, gc, psutil, logging, bcrypt, secrets, hashlib
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

# Setup logger for this module
logger = logging.getLogger("login")

# Constants
SESSION_DURATION = 3600  # 1 hour
MAX_SESSIONS_PER_USER = 5
SESSION_CLEANUP_INTERVAL = 300  # 5 minutes
PASSWORD_HASH_ROUNDS = 12
LOGIN_ATTEMPT_WINDOW = 900  # 15 minutes
MAX_LOGIN_ATTEMPTS = 5

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
                pass  # No specific attributes needed for Login module
        system_state = TempSystemState()
    return system_state

# Global function references (will be set by main server)
insert_log = None
verify_password_hash = None
hash_password = None

# Import required functions from other modules
from .db import get_db_connection, close_db_connection
from .config import get_jalali_now_str
from .token import get_current_user
from .Security import check_rate_limit, generate_captcha_text, generate_math_captcha, validate_captcha, record_captcha_attempt, is_captcha_blocked
from .config import CAPTCHA_CONFIG, PICO_AUTH_TOKENS, ESP32CAM_AUTH_TOKENS

# Import UI translations
from .translations_ui import UI_TRANSLATIONS

# Translations
translations = UI_TRANSLATIONS

def set_dependencies(log_func, verify_pwd_func, hash_pwd_func):
    """Set dependencies from main server"""
    global insert_log, verify_password_hash, hash_password
    insert_log = log_func
    verify_password_hash = verify_pwd_func
    hash_password = hash_pwd_func






# Initialize CAPTCHA storage
captcha_storage = {}

# User model
class User(BaseModel):
    username: str
    password: str
    role: str = "user"
    is_active: bool = True

# Translations
translations = {
    "fa": {
        "welcome": "خوش آمدید",
        "login": "ورود",
        "logout": "خروج",
        "username": "نام کاربری",
        "password": "رمز عبور",
        "submit": "ارسال",
        "error": "خطا",
        "success": "موفقیت"
    },
    "en": {
        "welcome": "Welcome",
        "login": "Login",
        "logout": "Logout",
        "username": "Username",
        "password": "Password",
        "submit": "Submit",
        "error": "Error",
        "success": "Success"
    }
}





# User Management Endpoints
async def create_user(user: User, request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Check if current user is admin
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        conn = await get_db_connection()
        
        # Check if username already exists
        existing_user = await conn.execute('SELECT COUNT(*) FROM users WHERE username = ?', (user.username,))
        if (await existing_user.fetchone())[0] > 0:
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # Hash password and create user
        password_hash = hash_password(user.password)
        await conn.execute('''
            INSERT INTO users (username, password_hash, role, is_active, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user.username, password_hash, user.role, user.is_active, get_jalali_now_str()))
        
        await conn.commit()
        await close_db_connection(conn)
        
        await insert_log(f"User '{user.username}' created by admin '{current_user.get('sub')}'", "auth")
        
        return {"status": "success", "message": f"User '{user.username}' created successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Error creating user")

async def get_users(current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Check if current user is admin
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        conn = await get_db_connection()
        users_query = await conn.execute('''
            SELECT username, role, is_active, created_at 
            FROM users 
            ORDER BY created_at DESC
        ''')
        users = await users_query.fetchall()
        await close_db_connection(conn)
        
        return {
            "status": "success",
            "users": [
                {
                    "username": user[0],
                    "role": user[1],
                    "is_active": bool(user[2]),
                    "created_at": user[3]
                }
                for user in users
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(status_code=500, detail="Error getting users")

async def toggle_user_status(username: str, current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Check if current user is admin
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        conn = await get_db_connection()
        
        # Get current status
        status_query = await conn.execute('SELECT is_active FROM users WHERE username = ?', (username,))
        user_status = await status_query.fetchone()
        
        if not user_status:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Toggle status
        new_status = not user_status[0]
        await conn.execute('UPDATE users SET is_active = ? WHERE username = ?', (new_status, username))
        await conn.commit()
        await close_db_connection(conn)
        
        action = "activated" if new_status else "deactivated"
        await insert_log(f"User '{username}' {action} by admin '{current_user.get('sub')}'", "auth")
        
        return {"status": "success", "message": f"User '{username}' {action} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling user status: {e}")
        raise HTTPException(status_code=500, detail="Error updating user status")
    
    

async def get_translations(lang: str = "fa"):
    """Get comprehensive UI translations for the specified language"""
    try:
        # Return the comprehensive UI translations
        return JSONResponse(UI_TRANSLATIONS.get(lang, UI_TRANSLATIONS["fa"]))
    except Exception as e:
        logger.error(f"Error getting translations for {lang}: {e}")
        # Fallback to basic translations
        return JSONResponse(translations.get(lang, translations["fa"]))

async def get_text_captcha(request: Request):
    """Generate text-based CAPTCHA"""
    if not CAPTCHA_CONFIG['ENABLE_TEXT_CAPTCHA']:
        raise HTTPException(status_code=404, detail="Text CAPTCHA not enabled")
    
    client_ip = request.client.host
    
    # Check if client is blocked
    if is_captcha_blocked(client_ip):
        raise HTTPException(status_code=429, detail="Too many CAPTCHA attempts")
    
    # Generate CAPTCHA
    captcha_text = generate_captcha_text(CAPTCHA_CONFIG['CAPTCHA_LENGTH'])
    
    # Store CAPTCHA with expiry
    captcha_id = secrets.token_urlsafe(16)

async def get_mobile_captcha(request: Request):
    """Generate mobile CAPTCHA for mobile login"""
    client_ip = request.client.host
    
    # Check if client is blocked
    if is_captcha_blocked(client_ip):
        raise HTTPException(status_code=429, detail="Too many CAPTCHA attempts")
    
    # Generate CAPTCHA
    captcha_text = generate_captcha_text(CAPTCHA_CONFIG['CAPTCHA_LENGTH'])
    
    # Store CAPTCHA with expiry
    captcha_id = secrets.token_urlsafe(16)
    captcha_storage[captcha_id] = {
        'text': captcha_text,
        'expires_at': time.time() + CAPTCHA_CONFIG['CAPTCHA_EXPIRY'],
        'client_ip': client_ip
    }
    
    return {
        "captcha_id": captcha_id,
        "captcha_text": captcha_text,
        "expires_in": CAPTCHA_CONFIG['CAPTCHA_EXPIRY']
    }


async def get_math_captcha(request: Request):
    """Generate mathematical CAPTCHA"""
    if not CAPTCHA_CONFIG['ENABLE_MATH_CAPTCHA']:
        raise HTTPException(status_code=404, detail="Math CAPTCHA not enabled")
    
    client_ip = request.client.host
    
    # Check if client is blocked
    if is_captcha_blocked(client_ip):
        raise HTTPException(status_code=429, detail="Too many CAPTCHA attempts")
    
    # Generate CAPTCHA
    question, answer = generate_math_captcha()
    
    # Store CAPTCHA with expiry
    captcha_id = secrets.token_urlsafe(16)
    captcha_storage[captcha_id] = {
        'question': question,
        'answer': answer,
        'expires_at': time.time() + CAPTCHA_CONFIG['CAPTCHA_EXPIRY'],
        'client_ip': client_ip
    }
    
    return {
        "captcha_id": captcha_id,
        "question": question,
        "expires_in": CAPTCHA_CONFIG['CAPTCHA_EXPIRY']
    }


async def verify_captcha(request: Request):
    """Verify CAPTCHA input"""
    try:
        data = await request.json()
        captcha_id = data.get('captcha_id')
        user_input = data.get('user_input')
        
        if not captcha_id or not user_input:
            raise HTTPException(status_code=400, detail="Missing captcha_id or user_input")
        
        # Get stored CAPTCHA
        if captcha_id not in captcha_storage:
            raise HTTPException(status_code=400, detail="Invalid or expired CAPTCHA")
        
        captcha_data = captcha_storage[captcha_id]
        
        # Check expiry
        if time.time() > captcha_data['expires_at']:
            del captcha_storage[captcha_id]
            raise HTTPException(status_code=400, detail="CAPTCHA expired")
        
        # Verify CAPTCHA
        client_ip = request.client.host
        is_valid = False
        
        if 'text' in captcha_data:
            # Text CAPTCHA
            is_valid = validate_captcha(
                user_input, 
                captcha_data['text'], 
                CAPTCHA_CONFIG['CAPTCHA_CASE_SENSITIVE']
            )
        elif 'answer' in captcha_data:
            # Math CAPTCHA
            try:
                user_answer = int(user_input)
                is_valid = user_answer == captcha_data['answer']
            except ValueError:
                is_valid = False
        
        # Record attempt
        record_captcha_attempt(client_ip, is_valid)
        
        # Clean up used CAPTCHA
        del captcha_storage[captcha_id]
        
        return {"valid": is_valid}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CAPTCHA verification error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")




async def get_tokens(password: str):
    """Get current authentication tokens (for debugging) - requires password"""
    # Password for accessing tokens (you can change this)
    TOKEN_ACCESS_PASSWORD = "spy_servoo_secure_2024"
    
    if password != TOKEN_ACCESS_PASSWORD:
        logger.warning(f"Invalid token access attempt with password: {password[:5]}...")
        return {"status": "error", "message": "Invalid password"}
    
    try:
        logger.info("Token access granted with valid password")
        return {
            "pico_tokens": PICO_AUTH_TOKENS,
            "esp32cam_tokens": ESP32CAM_AUTH_TOKENS,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting tokens: {e}")
        return {"status": "error", "message": str(e)}
