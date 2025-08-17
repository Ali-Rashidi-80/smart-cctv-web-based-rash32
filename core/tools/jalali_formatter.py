import logging
from datetime import datetime
from colorama import Fore, Style, Back, init as colorama_init
import re
import sys
import json

try:
    from persiantools.jdatetime import JalaliDateTime
    PERSIANTOOLS_AVAILABLE = True
except ImportError:
    PERSIANTOOLS_AVAILABLE = False

colorama_init(autoreset=True)

# رنگ‌بندی سطح لاگ
LEVEL_COLORS = {
    'DEBUG': Fore.CYAN + Style.BRIGHT,
    'INFO': Fore.GREEN + Style.BRIGHT,
    'WARNING': Fore.YELLOW + Style.BRIGHT,
    'ERROR': Fore.RED + Style.BRIGHT,
    'CRITICAL': Fore.WHITE + Back.RED + Style.BRIGHT,
}
# رنگ‌بندی متدهای HTTP
METHOD_COLORS = {
    'GET': Fore.BLUE + Style.BRIGHT,
    'POST': Fore.MAGENTA + Style.BRIGHT,
    'PUT': Fore.CYAN + Style.BRIGHT,
    'DELETE': Fore.RED + Style.BRIGHT,
    'PATCH': Fore.YELLOW + Style.BRIGHT,
}
# کلیدواژه‌های مهم (انگلیسی و فارسی)
KEYWORDS = {
    'SUCCESS': Fore.GREEN + Style.BRIGHT,
    'FAILED': Fore.RED + Style.BRIGHT,
    'ERROR': Fore.RED + Style.BRIGHT,
    'WARNING': Fore.YELLOW + Style.BRIGHT,
    'CRITICAL': Fore.WHITE + Back.RED + Style.BRIGHT,
    'STARTED': Fore.CYAN + Style.BRIGHT,
    'STOPPED': Fore.MAGENTA + Style.BRIGHT,
    'موفق': Fore.GREEN + Style.BRIGHT,
    'خطا': Fore.RED + Style.BRIGHT,
    'هشدار': Fore.YELLOW + Style.BRIGHT,
    'بحرانی': Fore.WHITE + Back.RED + Style.BRIGHT,
    'شروع': Fore.CYAN + Style.BRIGHT,
    'پایان': Fore.MAGENTA + Style.BRIGHT,
}
# Regexها
RE_NUMBER = re.compile(r'(\d+)', re.UNICODE)
RE_IP = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
RE_URL = re.compile(r'(https?://[\w\./\-\?&=%]+|/\S+)', re.UNICODE)
RE_FILE = re.compile(r'\b\w+\.(?:py|jpg|png|db|log|json|mp4|avi)\b', re.UNICODE)
RE_QUOTE = re.compile(r'("[^"]*"|\'[^\']*\')', re.UNICODE)
RE_STATUS_2XX_3XX = re.compile(r'\b(2\d\d|3\d\d)\b')
RE_STATUS_4XX = re.compile(r'\b4\d\d\b')
RE_STATUS_5XX = re.compile(r'\b5\d\d\b')

