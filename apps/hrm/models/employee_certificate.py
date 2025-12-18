from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.files.models import FileModel
from libs import ColorVariant
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin

from ..constants import CertificateType


@audit_logging_register
class EmployeeCertificate(ColoredValueMixin, AutoCodeMixin, BaseModel):
    """Employee certificate model for tracking qualifications and certifications.

    This model manages certificates for employees including foreign language certificates,
    computer certificates, diplomas, broker training completion, and real estate practice licenses.
    The certificate_code is the actual certificate number issued by the certifying organization.
    """

    CODE_PREFIX = "EC"

    class Status(models.TextChoices):
        VALID = "Valid", _("Valid")
        NEAR_EXPIRY = "Near Expiry", _("Near Expiry")
        EXPIRED = "Expired", _("Expired")

    VARIANT_MAPPING = {
        "status": {
            Status.VALID: ColorVariant.GREEN,
            Status.NEAR_EXPIRY: ColorVariant.YELLOW,
            Status.EXPIRED: ColorVariant.RED,
        },
    }

    code = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        null=True,
        blank=True,
        verbose_name="Code",
        help_text="Auto-generated unique code for this certificate",
    )
    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.CASCADE,
        related_name="certificates",
        verbose_name="Employee",
        help_text="Employee who owns this certificate",
    )
    certificate_type = models.CharField(
        max_length=50,
        choices=CertificateType.choices,
        verbose_name="Certificate type",
        help_text="Type of certificate",
    )
    certificate_code = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Certificate code",
        help_text="Certificate number or code issued by the certifying organization",
    )
    certificate_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Certificate name",
        help_text="Specific name of the certificate or exam",
    )
    issue_date = models.DateField(
        verbose_name="Issue date",
        help_text="Date when the certificate was issued",
    )
    effective_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Effective date",
        help_text="Date when the certificate becomes effective",
    )
    expiry_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Expiry date",
        help_text="Date when the certificate expires (if applicable)",
    )
    issuing_organization = models.CharField(
        max_length=100,
        verbose_name="Issuing organization",
        help_text="Organization that issued the certificate",
        blank=True,
        null=True,
    )
    attachment = models.ForeignKey(
        FileModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_certificates",
        verbose_name="Certificate file",
        help_text="Uploaded certificate file",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notes",
        help_text="Additional notes about the certificate",
    )
    training_specialization = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Training specialization",
        help_text="Training specialization or major",
    )
    graduation_diploma = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Graduation diploma",
        help_text="Graduation diploma or degree",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.VALID,
        verbose_name="Status",
        help_text="Certificate status based on expiry date",
        db_index=True,
    )

    class Meta:
        verbose_name = _("Employee certificate")
        verbose_name_plural = _("Employee certificates")
        db_table = "hrm_employee_certificate"
        ordering = ["certificate_type", "-created_at"]
        indexes = [
            models.Index(fields=["employee", "certificate_type"]),
            models.Index(fields=["certificate_code"]),
            models.Index(fields=["issue_date"]),
            models.Index(fields=["effective_date"]),
            models.Index(fields=["expiry_date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        if self.certificate_name:
            if self.certificate_code:
                return f"{self.certificate_code} - {self.certificate_name}"
            return self.certificate_name
        if self.certificate_code:
            return f"{self.certificate_code} - {self.get_certificate_type_display()}"
        return self.get_certificate_type_display()

    @property
    def colored_status(self):
        """Get status with color variant"""
        return self.get_colored_value("status")

    def compute_status(self):
        """Compute certificate status based on expiry date.

        Rules:
        - If no expiry_date: status = VALID
        - If expiry_date exists:
            - If current_date > expiry_date: EXPIRED
            - If current_date <= expiry_date and time_diff <= threshold: NEAR_EXPIRY
            - If current_date <= expiry_date and time_diff > threshold: VALID

        Returns:
            str: The computed status value
        """
        if not self.expiry_date:
            return self.Status.VALID

        today = date.today()
        near_expiry_days = getattr(settings, "HRM_CERTIFICATE_NEAR_EXPIRY_DAYS", 30)

        if today > self.expiry_date:
            return self.Status.EXPIRED
        elif (self.expiry_date - today).days <= near_expiry_days:
            return self.Status.NEAR_EXPIRY
        else:
            return self.Status.VALID

    def update_status(self):
        """Update the status field based on current expiry date"""
        self.status = self.compute_status()

    def clean(self):
        """Validate model data."""
        super().clean()
        if self.effective_date and self.expiry_date:
            if self.effective_date >= self.expiry_date:
                raise ValidationError({"effective_date": _("Effective date must be less than expiry date.")})
        if self.certificate_type == CertificateType.REAL_ESTATE_PRACTICE_LICENSE and not self.expiry_date:
            raise ValidationError({"expiry_date": _("Expiry date is required for real estate practice licenses.")})

    def save(self, *args, **kwargs):
        """Override save to automatically update status and validate data."""
        self.clean()
        self.update_status()
        super().save(*args, **kwargs)
