"""
Role Data Scope Models

These models link a Role to specific organizational units (Branch, Block, Department).
They are used for fine-grained data access control at organizational unit levels.
"""

from django.db import models

from libs.models import BaseModel


class RoleBranchScope(BaseModel):
    """
    Links a Role to allowed Branches.
    Only applies when Role.data_scope_level = 'branch'
    """

    role = models.ForeignKey(
        "core.Role",
        on_delete=models.CASCADE,
        related_name="branch_scopes",
        verbose_name="Role",
    )
    branch = models.ForeignKey(
        "hrm.Branch",
        on_delete=models.CASCADE,
        related_name="role_scopes",
        verbose_name="Branch",
    )

    class Meta:
        verbose_name = "Role Branch Scope"
        verbose_name_plural = "Role Branch Scopes"
        db_table = "hrm_role_branch_scope"
        unique_together = [["role", "branch"]]

    def __str__(self):
        return f"{self.role.name} -> {self.branch.name}"


class RoleBlockScope(BaseModel):
    """
    Links a Role to allowed Blocks.
    Only applies when Role.data_scope_level = 'block'
    """

    role = models.ForeignKey(
        "core.Role",
        on_delete=models.CASCADE,
        related_name="block_scopes",
        verbose_name="Role",
    )
    block = models.ForeignKey(
        "hrm.Block",
        on_delete=models.CASCADE,
        related_name="role_scopes",
        verbose_name="Block",
    )

    class Meta:
        verbose_name = "Role Block Scope"
        verbose_name_plural = "Role Block Scopes"
        db_table = "hrm_role_block_scope"
        unique_together = [["role", "block"]]

    def __str__(self):
        return f"{self.role.name} -> {self.block.name}"


class RoleDepartmentScope(BaseModel):
    """
    Links a Role to allowed Departments.
    Only applies when Role.data_scope_level = 'department'
    """

    role = models.ForeignKey(
        "core.Role",
        on_delete=models.CASCADE,
        related_name="department_scopes",
        verbose_name="Role",
    )
    department = models.ForeignKey(
        "hrm.Department",
        on_delete=models.CASCADE,
        related_name="role_scopes",
        verbose_name="Department",
    )

    class Meta:
        verbose_name = "Role Department Scope"
        verbose_name_plural = "Role Department Scopes"
        db_table = "hrm_role_department_scope"
        unique_together = [["role", "department"]]

    def __str__(self):
        return f"{self.role.name} -> {self.department.name}"
