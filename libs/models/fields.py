from django.db import models

from libs.strings import clean_html


class SafeTextField(models.TextField):
    """
    Custom TextField that sanitizes unsafe HTML tags and attributes using clean_html before saving.
    """

    def clean(self, value, model_instance):
        value = super().clean(value, model_instance)
        return clean_html(value)
