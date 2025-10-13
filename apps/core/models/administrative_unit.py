from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel

ENABLED_ADMINISTRATIVE_UNIT_CODE_UNIQUE_CONSTRAINT_NAME = "unique_enabled_administrative_unit_code"


@audit_logging_register
class AdministrativeUnit(BaseModel):
    """Model representing an administrative unit (district, ward, commune, etc.)"""

    class UnitLevel(models.TextChoices):
        DISTRICT = "district", _("District")
        COMMUNE = "commune", _("Commune")
        WARD = "ward", _("Ward")
        TOWNSHIP = "township", _("Township")

    code = models.CharField(
        max_length=50,
        verbose_name=_("Unit code"),
        help_text=_("Unique identifier code for the administrative unit"),
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_("Unit name"),
        help_text=_("Official name of the administrative unit"),
    )
    english_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("English name"),
        help_text=_("English name of the administrative unit"),
    )
    parent_province = models.ForeignKey(
        "Province",
        on_delete=models.CASCADE,
        related_name="administrative_units",
        verbose_name=_("Parent province"),
        help_text=_("Province that this unit belongs to"),
    )
    level = models.CharField(
        max_length=50,
        choices=UnitLevel.choices,
        verbose_name=_("Administrative level"),
        help_text=_("Administrative level of the unit"),
    )
    enabled = models.BooleanField(
        default=True,
        verbose_name=_("Enabled"),
        help_text=_("Whether this administrative unit is currently enabled"),
    )

    class Meta:
        verbose_name = _("Administrative Unit")
        verbose_name_plural = _("Administrative Units")
        db_table = "core_administrative_unit"
        ordering = ["parent_province__code", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(enabled=True),
                name=ENABLED_ADMINISTRATIVE_UNIT_CODE_UNIQUE_CONSTRAINT_NAME,
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.name} ({self.parent_province.name})"
