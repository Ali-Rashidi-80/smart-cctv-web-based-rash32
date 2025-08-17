import asyncio, aiosqlite, os, functools, gzip, logging, logging.config, logging.handlers
from typing import Optional
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
from pydantic import BaseModel, field_validator

# Import from shared config
from .config import (
    DB_FILE, BACKUP_DIR, get_jalali_now_str, retry_async,
    ADMIN_USERNAME, ADMIN_PASSWORD, CSRF_CONFIG, system_state
)

# Import CSRF and security functions from their correct modules
from .Security import log_security_event, validate_csrf_token, generate_csrf_token, get_csrf_token_from_request
from .token import get_current_user

# Setup logger for this module
logger = logging.getLogger("db")

# Constants
MAX_BACKUP_CHECK = int(os.getenv("MAX_BACKUP_CHECK", "5"))  # Maximum number of backups to check
DB_TIMEOUT = int(os.getenv("DB_TIMEOUT", "60"))

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

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    try:
        import bcrypt
        salt = bcrypt.gensalt(12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    except ImportError:
        # Fallback if bcrypt is not available
        import hashlib
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

def alert_admin(message: str, critical: bool = False):
    """Alert admin about critical issues"""
    try:
        if critical:
            logger.critical(f"🚨 CRITICAL ALERT: {message}")
        else:
            logger.warning(f"⚠️ ADMIN ALERT: {message}")
        
        # You can add additional alert mechanisms here like:
        # - Email notifications
        # - SMS alerts
        # - Slack/Discord webhooks
        # - System notifications
    except Exception as e:
        logger.error(f"Error sending admin alert: {e}")


# Define UserSettings model
class User(BaseModel):
    username: str
    password: str
    role: str = "user"  # admin, user
    is_active: bool = True
    created_at: Optional[str] = None

class UserSettings(BaseModel):
    username: Optional[str] = None
    ip: Optional[str] = None
    device_mode: Optional[str] = "desktop"
    theme: Optional[str] = "light"
    language: Optional[str] = "fa"
    servo1: Optional[int] = None
    servo2: Optional[int] = None
    photoQuality: Optional[int] = None
    smart_motion: Optional[bool] = False
    smart_tracking: Optional[bool] = False
    stream_enabled: Optional[bool] = False

    @field_validator('language')
    @classmethod
    def validate_language(cls, v):
        allowed = ['en', 'fa']
        if v not in allowed:
            raise ValueError(f"Invalid language: {v}")
        return v


async def check_db_health():
    try:
        conn = await asyncio.wait_for(aiosqlite.connect(DB_FILE, timeout=DB_TIMEOUT), timeout=DB_TIMEOUT)
        await conn.execute("PRAGMA integrity_check")
        await conn.close()
        return True
    except Exception as e:
        logger.error(f"Database health check error: {e}")
        return False


async def restore_db_from_backup():
    try:
        backups = sorted(
            [f for f in await asyncio.to_thread(os.listdir, BACKUP_DIR) if f.endswith('.gz')],
            key=lambda x: os.path.getctime(os.path.join(BACKUP_DIR, x)),
            reverse=True
        )[:MAX_BACKUP_CHECK]
        corrupt_count = 0
        for backup in backups:
            backup_file = os.path.join(BACKUP_DIR, backup)
            temp_file = os.path.join(BACKUP_DIR, "temp.db")
            try:
                await asyncio.to_thread(lambda: gzip.open(backup_file, 'rb').readinto, open(temp_file, 'wb'))
                await asyncio.to_thread(os.replace, temp_file, DB_FILE)
                if await check_db_health():
                    logger.info(f"Database restored from {backup}")
                    system_state = get_system_state()
                    system_state.db_initialized = False
                    await init_db()
                    return True
                await asyncio.to_thread(os.remove, temp_file)
                logger.warning(f"Backup {backup} is corrupt, deleted")
                await asyncio.to_thread(os.remove, backup_file)
                corrupt_count += 1
            except Exception as e:
                logger.error(f"Error restoring backup {backup}: {e}")
                if os.path.exists(temp_file):
                    await asyncio.to_thread(os.remove, temp_file)
                if os.path.exists(backup_file):
                    await asyncio.to_thread(os.remove, backup_file)
                corrupt_count += 1
        if corrupt_count > 3:
            logger.error("Multiple corrupt backups detected")
        logger.error("No valid backups found")
        return False
    except Exception as e:
        logger.error(f"Database restore error: {e}")
        return False


async def get_db_connection():
    """Get database connection with health check and enhanced error handling"""
    try:
        # Health check and recovery
        if not await check_db_health():
            if await restore_db_from_backup():
                logger.info("Database successfully restored")
            else:
                raise HTTPException(status_code=503, detail="Database corrupted and no valid backup available")
        
        # Create new connection with enhanced timeout handling
        conn = await asyncio.wait_for(aiosqlite.connect(DB_FILE, timeout=DB_TIMEOUT), timeout=DB_TIMEOUT)
        conn.row_factory = aiosqlite.Row
        
        # Enhanced SQLite settings for better concurrency and performance
        pragma_settings = [
            ("PRAGMA journal_mode=WAL", "journal_mode"),
            ("PRAGMA synchronous=NORMAL", "synchronous"),
            ("PRAGMA cache_size=10000", "cache_size"),  # Increased for better performance
            ("PRAGMA temp_store=MEMORY", "temp_store"),
            ("PRAGMA foreign_keys=ON", "foreign_keys"),
            ("PRAGMA busy_timeout=300000", "busy_timeout"),  # Increased to 5 minutes
            ("PRAGMA mmap_size=268435456", "mmap_size"),  # 256MB memory mapping
            ("PRAGMA page_size=4096", "page_size"),
            ("PRAGMA auto_vacuum=INCREMENTAL", "auto_vacuum"),
            ("PRAGMA wal_autocheckpoint=1000", "wal_autocheckpoint"),
            ("PRAGMA locking_mode=NORMAL", "locking_mode"),  # Changed from EXCLUSIVE to NORMAL
            ("PRAGMA checkpoint_fullfsync=OFF", "checkpoint_fullfsync"),
            ("PRAGMA journal_size_limit=67108864", "journal_size_limit"),  # 64MB
            ("PRAGMA optimize", "optimize")  # Added for better performance
        ]
        
        for pragma_sql, pragma_name in pragma_settings:
            try:
                await conn.execute(pragma_sql)
            except Exception as pragma_error:
                logger.warning(f"SQLite pragma {pragma_name} failed: {pragma_error}")
                # Continue without this specific setting
        
        # Verify critical settings
        try:
            cursor = await conn.execute("PRAGMA busy_timeout")
            timeout = await cursor.fetchone()
            if timeout[0] < 300000:  # Less than 5 minutes
                logger.warning(f"Busy timeout too low: {timeout[0]}, setting to 300000")
                await conn.execute("PRAGMA busy_timeout=300000")
        except Exception as e:
            logger.warning(f"Could not verify busy_timeout: {e}")
        
        return conn
    except asyncio.TimeoutError:
        logger.error("Database connection timeout")
        raise HTTPException(status_code=503, detail="Database unavailable")
    except aiosqlite.OperationalError as e:
        logger.error(f"Database operational error: {e}")
        raise HTTPException(status_code=503, detail="Database operational error")
    except aiosqlite.DatabaseError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=503, detail="Database error")
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Database connection error")


