import json
import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone
import sentry_sdk
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError

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
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        api_url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )

    try:
        with urlrequest.urlopen(req, timeout=10) as resp:
            status = getattr(resp, "status", 200)
            body = resp.read().decode("utf-8") if resp else ""
            if 200 <= status < 300:
                logger.info(
                    f"SMS OTP sent successfully to {phone_number}; status={status}"
                )
                return True
            logger.error(f"SMS provider returned non-2xx status={status}, body={body}")
            raise Exception(f"SMS provider error: status={status}")
    except (HTTPError, URLError) as e:
        logger.error(f"Failed to send SMS OTP to {phone_number}: {e}")
        sentry_sdk.capture_exception(e)
        raise self.retry(countdown=60, exc=e)
    except Exception as e:
        logger.error(f"Unexpected error sending SMS OTP to {phone_number}: {e}")
        sentry_sdk.capture_exception(e)
        raise self.retry(countdown=60, exc=e)
