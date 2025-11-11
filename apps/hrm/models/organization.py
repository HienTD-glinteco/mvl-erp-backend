from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel, SafeTextField

from ..constants import TEMP_CODE_PREFIX, DataScope


@audit_logging_register
class Branch(AutoCodeMixin, BaseModel):
    """Company branch"""

    CODE_PREFIX = "CN"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    name = models.CharField(max_length=200, verbose_name=_("Branch name"))
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Branch code"))
    address = SafeTextField(blank=True, verbose_name=_("Address"))
    phone = models.CharField(max_length=15, blank=True, verbose_name=_("Phone number"))
    email = models.EmailField(blank=True, verbose_name=_("Email"))
    province = models.ForeignKey(
        "core.Province",
        on_delete=models.PROTECT,
        related_name="branches",
        verbose_name=_("Province"),
    )
    administrative_unit = models.ForeignKey(
        "core.AdministrativeUnit",
        on_delete=models.PROTECT,
        related_name="branches",
        verbose_name=_("Administrative unit"),
    )
    description = SafeTextField(blank=True, verbose_name=_("Description"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Branch")
        verbose_name_plural = _("Branches")
        db_table = "hrm_branch"

    def __str__(self):
        return f"{self.code} - {self.name}"


@audit_logging_register
class Block(AutoCodeMixin, BaseModel):
    """Business unit/block"""

    CODE_PREFIX = "KH"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

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
    description = SafeTextField(blank=True, verbose_name=_("Description"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Block")
        verbose_name_plural = _("Blocks")
        db_table = "hrm_block"
        unique_together = [["code", "branch"]]

    def __str__(self):
        return f"{self.code} - {self.name} ({self.get_block_type_display()})"


@audit_logging_register
class Department(AutoCodeMixin, BaseModel):
    """Department"""

    CODE_PREFIX = "PB"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

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
    description = SafeTextField(blank=True, verbose_name=_("Description"))
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
        """Comprehensive validation for Department - SINGLE SOURCE OF TRUTH"""
        errors = {}

        self._validate_parent_department(errors)
        self._validate_management_department(errors)
        self._validate_function_by_block_type(errors)
        self._validate_business_block_function(errors)
        self._validate_support_block_function(errors)
        self._validate_main_department_uniqueness(errors)

        if errors:
            raise ValidationError(errors)

    def _validate_parent_department(self, errors):
        if self.parent_department and self.parent_department.block != self.block:
            errors["parent_department"] = _("Parent department must be in the same block as the child department.")

    def _validate_management_department(self, errors):
        if not self.management_department:
            return
        if self.management_department.id == self.id:
            errors["management_department"] = _("Department cannot manage itself.")
        elif self.management_department.block != self.block:
            errors["management_department"] = _("Management department must be in the same block.")
        elif self.management_department.function != self.function:
            errors["management_department"] = _("Management department must have the same function.")

    def _validate_function_by_block_type(self, errors):
        if not (self.block and self.function):
            return
        allowed_functions = [c[0] for c in self.get_function_choices_for_block_type(self.block.block_type)]
        if self.function not in allowed_functions:
            errors["function"] = _("This function is not compatible with block type %(block_type)s.") % {
                "block_type": self.block.get_block_type_display()
            }

    def _validate_business_block_function(self, errors):
        if self.block and self.block.block_type == Block.BlockType.BUSINESS:
            if self.function != self.DepartmentFunction.BUSINESS:
                errors["function"] = _("Business block can only have business function.")

    def _validate_support_block_function(self, errors):
        if self.block and self.block.block_type == Block.BlockType.SUPPORT:
            if self.function == self.DepartmentFunction.BUSINESS:
                errors["function"] = _("Support block cannot have business function.")

    def _validate_main_department_uniqueness(self, errors):
        if not self.is_main_department:
            return
        existing_main = Department.objects.filter(
            function=self.function, is_main_department=True, is_active=True
        ).exclude(id=self.id if self.id else None)
        if existing_main.exists():
            errors["is_main_department"] = _("A main department already exists for function %(function)s.") % {
                "function": self.get_function_display()
            }

    def save(self, *args, **kwargs):
        # Auto-set branch from block if not set
        if not self.branch and self.block and self.block.branch:
            self.branch = self.block.branch

        # Auto-set function based on block type if needed
        if self.block:
            # For business blocks, function must be business
            if self.block.block_type == Block.BlockType.BUSINESS:
                if not self.function or self.function != self.DepartmentFunction.BUSINESS:
                    self.function = self.DepartmentFunction.BUSINESS
            # For support blocks, if function is not set or is incorrectly set to business, default to HR_ADMIN
            elif self.block.block_type == Block.BlockType.SUPPORT:
                if not self.function or self.function == self.DepartmentFunction.BUSINESS:
                    self.function = self.DepartmentFunction.HR_ADMIN

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
class Position(AutoCodeMixin, BaseModel):
    """Position/Role"""

    CODE_PREFIX = "CV"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    name = models.CharField(max_length=200, verbose_name=_("Position name"))
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Position code"))
    data_scope = models.CharField(
        max_length=20,
        choices=DataScope.choices,
        default=DataScope.DEPARTMENT,
        verbose_name=_("Data scope"),
    )
    is_leadership = models.BooleanField(default=False, verbose_name=_("Leadership position"))
    description = SafeTextField(blank=True, verbose_name=_("Description"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Position")
        verbose_name_plural = _("Positions")
        db_table = "hrm_position"
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"
