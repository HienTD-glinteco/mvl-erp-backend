from .base import config

SMS_API_URL = config("SMS_API_URL", default="", cast=str)
SMS_SENDER_ID = config("SMS_SENDER_ID", default="", cast=str)
