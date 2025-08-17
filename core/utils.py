import asyncio, time, os, gc, random, gzip, shutil, psutil, logging, logging.config, logging.handlers
from datetime import datetime

# Setup logger for this module
logger = logging.getLogger("utils")

# Constants
FRAME_QUEUE_SIZE = int(os.getenv("FRAME_QUEUE_SIZE", "100"))
FRAME_BUFFER_SIZE = int(os.getenv("FRAME_BUFFER_SIZE", "50"))
FRAME_PROCESSING_TIMEOUT = float(os.getenv("FRAME_PROCESSING_TIMEOUT", "5.0"))
REALTIME_FRAME_PROCESSING = os.getenv("REALTIME_FRAME_PROCESSING", "true").lower() == "true"
ADAPTIVE_QUALITY = os.getenv("ADAPTIVE_QUALITY", "true").lower() == "true"
VIDEO_QUALITY = int(os.getenv("VIDEO_QUALITY", "80"))
FRAME_PROCESSING_ENABLED = os.getenv("FRAME_PROCESSING_ENABLED", "true").lower() == "true"
WEBSOCKET_ERROR_THRESHOLD = int(os.getenv("WEBSOCKET_ERROR_THRESHOLD", "10"))
INACTIVE_CLIENT_TIMEOUT = int(os.getenv("INACTIVE_CLIENT_TIMEOUT", "300"))
ERROR_RESET_INTERVAL = int(os.getenv("ERROR_RESET_INTERVAL", "3600"))
PERFORMANCE_UPDATE_INTERVAL = int(os.getenv("PERFORMANCE_UPDATE_INTERVAL", "30"))
MEMORY_THRESHOLD = int(os.getenv("MEMORY_THRESHOLD", "85"))
FRAME_DROP_RATIO = float(os.getenv("FRAME_DROP_RATIO", "0.1"))
FRAME_LATENCY_THRESHOLD = float(os.getenv("FRAME_LATENCY_THRESHOLD", "0.5"))
PROCESSING_OVERHEAD_THRESHOLD = float(os.getenv("PROCESSING_OVERHEAD_THRESHOLD", "0.3"))
PERFORMANCE_MONITORING = os.getenv("PERFORMANCE_MONITORING", "true").lower() == "true"

# Additional missing constants
DISK_THRESHOLD = float(os.getenv("DISK_THRESHOLD", "10.0"))  # 10% free space threshold
PSUTIL_AVAILABLE = True  # Will be updated based on import success
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "30"))
GALLERY_DIR = os.getenv("GALLERY_DIR", "gallery")
SECURITY_VIDEOS_DIR = os.getenv("SECURITY_VIDEOS_DIR", "security_videos")
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
DB_FILE = os.getenv("DB_FILE", "smart_camera_system.db")
BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))
BACKUP_INTERVAL = int(os.getenv("BACKUP_INTERVAL", "86400"))  # 24 hours in seconds
FRAME_CACHE_SIZE = int(os.getenv("FRAME_CACHE_SIZE", "100"))
FRAME_CACHE_CLEANUP_INTERVAL = int(os.getenv("FRAME_CACHE_CLEANUP_INTERVAL", "300"))  # 5 minutes
RATE_LIMIT_CONFIG = {
    'WINDOW_SIZE': int(os.getenv("RATE_LIMIT_WINDOW", "60")),
    'MAX_REQUESTS': int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100")),
    'LOGIN_MAX_REQUESTS': int(os.getenv("LOGIN_RATE_LIMIT_MAX", "5")),
    'OTP_MAX_REQUESTS': int(os.getenv("OTP_MAX_REQUESTS", "3")),
    'API_MAX_REQUESTS': int(os.getenv("API_RATE_LIMIT_MAX", "100"))
}

# Check for psutil availability
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Global system state reference (will be set by main server)
system_state = None

