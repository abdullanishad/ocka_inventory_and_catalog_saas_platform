# In accounts/msg91_client.py

import requests
import json
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

MSG91_SEND_OTP_URL = "https://api.msg91.com/api/v5/otp"
MSG91_VERIFY_OTP_URL = "https://api.msg91.com/api/v5/otp/verify"

def _get_auth_key():
    return settings.MSG91_AUTH_KEY

# --- NO LONGER NEEDED ---
# def _get_template_id():
#     return settings.MSG91_TEMPLATE_ID

def _format_phone(phone_number):
    """Ensures phone number is in 91XXXXXXXXXX format (without +)."""
    if not phone_number:
        return None
    phone_number = ''.join(filter(str.isdigit, phone_number))
    
    if len(phone_number) == 10:
        return f"91{phone_number}"
    elif len(phone_number) == 12 and phone_number.startswith("91"):
        return phone_number
    elif phone_number.startswith("+91") and len(phone_number) == 13:
        return phone_number[1:] # Remove the +
    
    return None # Invalid format for MSG91

def send_otp(phone_number):
    """Sends an OTP to the given phone number using MSG91 OTP Widget flow."""
    auth_key = _get_auth_key()
    formatted_phone = _format_phone(phone_number)

    if not auth_key or not formatted_phone:
        logger.error("MSG91_AUTH_KEY or phone number are missing.")
        return {"success": False, "error": "Invalid configuration or phone number."}

    # --- UPDATED PAYLOAD (NO TEMPLATE ID) ---
    # The widget name 'ocka' might be passed as 'flow_id' if needed,
    # but often just the authkey is enough to use the default flow.
    # Let's start with the simplest payload.
    payload = {
        "mobile": formatted_phone,
        "otp_length": 4  # Match your widget settings
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authkey": auth_key
    }

    try:
        response = requests.post(MSG91_SEND_OTP_URL, json=payload, headers=headers)
        response.raise_for_status() # Raise an error for bad responses (4xx, 5xx)
        
        data = response.json()
        if data.get("type") == "success":
            return {"success": True}
        else:
            return {"success": False, "error": data.get("message", "Failed to send OTP.")}
            
    except requests.exceptions.RequestException as e:
        logger.error(f"MSG9G1 send_otp error: {e}")
        try:
            return {"success": False, "error": e.response.json().get("message", "API Error")}
        except:
            return {"success": False, "error": str(e)}

def verify_otp(phone_number, otp_code):
    """Checks if the given OTP code is valid for the phone number."""
    auth_key = _get_auth_key()
    formatted_phone = _format_phone(phone_number)

    if not auth_key or not formatted_phone or not otp_code:
        return False

    params = {
        "mobile": formatted_phone,
        "otp": otp_code,
    }
    headers = {
        "accept": "application/json",
        "authkey": auth_key
    }

    try:
        response = requests.post(MSG91_VERIFY_OTP_URL, params=params, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        return data.get("type") == "success"
        
    except requests.exceptions.RequestException as e:
        logger.error(f"MSG91 verify_otp error: {e}")
        return False