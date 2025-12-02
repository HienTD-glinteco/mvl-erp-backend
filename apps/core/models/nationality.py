from django.db import models

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class Nationality(BaseModel):
    """Nationality model representing countries/nationalities."""

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nationality name",
    )

    class Meta:
        verbose_name = "Nationality"
        verbose_name_plural = "Nationalities"
        db_table = "core_nationality"
        ordering = ["name"]

    def __str__(self):
        return self.name
