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


def generate_certificate_code(certificate: "EmployeeCertificate", force_save: bool = True) -> None:
    """Generate and assign a code for an EmployeeCertificate instance.

    This function composes a certificate code using the certificate's prefix
    (based on certificate_type) and the certificate's numeric id zero-padded
    to 9 digits, producing a value like "CCNN000000123".

    The prefix is determined by the certificate_type:
    - FOREIGN_LANGUAGE: CCNN
    - COMPUTER: CCTH
    - DIPLOMA: BTN
    - OTHER: CCK
    - BROKER_TRAINING_COMPLETION: CCHMG
    - REAL_ESTATE_PRACTICE_LICENSE: CCBDS

    Side effects:
    - sets `certificate.code` to the generated value
    - if `force_save` is True, persists only the `code` field with
      `certificate.save(update_fields=["code"])` (to avoid saving unrelated fields)

    Args:
        certificate: EmployeeCertificate instance which MUST have a non-None `id`
            and a valid `certificate_type` attribute.
        force_save: If True (default), call `certificate.save(update_fields=["code"])`
            after assigning the generated code. If False, the caller is
            responsible for saving the instance.

    Raises:
        ValueError: If the provided `certificate` has no `id` set.
    """
    if not hasattr(certificate, "id") or certificate.id is None:
        raise ValueError("EmployeeCertificate must have an id to generate code")

    prefix = certificate.get_code_prefix()
    instance_id = certificate.id
    subcode = str(instance_id).zfill(9)

    certificate.code = f"{prefix}{subcode}"

    if force_save:
        certificate.save(update_fields=["code"])


@audit_logging_register
class EmployeeCertificate(ColoredValueMixin, AutoCodeMixin, BaseModel):
    """Employee certificate model for tracking qualifications and certifications.

    This model manages certificates for employees including foreign language certificates,
    computer certificates, diplomas, broker training completion, and real estate practice licenses.
    The certificate_code is the actual certificate number issued by the certifying organization.
    """

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
        verbose_name=_("Code"),
        help_text="Auto-generated unique code for this certificate",
    )
    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.CASCADE,
        related_name="certificates",
        verbose_name=_("Employee"),
        help_text="Employee who owns this certificate",
    )
    certificate_type = models.CharField(
        max_length=50,
        choices=CertificateType.choices,
        verbose_name=_("Certificate type"),
        help_text="Type of certificate",
    )
    certificate_code = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Certificate code"),
        help_text="Certificate number or code issued by the certifying organization",
    )
    certificate_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Certificate name"),
        help_text="Specific name of the certificate or exam",
    )
    issue_date = models.DateField(
        verbose_name=_("Issue date"),
        help_text="Date when the certificate was issued",
    )
    effective_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Effective date"),
        help_text="Date when the certificate becomes effective",
    )
    expiry_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Expiry date"),
        help_text="Date when the certificate expires (if applicable)",
    )
    issuing_organization = models.CharField(
        max_length=100,
        verbose_name=_("Issuing organization"),
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
        verbose_name=_("Certificate file"),
        help_text="Uploaded certificate file",
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes"),
        help_text="Additional notes about the certificate",
    )
    training_specialization = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_("Training specialization"),
        help_text="Training specialization or major",
    )
    graduation_diploma = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_("Graduation diploma"),
        help_text="Graduation diploma or degree",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.VALID,
        verbose_name=_("Status"),
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

    def get_code_prefix(self) -> str:
        """Get the code prefix based on certificate type.

        Returns:
            str: The code prefix for auto-generated certificate code.
                - FOREIGN_LANGUAGE: CCNN
                - COMPUTER: CCTH
                - DIPLOMA: BTN
                - OTHER: CCK
                - BROKER_TRAINING_COMPLETION: CCHMG
                - REAL_ESTATE_PRACTICE_LICENSE: CCBDS
        """
        prefix_mapping: dict[str, str] = {
            CertificateType.FOREIGN_LANGUAGE: "CCNN",
            CertificateType.COMPUTER: "CCTH",
            CertificateType.DIPLOMA: "BTN",
            CertificateType.OTHER: "CCK",
            CertificateType.BROKER_TRAINING_COMPLETION: "CCHMG",
            CertificateType.REAL_ESTATE_PRACTICE_LICENSE: "CCBDS",
        }
        return prefix_mapping.get(self.certificate_type, prefix_mapping[CertificateType.OTHER])

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