# Global dependencies (will be set by main server)
insert_log_func = None
send_to_web_clients_func = None
check_db_health_func = None

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
                self.system_shutdown = False
                self.websocket_error_count = 0
                self.frame_buffer_lock = asyncio.Lock()
                self.web_clients_lock = asyncio.Lock()
                self.performance_lock = asyncio.Lock()
                self.frame_buffer = []
                self.web_clients = []
                self.performance_metrics = {"avg_frame_latency": 0.0, "frame_processing_overhead": 0.0, "frame_drop_rate": 0.0, "memory_usage": 0.0, "cpu_usage": 0.0}
                self.frame_count = 0
                self.frame_drop_count = 0
                self.frame_skip_count = 0
                self.invalid_frame_count = 0
                self.current_quality = 80
                self.adaptive_quality = False
                self.realtime_enabled = False
                self.processing_enabled = True
                self.last_error_reset = time.time()
                self.last_performance_update = time.time()
                self.last_backup_time = time.time()
                self.last_frame_cache_cleanup = time.time()
                self.last_disk_space = 'N/A'
                self.memory_warning_sent = False
                self.frame_processing_times = []
                self.frame_cache = {}
                self.error_counts = {"websocket": 0, "database": 0, "frame_processing": 0, "memory": 0}
                self.last_cleanup_time = None
                self.frame_latency_sum = 0.0
                self.processing_timeout = 5.0
        system_state = TempSystemState()
    return system_state

def set_dependencies(log_func, web_clients_func, db_health_func):
    """Set the dependencies from main server"""
    global insert_log_func, send_to_web_clients_func, check_db_health_func
    insert_log_func = log_func
    send_to_web_clients_func = web_clients_func
    check_db_health_func = db_health_func

async def insert_log_wrapper(message: str, log_type: str, source: str = "utils"):
    """Insert log entry using the main server's log function"""
    if insert_log_func:
        await insert_log_func(message, log_type, source)
    else:
        logger.info(f"[{source}] {message}")

async def send_to_web_clients_wrapper(message):
    """Send message to web clients using the main server's function"""
    if send_to_web_clients_func:
        await send_to_web_clients_func(message)
    else:
        logger.info(f"Web client message (no function): {message}")

async def check_db_health_wrapper():
    """Check database health using the main server's function"""
    if check_db_health_func:
        return await check_db_health_func()
    else:
        logger.warning("Database health check function not available")
        return True

async def get_db_connection():
    """Get database connection - placeholder function"""
    try:
        import aiosqlite
        return await aiosqlite.connect(DB_FILE)
    except ImportError:
        logger.error("aiosqlite not available")
        return None
    except Exception as e:
        logger.error(f"Error getting database connection: {e}")
        return None

async def close_db_connection(conn):
    """Close database connection - placeholder function"""
    if conn:
        try:
            await conn.close()
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")


async def handle_critical_error(error_msg: str, source: str = "server"):
    """مدیریت خطاهای بحرانی"""
    logger.error(f"Critical error from {source}: {error_msg}")
    
    # Only log if insert_log_func is available
    if insert_log_func:
        try:
            await insert_log_wrapper(f"Critical error: {error_msg}", "error", source)
        except Exception as e:
            logger.error(f"Failed to insert critical error log: {e}")
    else:
        logger.warning("insert_log_func not available, skipping database log")
    
    # ارسال هشدار به تمام کلاینت‌ها
    await send_to_web_clients_wrapper({
        "type": "critical_error",
        "message": error_msg,
        "source": source,
        "timestamp": datetime.now().isoformat()
    })

