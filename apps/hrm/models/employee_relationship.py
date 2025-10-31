from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.files.models import FileModel
from libs.models import BaseModel

from ..constants import (
    HELP_TEXT_ADDRESS,
    HELP_TEXT_ATTACHMENT,
    HELP_TEXT_DATE_OF_BIRTH,
    HELP_TEXT_EMPLOYEE,
    HELP_TEXT_IS_ACTIVE,
    HELP_TEXT_NATIONAL_ID,
    HELP_TEXT_NOTE,
    HELP_TEXT_PHONE,
    HELP_TEXT_RELATION_TYPE,
    HELP_TEXT_RELATIVE_NAME,
    RelationType,
)
from ..utils.validators import validate_national_id, validate_phone


@audit_logging_register
class EmployeeRelationship(BaseModel):
    """Employee relationship/next-of-kin model.

    Stores information about employee relatives and next-of-kin contacts.
    Supports file attachments for supporting documents.

    Attributes:
        employee: Reference to the employee
        employee_code: Cached employee code for fast read (denormalized)
        employee_name: Cached employee name for fast read (denormalized)
        relative_name: Full name of the relative
        relation_type: Type of relationship (child, spouse, parent, etc.)
        date_of_birth: Date of birth of the relative
        national_id: National ID number (CMND/CCCD) - 9 or 12 digits
        address: Residential address
        phone: Contact phone number
        attachment: File attachment (supporting document)
        note: Additional notes
        is_active: Whether this record is active (soft delete)
        created_by: User who created this record
    """

    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.PROTECT,
        related_name="relationships",
        verbose_name=_("Employee"),
        help_text=HELP_TEXT_EMPLOYEE,
    )

    # Cached fields for performance
    employee_code = models.CharField(
        max_length=50,
        blank=True,
        editable=False,
        verbose_name=_("Employee code"),
        help_text=_("Cached employee code"),
    )

    employee_name = models.CharField(
        max_length=255,
        blank=True,
        editable=False,
        verbose_name=_("Employee name"),
        help_text=_("Cached employee name"),
    )

    relative_name = models.CharField(
        max_length=255,
        verbose_name=_("Relative name"),
        help_text=HELP_TEXT_RELATIVE_NAME,
    )

    relation_type = models.CharField(
        max_length=20,
        choices=RelationType.choices,
        verbose_name=_("Relation type"),
        help_text=HELP_TEXT_RELATION_TYPE,
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date of birth"),
        help_text=HELP_TEXT_DATE_OF_BIRTH,
    )

    national_id = models.CharField(
        max_length=12,
        blank=True,
        validators=[validate_national_id],
        verbose_name=_("National ID"),
        help_text=HELP_TEXT_NATIONAL_ID,
    )

    address = models.TextField(
        blank=True,
        verbose_name=_("Address"),
        help_text=HELP_TEXT_ADDRESS,
    )

    phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[validate_phone],
        verbose_name=_("Phone"),
        help_text=HELP_TEXT_PHONE,
    )

    attachment = models.ForeignKey(
        FileModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="relationship_attachments",
        verbose_name=_("Attachment"),
        help_text=HELP_TEXT_ATTACHMENT,
    )

    note = models.TextField(
        blank=True,
        verbose_name=_("Note"),
        help_text=HELP_TEXT_NOTE,
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is active"),
        help_text=HELP_TEXT_IS_ACTIVE,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_relationships",
        verbose_name=_("Created by"),
        help_text=_("User who created this record"),
    )

    class Meta:
        verbose_name = _("Employee Relationship")
        verbose_name_plural = _("Employee Relationships")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["employee", "is_active"]),
            models.Index(fields=["national_id"]),
        ]

    def __str__(self):
        return f"{self.relative_name} ({self.get_relation_type_display()}) - {self.employee}"

    def save(self, *args, **kwargs):
        """Override save to cache employee details"""
        if self.employee:
            self.employee_code = self.employee.code
            self.employee_name = self.employee.fullname
        super().save(*args, **kwargs)
