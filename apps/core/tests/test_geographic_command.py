import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.core.models import AdministrativeUnit, Province


class ImportAdministrativeDataCommandTest(TestCase):
    """Test cases for import_administrative_data management command"""

    def setUp(self):
        # Clear all data
        AdministrativeUnit.objects.all().delete()
        Province.objects.all().delete()

    def create_province_csv(self, content):
        """Helper to create a temporary province CSV file"""
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        return path

    def create_unit_csv(self, content):
        """Helper to create a temporary unit CSV file"""
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        return path

    def test_import_provinces_success(self):
        """Test importing provinces from CSV"""
        csv_content = """code,name,english_name,level,decree
01,Thành phố Hà Nội,Hanoi,Thành phố Trung ương,Nghị quyết 15/2019/NQ-CP
02,Tỉnh Hà Giang,Ha Giang,Tỉnh,Nghị định 24/2019/NĐ-CP
48,Thành phố Đà Nẵng,Da Nang,Thành phố Trung ương,Nghị quyết 120/2019/NQ-CP"""

        csv_path = self.create_province_csv(csv_content)

        try:
            out = StringIO()
            call_command("import_administrative_data", "--type=province", f"--file={csv_path}", stdout=out)

            # Check that provinces were created
            self.assertEqual(Province.objects.count(), 3)

            # Check province 1
            province1 = Province.objects.get(code="01")
            self.assertEqual(province1.name, "Thành phố Hà Nội")
            self.assertEqual(province1.english_name, "Hanoi")
            self.assertEqual(province1.level, Province.ProvinceLevel.CENTRAL_CITY)
            self.assertEqual(province1.decree, "Nghị quyết 15/2019/NQ-CP")
            self.assertTrue(province1.enabled)

            # Check province 2
            province2 = Province.objects.get(code="02")
            self.assertEqual(province2.level, Province.ProvinceLevel.PROVINCE)

            # Check output
            output = out.getvalue()
            self.assertIn("Created province:", output)
            self.assertIn("Thành phố Hà Nội", output)
            self.assertIn("Tỉnh Hà Giang", output)
            self.assertIn("Thành phố Đà Nẵng", output)
            self.assertIn("3 created", output)

        finally:
            os.unlink(csv_path)

    def test_import_provinces_update_existing(self):
        """Test updating existing provinces with changed data"""
        # Create initial province
        Province.objects.create(
            code="01",
            name="Old Name",
            english_name="Old English",
            level=Province.ProvinceLevel.PROVINCE,
            decree="Old Decree",
            enabled=True,
        )

        csv_content = """code,name,english_name,level,decree
01,Thành phố Hà Nội,Hanoi,Thành phố Trung ương,Nghị quyết 15/2019/NQ-CP"""

        csv_path = self.create_province_csv(csv_content)

        try:
            out = StringIO()
            call_command("import_administrative_data", "--type=province", f"--file={csv_path}", stdout=out)

            # Should still have 1 province (updated in place)
            self.assertEqual(Province.objects.count(), 2)
            self.assertEqual(Province.objects.filter(enabled=True).count(), 1)

            # Check updated province
            province = Province.objects.filter(code="01", enabled=True).first()
            self.assertEqual(province.name, "Thành phố Hà Nội")
            self.assertEqual(province.english_name, "Hanoi")
            self.assertEqual(province.level, Province.ProvinceLevel.CENTRAL_CITY)

            # Check output
            output = out.getvalue()
            self.assertIn("Updated province:", output)
            self.assertIn("Thành phố Hà Nội", output)
            self.assertIn("1 updated", output)
            self.assertIn("1 disabled", output)

        finally:
            os.unlink(csv_path)

    def test_import_provinces_no_changes(self):
        """Test importing provinces with no changes"""
        # Create province
        Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            decree="Nghị quyết 15/2019/NQ-CP",
            enabled=True,
        )

        csv_content = """code,name,english_name,level,decree
01,Thành phố Hà Nội,Hanoi,Thành phố Trung ương,Nghị quyết 15/2019/NQ-CP"""

        csv_path = self.create_province_csv(csv_content)

        try:
            out = StringIO()
            call_command("import_administrative_data", "--type=province", f"--file={csv_path}", stdout=out)

            # Should still have 1 province ENABLED
            self.assertEqual(Province.objects.count(), 1)
            self.assertEqual(Province.objects.filter(code="01", enabled=True).count(), 1)

            # Check output
            output = out.getvalue()
            self.assertIn("Province import summary:", output)
            self.assertIn("0 created", output)
            self.assertIn("0 disabled", output)
            self.assertIn("0 updated", output)

        finally:
            os.unlink(csv_path)

    def test_import_units_success(self):
        """Test importing administrative units from CSV"""
        # Create parent province first
        Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )

        csv_content = """code,name,parent_province_code,level
001,Quận Ba Đình,01,Quận
002,Quận Hoàn Kiếm,01,Quận
00001,Phường Phúc Xá,01,Phường"""

        csv_path = self.create_unit_csv(csv_content)

        try:
            out = StringIO()
            call_command("import_administrative_data", "--type=unit", f"--file={csv_path}", stdout=out)

            # Check that units were created
            self.assertEqual(AdministrativeUnit.objects.count(), 3)

            # Check district
            unit1 = AdministrativeUnit.objects.get(code="001")
            self.assertEqual(unit1.name, "Quận Ba Đình")
            self.assertEqual(unit1.parent_province.code, "01")
            self.assertEqual(unit1.level, AdministrativeUnit.UnitLevel.DISTRICT)
            self.assertTrue(unit1.enabled)

            # Check ward
            unit3 = AdministrativeUnit.objects.get(code="00001")
            self.assertEqual(unit3.level, AdministrativeUnit.UnitLevel.WARD)

            # Check output
            output = out.getvalue()
            self.assertIn("Created unit:", output)
            self.assertIn("Quận Ba Đình", output)
            self.assertIn("Quận Hoàn Kiếm", output)
            self.assertIn("Phường Phúc Xá", output)
            self.assertIn("3 created", output)

        finally:
            os.unlink(csv_path)

    def test_import_units_missing_province(self):
        """Test importing units with missing parent province"""
        csv_content = """code,name,parent_province_code,level
001,Quận Ba Đình,99,Quận"""

        csv_path = self.create_unit_csv(csv_content)

        try:
            out = StringIO()
            call_command("import_administrative_data", "--type=unit", f"--file={csv_path}", stdout=out)

            # No units should be created
            self.assertEqual(AdministrativeUnit.objects.count(), 0)

            # Check output
            output = out.getvalue()
            self.assertIn("Parent province not found", output)
            self.assertIn("1 skipped", output)

        finally:
            os.unlink(csv_path)

    def test_import_units_update_existing(self):
        """Test updating existing units with changed data"""
        # Create parent province
        province = Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )

        # Create initial unit
        AdministrativeUnit.objects.create(
            code="001",
            name="Old Name",
            parent_province=province,
            level=AdministrativeUnit.UnitLevel.COMMUNE,
            enabled=True,
        )

        csv_content = """code,name,parent_province_code,level
001,Quận Ba Đình,01,Quận"""

        csv_path = self.create_unit_csv(csv_content)

        try:
            out = StringIO()
            call_command("import_administrative_data", "--type=unit", f"--file={csv_path}", stdout=out)

            # Should still have 1 unit (updated in place)
            self.assertEqual(AdministrativeUnit.objects.count(), 2)
            self.assertEqual(AdministrativeUnit.objects.filter(enabled=True).count(), 1)

            # Check updated unit
            unit = AdministrativeUnit.objects.filter(code="001", enabled=True).first()
            self.assertEqual(unit.name, "Quận Ba Đình")
            self.assertEqual(unit.level, AdministrativeUnit.UnitLevel.DISTRICT)

            # Check output
            output = out.getvalue()
            self.assertIn("Updated unit:", output)
            self.assertIn("Quận Ba Đình", output)

        finally:
            os.unlink(csv_path)

    def test_import_dry_run_mode(self):
        """Test dry-run mode doesn't save data"""
        csv_content = """code,name,english_name,level,decree
01,Thành phố Hà Nội,Hanoi,Thành phố Trung ương,Nghị quyết 15/2019/NQ-CP"""

        csv_path = self.create_province_csv(csv_content)

        try:
            out = StringIO()
            call_command(
                "import_administrative_data", "--type=province", f"--file={csv_path}", "--dry-run", stdout=out
            )

            # No provinces should be created in dry-run mode
            self.assertEqual(Province.objects.count(), 0)

            # Check output
            output = out.getvalue()
            self.assertIn("DRY-RUN mode", output)
            self.assertIn("Created province:", output)  # Still shows what would be created
            self.assertIn("Thành phố Hà Nội", output)

        finally:
            os.unlink(csv_path)

    def test_import_missing_required_fields(self):
        """Test importing with missing required fields"""
        csv_content = """code,name,english_name,level,decree
,Thành phố Hà Nội,Hanoi,Thành phố Trung ương,Nghị quyết 15/2019/NQ-CP
02,,Ha Giang,Tỉnh,"""

        csv_path = self.create_province_csv(csv_content)

        try:
            out = StringIO()
            call_command("import_administrative_data", "--type=province", f"--file={csv_path}", stdout=out)

            # No provinces should be created
            self.assertEqual(Province.objects.count(), 0)

            # Check output
            output = out.getvalue()
            self.assertIn("Skipping row with missing code or name", output)

        finally:
            os.unlink(csv_path)
