from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.files.models import FileModel
from libs.models import AutoCodeMixin, BaseModel

from ..constants import RelationType
from ..utils.validators import validate_national_id


@audit_logging_register
class EmployeeDependent(AutoCodeMixin, BaseModel):
    """Employee dependent model for tracking employee dependents.

    This model manages employee dependents such as children, spouse, parents, etc.
    Supports file attachments for supporting documents via the project's file upload flow.

    Attributes:
        code: Auto-generated unique code
        employee: Reference to the employee
        dependent_name: Full name of the dependent
        relationship: Type of relationship (child, spouse, parent, etc.)
        date_of_birth: Date of birth of the dependent
        citizen_id: National ID number (CMND/CCCD) - 9 or 12 digits
        effective_date: Start date for tax deduction applicability
        tax_code: Tax code (optional)
        attachment: File attachment (supporting document)
        note: Additional notes
        is_active: Whether this record is active (soft delete)
        created_by: User who created this record
    """

    AUDIT_LOG_TARGET = "hrm.Employee"
    CODE_PREFIX = "ED"

    code = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        null=True,
        blank=True,
        verbose_name="Code",
        help_text="Auto-generated unique code for this dependent",
    )
    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.PROTECT,
        related_name="dependents",
        verbose_name="Employee",
        help_text="Employee associated with this dependent",
    )

    dependent_name = models.CharField(
        max_length=255,
        verbose_name="Dependent name",
        help_text="Full name of the dependent",
    )

    relationship = models.CharField(
        max_length=20,
        choices=RelationType.choices,
        verbose_name="Relationship",
        help_text="Type of relationship to the employee",
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date of birth",
        help_text="Date of birth of the dependent",
    )

    citizen_id = models.CharField(
        max_length=12,
        blank=True,
        validators=[validate_national_id],
        verbose_name="Citizen ID",
        help_text="National ID (CMND/CCCD) - 9 or 12 digits",
    )

    effective_date = models.DateField(
        verbose_name="Effective date",
        help_text="Start date for tax deduction applicability",
    )

    tax_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Tax code",
        help_text="Tax identification number",
    )

    attachment = models.ForeignKey(
        FileModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_dependents",
        verbose_name="Attachment",
        help_text="Supporting document or file attachment",
    )

    note = models.TextField(
        blank=True,
        verbose_name="Note",
        help_text="Additional notes or information",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Is active",
        help_text="Whether this dependent record is active",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_dependents",
        verbose_name="Created by",
        help_text="User who created this record",
    )

    class Meta:
        verbose_name = _("Employee Dependent")
        verbose_name_plural = _("Employee Dependents")
        db_table = "hrm_employee_dependent"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["employee", "is_active"]),
            models.Index(fields=["citizen_id"]),
            models.Index(fields=["dependent_name"]),
            models.Index(fields=["relationship"]),
        ]

    def __str__(self):
        return f"{self.dependent_name} ({self.get_relationship_display()}) - {self.employee}"
