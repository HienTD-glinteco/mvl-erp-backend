"""Shared pytest fixtures for core tests."""

import pytest
from django.contrib.auth import get_user_model

from apps.core.models import AdministrativeUnit, Nationality, Province

User = get_user_model()


@pytest.fixture
def province(db):
    """Create a test province."""
    return Province.objects.create(
        code="01",
        name="Thành phố Hà Nội",
        english_name="Hanoi",
        level=Province.ProvinceLevel.CENTRAL_CITY,
        enabled=True,
    )


@pytest.fixture
def province2(db):
    """Create a second test province."""
    return Province.objects.create(
        code="48",
        name="Thành phố Đà Nẵng",
        english_name="Da Nang",
        level=Province.ProvinceLevel.CENTRAL_CITY,
        enabled=True,
    )


@pytest.fixture
def admin_unit(db, province):
    """Create a test administrative unit."""
    return AdministrativeUnit.objects.create(
        code="001",
        name="Quận Ba Đình",
        parent_province=province,
        level=AdministrativeUnit.UnitLevel.DISTRICT,
        enabled=True,
    )


@pytest.fixture
def nationality(db):
    """Create a test nationality."""
    return Nationality.objects.create(name="Vietnamese")