async def close_db_connection(conn):
    """Close database connection with enhanced error handling"""
    try:
        if not conn:
            return
        
        # Check if connection is still open
        if hasattr(conn, '_connection') and conn._connection:
            await conn.close()
        else:
            logger.debug("Connection already closed or invalid")
            
    except aiosqlite.OperationalError as e:
        logger.warning(f"Operational error closing database connection: {e}")
        # Connection might be already closed
        pass
    except aiosqlite.DatabaseError as e:
        logger.warning(f"Database error closing connection: {e}")
        # Force close in case of database error
        try:
            if hasattr(conn, '_connection') and conn._connection:
                await conn.close()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Error closing database connection: {e}")
        # Force close in case of error
        try:
            if hasattr(conn, '_connection') and conn._connection:
                await conn.close()
        except Exception as e:
            logger.warning(f"Error in force closing database connection: {e}")
            pass


# --- Migration: Ensure device_mode column exists in user_settings table ---
async def migrate_user_settings_table():
    conn = await get_db_connection()
    try:
        # First, check if table exists and get current columns
        cursor = await conn.execute("PRAGMA table_info(user_settings)")
        columns = await cursor.fetchall()
        existing_columns = [col[1] for col in columns]
        
        logger.info(f"Current user_settings columns: {existing_columns}")
        
        # Create table if it doesn't exist with all required columns
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ip TEXT NOT NULL,
                theme TEXT DEFAULT 'light',
                language TEXT DEFAULT 'fa',
                flash_settings TEXT DEFAULT '{}',
                servo1 INTEGER DEFAULT 90,
                servo2 INTEGER DEFAULT 90,
                device_mode TEXT DEFAULT 'desktop',
                photo_quality INTEGER DEFAULT 80,
                smart_motion BOOLEAN DEFAULT FALSE,
                smart_tracking BOOLEAN DEFAULT FALSE,
                stream_enabled BOOLEAN DEFAULT FALSE,
                updated_at TEXT DEFAULT ''
            )
        ''')
        
        # Add missing columns one by one
        required_columns = {
            'username': 'TEXT NOT NULL',
            'ip': 'TEXT NOT NULL',
            'theme': 'TEXT DEFAULT "light"',
            'language': 'TEXT DEFAULT "fa"',
            'flash_settings': 'TEXT DEFAULT "{}"',
            'servo1': 'INTEGER DEFAULT 90',
            'servo2': 'INTEGER DEFAULT 90',
            'device_mode': 'TEXT DEFAULT "desktop"',
            'photo_quality': 'INTEGER DEFAULT 80',
            'smart_motion': 'BOOLEAN DEFAULT FALSE',
            'smart_tracking': 'BOOLEAN DEFAULT FALSE',
            'stream_enabled': 'BOOLEAN DEFAULT FALSE',
            'updated_at': 'TEXT DEFAULT ""'
        }
        
        for col_name, col_type in required_columns.items():
            if col_name not in existing_columns:
                try:
                    await conn.execute(f"ALTER TABLE user_settings ADD COLUMN {col_name} {col_type}")
                    logger.info(f"✅ Added column {col_name} to user_settings table")
                except Exception as e:
                    if 'duplicate column name' not in str(e).lower():
                        logger.warning(f"⚠️ Could not add column {col_name}: {e}")
        
        await conn.commit()
        logger.info("✅ User settings table migration completed successfully")
        
        # Verify all columns exist
        cursor = await conn.execute("PRAGMA table_info(user_settings)")
        final_columns = await cursor.fetchall()
        final_column_names = [col[1] for col in final_columns]
        logger.info(f"Final user_settings columns: {final_column_names}")
        
    except Exception as e:
        logger.error(f"❌ Error migrating user settings table: {e}")
        raise
    finally:
        await close_db_connection(conn)


# --- Migration: Ensure camera_logs has source and pico_timestamp columns ---
async def migrate_camera_logs_table():
    conn = await get_db_connection()
    try:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS camera_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                log_type TEXT NOT NULL,
                created_at TEXT DEFAULT '',
                source TEXT DEFAULT 'server',
                pico_timestamp TEXT DEFAULT NULL
            )
        ''')
        # Add columns if missing
        try:
            await conn.execute("ALTER TABLE camera_logs ADD COLUMN source TEXT DEFAULT 'server'")
        except Exception as e:
            if 'duplicate column name' not in str(e):
                raise
        try:
            await conn.execute("ALTER TABLE camera_logs ADD COLUMN pico_timestamp TEXT DEFAULT NULL")
        except Exception as e:
            if 'duplicate column name' not in str(e):
                raise
        await conn.commit()
    finally:
        await close_db_connection(conn)


