import asyncio, time, os, sys, gc, psutil, logging, secrets, string, jwt
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, Depends

# Setup logger for this module
logger = logging.getLogger("token")

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
                pass  # No specific attributes needed for Token module
        system_state = TempSystemState()
    return system_state

def set_dependencies(log_func):
    """Set the dependencies from main server"""
    global insert_log_func
    insert_log_func = log_func

# Global function reference for logging (will be set by main server)
insert_log_func = None

async def insert_log(message: str, log_type: str = "info", source: str = "token"):
    """Insert log entry using the main server's log function"""
    if insert_log_func:
        await insert_log_func(message, log_type, source)
    else:
        logger.info(f"[{source}] {message}")


ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
ALGORITHM = os.getenv("ALGORITHM", "HS256")

# Import SECRET_KEY and SECURITY_CONFIG from config
from .config import SECRET_KEY, SECURITY_CONFIG
from .Security import log_security_event





# Security tokens for microcontrollers
def generate_secure_tokens():
    """Generate secure tokens for microcontrollers"""
    import secrets
    import string
    
    # Generate Pico token
    pico_token = ''.join(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*") for _ in range(32))
    
    # Generate ESP32CAM token
    esp32cam_token = ''.join(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*") for _ in range(32))
    
    return pico_token, esp32cam_token

# Generate or load tokens
pico_tokens_env = os.getenv("PICO_AUTH_TOKENS")
esp32cam_tokens_env = os.getenv("ESP32CAM_AUTH_TOKENS")


if pico_tokens_env:
    # Use environment variable if provided
    if pico_tokens_env.startswith("[") and pico_tokens_env.endswith("]"):
        import json
        try:
            PICO_AUTH_TOKENS = json.loads(pico_tokens_env)
        except:
            PICO_AUTH_TOKENS, _ = generate_secure_tokens()
            PICO_AUTH_TOKENS = [PICO_AUTH_TOKENS]
    else:
        PICO_AUTH_TOKENS = pico_tokens_env.split(",")
else:
    # Generate new secure token
    pico_token, _ = generate_secure_tokens()
    PICO_AUTH_TOKENS = [pico_token]
    logger.info(f"Generated new Pico token: {pico_token[:10]}...")


if esp32cam_tokens_env:
    # Use environment variable if provided
    if esp32cam_tokens_env.startswith("[") and esp32cam_tokens_env.endswith("]"):
        import json
        try:
            ESP32CAM_AUTH_TOKENS = json.loads(esp32cam_tokens_env)
        except:
            _, esp32cam_token = generate_secure_tokens()
            ESP32CAM_AUTH_TOKENS = [esp32cam_token]
    else:
        ESP32CAM_AUTH_TOKENS = esp32cam_tokens_env.split(",") if esp32cam_tokens_env else []
else:
    # Generate new secure token
    _, esp32cam_token = generate_secure_tokens()
    ESP32CAM_AUTH_TOKENS = [esp32cam_token]
    logger.info(f"Generated new ESP32CAM token: {esp32cam_token[:10]}...")



# Log token information for debugging (only once)
if not hasattr(logger, '_credentials_logged'):
    logger.info(f"PICO_AUTH_TOKENS: {[token[:10] + '...' for token in PICO_AUTH_TOKENS]}")
    logger.info(f"ESP32CAM_AUTH_TOKENS: {[token[:10] + '...' for token in ESP32CAM_AUTH_TOKENS]}")
    logger._credentials_logged = True




def create_access_token(data: dict, expires_delta: timedelta = None, ip_address: str = None):
    """Enhanced access token creation with IP address and additional security measures"""
    to_encode = data.copy()
    
    # Add IP address to token for session hijacking protection
    if ip_address:
        to_encode["ip_address"] = ip_address
    
    # Add issued at time for replay attack protection
    to_encode["iat"] = datetime.now().timestamp()
    
    try:
        # Python 3.11+
        utc = getattr(datetime, "UTC", None)
        if utc is None:
            # Python <3.11
            from datetime import timezone
            utc = timezone.utc
        if expires_delta:
            expire = datetime.now(utc) + expires_delta
        else:
            expire = datetime.now(utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    except Exception:
        # Fallback for very old Python
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str):
    """Enhanced JWT token verification with algorithm verification and IP validation"""
    if not token:
        return None
    try:
        # Explicitly specify the algorithm to prevent algorithm confusion attacks
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={
            'verify_signature': True,
            'verify_exp': True,
            'verify_iat': False,
            'require': ['exp', 'sub']  # Remove 'iat' requirement as it might not be present
        })
        
        # Additional validation: check if token is not too old (replay attack protection)
        if 'iat' in payload:
            issued_at = datetime.fromtimestamp(payload['iat'])
            max_age_hours = SECURITY_CONFIG.get('MAX_TOKEN_AGE_HOURS', 1)  # Default 1 hour
            if datetime.now() - issued_at > timedelta(hours=max_age_hours):
                logger.warning(f"Token too old detected (older than {max_age_hours} hours)")
                return None
        
        # Validate required fields
        if 'sub' not in payload:
            logger.warning("Token missing required fields")
            return None
        
        # Add username field if not present (for backward compatibility)
        if 'username' not in payload:
            payload['username'] = payload['sub']
            
        return payload
    except jwt.ExpiredSignatureError:
        logger.info("Token expired")
        return None
    except jwt.InvalidAlgorithmError:
        logger.warning("Invalid algorithm in token")
        return None
    except jwt.InvalidSignatureError:
        logger.warning("Invalid token signature")
        return None
    except (jwt.exceptions.DecodeError, jwt.exceptions.PyJWTError) as e:
        logger.warning(f"Token decode error: {e}")
        return None
    


# Authentication dependency
def get_current_user(request: Request):
    """Get current user from token in cookies or headers with enhanced validation"""
    token = request.cookies.get("access_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    
    # Debug logging
    logger.info(f"[AUTH DEBUG] Token from cookie: {request.cookies.get('access_token')}")
    logger.info(f"[AUTH DEBUG] Token from header: {request.headers.get('Authorization')}")
    logger.info(f"[AUTH DEBUG] Final token: {token[:50] if token else 'None'}...")
    
    if not token:
        logger.info("[AUTH DEBUG] No token found")
        return None
    
    # Verify token and get user info
    user_info = verify_token(token)
    logger.info(f"[AUTH DEBUG] User info from token: {user_info}")
    
    if not user_info:
        logger.info("[AUTH DEBUG] Token verification failed")
        return None
    
    # Enhanced IP validation to prevent session hijacking
    client_ip = request.client.host if request.client else "unknown"
    token_ip = user_info.get('ip_address')
    
    logger.info(f"[AUTH DEBUG] Client IP: {client_ip}, Token IP: {token_ip}")
    
    if token_ip is not None and token_ip != client_ip:
        logger.warning(f"IP mismatch detected: token IP {token_ip} vs client IP {client_ip}")
        # Log security event
        asyncio.create_task(log_security_event(
            event_type="session_hijacking_attempt",
            description=f"IP mismatch detected for user {user_info.get('username')}",
            severity="high",
            ip_address=client_ip,
            user_id=user_info.get('id'),
            metadata={'token_ip': token_ip, 'client_ip': client_ip}
        ))
        return None
    
    # Additional validation: check if user is still active in database
    try:
        # This would be async in a real implementation, but we need to keep it sync for FastAPI dependency
        # In production, consider using a sync database connection or caching
        logger.info(f"[AUTH DEBUG] Returning user info: {user_info}")
        return user_info
    except Exception as e:
        logger.error(f"Error validating user: {e}")
        return None