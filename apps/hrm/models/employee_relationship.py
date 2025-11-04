from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.files.models import FileModel
from libs.models import AutoCodeMixin, BaseModel

from ..constants import RelationType
from ..utils.validators import validate_national_id, validate_phone


@audit_logging_register
class EmployeeRelationship(AutoCodeMixin, BaseModel):
    """Employee relationship/next-of-kin model.

    Stores information about employee relatives and next-of-kin contacts.
    Supports file attachments for supporting documents.

    Attributes:
        code: Auto-generated unique code
        employee: Reference to the employee
        employee_code: Cached employee code for fast read (denormalized)
        employee_name: Cached employee name for fast read (denormalized)
        relative_name: Full name of the relative
        relation_type: Type of relationship (child, spouse, parent, etc.)
        date_of_birth: Date of birth of the relative
        citizen_id: National ID number (CMND/CCCD) - 9 or 12 digits
        occupation: Occupation of the relative (optional)
        tax_code: Tax code (optional)
        address: Residential address
        phone: Contact phone number
        attachment: File attachment (supporting document)
        note: Additional notes
        is_active: Whether this record is active (soft delete)
        created_by: User who created this record
    """

    AUDIT_LOG_TARGET = "hrm.Employee"
    CODE_PREFIX = "ER"

    code = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        null=True,
        blank=True,
        verbose_name=_("Code"),
        help_text=_("Auto-generated unique code for this relationship"),
    )
    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.PROTECT,
        related_name="relationships",
        verbose_name=_("Employee"),
        help_text=_("Employee associated with this relationship"),
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
        help_text=_("Full name of the relative"),
    )

    relation_type = models.CharField(
        max_length=20,
        choices=RelationType.choices,
        verbose_name=_("Relation type"),
        help_text=_("Type of relationship to the employee"),
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date of birth"),
        help_text=_("Date of birth of the relative"),
    )

    citizen_id = models.CharField(
        max_length=12,
        blank=True,
        validators=[validate_national_id],
        verbose_name=_("Citizen ID"),
        help_text=_("National ID (CMND/CCCD) - 9 or 12 digits"),
    )

    occupation = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Occupation"),
        help_text=_("Occupation or job title of the relative"),
    )

    tax_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Tax code"),
        help_text=_("Tax identification number"),
    )

    address = models.TextField(
        blank=True,
        verbose_name=_("Address"),
        help_text=_("Residential address of the relative"),
    )

    phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[validate_phone],
        verbose_name=_("Phone"),
        help_text=_("Contact phone number"),
    )

    attachment = models.ForeignKey(
        FileModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="relationship_attachments",
        verbose_name=_("Attachment"),
        help_text=_("Supporting document or file attachment"),
    )

    note = models.TextField(
        blank=True,
        verbose_name=_("Note"),
        help_text=_("Additional notes or information"),
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is active"),
        help_text=_("Whether this relationship record is active"),
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
            models.Index(fields=["citizen_id"]),
        ]

    def __str__(self):
        return f"{self.relative_name} ({self.get_relation_type_display()}) - {self.employee}"

    def save(self, *args, **kwargs):
        """Override save to cache employee details"""
        if self.employee:
            self.employee_code = self.employee.code
            self.employee_name = self.employee.fullname
        super().save(*args, **kwargs)
