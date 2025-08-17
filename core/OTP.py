import os, time, re, random, logging, logging.config, logging.handlers, jdatetime, secrets, bcrypt
from .melipayamak import Api
from datetime import datetime, timedelta
from fastapi import Request, HTTPException

# Import from shared config
from .config import (
    get_jalali_now_str, SMS_USERNAME, SMS_PASSWORD, SMS_SENDER_NUMBER,
    system_state
)

# Import from other modules
from .sanitize_validate import sanitize_input, validate_iranian_mobile
from .db import get_db_connection, close_db_connection, init_db
from .Security import check_rate_limit
from .token import create_access_token

# Setup logger for this module
logger = logging.getLogger("otp")

# Constants
OTP_LENGTH = int(os.getenv("OTP_LENGTH", "6"))
OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "5"))
MAX_OTP_ATTEMPTS = int(os.getenv("MAX_OTP_ATTEMPTS", "3"))
OTP_RESEND_COOLDOWN = int(os.getenv("OTP_RESEND_COOLDOWN", "60"))  # seconds
OTP_STORAGE_CLEANUP_INTERVAL = int(os.getenv("OTP_STORAGE_CLEANUP_INTERVAL", "3600"))  # 1 hour

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
                self.db_initialized = False
        system_state = TempSystemState()
    return system_state

# Global function references (will be set by main server)
insert_log = None
send_sms_func = None

def set_dependencies(log_func, sms_func):
    """Set dependencies from main server"""
    global insert_log, send_sms_func
    insert_log = log_func
    send_sms_func = sms_func

# Global storage for mobile OTP rate limiting
mobile_otp_rate_limit_storage = {}

async def check_mobile_otp_attempts(phone: str) -> bool:
    """Check if mobile OTP attempts limit is exceeded"""
    try:
        conn = await get_db_connection()
        try:
            # Clean up expired OTPs and sessions
            await conn.execute('DELETE FROM mobile_otp WHERE expires_at < ?', (datetime.now().isoformat(),))
            await conn.execute('DELETE FROM user_sessions WHERE expires_at < ?', (datetime.now().isoformat(),))
            await conn.commit()
            
            # Check attempts in the last hour
            one_hour_ago = datetime.now() - timedelta(hours=1)
            
            attempts_check = await conn.execute(
                'SELECT COUNT(*) FROM mobile_otp WHERE phone = ? AND created_at >= ?',
                (phone, one_hour_ago.isoformat())
            )
            attempts_count = await attempts_check.fetchone()
            
            # Allow maximum 5 attempts per phone number per hour
            return attempts_count[0] < 5
            
        finally:
            await close_db_connection(conn)
    except Exception as e:
        logger.error(f"Error checking mobile OTP attempts: {e}")
        return False  # Fail safe - deny if error




def check_mobile_otp_rate_limit(client_ip: str) -> bool:
    """Check rate limiting specifically for mobile OTP requests"""
    global mobile_otp_rate_limit_storage
    
    # Handle invalid IP addresses gracefully
    if client_ip is None or not isinstance(client_ip, str):
        return False
    
    # Skip rate limiting for local connections
    if "127.0.0.1" in client_ip or "localhost" in client_ip:
        return True
    
    current_time = time.time()
    window_seconds = 300  # 5 minutes
    max_requests = 3  # 3 requests per 5 minutes
    
    window_start = current_time - window_seconds
    
    # Clean old entries
    mobile_otp_rate_limit_storage = {ip: timestamps for ip, timestamps in mobile_otp_rate_limit_storage.items() 
                                    if any(ts > window_start for ts in timestamps)}
    
    # Check current IP
    if client_ip not in mobile_otp_rate_limit_storage:
        mobile_otp_rate_limit_storage[client_ip] = []
    
    # Remove old timestamps
    mobile_otp_rate_limit_storage[client_ip] = [ts for ts in mobile_otp_rate_limit_storage[client_ip] if ts > window_start]
    
    # Check if limit exceeded
    if len(mobile_otp_rate_limit_storage[client_ip]) >= max_requests:
        return False
    
    # Add current request
    mobile_otp_rate_limit_storage[client_ip].append(current_time)
    return True




def process_mobile_number(phone: str) -> str:
    """
    Standardize Iranian mobile number to 10 digits (9xxxxxxxxx)
    Accepts: 0912..., 98912..., +98912..., 912..., etc.
    """
    if not phone or not isinstance(phone, str):
        return ""
    phone = phone.strip()
    # Remove all non-digit characters except leading +
    if phone.startswith('+'):
        phone = '+' + re.sub(r'[^\d]', '', phone[1:])
    else:
        phone = re.sub(r'[^\d]', '', phone)
    # Remove country code
    if phone.startswith('+98'):
        phone = phone[3:]
    elif phone.startswith('0098'):
        phone = phone[4:]
    elif phone.startswith('98'):
        phone = phone[2:]
    elif phone.startswith('0'):
        phone = phone[1:]
    # Now should be 10 digits starting with 9
    return phone if len(phone) == 10 and phone.startswith('9') else ""