async def monitor_system_health():
    """مانیتورینگ سلامت سیستم با متریک‌های پیشرفته"""
    # Get system state (will create temporary one if needed)
    system_state = get_system_state()
    
    # Wait for dependencies to be set
    while not insert_log_func and not system_state.system_shutdown:
        logger.info("Waiting for dependencies to be set...")
        await asyncio.sleep(5)
    
    if system_state.system_shutdown:
        return
        
    while not system_state.system_shutdown:
        try:
            # به‌روزرسانی متریک‌های عملکرد
            await update_performance_metrics()
            
            # بررسی حافظه
            if not await asyncio.to_thread(check_memory_usage):
                await handle_critical_error("High memory usage detected", "system_monitor")
            
            # بررسی فضای دیسک
            if not await check_disk_space():
                await handle_critical_error("Low disk space detected", "system_monitor")
            
            # بررسی وضعیت دیتابیس
            if not await check_db_health_wrapper():
                await handle_critical_error("Database health check failed", "system_monitor")
            
            # بررسی تعداد خطاهای WebSocket
            if system_state.websocket_error_count > WEBSOCKET_ERROR_THRESHOLD:
                await handle_critical_error(f"High WebSocket error count: {system_state.websocket_error_count}", "system_monitor")
                system_state.websocket_error_count = 0
            
            # بررسی buffer overflow با منطق پیشرفته
            async with system_state.frame_buffer_lock:
                if len(system_state.frame_buffer) > FRAME_BUFFER_SIZE * 1.5:
                    logger.warning("Frame buffer overflow detected, trimming")
                    frames_to_remove = int(FRAME_BUFFER_SIZE * FRAME_DROP_RATIO)
                    system_state.frame_buffer = system_state.frame_buffer[frames_to_remove:]
                    system_state.frame_drop_count += frames_to_remove
            
            # بررسی تعداد کلاینت‌های غیرفعال
            async with system_state.web_clients_lock:
                try:
                    inactive_clients = [c for c in system_state.web_clients if hasattr(c, 'last_activity') and (datetime.now() - c.last_activity).total_seconds() > INACTIVE_CLIENT_TIMEOUT]
                    if inactive_clients:
                        logger.warning(f"Found {len(inactive_clients)} inactive clients, cleaning up")
                        for client in inactive_clients:
                            try:
                                await client.close(code=1000)
                            except Exception as e:
                                logger.warning(f"Error closing inactive client: {e}")
                            try:
                                system_state.web_clients.remove(client)
                            except ValueError:
                                pass  # Client already removed
                except Exception as e:
                    logger.error(f"Error checking inactive clients: {e}")
            
            # بررسی عملکرد real-time با thread safety
            if PERFORMANCE_MONITORING:
                async with system_state.performance_lock:
                    avg_latency = system_state.performance_metrics["avg_frame_latency"]
                    if avg_latency > FRAME_LATENCY_THRESHOLD:
                        logger.warning(f"High frame latency detected: {avg_latency:.3f}s")
                        # کاهش کیفیت برای بهبود عملکرد
                        if system_state.adaptive_quality:
                            system_state.current_quality = max(60, system_state.current_quality - 5)
                            logger.info(f"Reduced quality to {system_state.current_quality} for better performance")
                    
                    # بررسی نرخ حذف فریم
                    drop_rate = system_state.performance_metrics["frame_drop_rate"]
                    if drop_rate > FRAME_DROP_RATIO:
                        logger.warning(f"High frame drop rate: {drop_rate:.2%}")
                
                # بررسی عملکرد پردازش
                processing_overhead = system_state.performance_metrics["frame_processing_overhead"]
                if processing_overhead > PROCESSING_OVERHEAD_THRESHOLD:
                    logger.warning(f"High processing overhead: {processing_overhead:.2%}")
            
            # پاکسازی frame_cache با تابع جدید
            await cleanup_frame_cache()
            
            # Reset error counts periodically
            current_time = time.time()
            if current_time - system_state.last_error_reset > ERROR_RESET_INTERVAL:
                system_state.error_counts = {"websocket": 0, "database": 0, "frame_processing": 0, "memory": 0}
                system_state.last_error_reset = current_time
            
            await asyncio.sleep(30)  # بررسی هر 30 ثانیه
            
        except Exception as e:
            logger.error(f"System health monitoring error: {e}")
            await asyncio.sleep(60)  # در صورت خطا، 1 دقیقه صبر کن



async def check_disk_space():
    try:
        total, used, free = await asyncio.to_thread(shutil.disk_usage, '.')
        free_percent = (free / total) * 100
        system_state.last_disk_space = f"{free_percent:.1f}% free"
        if free_percent < DISK_THRESHOLD:
            logger.warning(f"Low disk space: {free_percent:.1f}% free")
            # Only call insert_log if it's available and properly configured
            try:
                if insert_log_func:
                    await insert_log_func(f"Disk space warning: {free_percent:.1f}% free", "warning")
                else:
                    logger.warning("insert_log_func not available, skipping disk space log")
            except Exception as e:
                logger.debug(f"Could not log disk space warning: {e}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking disk space: {e}")
        return False

def check_memory_usage():
    if not PSUTIL_AVAILABLE:
        return {"available": True, "message": "psutil not available"}
    try:
        process = psutil.Process()
        mem_info = process.memory_info()
        total_memory = psutil.virtual_memory().total
        memory_percent = mem_info.rss / total_memory
        memory_info_dict = {
            "rss": mem_info.rss,
            "vms": mem_info.vms,
            "percent": memory_percent * 100,
            "total_memory": total_memory,
            "available": True
        }
        if memory_percent > MEMORY_THRESHOLD and not system_state.memory_warning_sent:
            logger.warning(f"High memory usage: {memory_percent*100:.1f}%")
            system_state.memory_warning_sent = True
            memory_info_dict["available"] = False
        elif memory_percent <= MEMORY_THRESHOLD:
            system_state.memory_warning_sent = False
        return memory_info_dict
    except Exception as e:
        logger.error(f"Error checking memory usage: {e}")
        return {"available": True, "error": str(e)}