class JalaliFileFormatter(logging.Formatter):
    """
    فرمت‌کننده لاگ برای فایل‌ها بدون رنگ و جداکننده
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created)
        if PERSIANTOOLS_AVAILABLE:
            try:
                jdt = JalaliDateTime.to_jalali(dt)
                weekday_fingilish = {
                    'saturday': 'shanbe',
                    'sunday': 'yekshanbe',
                    'monday': 'doshanbe',
                    'tuesday': 'seshanbe',
                    'wednesday': 'chaharshanbe',
                    'thursday': 'panjshanbe',
                    'friday': 'jome',
                }
                day_en = jdt.strftime('%A').lower()
                day_fing = weekday_fingilish.get(day_en, day_en)
                jalali_str = jdt.strftime('%Y-%m-%d %H:%M:%S') + f' {day_fing}'
                return jalali_str
            except Exception:
                pass
        # Fallback: Gregorian date, English weekday
        weekday_fingilish = {
            'saturday': 'shanbe',
            'sunday': 'yekshanbe',
            'monday': 'doshanbe',
            'tuesday': 'seshanbe',
            'wednesday': 'chaharshanbe',
            'thursday': 'panjshanbe',
            'friday': 'jome',
        }
        day_en = dt.strftime('%A').lower()
        day_fing = weekday_fingilish.get(day_en, day_en)
        gregorian_str = dt.strftime('%Y-%m-%d %H:%M:%S') + f' {day_fing}'
        return gregorian_str

    def format(self, record):
        # سطح لاگ بدون رنگ
        level = record.levelname.upper()
        record.levelname = level
        # پیام بدون رنگ - Fix the string formatting issue
        try:
            msg = record.getMessage()
        except TypeError:
            # Handle case where message has format placeholders but no args
            msg = str(record.msg) if record.msg else ""
        
        # اگر پیام دیکشنری یا JSON باشد، زیبا نمایش بده
        if isinstance(record.msg, (dict, list)):
            msg = json.dumps(record.msg, indent=2, ensure_ascii=False)
        else:
            msg = str(msg)
        
        # Remove any color codes from the message (more comprehensive)
        import re
        # Remove ANSI escape codes
        ansi_pattern = re.compile(r'\033\[[0-9;]*[a-zA-Z]')
        msg = ansi_pattern.sub('', msg)
        # Remove bracket color codes
        bracket_pattern = re.compile(r'\[[0-9;]*[a-zA-Z]')
        msg = bracket_pattern.sub('', msg)
        # Remove any remaining color-related text
        color_text_pattern = re.compile(r'\[32m|\[1m|\[0m|\[31m|\[33m|\[34m|\[35m|\[36m|\[37m')
        msg = color_text_pattern.sub('', msg)
        
        # فرمت نهایی بدون جداکننده
        return f"{self.formatTime(record)}  {record.levelname}  {msg}"

class JalaliFormatter(logging.Formatter):
    """
    فرمت‌کننده لاگ حرفه‌ای با تاریخ شمسی، رنگ‌بندی، جداکننده و جذابیت بصری ویژه برای ترمینال و فایل.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_color = sys.stdout.isatty()
        # Track repeated messages to avoid spam
        self.repeated_messages = {}
        self.max_repeats = 2  # کاهش از 3 به 2
        self.suppression_interval = 300  # 5 دقیقه به جای 1 ساعت

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created)
        if PERSIANTOOLS_AVAILABLE:
            try:
                jdt = JalaliDateTime.to_jalali(dt)
                weekday_fingilish = {
                    'saturday': 'shanbe',
                    'sunday': 'yekshanbe',
                    'monday': 'doshanbe',
                    'tuesday': 'seshanbe',
                    'wednesday': 'chaharshanbe',
                    'thursday': 'panjshanbe',
                    'friday': 'jome',
                }
                day_en = jdt.strftime('%A').lower()
                day_fing = weekday_fingilish.get(day_en, day_en)
                jalali_str = jdt.strftime('%Y-%m-%d %H:%M:%S') + f' {day_fing}'
                return jalali_str
            except Exception:
                pass
        # Fallback: Gregorian date, English weekday
        weekday_fingilish = {
            'saturday': 'shanbe',
            'sunday': 'yekshanbe',
            'monday': 'doshanbe',
            'tuesday': 'seshanbe',
            'wednesday': 'chaharshanbe',
            'thursday': 'panjshanbe',
            'friday': 'jome',
        }
        day_en = dt.strftime('%A').lower()
        day_fing = weekday_fingilish.get(day_en, day_en)
        gregorian_str = dt.strftime('%Y-%m-%d %H:%M:%S') + f' {day_fing}'
        return gregorian_str

    def should_log_message(self, record):
        """Check if message should be logged (avoid spam)"""
        # Skip suppression for suppression messages themselves
        if hasattr(record, 'suppression_message') and record.suppression_message:
            return True
        
        # Safe message extraction
        try:
            msg = record.getMessage()
        except TypeError:
            msg = str(record.msg) if record.msg else ""
            
        msg_key = f"{record.levelname}:{msg}"
        current_time = datetime.now()
        
        if msg_key in self.repeated_messages:
            count, first_time = self.repeated_messages[msg_key]
            # Reset counter if more than suppression_interval has passed
            if (current_time - first_time).total_seconds() > self.suppression_interval:
                self.repeated_messages[msg_key] = (1, current_time)
                return True
            
            if count >= self.max_repeats:
                # Log suppression message only once
                if count == self.max_repeats:
                    suppression_msg = f"Suppressing repeated message: {msg}"
                    record.msg = suppression_msg
                    # Mark this as a suppression message to avoid recursive suppression
                    record.suppression_message = True
                    return True
                # Completely suppress after the suppression message
                return False
            
            self.repeated_messages[msg_key] = (count + 1, first_time)
        else:
            self.repeated_messages[msg_key] = (1, current_time)
        
        return True

    def colorize_message(self, msg):
        # اگر خروجی رنگی نیست، هیچ رنگی اعمال نکن
        if not self.enable_color:
            return msg
        # اعداد
        msg = RE_NUMBER.sub(lambda m: Fore.YELLOW + m.group(1) + Style.RESET_ALL, msg)
        # متدهای HTTP
        for method, color in METHOD_COLORS.items():
            msg = re.sub(rf'\b{method}\b', color + method + Style.RESET_ALL, msg)
        # رشته‌های کوتیشن‌دار
        msg = RE_QUOTE.sub(Fore.CYAN + r'\1' + Style.RESET_ALL, msg)
        # آی‌پی
        msg = RE_IP.sub(Fore.LIGHTBLUE_EX + r'\g<0>' + Style.RESET_ALL, msg)
        # URL
        msg = RE_URL.sub(Fore.LIGHTMAGENTA_EX + r'\g<0>' + Style.RESET_ALL, msg)
        # فایل
        msg = RE_FILE.sub(Fore.LIGHTCYAN_EX + r'\g<0>' + Style.RESET_ALL, msg)
        # کلیدواژه‌های مهم
        for word, color in KEYWORDS.items():
            msg = re.sub(rf'\b{word}\b', color + word + Style.RESET_ALL, msg, flags=re.IGNORECASE)
        return msg

    def pretty_json(self, obj):
        # نمایش زیبا و رنگی دیکشنری/JSON
        if not self.enable_color:
            return json.dumps(obj, indent=2, ensure_ascii=False)
        txt = json.dumps(obj, indent=2, ensure_ascii=False)
        txt = RE_QUOTE.sub(Fore.CYAN + r'\1' + Style.RESET_ALL, txt)
        txt = RE_NUMBER.sub(lambda m: Fore.YELLOW + m.group(1) + Style.RESET_ALL, txt)
        txt = RE_FILE.sub(Fore.LIGHTCYAN_EX + r'\g<0>' + Style.RESET_ALL, txt)
        return txt

    def format(self, record):
        # Check if message should be logged
        if not self.should_log_message(record):
            return ""
        
        # سطح لاگ
        level = record.levelname.upper()
        level_color = LEVEL_COLORS.get(level, '') if self.enable_color else ''
        record.levelname = level_color + level + (Style.RESET_ALL if self.enable_color else '')
        
        # پیام - Fix the string formatting issue
        try:
            msg = record.getMessage()
        except TypeError:
            # Handle case where message has format placeholders but no args
            msg = str(record.msg) if record.msg else ""
        
        # اگر پیام دیکشنری یا JSON باشد، زیبا نمایش بده
        if isinstance(record.msg, (dict, list)):
            msg = self.pretty_json(record.msg)
        else:
            msg = self.colorize_message(str(msg))
        
        # وضعیت HTTP
        msg = RE_STATUS_2XX_3XX.sub(Fore.GREEN + r'\1' + Style.RESET_ALL if self.enable_color else r'\1', msg)
        msg = RE_STATUS_4XX.sub(Fore.YELLOW + r'\g<0>' + Style.RESET_ALL if self.enable_color else r'\g<0>', msg)
        msg = RE_STATUS_5XX.sub(Fore.RED + r'\g<0>' + Style.RESET_ALL if self.enable_color else r'\g<0>', msg)
        
        # جداکننده و فاصله
        formatted = f"{self.formatTime(record)}  {record.levelname}  {msg}"
        separator = '\n' + (Fore.LIGHTBLACK_EX + '-'*80 + Style.RESET_ALL if self.enable_color else '-'*80) + '\n'
        return f"{formatted}{separator}" 