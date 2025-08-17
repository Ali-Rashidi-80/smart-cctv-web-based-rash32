import datetime


try:
    from persiantools.jdatetime import JalaliDateTime
    PERSIANTOOLS_AVAILABLE = True
except ImportError:
    PERSIANTOOLS_AVAILABLE = False



def get_jalali_now_str():
    if 'PERSIANTOOLS_AVAILABLE' in globals() and PERSIANTOOLS_AVAILABLE:
        try:
            return JalaliDateTime.now().strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


