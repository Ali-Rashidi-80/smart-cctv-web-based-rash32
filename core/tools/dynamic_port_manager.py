import os, shutil, time, logging, threading, json, socket
from datetime import datetime

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False

JSON_DIR = os.path.join(os.path.dirname(__file__), "port_state")
JSON_PATH = os.path.join(JSON_DIR, "dynamic_ports.json")

def ensure_json_dir():
    try:
        os.makedirs(JSON_DIR, exist_ok=True)
    except Exception as e:
        print(f"[ERROR] Could not create JSON directory: {e}")
        logging.error(f"[ERROR] Could not create JSON directory: {e}")

def get_fingilish_weekday(dt):
    weekday_map = {
        'Saturday': 'shanbe',
        'Sunday': 'yekshanbe',
        'Monday': 'doshanbe',
        'Tuesday': 'seshanbe',
        'Wednesday': 'chaharshanbe',
        'Thursday': 'panjshanbe',
        'Friday': 'jome',
    }
    return weekday_map.get(dt.strftime('%A'), dt.strftime('%A'))

def get_jalali_now_str():
    try:
        from persiantools.jdatetime import JalaliDateTime
        dt = datetime.now()
        jdt = JalaliDateTime.to_jalali(dt)
        day_fing = get_fingilish_weekday(dt)
        return jdt.strftime('%Y/%m/%d %H:%M') + f' {day_fing}'
    except Exception:
        dt = datetime.now()
        day_fing = get_fingilish_weekday(dt)
        return dt.strftime('%Y/%m/%d %H:%M') + f' {day_fing}'

def format_ports_summary(ports):
    if not ports:
        return "[]"
    if len(ports) == 1:
        return f"[{ports[0]}]"
    return f"[{ports[0]}...{ports[-1]}]({len(ports)})"

def safe_str(val, width=5):
    return str(val) if val is not None else "-".ljust(width)

TAG_COLORS = {
    "INIT": Fore.CYAN + Style.BRIGHT,
    "REFRESH": Fore.BLUE + Style.BRIGHT,
    "PICK": Fore.GREEN + Style.BRIGHT,
    "RELEASE": Fore.MAGENTA + Style.BRIGHT,
    "CLEANUP": Fore.YELLOW + Style.BRIGHT,
    "ERROR": Fore.RED + Style.BRIGHT,
    "STOP": Fore.LIGHTBLACK_EX + Style.BRIGHT,
    "SERVER START": Fore.LIGHTGREEN_EX + Style.BRIGHT,
    "DEFAULT": Fore.WHITE + Style.BRIGHT,
}
FIELD_COLORS = {
    "active": Fore.LIGHTYELLOW_EX + Style.BRIGHT,
    "free": Fore.LIGHTGREEN_EX + Style.BRIGHT,
    "used": Fore.LIGHTRED_EX + Style.BRIGHT,
    "note": Fore.LIGHTCYAN_EX + Style.BRIGHT,
}

def colorize(text, color):
    if COLORAMA_AVAILABLE:
        return color + str(text) + Style.RESET_ALL
    return str(text)

def log_line(tag, active, free, used, note=None):
    tag_clean = tag.replace("[", "").replace("]", "").strip().upper()
    tag_color = TAG_COLORS.get(tag_clean, TAG_COLORS["DEFAULT"])
    parts = [
        colorize(f"{tag:<10}", tag_color),
        colorize(f"Active:{safe_str(active):<5}", FIELD_COLORS["active"]),
        colorize(f"Free:{format_ports_summary(free):<18}", FIELD_COLORS["free"]),
        colorize(f"Used:{format_ports_summary(used):<18}", FIELD_COLORS["used"])
    ]
    if note:
        parts.append(colorize(f"Note:{note}", FIELD_COLORS["note"]))
    return " | ".join(parts)

def default_state():
    return {
        "پورت_فعلی": None,
        "پورت_های_آزاد": [],
        "پورت_های_اشغال": [],
        "آخرین_بررسی": None,
        "تعداد_استفاده": {}
    }

