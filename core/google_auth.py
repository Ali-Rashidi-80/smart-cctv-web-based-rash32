import time, os, secrets, pyotp, httpx, logging
from typing import Optional
from datetime import datetime, timedelta
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi import Request, HTTPException
from pydantic import BaseModel, Field

# Setup logger
logger = logging.getLogger("google_auth")

# Import SystemState from config
from .config import SystemState

# Import required functions from other modules
from .db import init_db, get_db_connection, close_db_connection, insert_log as db_insert_log
from .Security import hash_password, check_rate_limit
from .config import get_jalali_now_str
from .sanitize_validate import sanitize_input
from .token import create_access_token




system_state = SystemState()
oauth_states = {}
ACCESS_TOKEN_EXPIRE_MINUTES = 60


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
                pass  # No specific attributes needed for Google Auth module
        system_state = TempSystemState()
    return system_state

def set_dependencies(log_func, create_user_func, verify_password_hash_func):
    """Set the dependencies from main server"""
    global insert_log_func, create_user_func_ref, verify_password_hash_func_ref
    insert_log_func = log_func
    create_user_func_ref = create_user_func
    verify_password_hash_func_ref = verify_password_hash_func

# Global function references (will be set by main server)
insert_log_func = None
create_user_func_ref = None
verify_password_hash_func_ref = None

async def insert_log(message: str, log_type: str = "info", source: str = "google_auth"):
    """Insert log entry using the main server's log function"""
    if insert_log_func:
        await insert_log_func(message, log_type, source)
    else:
        logger.info(f"[{source}] {message}")
def register_google_auth_routes(fastapi_app):
    """Register Google OAuth routes with the FastAPI app and wire dependencies."""
    try:
        # Wire system state and dependencies
        # system_state will be set by server via set_system_state
        if 'insert_log_func' not in globals() or insert_log_func is None:
            set_dependencies(db_insert_log, None, None)
    except Exception as e:
        logger.warning(f"Google Auth dependencies not fully set: {e}")

    fastapi_app.add_api_route("/auth/google", google_auth_redirect, methods=["GET"])
    fastapi_app.add_api_route("/auth/google/callback", google_auth_callback, methods=["GET"])

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
GOOGLE_AUTH_URL = os.getenv("GOOGLE_AUTH_URL")
GOOGLE_TOKEN_URL = os.getenv("GOOGLE_TOKEN_URL")
GOOGLE_USERINFO_URL = os.getenv("GOOGLE_USERINFO_URL")

# Check if Google OAuth is properly configured
GOOGLE_OAUTH_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
if not GOOGLE_OAUTH_ENABLED:
    logger.warning("⚠️ Google OAuth not configured - GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables are required")



class TwoFactorVerifyRequest(BaseModel):
    secret: str = Field(..., min_length=1)
    otp: str = Field(..., min_length=6, max_length=6)


class GoogleUserInfo(BaseModel):
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    verified_email: bool = False


async def get_google_auth_url(state: str = None) -> str:
    """Generate Google OAuth URL"""
    if not GOOGLE_OAUTH_ENABLED:
        raise HTTPException(status_code=500, detail="Google OAuth not configured - please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables")
    
    if not state:
        state = secrets.token_urlsafe(32)
    
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'scope': 'openid email profile',
        'response_type': 'code',
        'state': state,
        'access_type': 'offline',
        'prompt': 'consent'
    }
    
    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    return f"{GOOGLE_AUTH_URL}?{query_string}"


async def exchange_google_code_for_token(code: str) -> dict:
    """Exchange authorization code for access token"""
    if not GOOGLE_OAUTH_ENABLED:
        raise HTTPException(status_code=500, detail="Google OAuth not configured - please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables")
    
    async with httpx.AsyncClient() as client:
        data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': GOOGLE_REDIRECT_URI
        }
        
        response = await client.post(GOOGLE_TOKEN_URL, data=data)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Google OAuth token exchange failed: {response.status_code} - {response.text}")
            raise HTTPException(status_code=400, detail="Failed to exchange code for token")


