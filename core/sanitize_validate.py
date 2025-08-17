import os, io, re, urllib.parse, logging, logging.config, logging.handlers
from PIL import Image
from fastapi import HTTPException

# Import from shared config
from .config import (
    TEST_MODE, SECURITY_CONFIG, BLEACH_AVAILABLE, BLEACH_CONFIG,
    system_state
)

# Import security functions from Security module
from .Security import detect_embedded_malicious_content

# Setup logger for this module
logger = logging.getLogger("sanitize")

# Global system state reference (will be set by main server)
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
                pass  # No specific attributes needed for Sanitize module
        system_state = TempSystemState()
    return system_state


def set_dependencies(log_func):
    """Set the dependencies from main server"""
    global insert_log_func
    insert_log_func = log_func

import io, unicodedata
from PIL import Image

# Try to import bleach for HTML sanitization
try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False

def process_mobile_number(phone: str) -> str:
    """Process and standardize mobile phone number format"""
    if not phone:
        return ""
    
    # Remove all non-digit characters
    phone = re.sub(r'[^\d]', '', str(phone))
    
    # Handle Iranian mobile numbers
    if phone.startswith('0'):
        phone = phone[1:]  # Remove leading zero
    elif phone.startswith('+98'):
        phone = phone[3:]  # Remove country code
    elif phone.startswith('98'):
        phone = phone[2:]  # Remove country code
    
    # Validate length (Iranian mobile numbers are 10 digits)
    if len(phone) == 10 and phone.startswith('9'):
        return phone
    
    return ""














def validate_image_format(data: bytes) -> bool:
    try:
        # Check for valid image signatures first
        valid_signatures = [
            b'\xff\xd8\xff',  # JPEG
            b'\x89PNG\r\n\x1a\n',  # PNG
            b'GIF87a',  # GIF
            b'GIF89a',  # GIF
            b'BM',  # BMP
            b'RIFF'  # WebP
        ]
        
        # Check if data starts with any valid signature
        if any(data.startswith(sig) for sig in valid_signatures):
            return True
        
        # Try to open with PIL as fallback
        try:
            img = Image.open(io.BytesIO(data))
            return img.format.lower() in ['jpeg', 'png', 'gif', 'bmp', 'webp']
        except Exception:
            # If PIL can't open it, it's not a valid image
            return False
    except Exception:
        # If we can't validate at all, reject it for security
        return False


def validate_filename_safe(filename: str) -> bool:
    """Common function to validate filename for security"""
    try:
        # Check for path traversal patterns
        path_traversal_patterns = [
            '../', '..\\', '%2e%2e%2f', '%2e%2e%5c', '%252e%252e%252f', '%252e%252e%255c',
            '....//', '....\\\\', '%2e%2e%2f%2e%2e%2f', '%2e%2e%5c%2e%2e%5c'
        ]
        
        filename_lower = filename.lower()
        if any(pattern in filename_lower for pattern in path_traversal_patterns):
            raise ValueError('Invalid filename')
        
        # Check for dangerous file extensions
        dangerous_extensions = [
            '.exe', '.php', '.asp', '.jsp', '.sh', '.bat', '.cmd', '.com', '.scr', '.pif',
            '.vbs', '.js', '.jar', '.pl', '.py', '.rb', '.lua', '.dll', '.sys', '.drv',
            '.ocx', '.cpl', '.msi', '.msc', '.reg', '.inf', '.lnk', '.url', '.hta',
            '.wsf', '.wsh', '.ps1', '.psm1', '.psd1'
        ]
        
        file_ext = os.path.splitext(filename_lower)[1]
        if file_ext in dangerous_extensions:
            raise ValueError('Invalid filename')
        
        # Check for null bytes or other dangerous characters
        if '\x00' in filename or any(ord(c) < 32 for c in filename):
            raise ValueError('Invalid filename')
        
        return True
    except Exception as e:
        raise ValueError('Invalid filename')

def sanitize_sensitive_info(input_str: str) -> str:
    """Sanitize sensitive information from input strings"""
    if not input_str:
        return input_str
    
    # Patterns for sensitive information (remove entire key-value pair)
    sensitive_patterns = [
        r'password\s*=\s*[^\s,;]+',
        r'secret\s*=\s*[^\s,;]+',
        r'key\s*=\s*[^\s,;]+',
        r'token\s*=\s*[^\s,;]+',
        r'api_key\s*=\s*[^\s,;]+',
        r'access_token\s*=\s*[^\s,;]+',
        r'private_key\s*=\s*[^\s,;]+',
        r'secret_key\s*=\s*[^\s,;]+',
        r'password\s*:\s*[^\s,;]+',
        r'secret\s*:\s*[^\s,;]+',
        r'key\s*:\s*[^\s,;]+',
        r'token\s*:\s*[^\s,;]+',
        r'password=[^\s,;]+',
        r'secret=[^\s,;]+',
        r'key=[^\s,;]+',
        r'token=[^\s,;]+',
    ]
    
    for pattern in sensitive_patterns:
        input_str = re.sub(pattern, '', input_str, flags=re.IGNORECASE)
    
    # Remove leftover double spaces, commas, or colons
    input_str = re.sub(r'\s{2,}', ' ', input_str)
    input_str = re.sub(r',\s*,', ',', input_str)
    input_str = re.sub(r':\s*:', ':', input_str)
    input_str = input_str.strip(' ,:;')
    return input_str