async def update_performance_metrics():
    """به‌روزرسانی متریک‌های عملکرد با thread safety"""
    try:
        # Check if enough time has passed since last update
        current_time = time.time()
        if current_time - system_state.last_performance_update < PERFORMANCE_UPDATE_INTERVAL:
            return
        
        async with system_state.performance_lock:
            if PSUTIL_AVAILABLE:
                system_state.performance_metrics["memory_usage"] = psutil.virtual_memory().percent
                system_state.performance_metrics["cpu_usage"] = psutil.cpu_percent(interval=0.1)
            
            # محاسبه نرخ حذف فریم
            if system_state.frame_count > 0:
                system_state.performance_metrics["frame_drop_rate"] = system_state.frame_drop_count / system_state.frame_count
            
            # به‌روزرسانی زمان
            system_state.last_performance_update = current_time
        
    except Exception as e:
        logger.error(f"Error updating performance metrics: {e}")

async def get_performance_metrics():
    """دریافت متریک‌های عملکرد سیستم"""
    try:
        await update_performance_metrics()
        return {
            "status": "success",
            "metrics": system_state.performance_metrics,
            "frame_stats": {
                "total_frames": system_state.frame_count,
                "dropped_frames": system_state.frame_drop_count,
                "skipped_frames": system_state.frame_skip_count,
                "invalid_frames": system_state.invalid_frame_count,
                "buffer_size": len(system_state.frame_buffer)
            },
            "processing_stats": {
                "avg_latency": system_state.performance_metrics["avg_frame_latency"],
                "current_quality": system_state.current_quality,
                "realtime_enabled": system_state.realtime_enabled,
                "adaptive_quality": system_state.adaptive_quality
            }
        }
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        return {"status": "error", "message": "Error getting performance metrics"}

async def get_system_performance():
    """دریافت اطلاعات عملکرد سیستم"""
    try:
        await update_performance_metrics()
        current_time = time.time()
        frame_rate = 0
        if len(system_state.frame_processing_times) > 1:
            recent_times = system_state.frame_processing_times[-10:]
            avg_processing_time = sum(recent_times) / len(recent_times)
            frame_rate = 1.0 / avg_processing_time if avg_processing_time > 0 else 0
        return {
            "status": "success",
            "performance": {
                "frame_rate": min(frame_rate, VIDEO_FPS),
                "avg_latency": system_state.performance_metrics["avg_frame_latency"],
                "drop_rate": system_state.performance_metrics["frame_drop_rate"],
                "processing_overhead": system_state.performance_metrics["frame_processing_overhead"],
                "memory_usage": system_state.performance_metrics["memory_usage"],
                "cpu_usage": system_state.performance_metrics["cpu_usage"],
                "current_quality": system_state.current_quality,
                "adaptive_quality": system_state.adaptive_quality,
                "realtime_enabled": system_state.realtime_enabled
            },
            "frame_stats": {
                "total_processed": system_state.frame_count,
                "dropped": system_state.frame_drop_count,
                "skipped": system_state.frame_skip_count,
                "invalid": system_state.invalid_frame_count,
                "buffer_size": len(system_state.frame_buffer),
                "cache_size": len(system_state.frame_cache)
            },
            "system_info": {
                "uptime": current_time - system_state.last_backup_time,
                "last_performance_update": system_state.last_performance_update,
                "processing_enabled": system_state.processing_enabled,
                "last_backup": system_state.last_backup_time
            }
        }
    except Exception as e:
        logger.error(f"Error getting system performance: {e}")
        return {"status": "error", "message": "Error getting system performance"}












