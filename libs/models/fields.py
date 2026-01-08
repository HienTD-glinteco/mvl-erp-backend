from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError
from django.db import models

from libs.strings import clean_html


class SafeTextField(models.TextField):
    """
    Custom TextField that sanitizes unsafe HTML tags and attributes using clean_html before saving.
    Also validates actual text content length (without HTML tags) against max_length.
    """

    def clean(self, value, model_instance):
        value = super().clean(value, model_instance)
        cleaned = clean_html(value)

        # Validate actual text length if max_length is set
        if self.max_length is not None:
            soup = BeautifulSoup(cleaned, "html.parser")
            text_content = soup.get_text()
            if len(text_content) > self.max_length:
                raise ValidationError(
                    f"Ensure this value has at most {self.max_length} characters (it has {len(text_content)})."
                )

        return cleaned