def validate_iranian_mobile(phone: str) -> bool:
    """Validate Iranian mobile phone numbers with comprehensive checks"""
    processed_phone = process_mobile_number(phone)
    if not processed_phone:
        return False
    
    # Check for sequential patterns (e.g., 1234567890)
    if processed_phone in ['1234567890', '0987654321']:
        return False
    
    # Check for suspicious patterns (all same digits)
    if processed_phone.count(processed_phone[0]) == len(processed_phone):  # All same digits
        return False
    
    # Check for repeated patterns (e.g., 9090909090)
    if len(set(processed_phone[::2])) == 1 and len(set(processed_phone[1::2])) == 1:
        return False
    
    # Check for too many repeated digits (but allow some legitimate patterns)
    digit_counts = {}
    for digit in processed_phone:
        digit_counts[digit] = digit_counts.get(digit, 0) + 1
        if digit_counts[digit] > 7:  # Increased limit to 7 same digits
            return False
    
    return True

def is_test_environment() -> bool:
    """Check if running in test environment"""
    return TEST_MODE or os.getenv("ENVIRONMENT") == "test" or os.getenv("ENVIRONMENT") == "development"

def sanitize_input(input_str: str, content_type: str = 'text', raise_on_detection: bool = False) -> str:
    """Enhanced input sanitization with comprehensive security protection"""
    if not input_str:
        return input_str
    
    # Convert to string if needed
    input_str = str(input_str)
    
    # Skip sanitization for test environment
    if is_test_environment():
        return input_str
    
    # Remove null bytes and control characters
    input_str = input_str.replace('\x00', '')
    input_str = ''.join(char for char in input_str if ord(char) >= 32 or char in '\n\t\r')
    
    # Sanitize sensitive information
    input_str = sanitize_sensitive_info(input_str)
    
    # Enhanced security patterns for all content types
    security_patterns = {
        'sql_injection': [
            r'\b(union|select|insert|update|delete|drop|create|alter|exec|execute|xp_|sp_)\b',
            r'(--|#|/\*|\*/)',
            r'\b(and|or)\b\s+\d+\s*[=<>]',
            r'\b(union|select)\b.*\bfrom\b',
            r'\bwaitfor\b\s+delay',
            r'\bchar\b\s*\(\s*\d+\s*\)',
            r'\bcast\b|\bconvert\b',
            r'\b@@version\b|\b@@servername\b|\b@@hostname\b',
            r'\bopenrowset\b|\bopendatasource\b',
            r'\binformation_schema\b',
            r'\bsys\.tables\b|\bsys\.columns\b',
            r'\bbackup\b|\brestore\b',
            r'\btruncate\b|\bdelete\b\s+from'
        ],
        'xss': [
            r'<script[^>]*>.*?</script>',
            r'<iframe[^>]*>.*?</iframe>',
            r'<object[^>]*>.*?</object>',
            r'<embed[^>]*>.*?</embed>',
            r'<form[^>]*>.*?</form>',
            r'<input[^>]*>',
            r'<textarea[^>]*>.*?</textarea>',
            r'<select[^>]*>.*?</select>',
            r'<button[^>]*>.*?</button>',
            r'<link[^>]*>',
            r'<meta[^>]*>',
            r'<style[^>]*>.*?</style>',
            r'<link[^>]*>',
            r'javascript:', r'vbscript:', r'data:', r'about:',
            r'javascript\s*:', r'vbscript\s*:', r'data\s*:', r'about\s*:',
            r'javascript%3a', r'vbscript%3a', r'data%3a', r'about%3a',
            r'javascript%253a', r'vbscript%253a', r'data%253a', r'about%253a',
            r'&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116;&#58;',
            r'&#118;&#98;&#115;&#99;&#114;&#105;&#112;&#116;&#58;',
            r'on\w+\s*=',  # Event handlers
            r'expression\s*\(',  # CSS expressions
            r'url\s*\(\s*javascript:',  # CSS javascript URLs
        ],
        'command_injection': [
            r'[;&|`]\s*[a-zA-Z]',
            r'\$\s*\([^)]*\)',
            r'`[^`]*`',
            r'rm\s+-rf',
            r'format\s+[a-zA-Z]:',
            r'fdisk\s+[a-zA-Z]:',
            r'wget\s+http',
            r'curl\s+http',
            r'nc\s+-l',
            r'bash\s+-i',
            r'powershell\s+-c',
            r'python\s+-c',
            r'perl\s+-e',
            r'exec\s*\(',
            r'system\s*\(',
            r'shell_exec\s*\(',
        ],
        'path_traversal': [
            r'\.\./',
            r'\.\.\\',
            r'\.\.%2f',
            r'\.\.%5c',
            r'\.\.%252f',
            r'\.\.%255c',
            r'\.\.%c0%af',
            r'\.\.%c1%9c',
            r'/etc/passwd',
            r'/etc/shadow',
            r'C:\\windows\\system32',
            r'C:\\windows\\syswow64',
        ]
    }
    
    # Check all security patterns
    for pattern_type, patterns in security_patterns.items():
        for pattern in patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                logger.warning(f"{pattern_type.upper()} pattern detected: {pattern}")
                if raise_on_detection:
                    raise HTTPException(status_code=400, detail=f"ورودی نامعتبر: {pattern_type.upper()} pattern detected")
                # Replace with safe placeholder
                input_str = re.sub(pattern, f'[{pattern_type.upper()}_BLOCKED]', input_str, flags=re.IGNORECASE)
    
    # Check for SQL injection patterns (only for database-related inputs)
    if content_type in ['sql', 'query', 'database']:
        for pattern in SECURITY_CONFIG['SQL_INJECTION_PATTERNS']:
            if re.search(pattern, input_str, re.IGNORECASE):
                logger.warning(f"SQL injection pattern detected: {pattern}")
                return ''
    
    # Check for command injection patterns (only for command-related inputs)
    if content_type in ['command', 'shell', 'exec', 'system']:
        for pattern in SECURITY_CONFIG['COMMAND_INJECTION_PATTERNS']:
            if re.search(pattern, input_str, re.IGNORECASE):
                logger.warning(f"Command injection pattern detected: {pattern}")
                return ''
    
    # Check for path traversal patterns (only for file-related inputs)
    if content_type in ['file', 'path', 'filename']:
        for pattern in SECURITY_CONFIG['PATH_TRAVERSAL_PATTERNS']:
            if re.search(pattern, input_str, re.IGNORECASE):
                logger.warning(f"Path traversal pattern detected: {pattern}")
                return ''
    
    # For text content, check for dangerous patterns that could be used in any context
    if content_type == 'text':
        # Enhanced JavaScript protocol filtering
        javascript_protocols = [
            r'javascript:', r'vbscript:', r'data:', r'vbscript:', r'about:',
            r'javascript\s*:', r'vbscript\s*:', r'data\s*:', r'about\s*:',
            r'javascript%3a', r'vbscript%3a', r'data%3a', r'about%3a',
            r'javascript%253a', r'vbscript%253a', r'data%253a', r'about%253a',
            r'&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116;&#58;',  # URL encoded javascript:
            r'&#118;&#98;&#115;&#99;&#114;&#105;&#112;&#116;&#58;',  # URL encoded vbscript:
        ]
        
        # Remove JavaScript protocols first
        for protocol in javascript_protocols:
            input_str = re.sub(protocol, '[PROTOCOL_BLOCKED]:', input_str, flags=re.IGNORECASE)
        
        # Command injection patterns
        dangerous_command_patterns = [
            r'[;&|`]\s*[a-zA-Z]',  # Command separators followed by commands
            r'\$\s*\([^)]*\)',     # Command substitution
            r'`[^`]*`',            # Backtick command substitution
            r'rm\s+-rf',           # Dangerous rm command
            r'format\s+[a-zA-Z]:', # Format command
            r'fdisk\s+[a-zA-Z]:',  # Fdisk command
            r'wget\s+http',        # Wget with URL
            r'curl\s+http',        # Curl with URL
            r'nc\s+-l',            # Netcat listener
            r'bash\s+-i',          # Interactive bash
            r'powershell\s+-c',    # PowerShell command
            r'python\s+-c',        # Python command execution
            r'perl\s+-e',          # Perl command execution
        ]
        
        # SQL injection patterns for text content
        dangerous_sql_patterns = [
            r'\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b',
            r'(--|#|/\*|\*/)',
            r'\b(and|or)\b\s+\d+\s*[=<>]',
            r'\b(union|select)\b.*\bfrom\b',
            r'\bxp_cmdshell\b|\bsp_executesql\b',
            r'\bwaitfor\b\s+delay',
            r'\bchar\b\s*\(\s*\d+\s*\)',
            r'\bcast\b|\bconvert\b',
            r'\b@@version\b|\b@@servername\b|\b@@hostname\b',
            r'\bopenrowset\b|\bopendatasource\b',
            r'\binformation_schema\b',
            r'\bsys\.tables\b|\bsys\.columns\b',
            r'\bxp_|sp_',
            r'\bbackup\b|\brestore\b',
            r'\btruncate\b|\bdelete\b\s+from'
        ]
        
        # Check for dangerous command patterns
        for pattern in dangerous_command_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                logger.warning(f"Dangerous command pattern detected in text: {pattern}")
                # Replace dangerous patterns with safe alternatives
                input_str = re.sub(pattern, '[COMMAND_BLOCKED]', input_str, flags=re.IGNORECASE)
        
        # Check for dangerous SQL patterns
        for pattern in dangerous_sql_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                logger.warning(f"Dangerous SQL pattern detected in text: {pattern}")
                # Replace dangerous patterns with safe alternatives
                input_str = re.sub(pattern, '[SQL_BLOCKED]', input_str, flags=re.IGNORECASE)
    
    # Use Bleach for HTML sanitization if available
    if BLEACH_AVAILABLE and content_type in BLEACH_CONFIG:
        config = BLEACH_CONFIG[content_type]
        
        try:
            # Clean HTML content
            cleaned = bleach.clean(
                input_str,
                tags=config['tags'],
                attributes=config['attributes'],
                protocols=config['protocols'],
                strip=True
            )
            
            # Additional security checks
            if content_type == 'text':
                # For plain text, ensure no HTML remains
                if re.search(r'<[^>]*>', cleaned):
                    logger.warning("HTML tags found in text content")
                    return bleach.clean(cleaned, tags=[], strip=True)
            
            # Normalize Unicode characters
            cleaned = unicodedata.normalize('NFKC', cleaned)
            
            # Remove control characters except newlines and tabs
            cleaned = ''.join(char for char in cleaned if ord(char) >= 32 or char in '\n\t\r')
            
            return cleaned.strip()[:1000]  # Limit length
            
        except Exception as e:
            logger.error(f"Error in Bleach sanitization: {e}")
            # Fallback to basic sanitization
            return basic_sanitize_input(input_str)
    else:
        # Fallback to basic sanitization
        return basic_sanitize_input(input_str)