async def cleanup_old_files():
    """Clean up old files with enhanced error handling and connection management"""
    try:
        now = time.time()
        # Define allowed tables for security
        ALLOWED_TABLES = {'manual_photos', 'security_videos'}
        
        for folder, ext, table in [
            (GALLERY_DIR, ('.jpg', '.jpeg', '.png'), 'manual_photos'),
            (SECURITY_VIDEOS_DIR, ('.mp4', '.avi', '.mov'), 'security_videos')
        ]:
            if not os.path.exists(folder):
                continue
                
            files_to_delete = []
            for fname in await asyncio.to_thread(os.listdir, folder):
                if not fname.lower().endswith(ext):
                    continue
                fpath = os.path.join(folder, fname)
                try:
                    stat = await asyncio.to_thread(os.stat, fpath)
                    if now - stat.st_mtime > 30*24*3600:
                        files_to_delete.append((fname, fpath))
                except OSError as e:
                    logger.warning(f"Error checking file {fpath}: {e}")
                    continue
            
            # Delete files and update database in batches
            if files_to_delete:
                conn = None
                try:
                    conn = await get_db_connection()
                    for fname, fpath in files_to_delete:
                        try:
                            # Delete file first
                            await asyncio.to_thread(os.remove, fpath)
                            # Then update database - use whitelist validation for table name
                            if table not in ALLOWED_TABLES:
                                logger.error(f"Invalid table name detected: {table}")
                                continue
                            # Use parameterized query with table name validation
                            if table == 'manual_photos':
                                await conn.execute("DELETE FROM manual_photos WHERE filename=?", (fname,))
                            elif table == 'security_videos':
                                await conn.execute("DELETE FROM security_videos WHERE filename=?", (fname,))
                            else:
                                logger.error(f"Unknown table name: {table}")
                                continue
                            logger.debug(f"Deleted old file: {fname}")
                        except OSError as e:
                            logger.warning(f"Error deleting file {fpath}: {e}")
                        except Exception as e:
                            logger.error(f"Error updating database for {fname}: {e}")
                    
                    # Commit all changes
                    await conn.commit()
                    logger.info(f"Cleaned up {len(files_to_delete)} old files from {folder}")
                    
                except Exception as e:
                    logger.error(f"Error in cleanup batch for {folder}: {e}")
                finally:
                    if conn:
                        await close_db_connection(conn)
        
        system_state.last_cleanup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    except Exception as e:
        logger.error(f"Error cleaning up old files: {e}")
        # Force garbage collection on error
        await asyncio.to_thread(gc.collect)



async def cleanup_expired_recovery_codes():
    """Clean up expired recovery codes"""
    try:
        conn = await get_db_connection()
        await conn.execute(
            'DELETE FROM password_recovery WHERE expires_at < ?',
            (datetime.now().isoformat(),)
        )
        await conn.commit()
        await close_db_connection(conn)
        logger.info("Expired recovery codes cleaned up successfully")
    except Exception as e:
        logger.error(f"Error cleaning up expired recovery codes: {e}")


async def cleanup_in_memory_rate_limits():
    """Clean up expired in-memory rate limit entries"""
    try:
        current_time = time.time()
        
        # Clean up general rate limit storage
        # Note: RATE_LIMIT_CONFIG structure has changed, so we'll clean up safely
        try:
            # Clean api_rate_limit_storage if it exists and is a dict
            global api_rate_limit_storage
            if isinstance(api_rate_limit_storage, dict):
                # Clean expired entries (older than 1 hour)
                window_start = current_time - 3600  # 1 hour
                api_rate_limit_storage = {ip: timestamps for ip, timestamps in api_rate_limit_storage.items() 
                                        if isinstance(timestamps, list) and any(ts > window_start for ts in timestamps)}
            
            # Clean login_attempts_storage if it exists and is a dict
            global login_attempts_storage
            if isinstance(login_attempts_storage, dict):
                # Clean expired entries (older than 15 minutes)
                window_start = current_time - 900  # 15 minutes
                login_attempts_storage = {ip: data for ip, data in login_attempts_storage.items() 
                                        if isinstance(data, dict) and data.get('last_attempt', 0) > window_start}
        except (NameError, AttributeError) as e:
            # If the global variables don't exist, that's fine
            logger.debug(f"Rate limit storage not available for cleanup: {e}")
        
        logger.debug("In-memory rate limit storage cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up in-memory rate limits: {e}")


async def periodic_cleanup():
    while not system_state.system_shutdown:
        await cleanup_old_files()
        await cleanup_expired_recovery_codes()
        await cleanup_in_memory_rate_limits()
        await asyncio.sleep(24*3600)