async def get_google_user_info(access_token: str) -> GoogleUserInfo:
    """Get user information from Google"""
    async with httpx.AsyncClient() as client:
        headers = {'Authorization': f'Bearer {access_token}'}
        response = await client.get(GOOGLE_USERINFO_URL, headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            return GoogleUserInfo(
                id=user_data['id'],
                email=user_data['email'],
                name=user_data.get('name', ''),
                picture=user_data.get('picture'),
                verified_email=user_data.get('verified_email', False)
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to get user info")


async def create_or_get_google_user(google_user: GoogleUserInfo, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> dict:
    """Create or get user from Google OAuth"""
    conn = None
    try:
        # Ensure database is initialized (silent)
        if not system_state.db_initialized:
            await init_db()
        
        conn = await get_db_connection()
        
        # Normalize email for consistent lookups
        normalized_email = (google_user.email or "").lower()

        # Check if user exists by email
        user_check = await conn.execute(
            'SELECT username, email, role, is_active, google_id FROM users WHERE email = ?',
            (normalized_email,)
        )
        existing_user = await user_check.fetchone()
        
        if existing_user:
            # User exists, return user info
            username, email, role, is_active, existing_google_id = existing_user
            if not is_active:
                raise HTTPException(status_code=401, detail="حساب کاربری غیرفعال است")
            
            # Backfill google_id if missing
            try:
                if not existing_google_id:
                    await conn.execute(
                        'UPDATE users SET google_id = ? WHERE username = ?',
                        (google_user.id, username)
                    )
                    await conn.commit()
            except Exception:
                # Ignore if unique or other constraint issues
                pass

            await insert_log(f"Google OAuth login for existing user: {username}", "auth")
            return {
                "user_id": username,  # Added user_id field
                "username": username,
                "email": email,
                "role": role,
                "is_new_user": False
            }
        else:
            # If not found by email, try by google_id (if previously linked)
            try:
                gid_cur = await conn.execute(
                    'SELECT username, email, role, is_active FROM users WHERE google_id = ?',
                    (google_user.id,)
                )
                gid_user = await gid_cur.fetchone()
            except Exception:
                gid_user = None

            if gid_user:
                username, email, role, is_active = gid_user
                if not is_active:
                    raise HTTPException(status_code=401, detail="حساب کاربری غیرفعال است")
                await insert_log(f"Google OAuth login via google_id for user: {username}", "auth")
                return {
                    "user_id": username,
                    "username": username,
                    "email": email,
                    "role": role,
                    "is_new_user": False
                }

            # If email was not found and google_id not linked, try to match by recent session IP/UA when user's email is empty
            candidate_user = None
            if client_ip:
                try:
                    # Prefer matching with both IP and User-Agent to reduce false positives
                    if user_agent:
                        sess_cur = await conn.execute(
                            '''
                            SELECT u.username, u.email, u.role, u.is_active
                            FROM users u
                            JOIN user_sessions us ON us.user_id = u.id
                            WHERE us.client_ip = ? AND us.user_agent = ? AND us.is_active = 1 AND us.last_activity > ?
                            ORDER BY us.last_activity DESC
                            LIMIT 1
                            ''',
                            (client_ip, user_agent, (datetime.now() - timedelta(hours=72)).isoformat())
                        )
                        candidate_user = await sess_cur.fetchone()

                    # Fallback: match only by IP if no UA match found
                    if not candidate_user:
                        sess_cur2 = await conn.execute(
                            '''
                            SELECT u.username, u.email, u.role, u.is_active
                            FROM users u
                            JOIN user_sessions us ON us.user_id = u.id
                            WHERE us.client_ip = ? AND us.is_active = 1 AND us.last_activity > ?
                            ORDER BY us.last_activity DESC
                            LIMIT 1
                            ''',
                            (client_ip, (datetime.now() - timedelta(hours=72)).isoformat())
                        )
                        candidate_user = await sess_cur2.fetchone()
                except Exception:
                    candidate_user = None

            if candidate_user:
                username, email, role, is_active = candidate_user
                # Only auto-link if the found user's email is empty/null
                if not email:
                    try:
                        await conn.execute(
                            'UPDATE users SET email = ?, google_id = ? WHERE username = ?',
                            (normalized_email, google_user.id, username)
                        )
                        await conn.commit()
                        await insert_log(f"Linked Google account to existing user by IP: {username}", "auth")
                        return {
                            "user_id": username,
                            "username": username,
                            "email": normalized_email,
                            "role": role,
                            "is_new_user": False
                        }
                    except Exception:
                        # If update fails, proceed to create a new user below
                        pass

            # Create new user
            username = f"google_{google_user.id}"
            password_hash = hash_password(secrets.token_urlsafe(32))  # Random password
            
            await conn.execute(
                'INSERT INTO users (username, email, google_id, password_hash, role, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (username, normalized_email, google_user.id, password_hash, "user", True, get_jalali_now_str())
            )
            await conn.commit()
            
            await insert_log(f"New user created via Google OAuth: {username}", "auth")
            return {
                "user_id": username,  # Added user_id field
                "username": username,
                "email": google_user.email,
                "role": "user",
                "is_new_user": True
            }
    except Exception as e:
        logger.error(f"Error in create_or_get_google_user: {e}")
        raise HTTPException(status_code=500, detail="Database error during Google OAuth")
    finally:
        if conn:
            await close_db_connection(conn)

async def verify_2fa(request: TwoFactorVerifyRequest, req: Request):
    """Two-factor authentication verification"""
    client_ip = req.client.host
    
    # Ensure database is initialized (silent)
    if not system_state.db_initialized:
        await init_db()
    
    try:
        # Sanitize inputs
        sanitized_secret = sanitize_input(request.secret)
        sanitized_otp = sanitize_input(request.otp)
        
        # Extract username from secret
        if ':' not in sanitized_secret:
            raise HTTPException(status_code=400, detail="Invalid secret format")
        
        username, secret = sanitized_secret.split(':', 1)
        
        # Verify OTP
        totp = pyotp.TOTP(secret)
        if totp.verify(sanitized_otp):
            # Get user info from database
            conn = await get_db_connection()
            try:
                user_query = await conn.execute(
                    'SELECT username, role FROM users WHERE username = ? AND is_active = 1',
                    (username,)
                )
                user_data = await user_query.fetchone()
                
                if not user_data:
                    raise HTTPException(status_code=401, detail="User not found or inactive")
                
                username, role = user_data
                
                # Create access token
                access_token = create_access_token(
                    data={"sub": username, "role": role, "ip": client_ip}
                )
                
                await insert_log(f"2FA verification successful for {username} from {client_ip}", "auth")
                
                # Create response with cookie
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
                response.set_cookie(
                    key="access_token",
                    value=access_token,
                    max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                    httponly=True,
                    secure=os.getenv("ENVIRONMENT") == "production",
                    samesite="lax"
                )
                
                return response
            finally:
                await close_db_connection(conn)
        else:
            await insert_log(f"2FA verification failed from {client_ip} for user {username}", "auth")
            raise HTTPException(status_code=401, detail="کد تأیید اشتباه است")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"2FA verification error: {e}")
        raise HTTPException(status_code=500, detail="خطا در تأیید کد")

async def google_auth_redirect(req: Request):
    """Redirect to Google OAuth"""
    client_ip = req.client.host
    
    # Check rate limiting
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    try:
        state = secrets.token_urlsafe(32)
        auth_url = await get_google_auth_url(state)
        
        # Store state for validation
        oauth_states[state] = {
            "client_ip": client_ip,
            "timestamp": time.time()
        }
        
        # Log the redirect attempt
        await insert_log(f"Google OAuth redirect initiated from {client_ip}", "auth")
        
        return RedirectResponse(url=auth_url, status_code=302)
    except Exception as e:
        logger.error(f"Google OAuth redirect error: {e}")
        await insert_log(f"Google OAuth redirect error from {client_ip}: {str(e)}", "auth")
        return RedirectResponse(url="/login?error=google_auth_failed", status_code=302)


async def google_auth_callback(req: Request):
    """Handle Google OAuth callback"""
    client_ip = req.client.host
    
    # Check rate limiting
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    try:
        # Get authorization code and state from query parameters
        code = req.query_params.get("code")
        state = req.query_params.get("state")
        error = req.query_params.get("error")
        
        if error:
            await insert_log(f"Google OAuth error from {client_ip}: {error}", "auth")
            return RedirectResponse(url="/login?error=google_auth_failed", status_code=302)
        
        if not code:
            await insert_log(f"Google OAuth missing code from {client_ip}", "auth")
            return RedirectResponse(url="/login?error=google_auth_failed", status_code=302)
        
        # Validate state parameter
        if not state:
            await insert_log(f"Google OAuth missing state from {client_ip}", "auth")
            return RedirectResponse(url="/login?error=google_auth_failed", status_code=302)
        
        # Check if state exists and is valid
        if state not in oauth_states:
            await insert_log(f"Google OAuth invalid state from {client_ip}", "auth")
            return RedirectResponse(url="/login?error=google_auth_failed", status_code=302)
        
        # Check if state is not expired (5 minutes)
        state_data = oauth_states[state]
        if time.time() - state_data["timestamp"] > 300:  # 5 minutes
            await insert_log(f"Google OAuth expired state from {client_ip}", "auth")
            del oauth_states[state]
            return RedirectResponse(url="/login?error=google_auth_failed", status_code=302)
        
        # Check if client IP matches
        if state_data["client_ip"] != client_ip:
            await insert_log(f"Google OAuth IP mismatch from {client_ip}", "auth")
            del oauth_states[state]
            return RedirectResponse(url="/login?error=google_auth_failed", status_code=302)
        
        # Remove used state
        del oauth_states[state]
        
        # Exchange code for access token
        token_data = await exchange_google_code_for_token(code)
        access_token = token_data.get("access_token")
        
        if not access_token:
            await insert_log(f"Google OAuth no access token from {client_ip}", "auth")
            return RedirectResponse(url="/login?error=google_auth_failed")
        
        # Get user info from Google
        google_user = await get_google_user_info(access_token)
        
        # Create or get user from database (pass IP/UA to help link when email missing)
        user_agent = req.headers.get('user-agent')
        user_data = await create_or_get_google_user(google_user, client_ip=client_ip, user_agent=user_agent)
        
        # Create access token (without IP validation for Google OAuth)
        access_token = create_access_token(
            data={"sub": user_data["username"], "role": user_data["role"], "ip": None}
        )
        
        # Create response with token and set cookie
        response_data = {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "username": user_data["username"],
                "role": user_data["role"],
                "is_new_user": user_data["is_new_user"]
            }
        }
        
        # Redirect to dashboard with success message
        success_url = f"/dashboard?welcome={'new_user' if user_data['is_new_user'] else 'welcome_back'}"
        response = RedirectResponse(url=success_url, status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            path="/"
        )
        
        # Add debug logging
        logger.info(f"Google OAuth successful login for user {user_data['username']} from {client_ip}")
        
        return response
        
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        try:
            await insert_log(f"Google OAuth callback error from {client_ip}: {str(e)}", "auth")
        except Exception as log_error:
            logger.error(f"Failed to log Google OAuth error: {log_error}")
        return RedirectResponse(url="/login?error=google_auth_failed")