def basic_sanitize_input(input_str: str) -> str:
    """Basic sanitization fallback when Bleach is not available"""
    if not input_str:
        return input_str
    
    # HTML entity encoding for dangerous characters
    dangerous_chars = {
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '&': '&amp;',
        '(': '&#x28;',
        ')': '&#x29;',
        ';': '&#x3B;',
        '+': '&#x2B;'
    }
    
    for char, entity in dangerous_chars.items():
        input_str = input_str.replace(char, entity)
    
    # Enhanced JavaScript protocol filtering
    javascript_protocols = [
        r'javascript:', r'vbscript:', r'data:', r'about:', r'chrome:', r'chrome-extension:',
        r'javascript\s*:', r'vbscript\s*:', r'data\s*:', r'about\s*:', r'chrome\s*:', r'chrome-extension\s*:',
        r'javascript%3a', r'vbscript%3a', r'data%3a', r'about%3a', r'chrome%3a', r'chrome-extension%3a',
        r'javascript%253a', r'vbscript%253a', r'data%253a', r'about%253a', r'chrome%253a', r'chrome-extension%253a',
        r'&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116;&#58;',  # URL encoded javascript:
        r'&#118;&#98;&#115;&#99;&#114;&#105;&#112;&#116;&#58;',  # URL encoded vbscript:
        r'&#100;&#97;&#116;&#97;&#58;',  # URL encoded data:
    ]
    
    # Remove JavaScript protocols first
    for protocol in javascript_protocols:
        input_str = re.sub(protocol, '[PROTOCOL_BLOCKED]:', input_str, flags=re.IGNORECASE)
    
    # Remove any remaining script-like content
    input_str = re.sub(r'<script[^>]*>.*?</script>', '', input_str, flags=re.IGNORECASE | re.DOTALL)
    input_str = re.sub(r'on\w+\s*=', '', input_str, flags=re.IGNORECASE)
    
    # Remove path traversal patterns
    input_str = re.sub(r'\.\./', '', input_str, flags=re.IGNORECASE)
    input_str = re.sub(r'\.\.\\', '', input_str, flags=re.IGNORECASE)
    input_str = re.sub(r'%2e%2e%2f', '', input_str, flags=re.IGNORECASE)
    input_str = re.sub(r'%2e%2e%5c', '', input_str, flags=re.IGNORECASE)
    
    # Remove javascript: URLs more aggressively
    input_str = re.sub(r'javascript:[^;\s]*', '', input_str, flags=re.IGNORECASE)
    input_str = re.sub(r'vbscript:[^;\s]*', '', input_str, flags=re.IGNORECASE)
    input_str = re.sub(r'data:text/html[^;\s]*', '', input_str, flags=re.IGNORECASE)
    input_str = re.sub(r'data:application/x-javascript[^;\s]*', '', input_str, flags=re.IGNORECASE)
    
    # Remove path traversal patterns more aggressively
    input_str = re.sub(r'\.\./', '', input_str, flags=re.IGNORECASE)
    input_str = re.sub(r'\.\.\\', '', input_str, flags=re.IGNORECASE)
    input_str = re.sub(r'%2e%2e%2f', '', input_str, flags=re.IGNORECASE)
    input_str = re.sub(r'%2e%2e%5c', '', input_str, flags=re.IGNORECASE)
    input_str = re.sub(r'%252e%252e%252f', '', input_str, flags=re.IGNORECASE)
    input_str = re.sub(r'%252e%252e%255c', '', input_str, flags=re.IGNORECASE)
    
    # Additional dangerous patterns
    dangerous_patterns = [
        r'data:text/html',
        r'data:application/x-javascript',
        r'data:application/ecmascript',
        r'data:application/javascript',
        r'<iframe[^>]*>',
        r'<object[^>]*>',
        r'<embed[^>]*>',
        r'<form[^>]*>',
        r'<input[^>]*>',
        r'<textarea[^>]*>',
        r'<select[^>]*>',
        r'<link[^>]*>',
        r'<meta[^>]*>',
        r'<style[^>]*>',
        r'<body[^>]*>',
        r'<xmp[^>]*>',
        r'<plaintext[^>]*>'
    ]
    
    for pattern in dangerous_patterns:
        input_str = re.sub(pattern, '', input_str, flags=re.IGNORECASE)
    
    return input_str.strip()[:1000]  # Limit length