async def cleanup_frame_cache():
    """پاکسازی کش فریم‌ها برای جلوگیری از memory leak"""
    try:
        current_time = time.time()
        if current_time - system_state.last_frame_cache_cleanup < FRAME_CACHE_CLEANUP_INTERVAL:
            return
        
        async with system_state.performance_lock:
            # Remove old entries from frame cache
            cache_keys = list(system_state.frame_cache.keys())
            if len(cache_keys) > FRAME_CACHE_SIZE:
                keys_to_remove = cache_keys[:-FRAME_CACHE_SIZE]
                for key in keys_to_remove:
                    del system_state.frame_cache[key]
                logger.debug(f"Cleaned up {len(keys_to_remove)} old frame cache entries")
            
            # Cleanup frame processing times
            if len(system_state.frame_processing_times) > 100:
                system_state.frame_processing_times = system_state.frame_processing_times[-50:]
            
            # Cleanup frame buffer if too large
            async with system_state.frame_buffer_lock:
                if len(system_state.frame_buffer) > FRAME_BUFFER_SIZE * 1.2:
                    frames_to_remove = int(FRAME_BUFFER_SIZE * 0.2)
                    system_state.frame_buffer = system_state.frame_buffer[frames_to_remove:]
                    logger.debug(f"Cleaned up {frames_to_remove} old frame buffer entries")
            
            system_state.last_frame_cache_cleanup = current_time
            
            # Force garbage collection
            await asyncio.to_thread(gc.collect)
            
    except Exception as e:
        logger.error(f"Error cleaning up frame cache: {e}")














async def backup_database():
    try:
        if not await check_disk_space():
            logger.warning("Skipping backup due to low disk space")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.db.gz")
        temp_file = os.path.join(BACKUP_DIR, f"temp_{timestamp}.db")
        await asyncio.to_thread(shutil.copyfile, DB_FILE, temp_file)
        await asyncio.to_thread(lambda: shutil.copyfileobj(open(temp_file, 'rb'), gzip.open(backup_file, 'wb')))
        await asyncio.to_thread(os.remove, temp_file)
        logger.info(f"Database backup created: {backup_file}")
        system_state.last_backup_time = time.time()
        backups = sorted(
            [f for f in await asyncio.to_thread(os.listdir, BACKUP_DIR) if f.endswith('.gz')],
            key=lambda x: os.path.getctime(os.path.join(BACKUP_DIR, x))
        )
        for old_backup in backups[:-BACKUP_RETENTION_DAYS]:
            try:
                await asyncio.to_thread(os.remove, os.path.join(BACKUP_DIR, old_backup))
                logger.info(f"Deleted old backup: {old_backup}")
            except Exception as e:
                logger.error(f"Error deleting old backup {old_backup}: {e}")
    except Exception as e:
        logger.error(f"Backup process error: {e}")
        if os.path.exists(temp_file):
            await asyncio.to_thread(os.remove, temp_file)

async def periodic_backup_and_reset():
    """Periodic backup and reset with enhanced error handling and resource management"""
    while not system_state.system_shutdown:
        try:
            await asyncio.sleep(BACKUP_INTERVAL)
            
            # Check disk space first
            if not await check_disk_space():
                logger.warning("Low disk space detected during periodic check")
                # Try to clean up old files to free space
                await cleanup_old_files()
            
            # Perform backup with retry logic
            backup_success = False
            for attempt in range(3):
                try:
                    await backup_database()
                    backup_success = True
                    break
                except Exception as e:
                    logger.warning(f"Backup attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        await asyncio.sleep(60)  # Wait 1 minute before retry
            
            if not backup_success:
                logger.error("All backup attempts failed")
            
            # Check memory usage
            if not await asyncio.to_thread(check_memory_usage):
                logger.warning("High memory usage detected during periodic check")
                # اجرای garbage collection اضافی
                await asyncio.to_thread(gc.collect)
                # Force cleanup of system state
                await system_state.cleanup()
            
            # Perform system cleanup
            try:
                await system_state.cleanup()
            except Exception as e:
                logger.error(f"Error during system cleanup: {e}")
            
            logger.info("Periodic backup and reset completed")
            
        except asyncio.CancelledError:
            logger.info("Periodic backup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in periodic backup and reset: {e}")
            # اجرای garbage collection در صورت خطا
            await asyncio.to_thread(gc.collect)
            # Wait before retrying
            await asyncio.sleep(300)  # 5 minutes











async def retry_async(func, retries=7, delay=1, backoff=2, exceptions=(Exception,)):
    """Enhanced retry function with better error handling and logging"""
    last_exception = None
    for attempt in range(retries):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            logger.warning(f"Attempt {attempt+1}/{retries} failed: {e}")
            
            # Don't retry on certain critical errors
            if isinstance(e, (ValueError, TypeError, AttributeError)):
                logger.error(f"Critical error, not retrying: {e}")
                raise
            
            if attempt == retries - 1:
                logger.error(f"All {retries} attempts failed. Last error: {e}")
                raise last_exception
            
            # Exponential backoff with jitter
            jitter = random.uniform(0.8, 1.2)
            actual_delay = delay * jitter
            await asyncio.sleep(actual_delay)
            delay *= backoff





