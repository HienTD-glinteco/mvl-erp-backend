"""Shared pytest fixtures for payroll tests."""

import random
import string

import pytest
from django.contrib.auth import get_user_model

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee

User = get_user_model()


def random_code(prefix="", length=6):
    """Generate a random code."""
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{suffix}"


@pytest.fixture
def province(db):
    """Create a test province."""
    return Province.objects.create(
        name=f"Test Province {random_code()}",
        code=random_code("P"),
    )


@pytest.fixture
def admin_unit(db, province):
    """Create a test administrative unit."""
    return AdministrativeUnit.objects.create(
        parent_province=province,
        name=f"Test Admin Unit {random_code()}",
        code=random_code("AU"),
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )


@pytest.fixture
def branch(db, province, admin_unit):
    """Create a test branch."""
    return Branch.objects.create(
        name=f"Test Branch {random_code()}",
        code=random_code("BR"),
        province=province,
        administrative_unit=admin_unit,
    )


@pytest.fixture
def block(db, branch):
    """Create a test block."""
    return Block.objects.create(
        name=f"Test Block {random_code()}",
        code=random_code("BL"),
        branch=branch,
        block_type=Block.BlockType.BUSINESS,
    )


@pytest.fixture
def department(db, branch, block):
    """Create a test department."""
    return Department.objects.create(
        name=f"Test Department {random_code()}",
        code=random_code("D"),
        branch=branch,
        block=block,
    )


@pytest.fixture
def employee(db, branch, block, department):
    """Create a test employee."""
    from datetime import date

    code = random_code()
    return Employee.objects.create(
        username=f"emp{code}",
        email=f"emp{code}@example.com",
        phone=f"09{random_code(length=8)}",
        citizen_id=f"{random_code(length=12)}",
        status="active",
        branch=branch,
        block=block,
        department=department,
        start_date=date.today(),
    )


@pytest.fixture
def user(db):
    """Create a test user."""
    username = f"user{random_code()}"
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="testpass123",
    )
