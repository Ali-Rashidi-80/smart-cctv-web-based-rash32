import asyncio, time, os, sys, gc, psutil, logging, requests, json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import jdatetime
from .melipayamak import Api

# Setup logger for this module
logger = logging.getLogger("sms")

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
                pass  # No specific attributes needed for SMS module
        system_state = TempSystemState()
    return system_state


def set_dependencies(log_func):
    """Set the dependencies from main server"""
    global insert_log_func
    insert_log_func = log_func


# SMS configuration for password recovery
SMS_USERNAME = os.getenv("SMS_USERNAME")
SMS_PASSWORD = os.getenv("SMS_PASSWORD")
SMS_SENDER_NUMBER = os.getenv("SMS_SENDER_NUMBER")




async def send_password_recovery_sms(phone: str, token: str, username: str):
    """Send password recovery SMS with attractive message"""
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
        
        # Create attractive and professional SMS message
        message = (
            f"🔐 (سیستم هوشمند دوربین امنیتی)\n\n"
            f"👋 سلام ({username}) عزیز\n"
            f"🎯 درخواست بازیابی رمز عبور ثبت شد\n"
            f"📅 {jdate} ({day_of_week})\n"
            f"🕐 {formatted_time}\n\n"
            f"🔢 کد بازیابی:\n"
            f"📱 {token}\n\n"
            f"⚠️ نکات مهم:\n"
            f"⏰ انقضا: 5 دقیقه\n"
            f"• اگر شما درخواست نکرده‌اید، نادیده بگیرید\n\n"
            f"🛡️ امنیت شما، اولویت ماست\n\n"
            f"🚀 پشتیبانی\n"
            f"📱 ادمین: @a_ra_80\n"
            f"📢 کانال تلگرامی: @writeyourway\n\n"
            f"🔢 لغو 11"
        )
        
        # Send SMS
        if SMS_USERNAME and SMS_PASSWORD and SMS_SENDER_NUMBER:
            try:
                # Convert phone number to local format
                sms_phone = '0' + phone[3:] if phone.startswith('+989') else phone
                
                # Initialize API
                api = Api(SMS_USERNAME, SMS_PASSWORD)
                sms = api.sms()
                
                # Send SMS
                response = sms.send(sms_phone, SMS_SENDER_NUMBER, message)
                
                if response and 'error' in str(response).lower():
                    logger.error(f"Failed to send SMS to {sms_phone}: {response}")
                    raise Exception(f"SMS sending failed: {response}")
                
                logger.info(f"SMS sent successfully to {sms_phone}")
            except Exception as sms_error:
                logger.error(f"Failed to send recovery SMS: {sms_error}")
                # Don't raise the exception to avoid breaking the flow
                # Just log the error and continue
        else:
            # Log SMS content for development
            logger.info(f"Password recovery token for {phone}: {token}")
            logger.info(f"SMS would be sent to {phone}: {message}")
            
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")
        raise
