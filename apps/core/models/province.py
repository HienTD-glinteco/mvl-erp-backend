from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel

ENABLED_PROVINCE_CODE_UNIQUE_CONSTRAINT_NAME = "unique_enabled_province_code"


@audit_logging_register
class Province(BaseModel):
    """Model representing a province/city (administrative level 1 in Vietnam)"""

    class ProvinceLevel(models.TextChoices):
        CENTRAL_CITY = "central_city", _("Central City")
        PROVINCE = "province", _("Province")

    code = models.CharField(
        max_length=50,
        verbose_name="Province code",
        help_text="Unique identifier code for the province",
    )
    name = models.CharField(
        max_length=200,
        verbose_name="Province name",
        help_text="Official name of the province",
    )
    english_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="English name",
        help_text="English name of the province",
    )
    level = models.CharField(
        max_length=50,
        choices=ProvinceLevel.choices,
        verbose_name="Administrative level",
        help_text="Administrative level of the province",
    )
    decree = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Decree",
        help_text="Legal decree reference",
    )
    enabled = models.BooleanField(
        default=True,
        verbose_name="Enabled",
        help_text="Whether this province is currently enabled",
    )

    class Meta:
        verbose_name = "Province"
        verbose_name_plural = "Provinces"
        db_table = "core_province"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(enabled=True),
                name=ENABLED_PROVINCE_CODE_UNIQUE_CONSTRAINT_NAME,
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"
