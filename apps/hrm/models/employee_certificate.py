from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.files.models import FileModel
from libs.models import BaseModel

from ..constants import CERT_CODE_MAP, CertificateType


@audit_logging_register
class EmployeeCertificate(BaseModel):
    """Employee certificate model for tracking qualifications and certifications.

    This model manages certificates for employees including foreign language certificates,
    computer certificates, diplomas, broker training completion, and real estate practice licenses.
    The certificate_code is automatically derived from certificate_type using CERT_CODE_MAP.
    """

    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.CASCADE,
        related_name="certificates",
        verbose_name=_("Employee"),
        help_text=_("Employee who owns this certificate"),
    )
    certificate_type = models.CharField(
        max_length=50,
        choices=CertificateType.choices,
        verbose_name=_("Certificate type"),
        help_text=_("Type of certificate"),
    )
    certificate_code = models.CharField(
        max_length=20,
        editable=False,
        verbose_name=_("Certificate code"),
        help_text=_("Auto-generated certificate code based on certificate type"),
    )
    certificate_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Certificate name"),
        help_text=_("Specific name of the certificate or exam"),
    )
    issue_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Issue date"),
        help_text=_("Date when the certificate was issued"),
    )
    expiry_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Expiry date"),
        help_text=_("Date when the certificate expires (if applicable)"),
    )
    issuing_organization = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Issuing organization"),
        help_text=_("Organization that issued the certificate"),
    )
    file = models.ForeignKey(
        FileModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_certificates",
        verbose_name=_("Certificate file"),
        help_text=_("Uploaded certificate file"),
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes"),
        help_text=_("Additional notes about the certificate"),
    )

    class Meta:
        verbose_name = _("Employee certificate")
        verbose_name_plural = _("Employee certificates")
        db_table = "hrm_employee_certificate"
        ordering = ["certificate_code", "-issue_date"]
        indexes = [
            models.Index(fields=["employee", "certificate_type"]),
            models.Index(fields=["certificate_code"]),
            models.Index(fields=["issue_date"]),
            models.Index(fields=["expiry_date"]),
        ]

    def __str__(self):
        if self.certificate_name:
            return f"{self.certificate_code} - {self.certificate_name}"
        return f"{self.certificate_code} - {self.get_certificate_type_display()}"

    def save(self, *args, **kwargs):
        """Override save to auto-generate certificate_code from certificate_type."""
        if self.certificate_type:
            self.certificate_code = CERT_CODE_MAP.get(self.certificate_type, "CCK")
        super().save(*args, **kwargs)
