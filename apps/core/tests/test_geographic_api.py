import pytest
from django.urls import reverse
from rest_framework import status

from apps.core.models import AdministrativeUnit, Nationality, Province


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = response.json()
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


@pytest.mark.django_db
class TestProvinceAPI(APITestMixin):
    """Test cases for Province API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def provinces(self, db):
        """Create test provinces."""
        province1 = Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            decree="Nghị quyết 15/2019/NQ-CP",
            enabled=True,
        )
        province2 = Province.objects.create(
            code="02",
            name="Tỉnh Hà Giang",
            english_name="Ha Giang",
            level=Province.ProvinceLevel.PROVINCE,
            decree="Nghị định 24/2019/NĐ-CP",
            enabled=True,
        )
        province3 = Province.objects.create(
            code="03",
            name="Tỉnh Cao Bằng",
            english_name="Cao Bang",
            level=Province.ProvinceLevel.PROVINCE,
            decree="",
            enabled=False,
        )
        return province1, province2, province3

    def test_list_provinces(self, provinces):
        """Test listing provinces via API"""
        url = reverse("core:province-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 3

    def test_list_provinces_no_pagination(self, provinces):
        """Test that province list has no pagination"""
        url = reverse("core:province-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        # Response should be a list, not a paginated object
        assert isinstance(response_data, list)
        assert "count" not in (response_data if isinstance(response_data, dict) else {})

    def test_filter_provinces_by_enabled(self, provinces):
        """Test filtering provinces by enabled status"""
        url = reverse("core:province-list")
        response = self.client.get(url, {"enabled": "true"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2
        for item in response_data:
            assert item["enabled"] is True

    def test_filter_provinces_by_level(self, provinces):
        """Test filtering provinces by level"""
        url = reverse("core:province-list")
        response = self.client.get(url, {"level": Province.ProvinceLevel.CENTRAL_CITY})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["code"] == "01"

    def test_search_provinces(self, provinces):
        """Test searching provinces by name"""
        url = reverse("core:province-list")
        response = self.client.get(url, {"search": "Hà Nội"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == "Thành phố Hà Nội"

    def test_province_retrieve(self, provinces):
        """Test retrieving a single province"""
        province1 = provinces[0]
        url = reverse("core:province-detail", kwargs={"pk": province1.id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["code"] == "01"
        assert response_data["name"] == "Thành phố Hà Nội"
        assert response_data["english_name"] == "Hanoi"
        assert response_data["level"] == Province.ProvinceLevel.CENTRAL_CITY
        assert "level_display" in response_data


@pytest.mark.django_db
class TestAdministrativeUnitAPI(APITestMixin):
    """Test cases for AdministrativeUnit API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def admin_units(self, db):
        """Create test administrative units."""
        province1 = Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        province2 = Province.objects.create(
            code="48",
            name="Thành phố Đà Nẵng",
            english_name="Da Nang",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )

        unit1 = AdministrativeUnit.objects.create(
            code="001",
            name="Quận Ba Đình",
            parent_province=province1,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )
        unit2 = AdministrativeUnit.objects.create(
            code="002",
            name="Quận Hoàn Kiếm",
            parent_province=province1,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )
        unit3 = AdministrativeUnit.objects.create(
            code="00001",
            name="Phường Phúc Xá",
            parent_province=province1,
            level=AdministrativeUnit.UnitLevel.WARD,
            enabled=True,
        )
        unit4 = AdministrativeUnit.objects.create(
            code="490",
            name="Quận Hải Châu",
            parent_province=province2,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )
        unit5 = AdministrativeUnit.objects.create(
            code="003",
            name="Quận Đống Đa",
            parent_province=province1,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=False,
        )
        return {
            "province1": province1,
            "province2": province2,
            "unit1": unit1,
            "unit2": unit2,
            "unit3": unit3,
            "unit4": unit4,
            "unit5": unit5,
        }

    def test_list_administrative_units(self, admin_units):
        """Test listing administrative units via API"""
        url = reverse("core:administrative-unit-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert isinstance(response_data, list)
        assert len(response_data) == 5

    def test_list_administrative_units_no_pagination(self, admin_units):
        """Test that administrative unit list has no pagination"""
        url = reverse("core:administrative-unit-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert isinstance(response_data, list)
        assert "count" not in (response_data if isinstance(response_data, dict) else {})

    def test_filter_units_by_enabled(self, admin_units):
        """Test filtering administrative units by enabled status"""
        url = reverse("core:administrative-unit-list")
        response = self.client.get(url, {"enabled": "true"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 4
        for item in response_data:
            assert item["enabled"] is True

    def test_filter_units_by_province(self, admin_units):
        """Test filtering administrative units by parent province"""
        url = reverse("core:administrative-unit-list")
        response = self.client.get(url, {"parent_province": admin_units["province1"].id})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 4
        for item in response_data:
            assert item["province_code"] == "01"

    def test_filter_units_by_level(self, admin_units):
        """Test filtering administrative units by level"""
        url = reverse("core:administrative-unit-list")
        response = self.client.get(url, {"level": AdministrativeUnit.UnitLevel.DISTRICT})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 4

    def test_search_administrative_units(self, admin_units):
        """Test searching administrative units by name"""
        url = reverse("core:administrative-unit-list")
        response = self.client.get(url, {"search": "Ba Đình"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == "Quận Ba Đình"

    def test_unit_retrieve(self, admin_units):
        """Test retrieving a single administrative unit"""
        url = reverse("core:administrative-unit-detail", kwargs={"pk": admin_units["unit1"].id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["code"] == "001"
        assert response_data["name"] == "Quận Ba Đình"
        assert response_data["province_code"] == "01"
        assert response_data["province_name"] == "Thành phố Hà Nội"
        assert "level_display" in response_data

    def test_combined_filters(self, admin_units):
        """Test combining multiple filters"""
        url = reverse("core:administrative-unit-list")
        response = self.client.get(
            url,
            {
                "parent_province": admin_units["province1"].id,
                "level": AdministrativeUnit.UnitLevel.DISTRICT,
                "enabled": "true",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2
        for item in response_data:
            assert item["province_code"] == "01"
            assert item["level"] == AdministrativeUnit.UnitLevel.DISTRICT
            assert item["enabled"] is True


@pytest.mark.django_db
class TestNationalityAPI(APITestMixin):
    """Test cases for Nationality API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def nationalities(self, db):
        """Create test nationalities."""
        nationality1 = Nationality.objects.create(name="Vietnamese")
        nationality2 = Nationality.objects.create(name="American")
        nationality3 = Nationality.objects.create(name="Japanese")
        return nationality1, nationality2, nationality3

    def test_list_nationalities(self, nationalities):
        """Test listing nationalities via API"""
        url = reverse("core:nationality-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 3

    def test_list_nationalities_no_pagination(self, nationalities):
        """Test that nationality list has no pagination"""
        url = reverse("core:nationality-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert isinstance(response_data, list)
        assert "count" not in (response_data if isinstance(response_data, dict) else {})

    def test_search_nationalities(self, nationalities):
        """Test searching nationalities by name"""
        url = reverse("core:nationality-list")
        response = self.client.get(url, {"search": "Vietnamese"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == "Vietnamese"

    def test_filter_nationalities_by_name(self, nationalities):
        """Test filtering nationalities by name (case-insensitive)"""
        url = reverse("core:nationality-list")
        response = self.client.get(url, {"name": "american"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == "American"

    def test_nationality_retrieve(self, nationalities):
        """Test retrieving a single nationality"""
        nationality1 = nationalities[0]
        url = reverse("core:nationality-detail", kwargs={"pk": nationality1.id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["name"] == "Vietnamese"
        assert "id" in response_data
        assert "created_at" in response_data
        assert "updated_at" in response_data

    def test_nationality_ordering(self, nationalities):
        """Test that nationalities are ordered by name by default"""
        url = reverse("core:nationality-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        # Check ordering (alphabetical by name)
        names = [item["name"] for item in response_data]
        assert names == ["American", "Japanese", "Vietnamese"]
