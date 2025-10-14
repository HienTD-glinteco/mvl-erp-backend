from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel

from ..constants import TEMP_CODE_PREFIX


@audit_logging_register
class Employee(AutoCodeMixin, BaseModel):
    """Employee model representing staff members in the organization.
    
    This model stores employee information and their position in the
    organizational hierarchy. Employee codes are automatically generated
    with the prefix "MV" (e.g., MV001, MV002).
    
    A User account is automatically created when an Employee is created,
    using the employee's username and email fields.
    
    Attributes:
        code: Auto-generated unique employee code with "MV" prefix
        fullname: Employee's full name
        username: Unique username (also used for User account creation)
        email: Unique email address (also used for User account creation)
        phone: Contact phone number
        branch: Employee's branch in the organization
        block: Employee's block within the branch
        department: Employee's department within the block
        user: Associated User account (auto-created, nullable)
        note: Additional notes or information about the employee
    """

    CODE_PREFIX = "MV"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    code = models.CharField(max_length=50, unique=True, verbose_name=_("Employee code"))
    fullname = models.CharField(max_length=200, verbose_name=_("Full name"))
    username = models.CharField(max_length=100, unique=True, verbose_name=_("Username"))
    email = models.EmailField(unique=True, verbose_name=_("Email"))
    phone = models.CharField(max_length=15, blank=True, verbose_name=_("Phone number"))
    branch = models.ForeignKey(
        "Branch",
        on_delete=models.CASCADE,
        related_name="employees",
        verbose_name=_("Branch"),
    )
    block = models.ForeignKey(
        "Block",
        on_delete=models.CASCADE,
        related_name="employees",
        verbose_name=_("Block"),
    )
    department = models.ForeignKey(
        "Department",
        on_delete=models.CASCADE,
        related_name="employees",
        verbose_name=_("Department"),
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="employee",
        verbose_name=_("User"),
    )
    note = models.TextField(blank=True, verbose_name=_("Note"))

    class Meta:
        verbose_name = _("Employee")
        verbose_name_plural = _("Employees")
        db_table = "hrm_employee"

    def __str__(self):
        return f"{self.code} - {self.fullname}"

    def clean(self):
        """Validate organizational hierarchy relationships.
        
        Ensures that:
        - Block belongs to the selected Branch
        - Department belongs to the selected Block
        - Department belongs to the selected Branch
        
        Raises:
            ValidationError: If any organizational hierarchy constraint is violated
        """
        super().clean()
        
        # Validate relationship between branch, block, and department
        if self.block and self.branch:
            if self.block.branch_id != self.branch_id:
                raise ValidationError({
                    "block": _("Block must belong to the selected branch.")
                })
        
        if self.department and self.block:
            if self.department.block_id != self.block_id:
                raise ValidationError({
                    "department": _("Department must belong to the selected block.")
                })
        
        if self.department and self.branch:
            if self.department.branch_id != self.branch_id:
                raise ValidationError({
                    "department": _("Department must belong to the selected branch.")
                })
