import jalali_date_with_ntp
import utime


#jalali_dt = jalali_date_with_ntp.get_jalali_datetime()
#print(jalali_date_with_ntp.format_jalali_datetime(jalali_dt))


def format_timestamp():
    try:
        jalali_dt = jalali_date_with_ntp.get_jalali_datetime()
        if jalali_dt:
            return jalali_date_with_ntp.format_jalali_datetime(jalali_dt)
    except Exception:
        pass
    t = utime.localtime()
    return f"{t[0]}/{t[1]:02d}/{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d} (local)"

print(format_timestamp())

    
    