async def migrate_logs_table():
    """Migrate logs table to ensure all required columns exist"""
    conn = await get_db_connection()
    try:
        # Create table if it doesn't exist
        await conn.execute("""CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            log_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            source TEXT DEFAULT 'server',
            pico_timestamp TEXT DEFAULT NULL,
            user_id INTEGER DEFAULT NULL,
            ip_address TEXT DEFAULT NULL,
            user_agent TEXT DEFAULT NULL,
            session_token TEXT DEFAULT NULL,
            session_id TEXT DEFAULT NULL,
            security_event BOOLEAN DEFAULT 0,
            threat_level TEXT DEFAULT 'low'
        )""")
        
        # Add missing columns if they don't exist
        columns_to_add = [
            ("log_type", "TEXT NOT NULL DEFAULT 'info'"),
            ("source", "TEXT DEFAULT 'server'"),
            ("pico_timestamp", "TEXT DEFAULT NULL"),
            ("user_id", "INTEGER DEFAULT NULL"),
            ("ip_address", "TEXT DEFAULT NULL"),
            ("user_agent", "TEXT DEFAULT NULL"),
            ("session_token", "TEXT DEFAULT NULL"),
            ("session_id", "TEXT DEFAULT NULL"),
            ("security_event", "BOOLEAN DEFAULT 0"),
            ("threat_level", "TEXT DEFAULT 'low'")
        ]
        
        for column_name, column_def in columns_to_add:
            try:
                await conn.execute(f"ALTER TABLE logs ADD COLUMN {column_name} {column_def}")
                logger.info(f"Added column {column_name} to logs table")
            except Exception as e:
                if 'duplicate column name' not in str(e).lower():
                    logger.warning(f"Error adding column {column_name}: {e}")
        
        await conn.commit()
        logger.info("✅ Logs table migration completed successfully")
        
    except Exception as e:
        logger.error(f"Error migrating logs table: {e}")
        raise
    finally:
        await close_db_connection(conn)




