from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class BankAccount(BaseModel):
    """Bank account model for employee banking information.

    Attributes:
        employee: The employee who owns this account
        bank: The bank where this account is held
        account_number: Bank account number
        account_name: Name registered on the account
        is_primary: Whether this is the primary account for the employee
    """

    employee = models.ForeignKey(
        "Employee",
        on_delete=models.CASCADE,
        related_name="bank_accounts",
        verbose_name=_("Employee"),
    )
    bank = models.ForeignKey(
        "Bank",
        on_delete=models.CASCADE,
        related_name="bank_accounts",
        verbose_name=_("Bank"),
    )
    account_number = models.CharField(max_length=20, verbose_name=_("Account number"))
    account_name = models.CharField(max_length=50, verbose_name=_("Account name"))
    is_primary = models.BooleanField(default=False, verbose_name=_("Is primary"))

    class Meta:
        verbose_name = _("Bank Account")
        verbose_name_plural = _("Bank Accounts")
        db_table = "hrm_bank_account"
        ordering = ["-is_primary", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee"],
                condition=models.Q(is_primary=True),
                name="unique_primary_bank_account_per_employee",
            )
        ]

    def __str__(self):
        return f"{self.employee.fullname} - {self.bank.name} - {self.account_number}"

    def clean(self):
        """Validate bank account business rules"""
        super().clean()

        # Check if setting as primary and another primary exists
        if self.is_primary:
            existing_primary = BankAccount.objects.filter(employee=self.employee, is_primary=True).exclude(pk=self.pk)
            if existing_primary.exists():
                raise ValidationError(
                    {"is_primary": _("Employee already has a primary bank account. Please unset it first.")}
                )

    def save(self, *args, **kwargs):
        """Save bank account with validation"""
        self.clean()
        super().save(*args, **kwargs)
