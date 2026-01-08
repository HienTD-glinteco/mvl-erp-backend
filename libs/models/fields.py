from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import ngettext_lazy

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
            if cleaned:
                soup = BeautifulSoup(cleaned, "html.parser")
                text_content = soup.get_text(separator=" ", strip=True)
                text_length = len(text_content)
            else:
                text_length = 0

            if text_length > self.max_length:
                raise ValidationError(
                    ngettext_lazy(
                        "Ensure this value has at most %(limit_value)d character (it has %(show_value)d).",
                        "Ensure this value has at most %(limit_value)d characters (it has %(show_value)d).",
                        self.max_length,
                    ),
                    code="max_length",
                    params={"limit_value": self.max_length, "show_value": text_length},
                )

        return cleaned
