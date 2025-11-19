import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


class ProvinceAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Province API endpoints"""

    def setUp(self):
        # Clear all existing data for clean tests
        Province.objects.all().delete()
        User.objects.all().delete()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create test provinces
        self.province1 = Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            decree="Nghị quyết 15/2019/NQ-CP",
            enabled=True,
        )
        self.province2 = Province.objects.create(
            code="02",
            name="Tỉnh Hà Giang",
            english_name="Ha Giang",
            level=Province.ProvinceLevel.PROVINCE,
            decree="Nghị định 24/2019/NĐ-CP",
            enabled=True,
        )
        self.province3 = Province.objects.create(
            code="03",
            name="Tỉnh Cao Bằng",
            english_name="Cao Bang",
            level=Province.ProvinceLevel.PROVINCE,
            decree="",
            enabled=False,
        )

    def test_list_provinces(self):
        """Test listing provinces via API"""
        url = reverse("core:province-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 3)

    def test_list_provinces_no_pagination(self):
        """Test that province list has no pagination"""
        url = reverse("core:province-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        # Response should be a list, not a paginated object
        self.assertIsInstance(response_data, list)
        self.assertNotIn("count", response_data if isinstance(response_data, dict) else {})

    def test_filter_provinces_by_enabled(self):
        """Test filtering provinces by enabled status"""
        url = reverse("core:province-list")
        response = self.client.get(url, {"enabled": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)
        for item in response_data:
            self.assertTrue(item["enabled"])

    def test_filter_provinces_by_level(self):
        """Test filtering provinces by level"""
        url = reverse("core:province-list")
        response = self.client.get(url, {"level": Province.ProvinceLevel.CENTRAL_CITY})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["code"], "01")

    def test_search_provinces(self):
        """Test searching provinces by name"""
        url = reverse("core:province-list")
        response = self.client.get(url, {"search": "Hà Nội"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], "Thành phố Hà Nội")

    def test_province_retrieve(self):
        """Test retrieving a single province"""
        url = reverse("core:province-detail", kwargs={"pk": self.province1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["code"], "01")
        self.assertEqual(response_data["name"], "Thành phố Hà Nội")
        self.assertEqual(response_data["english_name"], "Hanoi")
        self.assertEqual(response_data["level"], Province.ProvinceLevel.CENTRAL_CITY)
        self.assertIn("level_display", response_data)


class AdministrativeUnitAPITest(TransactionTestCase, APITestMixin):
    """Test cases for AdministrativeUnit API endpoints"""

    def setUp(self):
        # Clear all existing data for clean tests
        AdministrativeUnit.objects.all().delete()
        Province.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create test provinces
        self.province1 = Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.province2 = Province.objects.create(
            code="48",
            name="Thành phố Đà Nẵng",
            english_name="Da Nang",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )

        # Create test administrative units
        self.unit1 = AdministrativeUnit.objects.create(
            code="001",
            name="Quận Ba Đình",
            parent_province=self.province1,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )
        self.unit2 = AdministrativeUnit.objects.create(
            code="002",
            name="Quận Hoàn Kiếm",
            parent_province=self.province1,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )
        self.unit3 = AdministrativeUnit.objects.create(
            code="00001",
            name="Phường Phúc Xá",
            parent_province=self.province1,
            level=AdministrativeUnit.UnitLevel.WARD,
            enabled=True,
        )
        self.unit4 = AdministrativeUnit.objects.create(
            code="490",
            name="Quận Hải Châu",
            parent_province=self.province2,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )
        self.unit5 = AdministrativeUnit.objects.create(
            code="003",
            name="Quận Đống Đa",
            parent_province=self.province1,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=False,
        )

    def test_list_administrative_units(self):
        """Test listing administrative units via API"""
        url = reverse("core:administrative-unit-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        # Response should be a list (no pagination)
        self.assertIsInstance(response_data, list)
        self.assertEqual(len(response_data), 5)

    def test_list_administrative_units_no_pagination(self):
        """Test that administrative unit list has no pagination"""
        url = reverse("core:administrative-unit-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        # Response should be a list, not a paginated object
        self.assertIsInstance(response_data, list)
        self.assertNotIn("count", response_data if isinstance(response_data, dict) else {})

    def test_filter_units_by_enabled(self):
        """Test filtering administrative units by enabled status"""
        url = reverse("core:administrative-unit-list")
        response = self.client.get(url, {"enabled": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 4)
        for item in response_data:
            self.assertTrue(item["enabled"])

    def test_filter_units_by_province(self):
        """Test filtering administrative units by parent province"""
        url = reverse("core:administrative-unit-list")
        response = self.client.get(url, {"parent_province": self.province1.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 4)
        for item in response_data:
            self.assertEqual(item["province_code"], "01")

    def test_filter_units_by_level(self):
        """Test filtering administrative units by level"""
        url = reverse("core:administrative-unit-list")
        response = self.client.get(url, {"level": AdministrativeUnit.UnitLevel.DISTRICT})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 4)

    def test_search_administrative_units(self):
        """Test searching administrative units by name"""
        url = reverse("core:administrative-unit-list")
        response = self.client.get(url, {"search": "Ba Đình"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], "Quận Ba Đình")

    def test_unit_retrieve(self):
        """Test retrieving a single administrative unit"""
        url = reverse("core:administrative-unit-detail", kwargs={"pk": self.unit1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["code"], "001")
        self.assertEqual(response_data["name"], "Quận Ba Đình")
        self.assertEqual(response_data["province_code"], "01")
        self.assertEqual(response_data["province_name"], "Thành phố Hà Nội")
        self.assertIn("level_display", response_data)

    def test_combined_filters(self):
        """Test combining multiple filters"""
        url = reverse("core:administrative-unit-list")
        response = self.client.get(
            url,
            {"parent_province": self.province1.id, "level": AdministrativeUnit.UnitLevel.DISTRICT, "enabled": "true"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)
        for item in response_data:
            self.assertEqual(item["province_code"], "01")
            self.assertEqual(item["level"], AdministrativeUnit.UnitLevel.DISTRICT)
            self.assertTrue(item["enabled"])


class NationalityAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Nationality API endpoints"""

    def setUp(self):
        # Import here to avoid circular import
        from apps.core.models import Nationality

        # Clear all existing data for clean tests
        Nationality.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create test nationalities
        self.nationality1 = Nationality.objects.create(name="Vietnamese")
        self.nationality2 = Nationality.objects.create(name="American")
        self.nationality3 = Nationality.objects.create(name="Japanese")

    def test_list_nationalities(self):
        """Test listing nationalities via API"""
        url = reverse("core:nationality-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 3)

    def test_list_nationalities_no_pagination(self):
        """Test that nationality list has no pagination"""
        url = reverse("core:nationality-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        # Response should be a list, not a paginated object
        self.assertIsInstance(response_data, list)
        self.assertNotIn("count", response_data if isinstance(response_data, dict) else {})

    def test_search_nationalities(self):
        """Test searching nationalities by name"""
        url = reverse("core:nationality-list")
        response = self.client.get(url, {"search": "Vietnamese"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], "Vietnamese")

    def test_filter_nationalities_by_name(self):
        """Test filtering nationalities by name (case-insensitive)"""
        url = reverse("core:nationality-list")
        response = self.client.get(url, {"name": "american"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], "American")

    def test_nationality_retrieve(self):
        """Test retrieving a single nationality"""
        url = reverse("core:nationality-detail", kwargs={"pk": self.nationality1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["name"], "Vietnamese")
        self.assertIn("id", response_data)
        self.assertIn("created_at", response_data)
        self.assertIn("updated_at", response_data)

    def test_nationality_ordering(self):
        """Test that nationalities are ordered by name by default"""
        url = reverse("core:nationality-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        # Check ordering (alphabetical by name)
        names = [item["name"] for item in response_data]
        self.assertEqual(names, ["American", "Japanese", "Vietnamese"])
