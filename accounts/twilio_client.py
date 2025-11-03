# Create this new file: accounts/twilio_client.py

from django.conf import settings
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)

def _get_twilio_client():
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    if not account_sid or not auth_token:
        logger.error("Twilio credentials not set in environment.")
        return None
    return Client(account_sid, auth_token)

def _get_service_sid():
    return settings.TWILIO_VERIFY_SERVICE_SID

def _format_phone(phone_number):
    """Ensures phone number is in E.164 format (e.g., +919020602744)."""
    if not phone_number:
        return None
    # Remove non-numeric characters
    phone_number = ''.join(filter(str.isdigit, phone_number))
    # Add +91 prefix if it's 10 digits (assuming Indian numbers)
    if len(phone_number) == 10:
        return f"+91{phone_number}"
    elif len(phone_number) == 12 and phone_number.startswith("91"):
        return f"+{phone_number}"
    elif phone_number.startswith("+"):
        return phone_number
    return None # Invalid format

def send_otp(phone_number):
    """Sends an OTP to the given phone number."""
    client = _get_twilio_client()
    service_sid = _get_service_sid()
    formatted_phone = _format_phone(phone_number)
    
    if not client or not service_sid or not formatted_phone:
        return {"success": False, "error": "Invalid configuration or phone number."}

    try:
        verification = client.verify.v2.services(service_sid) \
            .verifications \
            .create(to=formatted_phone, channel='sms')
        
        if verification.status == 'pending':
            return {"success": True}
        else:
            return {"success": False, "error": verification.status}
            
    except Exception as e:
        logger.error(f"Twilio send_otp error: {e}")
        return {"success": False, "error": str(e)}

def verify_otp(phone_number, otp_code):
    """Checks if the given OTP code is valid for the phone number."""
    client = _get_twilio_client()
    service_sid = _get_service_sid()
    formatted_phone = _format_phone(phone_number)

    if not client or not service_sid or not formatted_phone or not otp_code:
        return False

    try:
        check = client.verify.v2.services(service_sid) \
            .verification_checks \
            .create(to=formatted_phone, code=otp_code)
        
        return check.status == 'approved'
        
    except Exception as e:
        logger.error(f"Twilio verify_otp error: {e}")
        return False