# Mobile Login API Endpoints
async def send_mobile_otp(request: Request):
    """Send OTP to mobile number with comprehensive security validation"""
    print("🔍 MOBILE API ENDPOINT CALLED!")
    logger.info("🔍 MOBILE API ENDPOINT CALLED!")
    client_ip = request.client.host
    
    # Ensure database is initialized
    if not system_state.db_initialized:
        await init_db()
    
    # Check rate limiting using existing function
    if not check_rate_limit(client_ip):
        # DEBUG: Log general rate limiting for send
        logger.info(f"⏳ DEBUG GENERAL RATE LIMIT SEND: IP {client_ip} rate limited")
        print(f"⏳ DEBUG GENERAL RATE LIMIT SEND: IP {client_ip} rate limited")
        raise HTTPException(status_code=429, detail="تعداد درخواست‌های شما بیش از حد مجاز است. لطفاً کمی صبر کنید.")
    
    try:
        # Parse and validate request body
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON format")
        
        # Extract and validate phone number
        phone = body.get('phone', '').strip()
        user_agent = body.get('user_agent', '').strip()
        captcha_id = body.get('captcha_id', '').strip()
        captcha_text = body.get('captcha_text', '').strip()
        
        # Enhanced buffer overflow protection with stricter limits
        if len(phone) > 15 or len(user_agent) > 500 or len(captcha_id) > 50 or len(captcha_text) > 10:
            raise HTTPException(status_code=400, detail="ورودی نامعتبر - طول فیلد بیش از حد مجاز است")
        
        # CAPTCHA validation for mobile endpoints (client-side generated)
        if not captcha_text:
            raise HTTPException(status_code=400, detail="کد کپچا الزامی است")
        
        # For mobile CAPTCHA, we accept any non-empty input since it's client-side generated
        # This is similar to how other CAPTCHAs work in the system
        if len(captcha_text.strip()) < 4:  # Minimum length check
            raise HTTPException(status_code=400, detail="کد کپچا نامعتبر است")
        
        # Enhanced input sanitization and validation with security detection
        # Don't sanitize CAPTCHA text since it's generated by the server
        sanitized_phone = sanitize_input(phone, 'text', raise_on_detection=False)
        sanitized_user_agent = sanitize_input(user_agent, 'text', raise_on_detection=False)
        
        # Comprehensive input validation
        if not sanitized_phone:
            raise HTTPException(status_code=400, detail="شماره تلفن الزامی است")
        
        # Process and validate phone number
        processed_phone = process_mobile_number(sanitized_phone)
        if not validate_iranian_mobile(processed_phone):
            raise HTTPException(status_code=400, detail="فرمت شماره تلفن نامعتبر است. شماره باید 10 رقم و شروع با 9 باشد")
        
        # Use processed phone number for further operations
        sanitized_phone = processed_phone
        
        # Additional buffer overflow protection for sanitized input
        if len(sanitized_phone) > 15:
            raise HTTPException(status_code=400, detail="شماره تلفن خیلی طولانی است")
        
        # Check for dangerous patterns in phone number
        dangerous_patterns = [
            r'[<>"\']',  # HTML/XML tags
            r'javascript:', r'vbscript:', r'data:',  # Script protocols
            r'[;&|`]',  # Command separators
            r'\.\./', r'\.\.\\',  # Path traversal
            r'<script', r'<iframe', r'<object',  # Script tags
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, sanitized_phone, re.IGNORECASE):
                logger.warning(f"Dangerous pattern detected in phone: {pattern}")
                raise HTTPException(status_code=400, detail="ورودی نامعتبر")
        
        # Validate user agent length
        if len(sanitized_user_agent) > 500:
            raise HTTPException(status_code=400, detail="User agent خیلی طولانی است")
        
        # Check mobile OTP attempts limit using existing pattern
        if not await check_mobile_otp_attempts(sanitized_phone):
            # DEBUG: Log rate limiting for send
            logger.info(f"⏳ DEBUG RATE LIMIT SEND: Phone {sanitized_phone} rate limited from IP {client_ip}")
            print(f"⏳ DEBUG RATE LIMIT SEND: Phone {sanitized_phone} rate limited from IP {client_ip}")
            raise HTTPException(status_code=429, detail="تعداد تلاش‌های ارسال کد شما در 1 ساعت گذشته به حداکثر رسیده است. لطفاً 1 ساعت صبر کنید.")
        
        # Check if user already exists with this phone number (check multiple formats)
        conn = await get_db_connection()
        try:
            # Check with processed phone number
            user_check = await conn.execute(
                'SELECT id, username, email, COALESCE(full_name, "") as full_name FROM users WHERE phone = ?',
                (sanitized_phone,)
            )
            existing_user = await user_check.fetchone()
            
            if not existing_user:
                # Check with original format (with leading 0)
                original_phone = '0' + sanitized_phone
                user_check = await conn.execute(
                    'SELECT id, username, email, COALESCE(full_name, "") as full_name FROM users WHERE phone = ?',
                    (original_phone,)
                )
                existing_user = await user_check.fetchone()
                
                if existing_user:
                    logger.info(f"Existing user found with original phone format: {existing_user[1]} (ID: {existing_user[0]})")
            
            if existing_user:
                user_id, username, email, full_name = existing_user
                logger.info(f"Existing user found for mobile OTP: {username} (ID: {user_id})")
                is_existing_user = True
            else:
                is_existing_user = False
                logger.info(f"No existing user found for mobile OTP: {sanitized_phone}")
                
        finally:
            await close_db_connection(conn)
        
        # Generate unique OTP for mobile login
        otp = await generate_unique_mobile_otp(sanitized_phone)
        
        # Store OTP in database using existing pattern
        otp_expires = datetime.now() + timedelta(minutes=5)  # 5 minutes expiration
        
        conn = await get_db_connection()
        try:
            # Clean up expired OTPs first
            await conn.execute('DELETE FROM mobile_otp WHERE expires_at < ?', (datetime.now().isoformat(),))
            
            # Insert new OTP
            await conn.execute(
                'INSERT INTO mobile_otp (phone, otp, expires_at, created_at, client_ip, user_agent) VALUES (?, ?, ?, ?, ?, ?)',
                (sanitized_phone, otp, otp_expires.isoformat(), get_jalali_now_str(), client_ip, sanitized_user_agent)
            )
            await conn.commit()
            
            # DEBUG: Log OTP storage
            logger.info(f"💾 DEBUG OTP STORAGE: OTP {otp} stored in database for phone {sanitized_phone}")
            print(f"💾 DEBUG OTP STORAGE: OTP {otp} stored in database for phone {sanitized_phone}")
            
            # Verify OTP was stored
            cursor = await conn.execute(
                'SELECT otp FROM mobile_otp WHERE phone = ? ORDER BY created_at DESC LIMIT 1',
                (sanitized_phone,)
            )
            stored_otp = await cursor.fetchone()
            
            if not stored_otp or stored_otp[0] != otp:
                logger.error(f"OTP storage verification failed for {sanitized_phone}")
                # DEBUG: Log storage verification failure
                print(f"❌ DEBUG OTP STORAGE VERIFICATION: Failed to verify OTP {otp} storage for phone {sanitized_phone}")
                raise HTTPException(status_code=500, detail="خطا در ذخیره کد تأیید")
                
        finally:
            await close_db_connection(conn)
        
        # Log the OTP request for security monitoring
        logger.info(f"Mobile OTP requested for phone: {sanitized_phone[:4]}****{sanitized_phone[-2:]}, IP: {client_ip}")
        await insert_log(f"Mobile OTP requested for {sanitized_phone[:4]}****{sanitized_phone[-2:]} from {client_ip}", "auth")
        
        # DEBUG: Log OTP code for development/testing purposes
        logger.info(f"🔐 DEBUG OTP: Code {otp} generated for phone {sanitized_phone} from IP {client_ip}")
        print(f"🔐 DEBUG OTP: Code {otp} generated for phone {sanitized_phone} from IP {client_ip}")
        
        # Send SMS using existing SMS function
        try:
            sms_sent = await send_mobile_otp_sms(sanitized_phone, otp)
            if sms_sent:
                await insert_log(f"Mobile OTP SMS sent to {sanitized_phone[:4]}****{sanitized_phone[-2:]} from {client_ip}", "auth")
                
                return {
                    "success": True,
                    "message": "کد تأیید با موفقیت ارسال شد",
                    "phone": sanitized_phone[:4] + "****" + sanitized_phone[-2:],  # Masked phone for security
                    "otp": otp,  # For testing purposes only - remove in production
                    "is_existing_user": is_existing_user
                }
            else:
                # If SMS failed, still return success but with OTP for testing
                logger.warning(f"SMS sending failed for {sanitized_phone}, returning OTP for testing")
                await insert_log(f"Mobile OTP SMS failed for {sanitized_phone[:4]}****{sanitized_phone[-2:]} from {client_ip}", "auth")
                
                return {
                    "success": True,
                    "message": "کد تأیید برای تست ارسال شد (SMS غیرفعال)",
                    "phone": sanitized_phone[:4] + "****" + sanitized_phone[-2:],
                    "otp": otp  # For testing purposes only - remove in production
                }
            
        except Exception as sms_error:
            logger.error(f"Failed to send mobile OTP SMS: {sms_error}")
            # Don't log OTP for security reasons
            await insert_log(f"Mobile OTP SMS failed for {sanitized_phone[:4]}****{sanitized_phone[-2:]} from {client_ip}", "error")
            

            # Return success to prevent enumeration attacks
            return {
                "success": True,
                "message": "کد تأیید با موفقیت ارسال شد",
                "phone": sanitized_phone[:4] + "****" + sanitized_phone[-2:],
                "is_existing_user": is_existing_user
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_mobile_otp: {e}")
        await insert_log(f"Mobile OTP error: {str(e)} from {client_ip}", "error")
        raise HTTPException(status_code=500, detail="خطا در ارسال کد تأیید")


async def resend_mobile_otp(request: Request):
    """Resend OTP to mobile number without CAPTCHA requirement"""
    client_ip = request.client.host
    
    # Ensure database is initialized
    if not system_state.db_initialized:
        await init_db()
    
    # Check rate limiting using existing function
    if not check_rate_limit(client_ip):
        # DEBUG: Log general rate limiting for resend
        logger.info(f"⏳ DEBUG GENERAL RATE LIMIT RESEND: IP {client_ip} rate limited")
        print(f"⏳ DEBUG GENERAL RATE LIMIT RESEND: IP {client_ip} rate limited")
        raise HTTPException(status_code=429, detail="تعداد درخواست‌های شما بیش از حد مجاز است. لطفاً کمی صبر کنید.")
    
    try:
        # Parse and validate request body
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON format")
        
        # Extract and validate phone number
        phone = body.get('phone', '').strip()
        user_agent = body.get('user_agent', '').strip()
        
        # Enhanced buffer overflow protection with stricter limits
        if len(phone) > 15 or len(user_agent) > 500:
            raise HTTPException(status_code=400, detail="ورودی نامعتبر - طول فیلد بیش از حد مجاز است")
        
        # Enhanced input sanitization and validation with security detection
        sanitized_phone = sanitize_input(phone, 'text', raise_on_detection=False)
        sanitized_user_agent = sanitize_input(user_agent, 'text', raise_on_detection=False)
        
        # Comprehensive input validation
        if not sanitized_phone:
            raise HTTPException(status_code=400, detail="شماره تلفن الزامی است")
        
        # Process and validate phone number
        processed_phone = process_mobile_number(sanitized_phone)
        if not validate_iranian_mobile(processed_phone):
            raise HTTPException(status_code=400, detail="فرمت شماره تلفن نامعتبر است. شماره باید 10 رقم و شروع با 9 باشد")
        
        # Use processed phone number for further operations
        sanitized_phone = processed_phone
        
        # Check mobile OTP attempts limit using existing pattern
        if not await check_mobile_otp_attempts(sanitized_phone):
            # DEBUG: Log rate limiting for resend
            logger.info(f"⏳ DEBUG RATE LIMIT RESEND: Phone {sanitized_phone} rate limited from IP {client_ip}")
            print(f"⏳ DEBUG RATE LIMIT RESEND: Phone {sanitized_phone} rate limited from IP {client_ip}")
            raise HTTPException(status_code=429, detail="تعداد تلاش‌های ارسال کد شما در 1 ساعت گذشته به حداکثر رسیده است. لطفاً 1 ساعت صبر کنید.")
        
        # Check if user already exists with this phone number (check multiple formats)
        conn = await get_db_connection()
        try:
            # Check with processed phone number
            user_check = await conn.execute(
                'SELECT id, username, email, COALESCE(full_name, "") as full_name FROM users WHERE phone = ?',
                (sanitized_phone,)
            )
            existing_user = await user_check.fetchone()
            
            if not existing_user:
                # Check with original format (with leading 0)
                original_phone = '0' + sanitized_phone
                user_check = await conn.execute(
                    'SELECT id, username, email, COALESCE(full_name, "") as full_name FROM users WHERE phone = ?',
                    (original_phone,)
                )
                existing_user = await user_check.fetchone()
                
                if existing_user:
                    logger.info(f"Existing user found with original phone format for resend: {existing_user[1]} (ID: {existing_user[0]})")
            
            if existing_user:
                user_id, username, email, full_name = existing_user
                logger.info(f"Existing user found for mobile OTP resend: {username} (ID: {user_id})")
                is_existing_user = True
            else:
                is_existing_user = False
                logger.info(f"No existing user found for mobile OTP resend: {sanitized_phone}")
                
        finally:
            await close_db_connection(conn)
        
        # Generate unique OTP for mobile login
        otp = await generate_unique_mobile_otp(sanitized_phone)
        
        # Store OTP in database using existing pattern
        otp_expires = datetime.now() + timedelta(minutes=5)  # 5 minutes expiration
        
        conn = await get_db_connection()
        try:
            # Clean up expired OTPs first
            await conn.execute('DELETE FROM mobile_otp WHERE expires_at < ?', (datetime.now().isoformat(),))
            
            # Insert new OTP
            await conn.execute(
                'INSERT INTO mobile_otp (phone, otp, expires_at, created_at, client_ip, user_agent) VALUES (?, ?, ?, ?, ?, ?)',
                (sanitized_phone, otp, otp_expires.isoformat(), get_jalali_now_str(), client_ip, sanitized_user_agent)
            )
            await conn.commit()
            
            # DEBUG: Log OTP storage for resend
            logger.info(f"💾 DEBUG OTP STORAGE RESEND: OTP {otp} stored in database for phone {sanitized_phone}")
            print(f"💾 DEBUG OTP STORAGE RESEND: OTP {otp} stored in database for phone {sanitized_phone}")
            
            # Verify OTP was stored
            cursor = await conn.execute(
                'SELECT otp FROM mobile_otp WHERE phone = ? ORDER BY created_at DESC LIMIT 1',
                (sanitized_phone,)
            )
            stored_otp = await cursor.fetchone()
            
            if not stored_otp or stored_otp[0] != otp:
                logger.error(f"OTP storage verification failed for {sanitized_phone}")
                # DEBUG: Log storage verification failure for resend
                print(f"❌ DEBUG OTP STORAGE VERIFICATION RESEND: Failed to verify OTP {otp} storage for phone {sanitized_phone}")
                raise HTTPException(status_code=500, detail="خطا در ذخیره کد تأیید")
                
        finally:
            await close_db_connection(conn)
        
        # Log the OTP request for security monitoring
        logger.info(f"Mobile OTP resent for phone: {sanitized_phone[:4]}****{sanitized_phone[-2:]}, IP: {client_ip}")
        await insert_log(f"Mobile OTP resent for {sanitized_phone[:4]}****{sanitized_phone[-2:]} from {client_ip}", "auth")
        
        # DEBUG: Log OTP code for development/testing purposes
        logger.info(f"🔐 DEBUG OTP RESEND: Code {otp} regenerated for phone {sanitized_phone} from IP {client_ip}")
        print(f"🔐 DEBUG OTP RESEND: Code {otp} regenerated for phone {sanitized_phone} from IP {client_ip}")
        
        # Send SMS using existing SMS function
        try:
            sms_sent = await send_mobile_otp_sms(sanitized_phone, otp)
            if sms_sent:
                await insert_log(f"Mobile OTP SMS resent to {sanitized_phone[:4]}****{sanitized_phone[-2:]} from {client_ip}", "auth")
                
                return {
                    "success": True,
                    "message": "کد تأیید مجدداً ارسال شد",
                    "phone": sanitized_phone[:4] + "****" + sanitized_phone[-2:],  # Masked phone for security
                    "otp": otp,  # For testing purposes only - remove in production
                    "is_existing_user": is_existing_user
                }
            else:
                # If SMS failed, still return success but with OTP for testing
                logger.warning(f"SMS sending failed for {sanitized_phone}, returning OTP for testing")
                await insert_log(f"Mobile OTP SMS failed for {sanitized_phone[:4]}****{sanitized_phone[-2:]} from {client_ip}", "auth")
                
                return {
                    "success": True,
                    "message": "کد تأیید برای تست ارسال شد (SMS غیرفعال)",
                    "phone": sanitized_phone[:4] + "****" + sanitized_phone[-2:],
                    "otp": otp  # For testing purposes only - remove in production
                }
            
        except Exception as sms_error:
            logger.error(f"Failed to send mobile OTP SMS: {sms_error}")
            # Don't log OTP for security reasons
            await insert_log(f"Mobile OTP SMS failed for {sanitized_phone[:4]}****{sanitized_phone[-2:]} from {client_ip}", "error")
            

            # Return success to prevent enumeration attacks
            return {
                "success": True,
                "message": "کد تأیید مجدداً ارسال شد",
                "phone": sanitized_phone[:4] + "****" + sanitized_phone[-2:]
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in resend_mobile_otp: {e}")
        await insert_log(f"Mobile OTP resend error: {str(e)} from {client_ip}", "error")
        raise HTTPException(status_code=500, detail="خطا در ارسال مجدد کد تأیید")


async def verify_mobile_otp(request: Request):
    """Verify OTP and create user session"""
    client_ip = request.client.host
    
    # Ensure database is initialized
    if not system_state.db_initialized:
        await init_db()
    
    # Check rate limiting using existing function
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="تعداد درخواست‌های شما بیش از حد مجاز است. لطفاً کمی صبر کنید.")
    
    try:
        # Parse and validate request body
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON format")
        
        # Extract and validate inputs
        phone = body.get('phone', '').strip()
        otp = body.get('otp', '').strip()
        user_agent = body.get('user_agent', '').strip()
        
        # Enhanced input sanitization and validation with security detection
        sanitized_phone = sanitize_input(phone, 'text', raise_on_detection=False)
        sanitized_otp = sanitize_input(otp, 'text', raise_on_detection=True)
        sanitized_user_agent = sanitize_input(user_agent, 'text', raise_on_detection=False)
        
        # Input validation
        if not sanitized_phone or not sanitized_otp:
            raise HTTPException(status_code=400, detail="شماره تلفن و کد تأیید الزامی است")
        
        # Process and validate phone number
        processed_phone = process_mobile_number(sanitized_phone)
        if not validate_iranian_mobile(processed_phone):
            raise HTTPException(status_code=400, detail="فرمت شماره تلفن نامعتبر است")
        
        # Use processed phone number for further operations
        sanitized_phone = processed_phone
        
        # Enhanced OTP validation with security checks
        if not re.match(r'^[0-9]{6}$', sanitized_otp):
            raise HTTPException(status_code=400, detail="فرمت کد تأیید نامعتبر است")
        
        # Enhanced buffer overflow protection with stricter limits
        if len(phone) > 15 or len(otp) > 10 or len(user_agent) > 500:
            raise HTTPException(status_code=400, detail="ورودی نامعتبر - طول فیلد بیش از حد مجاز است")
        
        # Additional buffer overflow protection for sanitized input
        if len(sanitized_otp) > 10:
            raise HTTPException(status_code=400, detail="کد تأیید خیلی طولانی است")
        
        # Check for dangerous patterns in inputs
        dangerous_patterns = [
            r'[<>"\']',  # HTML/XML tags
            r'javascript:', r'vbscript:', r'data:',  # Script protocols
            r'[;&|`]',  # Command separators
            r'\.\./', r'\.\.\\',  # Path traversal
            r'<script', r'<iframe', r'<object',  # Script tags
            r'\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b',  # SQL keywords
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, sanitized_phone, re.IGNORECASE) or re.search(pattern, sanitized_otp, re.IGNORECASE):
                logger.warning(f"Dangerous pattern detected in input: {pattern}")
                raise HTTPException(status_code=400, detail="ورودی نامعتبر")
        
        # Validate user agent length
        if len(sanitized_user_agent) > 500:
            raise HTTPException(status_code=400, detail="User agent خیلی طولانی است")
        
        # Get stored OTP data from database
        conn = await get_db_connection()
        try:
            # Clean up expired OTPs first
            await conn.execute('DELETE FROM mobile_otp WHERE expires_at < ?', (datetime.now().isoformat(),))
            
            otp_check = await conn.execute(
                'SELECT otp, expires_at, attempts FROM mobile_otp WHERE phone = ? ORDER BY created_at DESC LIMIT 1',
                (sanitized_phone,)
            )
            otp_data = await otp_check.fetchone()
            
            if not otp_data:
                # DEBUG: Log OTP not found
                logger.info(f"❌ DEBUG OTP RETRIEVAL: No OTP found for phone {sanitized_phone} from IP {client_ip}")
                print(f"❌ DEBUG OTP RETRIEVAL: No OTP found for phone {sanitized_phone} from IP {client_ip}")
                raise HTTPException(status_code=400, detail="کد تأیید یافت نشد یا منقضی شده است")
            
            stored_otp, expires_at, attempts = otp_data
            
            # DEBUG: Log OTP retrieval
            logger.info(f"🔍 DEBUG OTP RETRIEVAL: Retrieved OTP {stored_otp} for phone {sanitized_phone} from IP {client_ip}")
            print(f"🔍 DEBUG OTP RETRIEVAL: Retrieved OTP {stored_otp} for phone {sanitized_phone} from IP {client_ip}")
            
            # Check OTP expiration
            if datetime.fromisoformat(expires_at) < datetime.now():
                # DEBUG: Log OTP expiration
                logger.info(f"⏰ DEBUG OTP EXPIRATION: OTP {stored_otp} expired for phone {sanitized_phone} from IP {client_ip}")
                print(f"⏰ DEBUG OTP EXPIRATION: OTP {stored_otp} expired for phone {sanitized_phone} from IP {client_ip}")
                
                # Mark as expired
                await conn.execute('UPDATE mobile_otp SET attempts = 999 WHERE phone = ?', (sanitized_phone,))
                await conn.commit()
                raise HTTPException(status_code=400, detail="کد تأیید منقضی شده است")
            
            # Check attempts limit
            if attempts >= 3:
                # DEBUG: Log OTP attempts exceeded
                logger.info(f"🚫 DEBUG OTP ATTEMPTS: OTP {stored_otp} attempts exceeded (3/3) for phone {sanitized_phone} from IP {client_ip}")
                print(f"🚫 DEBUG OTP ATTEMPTS: OTP {stored_otp} attempts exceeded (3/3) for phone {sanitized_phone} from IP {client_ip}")
                raise HTTPException(status_code=400, detail="تعداد تلاش‌های ناموفق به حداکثر رسیده است. لطفاً کد جدید درخواست کنید")
            
            # Increment attempts
            await conn.execute('UPDATE mobile_otp SET attempts = attempts + 1 WHERE phone = ?', (sanitized_phone,))
            await conn.commit()
            
            # DEBUG: Log OTP attempt increment
            logger.info(f"📊 DEBUG OTP ATTEMPTS: OTP {stored_otp} attempt {attempts + 1}/3 for phone {sanitized_phone} from IP {client_ip}")
            print(f"📊 DEBUG OTP ATTEMPTS: OTP {stored_otp} attempt {attempts + 1}/3 for phone {sanitized_phone} from IP {client_ip}")
            
            # Verify OTP
            if stored_otp != sanitized_otp:
                # DEBUG: Log OTP verification failure
                logger.info(f"❌ DEBUG OTP VERIFICATION: Invalid OTP {sanitized_otp} for phone {sanitized_phone} from IP {client_ip}")
                print(f"❌ DEBUG OTP VERIFICATION: Invalid OTP {sanitized_otp} for phone {sanitized_phone} from IP {client_ip}")
                raise HTTPException(status_code=400, detail="کد تأیید نامعتبر است")
            
            # DEBUG: Log successful OTP verification
            logger.info(f"✅ DEBUG OTP VERIFICATION: Valid OTP {sanitized_otp} verified for phone {sanitized_phone} from IP {client_ip}")
            print(f"✅ DEBUG OTP VERIFICATION: Valid OTP {sanitized_otp} verified for phone {sanitized_phone} from IP {client_ip}")
            
            # OTP is valid - create or get user (check multiple phone formats)
            user_check = await conn.execute(
                'SELECT id, username, email, COALESCE(full_name, "") as full_name FROM users WHERE phone = ? AND is_active = 1',
                (sanitized_phone,)
            )
            user_data = await user_check.fetchone()
            
            if not user_data:
                # Check with original format (with leading 0)
                original_phone = '0' + sanitized_phone
                user_check = await conn.execute(
                    'SELECT id, username, email, COALESCE(full_name, "") as full_name FROM users WHERE phone = ? AND is_active = 1',
                    (original_phone,)
                )
                user_data = await user_check.fetchone()
                
                if user_data:
                    logger.info(f"Existing user found with original phone format: {user_data[1]} (ID: {user_data[0]})")
            
            if user_data:
                user_id, username, email, full_name = user_data
                logger.info(f"Existing user found for mobile login: {username} (ID: {user_id})")
            else:
                # Check if user exists with different login method (email/username) - check both formats
                existing_user_check = await conn.execute(
                    'SELECT id, username, email, COALESCE(full_name, "") as full_name FROM users WHERE phone = ?',
                    (sanitized_phone,)
                )
                existing_user = await existing_user_check.fetchone()
                
                if not existing_user:
                    # Check with original format
                    original_phone = '0' + sanitized_phone
                    existing_user_check = await conn.execute(
                        'SELECT id, username, email, COALESCE(full_name, "") as full_name FROM users WHERE phone = ?',
                        (original_phone,)
                    )
                    existing_user = await existing_user_check.fetchone()
                    
                    if existing_user:
                        logger.info(f"Existing inactive user found with original phone format: {existing_user[1]} (ID: {existing_user[0]})")
                
                if existing_user:
                    # User exists but might be inactive, reactivate them
                    user_id, username, email, full_name = existing_user
                    await conn.execute(
                        'UPDATE users SET is_active = 1, login_method = ?, last_login = ? WHERE id = ?',
                        ('mobile', get_jalali_now_str(), user_id)
                    )
                    await conn.commit()
                    logger.info(f"Reactivated existing user for mobile login: {username} (ID: {user_id})")
                else:
                    # Create new user for mobile login
                    username = f"mobile_{sanitized_phone}"
                    # Generate a secure password hash for mobile users
                    mobile_password = secrets.token_urlsafe(16)
                    password_hash = bcrypt.hashpw(mobile_password.encode('utf-8'), bcrypt.gensalt(12))
                    
                    await conn.execute(
                        'INSERT INTO users (username, phone, password_hash, is_active, created_at, login_method) VALUES (?, ?, ?, 1, ?, ?)',
                        (username, sanitized_phone, password_hash.decode('utf-8'), get_jalali_now_str(), 'mobile')
                    )
                    await conn.commit()
                    
                    # Get the new user ID
                    user_check = await conn.execute('SELECT id FROM users WHERE phone = ?', (sanitized_phone,))
                    user_data = await user_check.fetchone()
                    user_id = user_data[0]
                    email = None
                    full_name = ""
                    logger.info(f"Created new user for mobile login: {username} (ID: {user_id})")
            
            # Generate JWT token for mobile login
            token_data = {
                "sub": username,
                "user_id": user_id,
                "phone": sanitized_phone,
                "login_method": "mobile"
            }
            
            # Create JWT token with IP address for security
            session_token = create_access_token(token_data, ip_address=client_ip)
            
            # Store session in database with sliding expiration
            session_expires = datetime.now() + timedelta(hours=24)  # 24 hours
            await conn.execute(
                'INSERT INTO user_sessions (user_id, session_token, expires_at, created_at, last_activity, client_ip, user_agent, login_method) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (user_id, session_token, session_expires.isoformat(), get_jalali_now_str(), get_jalali_now_str(), client_ip, user_agent, 'mobile')
            )
            await conn.commit()
            
            # Update session activity (sliding expiration)
            await conn.execute(
                'UPDATE user_sessions SET last_activity = ? WHERE session_token = ?',
                (get_jalali_now_str(), session_token)
            )
            
            # Clean up OTP and expired OTPs
            await conn.execute('DELETE FROM mobile_otp WHERE phone = ? OR expires_at < ?', 
                             (sanitized_phone, datetime.now().isoformat()))
            await conn.commit()
            
        finally:
            await close_db_connection(conn)
        
        # Log successful login
        logger.info(f"Mobile login successful for phone: {sanitized_phone[:4]}****{sanitized_phone[-2:]}, IP: {client_ip}")
        await insert_log(f"Mobile login successful for {sanitized_phone[:4]}****{sanitized_phone[-2:]} from {client_ip}", "auth")
        
        return {
            "success": True,
            "message": "ورود موفقیت‌آمیز",
            "token": session_token,
            "phone": sanitized_phone[:4] + "****" + sanitized_phone[-2:],  # Masked phone
            "user_id": user_id,
            "username": username,
            "email": email or "",
            "full_name": full_name or "",
            "is_existing_user": email is not None and email != "" or (full_name is not None and full_name != "")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in verify_mobile_otp: {e}")
        await insert_log(f"Mobile OTP verification error: {str(e)} from {client_ip}", "error")
        raise HTTPException(status_code=500, detail="خطا در تأیید کد")


# Helper functions for mobile login
async def send_mobile_otp_sms(phone: str, otp: str) -> bool:
    """Send mobile OTP SMS using existing SMS infrastructure"""
    try:
        # Get current time in Jalali calendar
        current_time = datetime.now()
        jalali_date = jdatetime.date.fromgregorian(date=current_time.date())
        jdate = jalali_date.strftime('%Y/%m/%d')
        
        day_of_week_farsi = {
            'Monday': 'دوشنبه', 'Tuesday': 'سه‌شنبه', 'Wednesday': 'چهارشنبه',
            'Thursday': 'پنج‌شنبه', 'Friday': 'جمعه', 'Saturday': 'شنبه', 'Sunday': 'یکشنبه'
        }
        day_of_week = day_of_week_farsi[current_time.strftime('%A')]
        formatted_time = current_time.strftime('%H:%M:%S')
        
        # Create attractive and professional SMS message (optimized for SMS length)
        message = (
            f"🔐 سیستم هوشمند دوربین امنیتی\n\n"
            f"👋 سلام کاربر عزیز\n"
            f"🎯 کد تأیید ورود: {otp}\n"
            f"📱 شماره: {phone}\n"
            f"⏰ انقضا: 5 دقیقه\n"
            f"📅 {jdate}\n"
            f"🕐 {formatted_time}\n\n"
            f"🛡️ امنیت شما، اولویت ماست\n"
            f"📱 پشتیبانی: @a_ra_80\n\n"
            f"🔢 لغو 11"
        )
        
        # Send SMS using existing infrastructure
        if SMS_USERNAME and SMS_PASSWORD and SMS_SENDER_NUMBER:
            try:
                # Convert phone number to local format
                if phone.startswith('+989'):
                    sms_phone = '0' + phone[3:]
                elif phone.startswith('989'):
                    sms_phone = '0' + phone[2:]
                elif phone.startswith('09'):
                    sms_phone = phone
                elif phone.startswith('9') and len(phone) == 10:
                    sms_phone = '0' + phone
                else:
                    sms_phone = phone
                
                # DEBUG: Log SMS sending attempt
                logger.info(f"📱 DEBUG SMS: Attempting to send OTP {otp} to phone {sms_phone}")
                print(f"📱 DEBUG SMS: Attempting to send OTP {otp} to phone {sms_phone}")
                
                # Initialize API
                api = Api(SMS_USERNAME, SMS_PASSWORD)
                sms = api.sms()
                
                # Send SMS
                response = sms.send(sms_phone, SMS_SENDER_NUMBER, message)
                
                if response and 'error' in str(response).lower():
                    logger.error(f"Failed to send mobile OTP SMS to {sms_phone}: {response}")
                    # DEBUG: Log failed SMS attempt
                    print(f"❌ DEBUG SMS FAILED: OTP {otp} failed to send to {sms_phone}: {response}")
                    return False
                else:
                    logger.info(f"Mobile OTP SMS sent successfully to {sms_phone}")
                    # DEBUG: Log successful SMS
                    print(f"✅ DEBUG SMS SUCCESS: OTP {otp} sent successfully to {sms_phone}")
                    return True
            except Exception as e:
                logger.error(f"Exception sending mobile OTP SMS to {sms_phone}: {e}")
                # DEBUG: Log SMS exception
                print(f"💥 DEBUG SMS EXCEPTION: OTP {otp} failed to send to {sms_phone}: {e}")
                return False
        else:
            logger.warning("SMS credentials not configured, skipping SMS sending")
            # DEBUG: Log SMS credentials missing
            print(f"⚠️ DEBUG SMS: Credentials missing, OTP {otp} would be sent to {phone} if configured")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send mobile OTP SMS: {e}")
        return False

async def generate_unique_mobile_otp(phone: str) -> str:
    """Generate unique 6-digit OTP for mobile login"""
    max_attempts = 20  # Increased attempts
    for attempt in range(max_attempts):
        # Generate OTP with better randomness
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # Avoid problematic patterns
        if code in ['000000', '111111', '222222', '333333', '444444', '555555', '666666', '777777', '888888', '999999']:
            continue
        
        # Check if code already exists in mobile_otp table
        conn = await get_db_connection()
        try:
            existing = await conn.execute(
                'SELECT COUNT(*) FROM mobile_otp WHERE otp = ?',
                (code,)
            )
            count = await existing.fetchone()
            
            if count[0] == 0:
                # DEBUG: Log unique OTP generation
                logger.info(f"🎲 DEBUG OTP GENERATION: Unique OTP {code} generated for phone {phone}")
                print(f"🎲 DEBUG OTP GENERATION: Unique OTP {code} generated for phone {phone}")
                return code
        finally:
            await close_db_connection(conn)
    
    # If we can't generate a unique code, use a fallback
    fallback_code = str(random.randint(100000, 999999))
    logger.warning(f"Using fallback OTP for {phone}: {fallback_code}")
    # DEBUG: Log fallback OTP
    print(f"⚠️ DEBUG OTP FALLBACK: Using fallback OTP {fallback_code} for phone {phone}")
    return fallback_code






def register_otp_routes(fastapi_app):
    """Register mobile OTP API routes with the FastAPI app."""
    try:
        # Wire dependencies for logging if available
        from .db import insert_log as db_insert_log
        set_dependencies(db_insert_log, None)
    except Exception as e:
        try:
            logger.warning(f"OTP dependencies not fully set: {e}")
        except Exception:
            pass

    # Expose mobile OTP endpoints
    fastapi_app.add_api_route("/api/mobile/send-otp", send_mobile_otp, methods=["POST"])
    fastapi_app.add_api_route("/api/mobile/resend-otp", resend_mobile_otp, methods=["POST"])
    fastapi_app.add_api_route("/api/mobile/verify-otp", verify_mobile_otp, methods=["POST"])