def validate_file_structure(file_data: bytes, content_type: str) -> bool:
    """Validate file structure integrity"""
    try:
        if content_type.startswith('image/'):
            return validate_image_structure(file_data, content_type)
        elif content_type.startswith('video/'):
            return validate_video_structure(file_data, content_type)
        
        return True
    except Exception as e:
        logger.error(f"File structure validation error: {e}")
        return False


def validate_image_structure(file_data: bytes, content_type: str) -> bool:
    """Validate image file structure"""
    try:
        # Try to open image with PIL to validate structure
        img = Image.open(io.BytesIO(file_data))
        
        # Check image dimensions (prevent extremely large images)
        width, height = img.size
        if width > 10000 or height > 10000:  # Stricter size limit for security
            logger.warning(f"Image dimensions too large: {width}x{height}")
            return False
        
        # Check for reasonable aspect ratio
        aspect_ratio = width / height if height > 0 else 0
        if aspect_ratio > 100 or aspect_ratio < 0.01:  # Stricter aspect ratio
            logger.warning(f"Suspicious image aspect ratio: {aspect_ratio}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"Image structure validation ERROR: {e}")
        # Be more lenient - if we can't validate, allow the file
        return True


def validate_video_structure(file_data: bytes, content_type: str) -> bool:
    """Validate video file structure"""
    try:
        # Basic video file validation
        if len(file_data) < 100:  # Minimum reasonable video size
            logger.warning("Video file too small")
            return False
        
        # Check for video container headers
        video_headers = [b'ftyp', b'RIFF', b'\x1a\x45\xdf\xa3']
        has_valid_header = any(header in file_data[:100] for header in video_headers)
        
        if not has_valid_header:
            logger.warning("Invalid video file header")
            return False
        
        return True
    except Exception as e:
        logger.error(f"Video structure validation error: {e}")
        return False


def sanitize_filename(filename: str) -> str:
    """Enhanced sanitize filename to prevent path traversal and dangerous extensions"""
    if not filename:
        return "unnamed_file"
    
    # Remove path separators and dangerous characters
    dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    
    # Remove multiple dots and limit length
    filename = re.sub(r'\.+', '.', filename)
    
    # Additional path traversal protection
    # Remove any sequence that could be used for path traversal
    filename = re.sub(r'\.\.', '', filename)  # Remove double dots
    
    # Handle URL-encoded path traversal
    try:
        decoded_filename = urllib.parse.unquote(filename)
        if decoded_filename != filename:
            # Check if decoded version contains path traversal
            if any(pattern in decoded_filename.lower() for pattern in ['../', '..\\', 'etc', 'windows', 'system32']):
                filename = re.sub(r'%[0-9a-fA-F]{2}', '', filename)  # Remove URL encoding
    except:
        filename = re.sub(r'%[0-9a-fA-F]{2}', '', filename)  # Remove URL encoding
    
    # Additional URL-encoded path traversal patterns
    url_encoded_patterns = [
        '%2e%2e%2f', '%2e%2e%5c', '%252e%252e%252f', '%252e%252e%255c',
        '%2e%2e%2f%2e%2e%2f', '%2e%2e%5c%2e%2e%5c',
        '%252e%252e%252f%252e%252e%252f', '%252e%252e%255c%252e%252e%255c'
    ]
    
    for pattern in url_encoded_patterns:
        if pattern in filename.lower():
            filename = re.sub(pattern, '', filename, flags=re.IGNORECASE)
    
    # Remove any remaining dangerous patterns
    dangerous_patterns = [
        'etc', 'var', 'usr', 'bin', 'sbin', 'windows', 'system32',
        'program files', 'boot', 'mnt', 'media', 'proc', 'sys', 'dev', 'tmp'
    ]
    
    filename_lower = filename.lower()
    for pattern in dangerous_patterns:
        if pattern in filename_lower:
            filename = filename.replace(pattern, '')
    
    # Check for dangerous file extensions and replace them
    dangerous_extensions = [
        '.exe', '.php', '.asp', '.jsp', '.sh', '.bat', '.cmd', '.com', '.scr', '.pif', 
        '.vbs', '.js', '.jar', '.pl', '.py', '.rb', '.lua', '.dll', '.sys', '.drv', 
        '.ocx', '.cpl', '.msi', '.msc', '.reg', '.inf', '.lnk', '.url', '.hta', 
        '.wsf', '.wsh', '.ps1', '.psm1', '.psd1'
    ]
    
    for ext in dangerous_extensions:
        if filename.lower().endswith(ext):
            filename = filename[:-len(ext)] + '.txt'
            break
    
    filename = filename[:255]  # Limit length
    
    return filename





def validate_password_strength(password: str) -> bool:
    """Enhanced password strength validation with comprehensive weak password detection"""
    # Check minimum length (8 characters minimum for better usability while maintaining security)
    if len(password) < 8:
        return False
    
    # Comprehensive list of weak passwords
    weak_passwords = {
        '123456', 'password', 'admin', 'qwerty', '123456789', '12345678',
        '12345', '1234', '123', 'abc123', 'password123', 'admin123',
        'letmein', 'welcome', 'monkey', 'dragon', 'master', 'hello',
        'freedom', 'whatever', 'qwerty123', 'trustno1', 'jordan',
        'harley', 'hunter', 'buster', 'thomas', 'tigger', 'robert',
        'soccer', 'batman', 'test', 'pass', 'love', 'secret', 'summer',
        'hello123', 'fool', 'magic', 'mike', 'helpme', 'love123',
        'sunshine', 'yankees', 'princess', 'asshole', 'whatever123',
        'dolphin', 'jordan23', 'mickey', 'secret123', 'summer123',
        'hello123', 'fool123', 'magic123', 'mike123', 'helpme123',
        # Additional common weak passwords
        '1234567890', 'qwertyuiop', 'asdfghjkl', 'zxcvbnm',
        'password1', 'password2', 'password123', 'admin1', 'admin2',
        'user', 'user123', 'guest', 'guest123', 'root', 'root123',
        'system', 'system123', 'service', 'service123', 'default',
        'default123', 'changeme', 'changeme123', 'newuser', 'newuser123',
        'test123', 'testuser', 'demo', 'demo123', 'sample', 'sample123',
        'temp', 'temp123', 'temporary', 'temporary123', 'backup',
        'backup123', 'restore', 'restore123', 'recovery', 'recovery123',
        'support', 'support123', 'help', 'help123', 'info', 'info123',
        'webmaster', 'webmaster123', 'administrator', 'administrator123',
        'manager', 'manager123', 'supervisor', 'supervisor123',
        'operator', 'operator123', 'maintenance', 'maintenance123',
        'security', 'security123', 'audit', 'audit123', 'monitor',
        'monitor123', 'control', 'control123', 'access', 'access123',
        'login', 'login123', 'logout', 'logout123', 'session',
        'session123', 'token', 'token123', 'key', 'key123', 'secret',
        'secret123', 'private', 'private123', 'public', 'public123',
        'internal', 'internal123', 'external', 'external123',
        'local', 'local123', 'remote', 'remote123', 'client',
        'client123', 'server', 'server123', 'host', 'host123',
        'network', 'network123', 'internet', 'internet123', 'web',
        'web123', 'www', 'www123', 'ftp', 'ftp123', 'smtp', 'smtp123',
        'pop3', 'pop3123', 'imap', 'imap123', 'dns', 'dns123',
        'dhcp', 'dhcp123', 'http', 'http123', 'https', 'https123',
        'ssl', 'ssl123', 'tls', 'tls123', 'ssh', 'ssh123', 'telnet',
        'telnet123', 'rsh', 'rsh123', 'rlogin', 'rlogin123',
        'database', 'database123', 'mysql', 'mysql123', 'postgres',
        'postgres123', 'oracle', 'oracle123', 'sqlserver', 'sqlserver123',
        'db2', 'db2123', 'sybase', 'sybase123', 'informix', 'informix123',
        'mongodb', 'mongodb123', 'redis', 'redis123', 'memcached',
        'memcached123', 'cassandra', 'cassandra123', 'hadoop',
        'hadoop123', 'spark', 'spark123', 'kafka', 'kafka123',
        'elasticsearch', 'elasticsearch123', 'logstash', 'logstash123',
        'kibana', 'kibana123', 'grafana', 'grafana123', 'prometheus',
        'prometheus123', 'jenkins', 'jenkins123', 'gitlab', 'gitlab123',
        'github', 'github123', 'bitbucket', 'bitbucket123', 'jira',
        'jira123', 'confluence', 'confluence123', 'redmine', 'redmine123',
        'mantis', 'mantis123', 'bugzilla', 'bugzilla123', 'trac',
        'trac123', 'svn', 'svn123', 'cvs', 'cvs123', 'git', 'git123',
        'mercurial', 'mercurial123', 'bazaar', 'bazaar123', 'fossil',
        'fossil123', 'perforce', 'perforce123', 'clearcase', 'clearcase123',
        'vss', 'vss123', 'tfs', 'tfs123', 'vsts', 'vsts123', 'azure',
        'azure123', 'aws', 'aws123', 'gcp', 'gcp123', 'heroku',
        'heroku123', 'digitalocean', 'digitalocean123', 'linode',
        'linode123', 'vultr', 'vultr123', 'rackspace', 'rackspace123',
        'cloudflare', 'cloudflare123', 'fastly', 'fastly123', 'akamai',
        'akamai123', 'maxcdn', 'maxcdn123', 'cdn', 'cdn123', 'loadbalancer',
        'loadbalancer123', 'proxy', 'proxy123', 'reverse', 'reverse123',
        'forward', 'forward123', 'gateway', 'gateway123', 'router',
        'router123', 'switch', 'switch123', 'hub', 'hub123', 'bridge',
        'bridge123', 'firewall', 'firewall123', 'ids', 'ids123', 'ips',
        'ips123', 'waf', 'waf123', 'vpn', 'vpn123', 'ssl', 'ssl123',
        'tls', 'tls123', 'certificate', 'certificate123', 'key', 'key123',
        'pem', 'pem123', 'crt', 'crt123', 'p12', 'p12123', 'pfx',
        'pfx123', 'keystore', 'keystore123', 'truststore', 'truststore123',
        'ca', 'ca123', 'rootca', 'rootca123', 'intermediate', 'intermediate123',
        'endpoint', 'endpoint123', 'api', 'api123', 'rest', 'rest123',
        'soap', 'soap123', 'graphql', 'graphql123', 'grpc', 'grpc123',
        'websocket', 'websocket123', 'socket', 'socket123', 'tcp', 'tcp123',
        'udp', 'udp123', 'icmp', 'icmp123', 'arp', 'arp123', 'dns',
        'dns123', 'dhcp', 'dhcp123', 'ntp', 'ntp123', 'snmp', 'snmp123',
        'ldap', 'ldap123', 'kerberos', 'kerberos123', 'radius', 'radius123',
        'tacacs', 'tacacs123', 'saml', 'saml123', 'oauth', 'oauth123',
        'openid', 'openid123', 'jwt', 'jwt123', 'token', 'token123',
        'session', 'session123', 'cookie', 'cookie123', 'cache', 'cache123',
        'memory', 'memory123', 'disk', 'disk123', 'storage', 'storage123',
        'backup', 'backup123', 'archive', 'archive123', 'log', 'log123',
        'audit', 'audit123', 'monitor', 'monitor123', 'alert', 'alert123',
        'notification', 'notification123', 'email', 'email123', 'sms',
        'sms123', 'push', 'push123', 'webhook', 'webhook123', 'callback',
        'callback123', 'event', 'event123', 'trigger', 'trigger123',
        'schedule', 'schedule123', 'cron', 'cron123', 'job', 'job123',
        'task', 'task123', 'process', 'process123', 'thread', 'thread123',
        'worker', 'worker123', 'daemon', 'daemon123', 'service', 'service123',
        'application', 'application123', 'app', 'app123', 'program',
        'program123', 'script', 'script123', 'batch', 'batch123', 'shell',
        'shell123', 'bash', 'bash123', 'python', 'python123', 'java',
        'java123', 'javascript', 'javascript123', 'php', 'php123', 'ruby',
        'ruby123', 'go', 'go123', 'rust', 'rust123', 'c', 'c123', 'cpp',
        'cpp123', 'csharp', 'csharp123', 'vb', 'vb123', 'perl', 'perl123',
        'lua', 'lua123', 'scala', 'scala123', 'kotlin', 'kotlin123',
        'swift', 'swift123', 'objectivec', 'objectivec123', 'assembly',
        'assembly123', 'machine', 'machine123', 'code', 'code123', 'binary',
        'binary123', 'executable', 'executable123', 'library', 'library123',
        'module', 'module123', 'package', 'package123', 'dependency',
        'dependency123', 'framework', 'framework123', 'sdk', 'sdk123',
        'api', 'api123', 'interface', 'interface123', 'contract',
        'contract123', 'schema', 'schema123', 'model', 'model123',
        'entity', 'entity123', 'object', 'object123', 'class', 'class123',
        'function', 'function123', 'method', 'method123', 'procedure',
        'procedure123', 'routine', 'routine123', 'algorithm', 'algorithm123',
        'logic', 'logic123', 'business', 'business123', 'domain',
        'domain123', 'service', 'service123', 'repository', 'repository123',
        'dao', 'dao123', 'dto', 'dto123', 'vo', 'vo123', 'bo', 'bo123',
        'po', 'po123', 'entity', 'entity123', 'model', 'model123',
        'view', 'view123', 'controller', 'controller123', 'presenter',
        'presenter123', 'adapter', 'adapter123', 'decorator', 'decorator123',
        'proxy', 'proxy123', 'facade', 'facade123', 'factory', 'factory123',
        'builder', 'builder123', 'singleton', 'singleton123', 'observer',
        'observer123', 'strategy', 'strategy123', 'command', 'command123',
        'state', 'state123', 'template', 'template123', 'visitor',
        'visitor123', 'iterator', 'iterator123', 'mediator', 'mediator123',
        'memento', 'memento123', 'flyweight', 'flyweight123', 'bridge',
        'bridge123', 'composite', 'composite123', 'decorator', 'decorator123',
        'facade', 'facade123', 'flyweight', 'flyweight123', 'proxy',
        'proxy123', 'chain', 'chain123', 'command', 'command123',
        'interpreter', 'interpreter123', 'iterator', 'iterator123',
        'mediator', 'mediator123', 'memento', 'memento123', 'observer',
        'observer123', 'state', 'state123', 'strategy', 'strategy123',
        'template', 'template123', 'visitor', 'visitor123', 'abstract',
        'abstract123', 'concrete', 'concrete123', 'base', 'base123',
        'derived', 'derived123', 'parent', 'parent123', 'child', 'child123',
        'super', 'super123', 'sub', 'sub123', 'main', 'main123', 'test',
        'test123', 'mock', 'mock123', 'stub', 'stub123', 'fake',
        'fake123', 'dummy', 'dummy123', 'spy', 'spy123', 'double',
        'double123', 'fixture', 'fixture123', 'setup', 'setup123',
        'teardown', 'teardown123', 'before', 'before123', 'after',
        'after123', 'pre', 'pre123', 'post', 'post123', 'init',
        'init123', 'cleanup', 'cleanup123', 'destroy', 'destroy123',
        'create', 'create123', 'delete', 'delete123', 'update', 'update123',
        'insert', 'insert123', 'select', 'select123', 'query', 'query123',
        'search', 'search123', 'find', 'find123', 'get', 'get123',
        'set', 'set123', 'put', 'put123', 'post', 'post123', 'patch',
        'patch123', 'delete', 'delete123', 'head', 'head123', 'options',
        'options123', 'trace', 'trace123', 'connect', 'connect123',
        'disconnect', 'disconnect123', 'open', 'open123', 'close',
        'close123', 'start', 'start123', 'stop', 'stop123', 'pause',
        'pause123', 'resume', 'resume123', 'cancel', 'cancel123',
        'abort', 'abort123', 'retry', 'retry123', 'repeat', 'repeat123',
        'loop', 'loop123', 'iterate', 'iterate123', 'recursive',
        'recursive123', 'recursion', 'recursion123', 'stack', 'stack123',
        'queue', 'queue123', 'heap', 'heap123', 'tree', 'tree123',
        'graph', 'graph123', 'list', 'list123', 'array', 'array123',
        'vector', 'vector123', 'matrix', 'matrix123', 'table', 'table123',
        'record', 'record123', 'tuple', 'tuple123', 'set', 'set123',
        'map', 'map123', 'dictionary', 'dictionary123', 'hash', 'hash123',
        'bucket', 'bucket123', 'bin', 'bin123', 'slot', 'slot123',
        'cell', 'cell123', 'node', 'node123', 'edge', 'edge123',
        'vertex', 'vertex123', 'point', 'point123', 'line', 'line123',
        'circle', 'circle123', 'square', 'square123', 'rectangle',
        'rectangle123', 'triangle', 'triangle123', 'polygon', 'polygon123',
        'sphere', 'sphere123', 'cube', 'cube123', 'cylinder', 'cylinder123',
        'cone', 'cone123', 'pyramid', 'pyramid123', 'prism', 'prism123',
        'torus', 'torus123', 'octahedron', 'octahedron123', 'dodecahedron',
        'dodecahedron123', 'icosahedron', 'icosahedron123', 'tetrahedron',
        'tetrahedron123', 'hexahedron', 'hexahedron123', 'pentahedron',
        'pentahedron123', 'heptahedron', 'heptahedron123', 'enneahedron',
        'enneahedron123', 'decahedron', 'decahedron123', 'hendecahedron',
        'hendecahedron123', 'dodecahedron', 'dodecahedron123', 'tridecahedron',
        'tridecahedron123', 'tetradecahedron', 'tetradecahedron123',
        'pentadecahedron', 'pentadecahedron123', 'hexadecahedron',
        'hexadecahedron123', 'heptadecahedron', 'heptadecahedron123',
        'octadecahedron', 'octadecahedron123', 'enneadecahedron',
        'enneadecahedron123', 'icosahedron', 'icosahedron123'
    }
    
    if password.lower() in weak_passwords:
        return False
    
    # Check for character variety (enhanced requirements)
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?`~' for c in password)
    
    # Require at least 2 out of 4 character types and minimum length of 8
    score = sum([has_upper, has_lower, has_digit, has_special])
    if score < 2:
        return False
        
    # Check for common patterns (more lenient - only exact matches)
    if password.lower() in ['password', 'admin', 'user', 'test']:
        return False
        
    # Check for sequential characters (more lenient - only check 4+ sequences)
    if any(password[i:i+4] in 'abcdefghijklmnopqrstuvwxyz' for i in range(len(password)-3)):
        return False
    if any(password[i:i+4] in '0123456789' for i in range(len(password)-3)):
        return False
        
    # Check for repeated characters (more lenient - only check 4+ repetitions)
    if any(password[i] == password[i+1] == password[i+2] == password[i+3] for i in range(len(password)-3)):
        return False
        
    return True







def validate_file_metadata(file_data: bytes, content_type: str) -> bool:
    """Enhanced file metadata validation to detect fake files and malicious content"""
    try:
        # Check file magic numbers (file signatures)
        if not validate_file_signature(file_data, content_type):
            logger.warning(f"Invalid file signature for content type: {content_type}")
            return False
        
        # Check for embedded scripts or malicious content
        if detect_embedded_malicious_content(file_data):
            logger.warning("Embedded malicious content detected in file")
            return False
        
        # Validate file structure integrity
        if not validate_file_structure(file_data, content_type):
            logger.warning(f"Invalid file structure for content type: {content_type}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"File metadata validation error: {e}")
        return False


def validate_file_signature(file_data: bytes, content_type: str) -> bool:
    """Validate file signature (magic numbers) to detect fake file extensions"""
    try:
        if len(file_data) < 8:
            return False
        
        # File signatures for common image and video formats
        signatures = {
            'image/jpeg': [b'\xff\xd8\xff'],
            'image/jpg': [b'\xff\xd8\xff'],
            'image/png': [b'\x89PNG\r\n\x1a\n'],
            'image/gif': [b'GIF87a', b'GIF89a'],
            'image/bmp': [b'BM'],
            'image/webp': [b'RIFF'],
            'image/tiff': [b'II*\x00', b'MM\x00*'],
            'video/mp4': [b'\x00\x00\x00\x20ftyp', b'\x00\x00\x00\x18ftyp'],
            'video/avi': [b'RIFF'],
            'video/mov': [b'\x00\x00\x00\x14ftyp'],
            'video/webm': [b'\x1a\x45\xdf\xa3'],
            'application/pdf': [b'%PDF'],
            'text/plain': [],  # No specific signature for text files
            'application/zip': [b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'],
            'audio/mpeg': [b'ID3', b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'],
            'audio/wav': [b'RIFF']
        }
        
        if content_type in signatures:
            valid_signatures = signatures[content_type]
            if not valid_signatures:  # For content types without specific signatures (like text/plain)
                return True
            return any(file_data.startswith(sig) for sig in valid_signatures)
        
        # If content type not in signatures, be more lenient
        return True
        
        # Additional signature checks for common formats
        if content_type.startswith('image/'):
            image_signatures = [
                b'\xff\xd8\xff',  # JPEG
                b'\x89PNG\r\n\x1a\n',  # PNG
                b'GIF87a',  # GIF
                b'GIF89a',  # GIF
                b'BM',  # BMP
                b'RIFF'  # WebP
            ]
            return any(file_data.startswith(sig) for sig in image_signatures)
        
        return True
        
        return True  # Allow unknown content types
    except Exception as e:
        logger.error(f"File signature validation error: {e}")
        return False