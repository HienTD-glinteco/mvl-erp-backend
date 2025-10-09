from django.test import TestCase

from apps.core.models import AdministrativeUnit, Province


class ProvinceModelTest(TestCase):
    """Test cases for Province model"""

    def setUp(self):
        self.province = Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            decree="Nghị quyết 15/2019/NQ-CP",
            enabled=True,
        )

    def test_province_creation(self):
        """Test creating a province"""
        self.assertEqual(self.province.code, "01")
        self.assertEqual(self.province.name, "Thành phố Hà Nội")
        self.assertEqual(self.province.english_name, "Hanoi")
        self.assertEqual(self.province.level, Province.ProvinceLevel.CENTRAL_CITY)
        self.assertEqual(self.province.decree, "Nghị quyết 15/2019/NQ-CP")
        self.assertTrue(self.province.enabled)

    def test_province_str_representation(self):
        """Test string representation of province"""
        expected = "01 - Thành phố Hà Nội"
        self.assertEqual(str(self.province), expected)

    def test_province_code_unique(self):
        """Test that province code is unique"""
        with self.assertRaises(Exception):
            Province.objects.create(
                code="01",
                name="Another City",
                english_name="Another",
                level=Province.ProvinceLevel.PROVINCE,
                enabled=True,
            )

    def test_province_level_choices(self):
        """Test province level choices"""
        province_city = Province.objects.create(
            code="02",
            name="Tỉnh Hà Giang",
            english_name="Ha Giang",
            level=Province.ProvinceLevel.PROVINCE,
            enabled=True,
        )
        self.assertEqual(province_city.level, Province.ProvinceLevel.PROVINCE)
        self.assertEqual(province_city.get_level_display(), "Province")

    def test_province_optional_fields(self):
        """Test that optional fields can be blank"""
        province = Province.objects.create(
            code="03",
            name="Tỉnh Cao Bằng",
            level=Province.ProvinceLevel.PROVINCE,
            enabled=True,
        )
        self.assertEqual(province.english_name, "")
        self.assertEqual(province.decree, "")

    def test_province_enabled_default(self):
        """Test that enabled defaults to True"""
        province = Province.objects.create(
            code="04", name="Test Province", level=Province.ProvinceLevel.PROVINCE
        )
        self.assertTrue(province.enabled)


class AdministrativeUnitModelTest(TestCase):
    """Test cases for AdministrativeUnit model"""

    def setUp(self):
        self.province = Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.unit = AdministrativeUnit.objects.create(
            code="001",
            name="Quận Ba Đình",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )

    def test_unit_creation(self):
        """Test creating an administrative unit"""
        self.assertEqual(self.unit.code, "001")
        self.assertEqual(self.unit.name, "Quận Ba Đình")
        self.assertEqual(self.unit.parent_province, self.province)
        self.assertEqual(self.unit.level, AdministrativeUnit.UnitLevel.DISTRICT)
        self.assertTrue(self.unit.enabled)

    def test_unit_str_representation(self):
        """Test string representation of administrative unit"""
        expected = "001 - Quận Ba Đình (Thành phố Hà Nội)"
        self.assertEqual(str(self.unit), expected)

    def test_unit_code_unique(self):
        """Test that unit code is unique"""
        with self.assertRaises(Exception):
            AdministrativeUnit.objects.create(
                code="001",
                name="Another District",
                parent_province=self.province,
                level=AdministrativeUnit.UnitLevel.DISTRICT,
                enabled=True,
            )

    def test_unit_level_choices(self):
        """Test administrative unit level choices"""
        ward = AdministrativeUnit.objects.create(
            code="00001",
            name="Phường Phúc Xá",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.WARD,
            enabled=True,
        )
        self.assertEqual(ward.level, AdministrativeUnit.UnitLevel.WARD)
        self.assertEqual(ward.get_level_display(), "Ward")

        commune = AdministrativeUnit.objects.create(
            code="00002",
            name="Xã Test",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.COMMUNE,
            enabled=True,
        )
        self.assertEqual(commune.level, AdministrativeUnit.UnitLevel.COMMUNE)
        self.assertEqual(commune.get_level_display(), "Commune")

        township = AdministrativeUnit.objects.create(
            code="00003",
            name="Thị trấn Test",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.TOWNSHIP,
            enabled=True,
        )
        self.assertEqual(township.level, AdministrativeUnit.UnitLevel.TOWNSHIP)
        self.assertEqual(township.get_level_display(), "Township")

    def test_unit_cascade_delete(self):
        """Test that units are deleted when parent province is deleted"""
        province2 = Province.objects.create(
            code="48",
            name="Thành phố Đà Nẵng",
            english_name="Da Nang",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        unit2 = AdministrativeUnit.objects.create(
            code="490",
            name="Quận Hải Châu",
            parent_province=province2,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )
        
        province_id = province2.id
        unit_id = unit2.id
        
        province2.delete()
        
        # Unit should be deleted
        self.assertFalse(AdministrativeUnit.objects.filter(id=unit_id).exists())

    def test_unit_related_name(self):
        """Test that units can be accessed from province"""
        unit2 = AdministrativeUnit.objects.create(
            code="002",
            name="Quận Hoàn Kiếm",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )
        
        units = self.province.administrative_units.all()
        self.assertEqual(units.count(), 2)
        self.assertIn(self.unit, units)
        self.assertIn(unit2, units)

    def test_unit_enabled_default(self):
        """Test that enabled defaults to True"""
        unit = AdministrativeUnit.objects.create(
            code="003",
            name="Test Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
        self.assertTrue(unit.enabled)
