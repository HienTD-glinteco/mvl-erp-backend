from django.db import models
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.base_model_mixin import BaseModel

from ..constants import TEMP_CODE_PREFIX


@audit_logging_register
class Branch(BaseModel):
    """Company branch"""

    CODE_PREFIX = "CN"

    name = models.CharField(max_length=200, verbose_name=_("Branch name"))
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Branch code"))
    address = models.TextField(blank=True, verbose_name=_("Address"))
    phone = models.CharField(max_length=15, blank=True, verbose_name=_("Phone number"))
    email = models.EmailField(blank=True, verbose_name=_("Email"))
    province = models.ForeignKey(
        "core.Province",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="branches",
        verbose_name=_("Province"),
    )
    administrative_unit = models.ForeignKey(
        "core.AdministrativeUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="branches",
        verbose_name=_("Administrative unit"),
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Branch")
        verbose_name_plural = _("Branches")
        db_table = "hrm_branch"

    def save(self, *args, **kwargs):
        """Override save to set temporary code for new instances."""
        # Set temporary code for new instances that don't have a code yet
        # Use random string to avoid collisions, not all, but most of the time.
        if self._state.adding and not self.code:
            self.code = f"{TEMP_CODE_PREFIX}{get_random_string(20)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"


@audit_logging_register
class Block(BaseModel):
    """Business unit/block"""

    CODE_PREFIX = "KH"

    class BlockType(models.TextChoices):
        SUPPORT = "support", _("Support Block")
        BUSINESS = "business", _("Business Block")

    name = models.CharField(max_length=200, verbose_name=_("Block name"))
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Block code"))
    block_type = models.CharField(max_length=20, choices=BlockType.choices, verbose_name=_("Block type"))
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="blocks",
        verbose_name=_("Branch"),
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Block")
        verbose_name_plural = _("Blocks")
        db_table = "hrm_block"
        unique_together = [["code", "branch"]]

    def save(self, *args, **kwargs):
        """Override save to set temporary code for new instances."""
        # Set temporary code for new instances that don't have a code yet
        # Use random string to avoid collisions, not all, but most of the time.
        if self._state.adding and not self.code:
            self.code = f"{TEMP_CODE_PREFIX}{get_random_string(20)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name} ({self.get_block_type_display()})"


@audit_logging_register
class Department(BaseModel):
    """Department"""

    CODE_PREFIX = "PB"

    class DepartmentFunction(models.TextChoices):
        # Business function
        BUSINESS = "business", _("Business")

        # Support functions
        HR_ADMIN = "hr_admin", _("HR Administration")
        RECRUIT_TRAINING = "recruit_training", _("Recruitment & Training")
        MARKETING = "marketing", _("Marketing")
        BUSINESS_SECRETARY = "business_secretary", _("Business Secretary")
        ACCOUNTING = "accounting", _("Accounting")
        TRADING_FLOOR = "trading_floor", _("Trading Floor")
        PROJECT_PROMOTION = "project_promotion", _("Project Promotion")
        PROJECT_DEVELOPMENT = "project_development", _("Project Development")

    name = models.CharField(max_length=200, verbose_name=_("Department name"))
    code = models.CharField(max_length=50, verbose_name=_("Department code"))
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="departments", verbose_name=_("Branch"))
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name="departments", verbose_name=_("Block"))
    parent_department = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sub_departments",
        verbose_name=_("Parent department"),
    )
    # New fields according to SRS 2.3.2
    function = models.CharField(
        max_length=50,
        choices=DepartmentFunction.choices,
        default=DepartmentFunction.BUSINESS,  # Default to business function
        verbose_name=_("Department function"),
    )
    is_main_department = models.BooleanField(default=False, verbose_name=_("Is main department"))
    management_department = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_departments",
        verbose_name=_("Management department"),
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")
        db_table = "hrm_department"
        unique_together = [["code", "block"]]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def full_hierarchy(self):
        """Get full hierarchy path"""
        if self.parent_department:
            return f"{self.parent_department.full_hierarchy} > {self.name}"
        return self.name

    def clean(self):
        """Custom validation for Department"""
        from django.core.exceptions import ValidationError

        # Validate management department is in same block and function
        if self.management_department:
            if self.management_department.id == self.id:
                raise ValidationError({"management_department": _("Department cannot manage itself.")})
            if self.management_department.block != self.block:
                raise ValidationError({"management_department": _("Management department must be in the same block.")})
            if self.management_department.function != self.function:
                raise ValidationError(
                    {"management_department": _("Management department must have the same function.")}
                )

        # Validate only one main department per function
        if self.is_main_department:
            existing_main = Department.objects.filter(
                function=self.function, is_main_department=True, is_active=True
            ).exclude(id=self.id)

            if existing_main.exists():
                raise ValidationError(
                    {
                        "is_main_department": _("A main department already exists for function %(function)s.")
                        % {"function": self.get_function_display()}
                    }
                )

    def save(self, *args, **kwargs):
        # Set temporary code for new instances that don't have a code yet
        if self._state.adding and not self.code:
            self.code = f"{TEMP_CODE_PREFIX}{get_random_string(20)}"

        # Auto-set branch from block if not set
        if not self.branch and self.block and self.block.branch:
            self.branch = self.block.branch

        # Auto-set function based on block type if not set
        if not self.function and self.block:
            if self.block.block_type == Block.BlockType.BUSINESS:
                self.function = self.DepartmentFunction.BUSINESS

        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def get_function_choices_for_block_type(cls, block_type):
        """Get available function choices based on block type"""
        if block_type == Block.BlockType.BUSINESS:
            return [(cls.DepartmentFunction.BUSINESS, _("Business"))]
        elif block_type == Block.BlockType.SUPPORT:
            return [
                (cls.DepartmentFunction.HR_ADMIN, _("HR Administration")),
                (cls.DepartmentFunction.RECRUIT_TRAINING, _("Recruitment & Training")),
                (cls.DepartmentFunction.MARKETING, _("Marketing")),
                (cls.DepartmentFunction.BUSINESS_SECRETARY, _("Business Secretary")),
                (cls.DepartmentFunction.ACCOUNTING, _("Accounting")),
                (cls.DepartmentFunction.TRADING_FLOOR, _("Trading Floor")),
                (cls.DepartmentFunction.PROJECT_PROMOTION, _("Project Promotion")),
                (cls.DepartmentFunction.PROJECT_DEVELOPMENT, _("Project Development")),
            ]
        return []


