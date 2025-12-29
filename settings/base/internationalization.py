"""Internationalization settings.
https://docs.djangoproject.com/en/5.1/topics/i18n/
"""

import os

from ..base import BASE_DIR

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_L10N = True
USE_TZ = True


LOCALE_PATHS = [
    os.path.join(BASE_DIR, "locale"),  # add locale path for non-specific app
]

LANGUAGE = [("vi", "Vietnamese"), ("en", "English")]
