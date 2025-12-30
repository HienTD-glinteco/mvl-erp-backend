# TODO: fix this import command, after clarifying how we should update/disable existing records

import polars as pl
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import AdministrativeUnit, Province


class Command(BaseCommand):
    """Management command to import Province and AdministrativeUnit data from CSV or Excel files"""

    help = "Import administrative data (provinces and units) from CSV or Excel files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            type=str,
            required=True,
            choices=["province", "unit"],
            help="Type of data to import: 'province' or 'unit'",
        )
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="Path to the CSV or Excel file to import",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run in dry-run mode without saving to database",
        )

    def handle(self, *args, **options):
        data_type = options["type"]
        file_path = options["file"]
        dry_run = options.get("dry_run", False)

        self.stdout.write(self.style.SUCCESS("Starting import of {} data from {}".format(data_type, file_path)))

        if dry_run:
            self.stdout.write(self.style.WARNING("Running in DRY-RUN mode - no data will be saved"))

        try:
            # Read file using polars (supports both CSV and Excel), make sure all the columns are read as string.
            if file_path.endswith((".xlsx", ".xls")):
                df = pl.read_excel(file_path, read_options={"n_rows": 0})  # Read header only to infer schema
                schema_overrides = dict.fromkeys(df.columns, pl.String)
                df = pl.read_excel(file_path, schema_overrides=schema_overrides)
            else:
                df = pl.read_csv(file_path, n_rows=0)  # Read header only to infer schema
                schema_overrides = dict.fromkeys(df.columns, pl.String)
                df = pl.read_csv(file_path, schema_overrides=schema_overrides)

            self.stdout.write("Loaded {} rows from file".format(len(df)))

            if data_type == "province":
                self._import_provinces(df, dry_run)
            else:
                self._import_units(df, dry_run)

            self.stdout.write(self.style.SUCCESS("Import completed successfully"))

        except Exception as e:
            self.stdout.write(self.style.ERROR("Error during import: {}".format(str(e))))
            raise

    def _import_provinces(self, df, dry_run):
        """Import province data from dataframe"""
        created_count = 0
        updated_count = 0
        disabled_count = 0

        with transaction.atomic():
            for row in df.iter_rows(named=True):
                # Support both Vietnamese and English column names
                code = str(row.get("Mã") or row.get("code") or "").strip()
                name = str(row.get("Tên") or row.get("name") or "").strip()
                english_name = str(row.get("Tên Tiếng Anh") or row.get("english_name") or "").strip()
                level = str(row.get("Cấp") or row.get("level") or "").strip()
                decree = str(row.get("Nghị định") or row.get("decree") or "").strip()

                if not code or not name:
                    self.stdout.write(self.style.WARNING("Skipping row with missing code or name: {}".format(row)))
                    continue

                # Map level to choices
                level_mapping = {
                    "Thành phố Trung ương": Province.ProvinceLevel.CENTRAL_CITY,
                    "Tỉnh": Province.ProvinceLevel.PROVINCE,
                }
                mapped_level = level_mapping.get(level, Province.ProvinceLevel.PROVINCE)
                current_information = "|".join([name, english_name, mapped_level, decree])

                try:
                    existing = Province.objects.filter(code=code, enabled=True).first()

                    if existing:
                        # Check if data has changed
                        existing_information = (
                            f"{existing.name}|{existing.english_name}|{existing.level}|{existing.decree}"
                        )
                        existing_information = "|".join(
                            [existing.name, existing.english_name, existing.level, existing.decree]
                        )
                        # Compare old and new record information, without code field
                        if existing_information != current_information:
                            # Disable old record
                            existing.enabled = False
                            if not dry_run:
                                existing.save()
                            disabled_count += 1

                            # Create new record
                            new_province = Province(
                                code=code,
                                name=name,
                                english_name=english_name,
                                level=mapped_level,
                                decree=decree,
                                enabled=True,
                            )
                            if not dry_run:
                                new_province.save()
                            updated_count += 1
                            self.stdout.write("Updated province: {} - {}".format(code, name))
                        else:
                            self.stdout.write("Province unchanged: {} - {}".format(code, name))
                    else:
                        # Create new record
                        province = Province(
                            code=code,
                            name=name,
                            english_name=english_name,
                            level=mapped_level,
                            decree=decree,
                            enabled=True,
                        )
                        if not dry_run:
                            province.save()
                        created_count += 1
                        self.stdout.write("Created province: {} - {}".format(code, name))

                except Exception as e:
                    self.stdout.write(self.style.ERROR("Error processing row {}: {}".format(row, str(e))))

            if dry_run:
                # Rollback transaction in dry-run mode
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                "Province import summary: {} created, {} updated, {} disabled".format(
                    created_count, updated_count, disabled_count
                )
            )
        )

    def _import_units(self, df, dry_run):  # noqa: C901
        """Import administrative unit data from dataframe"""
        created_count = 0
        updated_count = 0
        disabled_count = 0
        skipped_count = 0

        for row in df.iter_rows(named=True):
            # Support both Vietnamese and English column names
            code = str(row.get("Mã") or row.get("code") or "").strip()
            name = str(row.get("Tên") or row.get("name") or "").strip()
            english_name = str(row.get("Tên Tiếng Anh") or row.get("english_name") or "").strip()
            parent_province_code = str(row.get("Mã TP") or row.get("parent_province_code") or "").strip()
            level = str(row.get("Cấp") or row.get("level") or "").strip()

            if not code or not name or not parent_province_code:
                self.stdout.write(self.style.WARNING("Skipping row with missing required fields: {}".format(row)))
                skipped_count += 1
                continue

            # Map level to choices
            level_mapping = {
                "Quận": AdministrativeUnit.UnitLevel.DISTRICT,
                "Huyện": AdministrativeUnit.UnitLevel.DISTRICT,
                "Thành phố": AdministrativeUnit.UnitLevel.DISTRICT,
                "Thị xã": AdministrativeUnit.UnitLevel.DISTRICT,
                "Xã": AdministrativeUnit.UnitLevel.COMMUNE,
                "Phường": AdministrativeUnit.UnitLevel.WARD,
                "Thị trấn": AdministrativeUnit.UnitLevel.TOWNSHIP,
            }
            mapped_level = level_mapping.get(level, AdministrativeUnit.UnitLevel.COMMUNE)
            current_information = "|".join([name, english_name, parent_province_code, mapped_level])

            try:
                # Find parent province
                parent_province = Province.objects.filter(code=parent_province_code, enabled=True).first()

                if not parent_province:
                    self.stdout.write(
                        self.style.WARNING(
                            "Parent province not found for code {}: {}".format(parent_province_code, row)
                        )
                    )
                    skipped_count += 1
                    continue

                with transaction.atomic():
                    existing = AdministrativeUnit.objects.filter(code=code, enabled=True).first()

                    if existing:
                        # Check if data has changed
                        existing_information = "|".join(
                            [existing.name, existing.english_name, existing.parent_province.code, existing.level]
                        )
                        if existing_information != current_information:
                            # Disable old record
                            existing.enabled = False
                            if not dry_run:
                                existing.save()
                            disabled_count += 1

                            # Create new record
                            new_unit = AdministrativeUnit(
                                code=code,
                                name=name,
                                english_name=english_name,
                                parent_province=parent_province,
                                level=mapped_level,
                                enabled=True,
                            )
                            if not dry_run:
                                new_unit.save()
                            updated_count += 1
                            self.stdout.write("Updated unit: {} - {}".format(code, name))
                        else:
                            self.stdout.write("Unit unchanged: {} - {}".format(code, name))
                    else:
                        # Create new record
                        unit = AdministrativeUnit(
                            code=code,
                            name=name,
                            english_name=english_name,
                            parent_province=parent_province,
                            level=mapped_level,
                            enabled=True,
                        )
                        if not dry_run:
                            unit.save()
                        created_count += 1
                        self.stdout.write("Created unit: {} - {}".format(code, name))

            except Exception as e:
                self.stdout.write(self.style.ERROR("Error processing row {}: {}".format(row, str(e))))

        if dry_run:
            # Rollback transaction in dry-run mode
            transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                "Unit import summary: {} created, {} updated, {} disabled, {} skipped".format(
                    created_count, updated_count, disabled_count, skipped_count
                )
            )
        )