@audit_logging_register
class Position(BaseModel):
    """Position/Role"""

    class PositionLevel(models.IntegerChoices):
        CEO = 1, _("Chief Executive Officer (CEO)")
        DIRECTOR = 2, _("Block Director")
        DEPUTY_DIRECTOR = 3, _("Deputy Block Director")
        MANAGER = 4, _("Department Manager")
        DEPUTY_MANAGER = 5, _("Deputy Department Manager")
        SUPERVISOR = 6, _("Supervisor")
        STAFF = 7, _("Staff")
        INTERN = 8, _("Intern")

    name = models.CharField(max_length=200, verbose_name=_("Position name"))
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Position code"))
    level = models.IntegerField(choices=PositionLevel.choices, verbose_name=_("Level"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Position")
        verbose_name_plural = _("Positions")
        db_table = "hrm_position"
        ordering = ["level", "name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


@audit_logging_register
class OrganizationChart(BaseModel):
    """Organization chart entry"""

    employee = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="organization_positions",
        verbose_name=_("Employee"),
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name="organization_positions",
        verbose_name=_("Position"),
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="organization_positions",
        verbose_name=_("Department"),
    )
    start_date = models.DateField(verbose_name=_("Start date"))
    end_date = models.DateField(null=True, blank=True, verbose_name=_("End date"))
    is_primary = models.BooleanField(default=True, verbose_name=_("Is primary position"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Organization Chart")
        verbose_name_plural = _("Organization Charts")
        db_table = "hrm_organization_chart"
        unique_together = [["employee", "position", "department", "start_date"]]

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.position.name} at {self.department.name}"

    def clean(self):
        """Validate organization chart entry"""
        from django.core.exceptions import ValidationError

        # Ensure employee can only have one primary position per department at a time
        if self.is_primary and self.is_active:
            existing = OrganizationChart.objects.filter(
                employee=self.employee,
                department=self.department,
                is_primary=True,
                is_active=True,
                end_date__isnull=True,
            ).exclude(id=self.id)

            if existing.exists():
                raise ValidationError(_("Employee can only have one primary position in a department at a time."))