# --- Enhanced Database Initialization with Robust Error Handling ---
async def init_db():
    global system_state
    # Get system state safely
    system_state = get_system_state()
    
    if system_state.db_initialized:
        logger.debug("Database already initialized")
        return
    
    conn = None
    try:
        # Create database file if it doesn't exist
        if not os.path.exists(DB_FILE):
            logger.info(f"Creating new database file: {DB_FILE}")
        
        conn = await asyncio.wait_for(aiosqlite.connect(DB_FILE, timeout=DB_TIMEOUT), timeout=DB_TIMEOUT)
        conn.row_factory = aiosqlite.Row
        
        # Enable WAL mode for better concurrency
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA cache_size=10000")
        await conn.execute("PRAGMA temp_store=MEMORY")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.execute("PRAGMA busy_timeout=60000")  # Increased to 60 seconds
        await conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory mapping
        await conn.execute("PRAGMA page_size=4096")
        await conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
        
        logger.info("Creating database tables...")
        
        # Create users table first (most critical)
        await conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            is_active BOOLEAN DEFAULT 1,
            two_fa_enabled BOOLEAN DEFAULT 0,
            two_fa_secret TEXT,
            created_at TEXT NOT NULL,
            last_login TEXT,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TEXT,
            email TEXT UNIQUE,
            full_name TEXT,
            google_id TEXT UNIQUE,
            profile_picture TEXT,
            settings TEXT DEFAULT '{}',
            password_changed_at TEXT,
            last_password_reset TEXT,
            account_locked BOOLEAN DEFAULT 0,
            lock_reason TEXT,
            login_history TEXT DEFAULT '[]',
            login_method TEXT DEFAULT 'web'
        )""")
        logger.info("✅ Users table created/verified")
        
        # Ensure email column exists for legacy databases and enforce uniqueness
        try:
            await conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
            logger.info("✅ Added email column to users table")
        except Exception as e:
            if "duplicate column name" not in str(e).lower():
                logger.warning(f"Could not add email column: {e}")
            else:
                logger.info("✅ email column already exists")
        # Create a unique index on email (NULLs allowed, uniqueness enforced when not NULL)
        try:
            await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email)")
            logger.info("✅ Ensured unique index on users.email")
        except Exception as e:
            logger.warning(f"Could not create unique index on users.email: {e}")

        # Add full_name column if it doesn't exist (for existing databases)
        try:
            await conn.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
            logger.info("✅ Added full_name column to users table")
        except Exception as e:
            if "duplicate column name" not in str(e).lower():
                logger.warning(f"Could not add full_name column: {e}")
            else:
                logger.info("✅ full_name column already exists")
        
        # Create user_sessions table for session management
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token TEXT UNIQUE NOT NULL,
            csrf_token TEXT,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
            client_ip TEXT,
            user_agent TEXT,
            login_method TEXT DEFAULT 'web',
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        logger.info("✅ User sessions table created/verified")
        
        # Add csrf_token column if it doesn't exist (for existing databases)
        try:
            await conn.execute("ALTER TABLE user_sessions ADD COLUMN csrf_token TEXT")
            logger.info("✅ Added csrf_token column to user_sessions table")
        except Exception as e:
            if "duplicate column name" not in str(e).lower():
                logger.warning(f"Could not add csrf_token column: {e}")
            else:
                logger.info("✅ csrf_token column already exists")
        
        # Create temp_csrf_tokens table for unauthenticated users
        await conn.execute("""CREATE TABLE IF NOT EXISTS temp_csrf_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            csrf_token TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(session_id)
        )""")
        
        # Create indexes for temp_csrf_tokens
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_temp_csrf_session ON temp_csrf_tokens(session_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_temp_csrf_expires ON temp_csrf_tokens(expires_at)")
        logger.info("✅ Temporary CSRF tokens table created/verified")
        
        # Create password recovery table
        await conn.execute("""CREATE TABLE IF NOT EXISTS password_recovery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            used BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        logger.info("✅ Password recovery table created/verified")
        
        # Create mobile_otp table for mobile login
        await conn.execute("""CREATE TABLE IF NOT EXISTS mobile_otp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            otp TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            client_ip TEXT,
            user_agent TEXT
        )""")
        
        # Create indexes for better performance
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_mobile_otp_phone ON mobile_otp(phone)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_mobile_otp_expires ON mobile_otp(expires_at)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_mobile_otp_created ON mobile_otp(created_at)")
        
        logger.info("✅ Mobile OTP table created/verified")
        
        # Create camera_logs table
        await conn.execute("""CREATE TABLE IF NOT EXISTS camera_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            log_type TEXT NOT NULL,
            created_at TEXT DEFAULT '',
            source TEXT DEFAULT 'server',
            pico_timestamp TEXT DEFAULT NULL
        )""")
        logger.info("✅ Camera logs table created/verified")
        
        # Create logs table for general logging
        await conn.execute("""CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            log_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            source TEXT DEFAULT 'server',
            pico_timestamp TEXT DEFAULT NULL,
            user_id INTEGER DEFAULT NULL,
            ip_address TEXT DEFAULT NULL,
            user_agent TEXT DEFAULT NULL,
            session_token TEXT DEFAULT NULL,
            security_event BOOLEAN DEFAULT 0,
            threat_level TEXT DEFAULT 'low'
        )""")
        logger.info("✅ Logs table created/verified")
        
        # Create servo_commands table
        await conn.execute("""CREATE TABLE IF NOT EXISTS servo_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            servo1 INTEGER NOT NULL,
            servo2 INTEGER NOT NULL,
            created_at TEXT DEFAULT '',
            processed INTEGER DEFAULT 0
        )""")
        logger.info("✅ Servo commands table created/verified")
        
        # Create action_commands table
        await conn.execute("""CREATE TABLE IF NOT EXISTS action_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            intensity INTEGER DEFAULT 50,
            created_at TEXT DEFAULT '',
            processed INTEGER DEFAULT 0
        )""")
        logger.info("✅ Action commands table created/verified")
        
        # Create device_mode_commands table
        await conn.execute("""CREATE TABLE IF NOT EXISTS device_mode_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_mode TEXT NOT NULL,
            created_at TEXT DEFAULT '',
            processed INTEGER DEFAULT 0,
            user_id INTEGER,
            ip_address TEXT,
            user_agent TEXT,
            session_token TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )""")
        logger.info("✅ Device mode commands table created/verified")
        
        # Create security_events table for advanced threat detection
        await conn.execute("""CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            description TEXT NOT NULL,
            ip_address TEXT,
            user_id INTEGER,
            session_id TEXT,
            user_agent TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved BOOLEAN DEFAULT 0,
            resolved_at TEXT,
            resolved_by TEXT,
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )""")
        logger.info("✅ Security events table created/verified")
        
        # Create rate_limit_logs table for monitoring rate limiting
        await conn.execute("""CREATE TABLE IF NOT EXISTS rate_limit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            request_count INTEGER DEFAULT 1,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            blocked BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        logger.info("✅ Rate limit logs table created/verified")
        
        # Create manual_photos table
        await conn.execute("""CREATE TABLE IF NOT EXISTS manual_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            quality INTEGER DEFAULT 80,
            flash_used BOOLEAN DEFAULT FALSE,
            flash_intensity INTEGER DEFAULT 50,
            created_at TEXT DEFAULT ''
        )""")
        logger.info("✅ Manual photos table created/verified")
        
        # Create security_videos table
        await conn.execute("""CREATE TABLE IF NOT EXISTS security_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            hour_of_day INTEGER NOT NULL,
            duration INTEGER DEFAULT 3600,
            created_at TEXT DEFAULT ''
        )""")
        logger.info("✅ Security videos table created/verified")
        
        # Create user_settings table with migration
        await migrate_user_settings_table()
        logger.info("✅ User settings table created/verified with migration")
        
        # Migrate logs table to ensure all columns exist
        await migrate_logs_table()
        logger.info("✅ Logs table migration completed")
        
        # Insert default admin user if not exists
        try:
            admin_exists = await conn.execute('SELECT COUNT(*) FROM users WHERE username = ?', (ADMIN_USERNAME,))
            admin_count = await admin_exists.fetchone()
            
            if admin_count[0] == 0:
                admin_password_hash = hash_password(ADMIN_PASSWORD)
                await conn.execute('''
                    INSERT INTO users (username, password_hash, role, is_active, created_at)
                    VALUES (?, ?, 'admin', 1, ?)
                ''', (ADMIN_USERNAME, admin_password_hash, get_jalali_now_str()))
                logger.info(f"✅ Default admin user '{ADMIN_USERNAME}' created")
            else:
                logger.info(f"✅ Admin user '{ADMIN_USERNAME}' already exists")
        except Exception as e:
            logger.warning(f"⚠️ Error checking/creating admin user: {e}")
            # Continue anyway - user might already exist
        
        # Create indexes for better performance and security
        logger.info("Creating database indexes...")
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_user_sessions_session_token ON user_sessions(session_token)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_security_events_event_type ON security_events(event_type)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_security_events_severity ON security_events(severity)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_security_events_ip_address ON security_events(ip_address)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_password_recovery_token ON password_recovery(token)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_password_recovery_expires_at ON password_recovery(expires_at)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_rate_limit_logs_ip_endpoint ON rate_limit_logs(ip_address, endpoint)')
        logger.info("✅ Database indexes created successfully")
        
        await conn.commit()
        system_state = get_system_state()
        system_state.db_initialized = True
        logger.info("🎉 Database and all tables initialized successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
        system_state = get_system_state()
        system_state.db_initialized = False
        raise
    finally:
        if conn:
            await close_db_connection(conn)

def robust_db_endpoint(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except aiosqlite.OperationalError as e:
            if 'no such table' in str(e):
                try:
                    logger.debug("Table not found, attempting database initialization")
                    system_state = get_system_state()
                    if not system_state.db_initialized:
                        await init_db()
                    return await func(*args, **kwargs)
                except Exception as e2:
                    logger.error(f"DB recovery failed: {e2}")
                    raise HTTPException(status_code=500, detail="Database recovery failed")
            elif 'database is locked' in str(e):
                logger.error(f"Database locked: {e}")
                raise HTTPException(status_code=503, detail="Database is locked, please try again")
            else:
                logger.error(f"Database operational error: {e}")
                raise HTTPException(status_code=503, detail="Database operational error")
        except aiosqlite.DatabaseError as e:
            logger.error(f"Database error: {e}")
            raise HTTPException(status_code=503, detail="Database error")
        except asyncio.TimeoutError as e:
            logger.error(f"Database timeout: {e}")
            raise HTTPException(status_code=503, detail="Database timeout")
        except Exception as e:
            logger.error(f"Unexpected DB error: {e}")
            # Return proper error response for test environment
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=503,
                content={"detail": "Database error", "error": str(e)}
            )
    return wrapper





# --- Migration: Ensure all required tables exist, including camera_logs ---
async def migrate_all_tables():
    """Migrate database tables with better error handling"""
    conn = await get_db_connection()
    try:
        # device_mode_commands table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS device_mode_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_mode TEXT NOT NULL,
                created_at TEXT DEFAULT '',
                processed INTEGER DEFAULT 0
            )
        ''')
        # camera_logs table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS camera_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                log_type TEXT NOT NULL,
                created_at TEXT DEFAULT '',
                source TEXT DEFAULT 'server',
                pico_timestamp TEXT DEFAULT NULL
            )
        ''')
        
        # password_recovery table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS password_recovery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                used BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')
        
        # Migrate existing users table to add new columns with better error handling
        try:
            # Check if email column exists - handle UNIQUE constraint properly
            await conn.execute('ALTER TABLE users ADD COLUMN email TEXT')
            logger.info("Added email column to users table")
            # Add UNIQUE constraint separately if needed
            try:
                await conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL')
                logger.info("Added unique index for email column")
            except Exception as idx_e:
                logger.debug(f"Email unique index already exists: {idx_e}")
        except Exception as e:
            if "duplicate column name" in str(e):
                logger.debug("Email column already exists (non-critical)")
            else:
                logger.warning(f"Could not add email column: {e}")
        
        # Add username unique constraint if not exists
        try:
            await conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)')
            logger.info("Added unique index for username column")
        except Exception as idx_e:
            logger.debug(f"Username unique index already exists: {idx_e}")
        
        # Force create username unique constraint
        try:
            await conn.execute('CREATE UNIQUE INDEX idx_users_username_unique ON users(username)')
            logger.info("Added unique constraint for username column")
        except Exception as idx_e:
            if "UNIQUE constraint failed" in str(idx_e) or "already exists" in str(idx_e):
                logger.debug("Username unique constraint already exists")
            else:
                logger.warning(f"Could not add username unique constraint: {idx_e}")
        
        # Alternative approach: Drop and recreate if needed
        try:
            await conn.execute('DROP INDEX IF EXISTS idx_users_username_unique')
            await conn.execute('CREATE UNIQUE INDEX idx_users_username_unique ON users(username)')
            logger.info("Recreated unique constraint for username column")
        except Exception as idx_e:
            logger.debug(f"Could not recreate username unique constraint: {idx_e}")
                
        try:
            # Check if two_fa_enabled column exists
            await conn.execute('ALTER TABLE users ADD COLUMN two_fa_enabled BOOLEAN DEFAULT 0')
            logger.info("Added two_fa_enabled column to users table")
        except Exception as e:
            if "duplicate column name" in str(e):
                logger.debug("two_fa_enabled column already exists (non-critical)")
            else:
                logger.warning(f"Could not add two_fa_enabled column: {e}")
                
        try:
            # Check if two_fa_secret column exists
            await conn.execute('ALTER TABLE users ADD COLUMN two_fa_secret TEXT')
            logger.info("Added two_fa_secret column to users table")
        except Exception as e:
            if "duplicate column name" in str(e):
                logger.debug("two_fa_secret column already exists (non-critical)")
            else:
                logger.warning(f"Could not add two_fa_secret column: {e}")
        
        await conn.commit()
    finally:
        await close_db_connection(conn)






async def execute_db_insert(query: str, params: tuple, migration_handler=None, init_handler=None):
    """Common function to execute database insert with retry, migration handling, and optional init"""
    async def _insert():
        if init_handler:
            await init_handler()
        conn = await get_db_connection()
        try:
            await conn.execute(query, params)
            await conn.commit()
        except Exception as e:
            if migration_handler and 'no such table' in str(e):
                await migration_handler()
                # Try again after migration
                await conn.execute(query, params)
                await conn.commit()
            else:
                raise
        finally:
            await close_db_connection(conn)
    await retry_async(_insert)


async def insert_log(message: str, log_type: str, source: str = "server", pico_timestamp: str = None, 
                    user_id: int = None, ip_address: str = None, user_agent: str = None, 
                    session_id: str = None, security_event: bool = False, threat_level: str = "low"):
    """Insert log entry into database with enhanced security logging"""
    if not message or len(message) > 1000:
        logger.warning("Invalid log message")
        return
    try:
        await execute_db_insert(
            """INSERT INTO logs (message, log_type, created_at, source, pico_timestamp, 
                               user_id, ip_address, user_agent, session_id, security_event, threat_level) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (message[:1000], log_type, get_jalali_now_str(), source, pico_timestamp,
             user_id, ip_address, user_agent, session_id, security_event, threat_level),
            init_handler=init_db
        )
    except Exception as e:
        logger.error(f"Failed to insert log: {e}")
        # Don't raise exception to avoid breaking the main flow
    
    # برای خطاهای بحرانی، هشدار به admin
    if log_type == "error" and ("critical" in message.lower() or "fatal" in message.lower()):
        alert_admin(f"Critical error from {source}: {message}", critical=True)


