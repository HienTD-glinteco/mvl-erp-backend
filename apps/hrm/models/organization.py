from django.db import models

from libs.base_model_mixin import BaseModel


class Branch(BaseModel):
    """Chi nhánh - Company branch"""

    name = models.CharField(max_length=200, verbose_name="Tên chi nhánh")
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã chi nhánh")
    address = models.TextField(blank=True, verbose_name="Địa chỉ")
    phone = models.CharField(max_length=15, blank=True, verbose_name="Số điện thoại")
    email = models.EmailField(blank=True, verbose_name="Email")
    is_active = models.BooleanField(default=True, verbose_name="Hoạt động")

    class Meta:
        verbose_name = "Chi nhánh"
        verbose_name_plural = "Chi nhánh"
        db_table = "hrm_branch"

    def __str__(self):
        return f"{self.code} - {self.name}"


class Block(BaseModel):
    """Khối - Business unit/block"""

    class BlockType(models.TextChoices):
        SUPPORT = "support", "Khối hỗ trợ"
        BUSINESS = "business", "Khối kinh doanh"

    name = models.CharField(max_length=200, verbose_name="Tên khối")
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã khối")
    block_type = models.CharField(max_length=20, choices=BlockType.choices, verbose_name="Loại khối")
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="blocks",
        verbose_name="Chi nhánh",
    )
    description = models.TextField(blank=True, verbose_name="Mô tả")
    is_active = models.BooleanField(default=True, verbose_name="Hoạt động")

    class Meta:
        verbose_name = "Khối"
        verbose_name_plural = "Khối"
        db_table = "hrm_block"
        unique_together = [["code", "branch"]]

    def __str__(self):
        return f"{self.code} - {self.name} ({self.get_block_type_display()})"


class Department(BaseModel):
    """Phòng ban - Department"""

    class DepartmentFunction(models.TextChoices):
        # Business function
        BUSINESS = "business", "Kinh doanh"

        # Support functions
        HR_ADMIN = "hr_admin", "Hành chính Nhân sự"
        RECRUIT_TRAINING = "recruit_training", "Tuyển dụng - Đào tạo"
        MARKETING = "marketing", "Marketing"
        BUSINESS_SECRETARY = "business_secretary", "Thư ký Kinh doanh"
        ACCOUNTING = "accounting", "Kế toán"
        TRADING_FLOOR = "trading_floor", "Sàn liên kết"
        PROJECT_PROMOTION = "project_promotion", "Xúc tiến Dự án"
        PROJECT_DEVELOPMENT = "project_development", "Phát triển Dự án"

    name = models.CharField(max_length=200, verbose_name="Tên phòng ban")
    code = models.CharField(max_length=50, verbose_name="Mã phòng ban")
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name="departments", verbose_name="Khối")
    parent_department = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sub_departments",
        verbose_name="Phòng ban cha",
    )
    # New fields according to SRS 2.3.2
    function = models.CharField(
        max_length=50,
        choices=DepartmentFunction.choices,
        default=DepartmentFunction.BUSINESS,  # Default to business function
        verbose_name="Chức năng phòng ban",
    )
    is_main_department = models.BooleanField(default=False, verbose_name="Phòng ban đầu mối")
    management_department = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_departments",
        verbose_name="Phòng ban quản lý",
    )
    description = models.TextField(blank=True, verbose_name="Mô tả")
    is_active = models.BooleanField(default=True, verbose_name="Hoạt động")

    class Meta:
        verbose_name = "Phòng ban"
        verbose_name_plural = "Phòng ban"
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
                raise ValidationError({"management_department": "Phòng ban không thể quản lý chính nó."})
            if self.management_department.block != self.block:
                raise ValidationError({"management_department": "Phòng ban quản lý phải thuộc cùng khối."})
            if self.management_department.function != self.function:
                raise ValidationError({"management_department": "Phòng ban quản lý phải có cùng chức năng."})

        # Validate only one main department per function
        if self.is_main_department:
            existing_main = Department.objects.filter(
                function=self.function, is_main_department=True, is_active=True
            ).exclude(id=self.id)

            if existing_main.exists():
                raise ValidationError(
                    {"is_main_department": f"Đã có phòng ban đầu mối cho chức năng {self.get_function_display()}."}
                )

    def save(self, *args, **kwargs):
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
            return [(cls.DepartmentFunction.BUSINESS, "Kinh doanh")]
        elif block_type == Block.BlockType.SUPPORT:
            return [
                (cls.DepartmentFunction.HR_ADMIN, "Hành chính Nhân sự"),
                (cls.DepartmentFunction.RECRUIT_TRAINING, "Tuyển dụng - Đào tạo"),
                (cls.DepartmentFunction.MARKETING, "Marketing"),
                (cls.DepartmentFunction.BUSINESS_SECRETARY, "Thư ký Kinh doanh"),
                (cls.DepartmentFunction.ACCOUNTING, "Kế toán"),
                (cls.DepartmentFunction.TRADING_FLOOR, "Sàn liên kết"),
                (cls.DepartmentFunction.PROJECT_PROMOTION, "Xúc tiến Dự án"),
                (cls.DepartmentFunction.PROJECT_DEVELOPMENT, "Phát triển Dự án"),
            ]
        return []


class Position(BaseModel):
    """Chức vụ - Position/Role"""

    class PositionLevel(models.IntegerChoices):
        CEO = 1, "Tổng Giám đốc (TGD)"
        DIRECTOR = 2, "Giám đốc khối"
        DEPUTY_DIRECTOR = 3, "Phó Giám đốc khối"
        MANAGER = 4, "Trưởng phòng"
        DEPUTY_MANAGER = 5, "Phó Trưởng phòng"
        SUPERVISOR = 6, "Giám sát"
        STAFF = 7, "Nhân viên"
        INTERN = 8, "Thực tập sinh"

    name = models.CharField(max_length=200, verbose_name="Tên chức vụ")
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã chức vụ")
    level = models.IntegerField(choices=PositionLevel.choices, verbose_name="Cấp bậc")
    description = models.TextField(blank=True, verbose_name="Mô tả")
    is_active = models.BooleanField(default=True, verbose_name="Hoạt động")

    class Meta:
        verbose_name = "Chức vụ"
        verbose_name_plural = "Chức vụ"
        db_table = "hrm_position"
        ordering = ["level", "name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class OrganizationChart(BaseModel):
    """Sơ đồ tổ chức - Organization chart entry"""

    employee = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="organization_positions",
        verbose_name="Nhân viên",
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name="organization_positions",
        verbose_name="Chức vụ",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="organization_positions",
        verbose_name="Phòng ban",
    )
    start_date = models.DateField(verbose_name="Ngày bắt đầu")
    end_date = models.DateField(null=True, blank=True, verbose_name="Ngày kết thúc")
    is_primary = models.BooleanField(default=True, verbose_name="Chức vụ chính")
    is_active = models.BooleanField(default=True, verbose_name="Hoạt động")

    class Meta:
        verbose_name = "Sơ đồ tổ chức"
        verbose_name_plural = "Sơ đồ tổ chức"
        db_table = "hrm_organization_chart"
        unique_together = [["employee", "position", "department", "start_date"]]

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.position.name} tại {self.department.name}"

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
                raise ValidationError(
                    "Nhân viên chỉ có thể có một chức vụ chính trong một phòng ban tại một thời điểm."
                )