class DynamicPortManager:
    """
    Smart dynamic port manager for network servers with state saved in JSON.
    - Console logs are in English (for devs) and colored (if colorama is available)
    - JSON state is in Persian (for monitoring)
    - Weekday is always Fingilish
    - JSON file is always in utils/port_state/dynamic_ports.json
    - Logs are minimal, structured, and only on real changes
    - All exceptions and edge cases are handled gracefully.
    """
    def __init__(self, start=3000, end=9000, json_path=JSON_PATH, refresh_interval=60, enable_background_logging=False):
        ensure_json_dir()
        self.start = start
        self.end = end
        self.json_path = json_path
        self.refresh_interval = refresh_interval  # Increased from 10 to 60 seconds
        self.enable_background_logging = enable_background_logging  # New parameter to control background logging
        self.lock = threading.Lock()
        self.state = self._load_state()
        self._last_log_snapshot = self._snapshot_state()
        self._stop_event = threading.Event()
        self._bg_thread = threading.Thread(target=self.background_refresh, daemon=True)
        self._bg_thread.start()
        # Only log initialization once to reduce console noise
        if not hasattr(self, '_initialized'):
            self.log_state("INIT", note="DynamicPortManager started.")
            self._initialized = True

    def _load_state(self):
        ensure_json_dir()
        state = None
        try:
            if os.path.exists(self.json_path):
                with open(self.json_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        # فایل خالی
                        raise json.decoder.JSONDecodeError("Empty JSON file", "", 0)
                    state = json.loads(content)
            else:
                state = default_state()
        except json.decoder.JSONDecodeError as e:
            self.handle_io_error(e, "load_state (JSONDecodeError)")
            # حذف فایل خراب و مقداردهی پیش‌فرض
            try:
                os.remove(self.json_path)
            except Exception:
                pass
            state = default_state()
        except Exception as e:
            self.handle_io_error(e, "load_state (Other Exception)")
            state = default_state()
        # مقداردهی کلیدهای پیش‌فرض اگر نبودند
        for k, v in default_state().items():
            if k not in state:
                state[k] = v
        return state

    def _save_state(self):
        ensure_json_dir()
        try:
            with self.lock:
                # ایجاد فایل موقت برای جلوگیری از corruption
                temp_path = self.json_path + ".tmp"
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(self.state, f, indent=2, ensure_ascii=False)
                
                # جایگزینی فایل اصلی با فایل موقت
                if os.path.exists(self.json_path):
                    os.remove(self.json_path)
                os.rename(temp_path, self.json_path)
        except Exception as e:
            self.handle_io_error(e, "save_state")
            # حذف فایل موقت در صورت خطا
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except:
                pass

    def _is_port_free(self, port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("", port))
                return True
        except Exception:
            return False

    def _snapshot_state(self):
        return {
            "current": self.state.get("پورت_فعلی"),
            "free_count": len(self.state.get("پورت_های_آزاد", [])),
            "used_count": len(self.state.get("پورت_های_اشغال", [])),
        }

    def _should_log(self, tag, prev, curr):
        # If background logging is disabled, only log important events
        if not self.enable_background_logging and tag in ("REFRESH", "CLEANUP"):
            return False
        
        # Reduce logging frequency - only log significant changes
        if tag in ("INIT", "ERROR", "STOP", "PICK", "RELEASE"):
            return True  # Always log important events
        if tag == "CLEANUP":
            # Only log cleanup once per 10 minutes
            if hasattr(self, '_last_cleanup_log'):
                if time.time() - self._last_cleanup_log < 600:  # 10 minutes
                    return False
                self._last_cleanup_log = time.time()
            else:
                self._last_cleanup_log = time.time()
            return True
        if tag == "REFRESH":
            # Only log refresh once per 5 minutes
            if hasattr(self, '_last_refresh_log'):
                if time.time() - self._last_refresh_log < 300:  # 5 minutes
                    return False
                self._last_refresh_log = time.time()
            else:
                self._last_refresh_log = time.time()
            return True
        # For other tags, only log if there are significant changes
        return (
            prev["current"] != curr["current"] or
            abs(prev["free_count"] - curr["free_count"]) > 5 or  # Only log if free count changes by more than 5
            abs(prev["used_count"] - curr["used_count"]) > 2    # Only log if used count changes by more than 2
        )

    def find_free_ports(self, count=20):
        free_ports = []
        used_ports = []
        for port in range(self.start, self.end):
            if self._is_port_free(port):
                free_ports.append(port)
                if len(free_ports) >= count:
                    break
            else:
                used_ports.append(port)
        self.state["پورت_های_آزاد"] = free_ports
        self.state["پورت_های_اشغال"] = used_ports
        self.state["آخرین_بررسی"] = get_jalali_now_str()
        self._save_state()
        # Use the improved logging logic in _should_log
        self._maybe_log("REFRESH")
        return free_ports

    def pick_port(self):
        self.find_free_ports()
        free_ports = self.state["پورت_های_آزاد"]
        if not free_ports:
            raise RuntimeError("No free ports found in the given range.")
        port = min(free_ports)
        self.state["پورت_فعلی"] = port
        self.state["پورت_های_اشغال"] = list(set(self.state["پورت_های_اشغال"]) | {port})
        self.state["تعداد_استفاده"][str(port)] = self.state["تعداد_استفاده"].get(str(port), 0) + 1
        self._save_state()
        self._maybe_log("PICK")
        return port

    def release_port(self):
        port = self.state.get("پورت_فعلی")
        if port:
            self.state["پورت_فعلی"] = None
            if port in self.state["پورت_های_اشغال"]:
                self.state["پورت_های_اشغال"].remove(port)
            self._save_state()
            self._maybe_log("RELEASE")

    def background_refresh(self):
        """Background refresh with enhanced error handling and resource management"""
        while not self._stop_event.is_set():
            try:
                self.find_free_ports()
                self.cleanup_state()
            except Exception as e:
                self.handle_io_error(e, "background_refresh")
                # Wait longer on error to prevent rapid retries
                time.sleep(self.refresh_interval * 2)
            else:
                time.sleep(self.refresh_interval)

    def cleanup_state(self):
        free_ports = [p for p in self.state.get("پورت_های_آزاد", []) if self._is_port_free(p)]
        used_ports = [p for p in self.state.get("پورت_های_اشغال", []) if not self._is_port_free(p)]
        self.state["پورت_های_آزاد"] = free_ports
        self.state["پورت_های_اشغال"] = used_ports
        self._save_state()
        # Use the improved logging logic in _should_log
        self._maybe_log("CLEANUP")

    def get_state(self):
        return self.state

    def log_state(self, tag, note=None):
        now = get_jalali_now_str()
        state = getattr(self, "state", None)
        if not state:
            msg = f"[{now}] | {tag:<10} | ERROR: state is not initialized"
            print(msg)
            logging.error(msg)
            return
        msg = (
            f"[{now}] | "
            + log_line(
                tag,
                state.get('پورت_فعلی'),
                state.get('پورت_های_آزاد', []),
                state.get('پورت_های_اشغال', []),
                note
            )
        )
        # Only print to console, don't duplicate in logging
        print(msg)

    def _maybe_log(self, tag):
        prev = self._last_log_snapshot
        curr = self._snapshot_state()
        if self._should_log(tag, prev, curr):
            self.log_state(tag)
            self._last_log_snapshot = curr

    def handle_io_error(self, e, context):
        now = get_jalali_now_str()
        msg = f"[{now}] | [ERROR] {context}: {e}"
        print(msg)
        logging.error(msg)
        if hasattr(self, "state"):
            self.log_state("ERROR", note=str(e))
        
        # اگر خطا مربوط به جیسون خراب یا خالی بود، فایل را حذف کن تا سالم ساخته شود
        if (isinstance(e, json.decoder.JSONDecodeError) or "Empty JSON" in str(e)) and os.path.exists(self.json_path):
            try:
                # ایجاد backup از فایل خراب قبل از حذف
                backup_path = self.json_path + f".corrupted_{int(time.time())}"
                shutil.copy2(self.json_path, backup_path)
                print(f"[{now}] | [ERROR] Corrupted file backed up to: {backup_path}")
                
                os.remove(self.json_path)
                print(f"[{now}] | [ERROR] Corrupted/Empty JSON file removed: {self.json_path}")
                logging.error(f"[{now}] | [ERROR] Corrupted/Empty JSON file removed: {self.json_path}")
                
                # تلاش برای بازسازی state
                self.state = default_state()
                self._save_state()
                print(f"[{now}] | [INFO] State reconstructed from default")
                
            except Exception as ex:
                print(f"[{now}] | [ERROR] Could not remove corrupted JSON file: {ex}")
                logging.error(f"[{now}] | [ERROR] Could not remove corrupted JSON file: {ex}")
        
        # بررسی خطاهای دیگر
        elif isinstance(e, PermissionError):
            print(f"[{now}] | [ERROR] Permission denied accessing file: {self.json_path}")
            logging.error(f"[{now}] | [ERROR] Permission denied accessing file: {self.json_path}")
        elif isinstance(e, OSError):
            print(f"[{now}] | [ERROR] OS error accessing file: {e}")
            logging.error(f"[{now}] | [ERROR] OS error accessing file: {e}")

    def stop(self):
        self._stop_event.set()
        self._bg_thread.join(timeout=2)
        self.release_port()
        self.log_state("STOP", note="DynamicPortManager stopped.")

# Usage example in your main server:
# from utils.dynamic_port_manager import DynamicPortManager
# port_manager = DynamicPortManager(3000, 9000)
# port = port_manager.pick_port()
# ...
# port_manager.stop() on shutdown