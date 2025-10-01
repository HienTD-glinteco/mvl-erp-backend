import logging

import requests
import sentry_sdk
from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_otp_sms_task(self, phone_number: str, otp_code: str):
    """
    Send OTP via third-party SMS provider by POSTing JSON to their API URL.
    API URL is configurable via settings.SMS_API_URL; uses a fake default if missing.
    """
    api_url = settings.SMS_API_URL

    payload = {
        "to": phone_number,
        "message": f"Ma OTP cua ban la: {otp_code}. Ma co hieu luc trong 3 phut.",
        "sender": settings.SMS_SENDER_ID,
        "timestamp": timezone.now().isoformat(),
    }

    try:
        response = requests.post(api_url, json=payload, timeout=10)
        if 200 <= response.status_code < 300:
            logger.info(f"SMS OTP sent successfully to {phone_number}; status={response.status_code}")
            return True
        logger.error(f"SMS provider returned non-2xx status={response.status_code}, body={response.text}")
        raise Exception(f"SMS provider error: status={response.status_code}")
    except requests.RequestException as e:
        logger.error(f"Failed to send SMS OTP to {phone_number}: {e}")
        sentry_sdk.capture_exception(e)
        raise self.retry(countdown=60, exc=e)
    except Exception as e:
        logger.error(f"Unexpected error sending SMS OTP to {phone_number}: {e}")
        sentry_sdk.capture_exception(e)
        raise self.retry(countdown=60, exc=e)
