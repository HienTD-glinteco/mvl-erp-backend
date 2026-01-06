import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.hrm.models import Position


class Command(BaseCommand):
    help = "Setup default organizational data"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Setting up default organizational data..."))
        # Load positions from CSV fixture
        csv_path = Path(__file__).resolve().parents[2] / "fixtures" / "default_positions.csv"
        if not csv_path.exists():
            self.stdout.write(self.style.ERROR("CSV file not found: %s" % str(csv_path)))
            return

        positions_data = []
        try:
            with csv_path.open(mode="r", encoding="utf-8") as f:
                reader = csv.reader(f)
                # Skip header row unconditionally to avoid hardcoding header names
                next(reader, None)
                for row in reader:
                    if not row:
                        continue
                    # Expect first two columns: code, name; trailing commas may yield extra empty columns
                    code = (row[0] if len(row) > 0 else "").strip()
                    name = (row[1] if len(row) > 1 else "").strip()
                    if code and name:
                        positions_data.append({"code": code, "name": name})
        except Exception as exc:
            self.stdout.write(self.style.ERROR("Failed to read CSV: %s" % str(exc)))
            return

        if not positions_data:
            self.stdout.write(self.style.ERROR("No positions found in CSV: %s" % str(csv_path)))
            return

        for position_data in positions_data:
            position, created = Position.objects.get_or_create(
                code=position_data["code"],
                defaults={
                    "name": position_data["name"],
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write("Created position: %s" % position.name)
            else:
                self.stdout.write("Position already exists: %s" % position.name)

        self.stdout.write(self.style.SUCCESS("Successfully set up default organizational data!"))