async def insert_servo_command(servo1: int, servo2: int):
    if not (0 <= servo1 <= 180 and 0 <= servo2 <= 180):
        logger.warning("Invalid servo command")
        return
    await execute_db_insert(
        "INSERT INTO servo_commands (servo1, servo2, created_at) VALUES (?, ?, ?)", 
        (servo1, servo2, get_jalali_now_str())
    )


async def insert_action_command(action: str, intensity: int = 50):
    if not action or len(action) > 50:
        logger.warning("Invalid action command")
        return
    await execute_db_insert(
        "INSERT INTO action_commands (action, intensity, created_at) VALUES (?, ?, ?)", 
        (action, intensity, get_jalali_now_str())
    )


async def insert_device_mode_command(device_mode: str):
    if device_mode not in ["desktop", "mobile"]:
        logger.warning(f"Invalid device mode: {device_mode}")
        return
    await execute_db_insert(
        "INSERT INTO device_mode_commands (device_mode, created_at) VALUES (?, ?)", 
        (device_mode, get_jalali_now_str()),
        migration_handler=migrate_all_tables
    )



async def store_user_csrf_token(username: str, token: str):
    """Store CSRF token in database for user with enhanced security"""
    try:
        conn = await get_db_connection()
        # First get the user_id for the username
        cursor = await conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        )
        user_result = await cursor.fetchone()
        
        if not user_result:
            logger.warning(f"User {username} not found for CSRF token storage")
            await close_db_connection(conn)
            return
        
        user_id = user_result[0]
        
        # Store or update CSRF token in user_sessions table
        await conn.execute("""
            INSERT OR REPLACE INTO user_sessions 
            (user_id, session_token, csrf_token, expires_at, created_at, last_activity, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (
            user_id, 
            f"csrf_session_{username}_{int(datetime.now().timestamp())}", 
            token, 
            (datetime.now() + timedelta(hours=1)).isoformat(),
            get_jalali_now_str(),
            get_jalali_now_str()
        ))
        await conn.commit()
        await close_db_connection(conn)
        logger.info(f"CSRF token stored for user {username}")
    except Exception as e:
        logger.error(f"Error storing CSRF token for {username}: {e}")



def require_csrf_token(func):
    """Enhanced decorator to require CSRF token validation with improved security"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract request from args
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        
        if not request:
            # Try to get from kwargs
            request = kwargs.get('request') or kwargs.get('req')
        
        if not request or not isinstance(request, Request):
            raise HTTPException(status_code=400, detail="Request object not found")
        
        # Skip CSRF check for exempt paths (WebSocket, static files, health checks)
        if hasattr(request, 'url') and request.url and any(request.url.path.startswith(path) for path in CSRF_CONFIG['EXEMPT_PATHS']):
            return await func(*args, **kwargs)
        
        # Skip CSRF check for safe methods
        if hasattr(request, 'method') and request.method in ["GET", "HEAD", "OPTIONS"]:
            return await func(*args, **kwargs)
        
        # Get CSRF token from request
        csrf_token = get_csrf_token_from_request(request)
        
        if not csrf_token:
            path_info = request.url.path if hasattr(request, 'url') and request.url else "unknown"
            logger.warning(f"CSRF token missing for {getattr(request, 'method', 'unknown')} {path_info} from {getattr(request.client, 'host', 'unknown')}")
            await log_security_event("CSRF_MISSING", f"CSRF token missing from {getattr(request.client, 'host', 'unknown')}", "medium", 
                                   getattr(request.client, 'host', 'unknown'), user_agent=request.headers.get('user-agent'))
            raise HTTPException(status_code=403, detail="CSRF token missing")
        
        # Get stored token from user session
        try:
            user = get_current_user(request)
            if not user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            # Get stored token from database
            stored_token = await get_user_csrf_token(user.get('username'))
            
            if not stored_token or not validate_csrf_token(csrf_token, stored_token):
                path_info = request.url.path if hasattr(request, 'url') and request.url else "unknown"
                logger.warning(f"Invalid CSRF token for {getattr(request, 'method', 'unknown')} {path_info} from {getattr(request.client, 'host', 'unknown')}")
                await log_security_event("CSRF_ATTEMPT", f"Invalid CSRF token from {getattr(request.client, 'host', 'unknown')}", "high", 
                                       getattr(request.client, 'host', 'unknown'), user_agent=request.headers.get('user-agent'))
                raise HTTPException(status_code=403, detail="Invalid CSRF token")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"CSRF validation error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
        
        return await func(*args, **kwargs)
    
    return wrapper


async def get_user_csrf_token(username: str) -> str:
    """Get CSRF token from database for user with enhanced security"""
    try:
        conn = await get_db_connection()
        cursor = await conn.execute("""
            SELECT us.csrf_token, us.expires_at 
            FROM user_sessions us 
            JOIN users u ON us.user_id = u.id 
            WHERE u.username = ? AND us.expires_at > ? AND us.is_active = 1
            ORDER BY us.created_at DESC
            LIMIT 1
        """, (username, datetime.now().isoformat()))
        result = await cursor.fetchone()
        await close_db_connection(conn)
        
        if result and result[0]:
            token, expiry = result
            # Check if token is expired
            if expiry and datetime.fromisoformat(expiry) > datetime.now():
                return token
            else:
                # Token expired, generate new one
                new_token = generate_csrf_token()
                await store_user_csrf_token(username, new_token)
                return new_token
        else:
            # No token exists, generate new one
            new_token = generate_csrf_token()
            await store_user_csrf_token(username, new_token)
            return new_token
    except Exception as e:
        logger.error(f"Error getting CSRF token for {username}: {e}")
        return None
