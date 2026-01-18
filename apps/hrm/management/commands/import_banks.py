import json

from django.core.management.base import BaseCommand, CommandError

from apps.hrm.models import Bank


class Command(BaseCommand):
    help = "Import default banks from a JSON file"

    def add_arguments(self, parser):
        parser.add_argument(
            "json_path",
            type=str,
            help="Path to the JSON file containing bank data",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear all existing banks before importing",
        )

    def handle(self, *args, **options):
        json_path = options["json_path"]
        clear = options["clear"]

        # Read JSON file
        try:
            with open(json_path, encoding="utf-8") as f:
                banks_data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"File not found: {json_path}")
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON file: {e}")

        # Clear existing banks if requested
        if clear:
            deleted_count, _ = Bank.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted_count} existing banks"))

        created_count = 0
        updated_count = 0

        for bank_data in banks_data:
            code = bank_data.get("code")
            name = bank_data.get("name")

            if not code:
                self.stderr.write(self.style.WARNING(f"Skipping entry without code: {bank_data}"))
                continue

            if not name:
                self.stderr.write(self.style.WARNING(f"Skipping entry without name: {bank_data}"))
                continue

            bank, created = Bank.objects.update_or_create(
                code=code,
                defaults={"name": name},
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created bank: {code} - {name}"))
            else:
                updated_count += 1
                self.stdout.write(self.style.SUCCESS(f"Updated bank: {code} - {name}"))

        self.stdout.write(
            self.style.SUCCESS(f"Successfully imported banks. Created: {created_count}, Updated: {updated_count}")
        )
