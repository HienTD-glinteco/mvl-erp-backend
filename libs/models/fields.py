from django.db import models

from libs.drf.validators import HTMLContentMaxLengthValidator
from libs.strings import clean_html


class SafeTextField(models.TextField):
    """
    Custom TextField that sanitizes unsafe HTML tags and attributes using clean_html before saving.
    Also validates actual text content length (without HTML tags) against max_length.
    """

    def clean(self, value, model_instance):
        value = super().clean(value, model_instance)
        # 1. Sanitize HTML
        cleaned = clean_html(value)

        # 2. Validate actual text length if max_length is set
        if self.max_length is not None:
            HTMLContentMaxLengthValidator(self.max_length)(cleaned)

        return cleaned
