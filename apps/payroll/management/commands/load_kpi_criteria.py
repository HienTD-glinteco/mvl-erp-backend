import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.payroll.models import KPICriterion


class Command(BaseCommand):
    help = "Load default KPI criteria from fixtures"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing KPI criteria before loading",
        )

    def handle(self, *args, **options):
        fixtures_path = Path(__file__).parent.parent.parent / "fixtures" / "kpi_criteria.json"

        if not fixtures_path.exists():
            self.stdout.write(self.style.ERROR(f"Fixtures file not found: {fixtures_path}"))
            return

        with open(fixtures_path, "r") as f:
            data = json.load(f)

        if options["clear"]:
            deleted_count = KPICriterion.objects.count()
            KPICriterion.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted_count} existing KPI criteria"))

        created_count = 0
        updated_count = 0
        skipped_count = 0

        with transaction.atomic():
            for item in data:
                fields = item["fields"]
                pk = item.get("pk")

                try:
                    criterion, created = KPICriterion.objects.update_or_create(
                        id=pk,
                        defaults={
                            "target": fields["target"],
                            "evaluation_type": fields["evaluation_type"],
                            "criterion": fields["criterion"],
                            "sub_criterion": fields.get("sub_criterion"),
                            "description": fields.get("description", ""),
                            "component_total_score": fields["component_total_score"],
                            "group_number": fields["group_number"],
                            "order": fields["order"],
                            "active": fields.get("active", True),
                        },
                    )

                    if created:
                        created_count += 1
                        self.stdout.write(self.style.SUCCESS(f"Created: {criterion.target} - {criterion.criterion}"))
                    else:
                        updated_count += 1
                        self.stdout.write(self.style.WARNING(f"Updated: {criterion.target} - {criterion.criterion}"))

                except Exception as e:
                    skipped_count += 1
                    self.stdout.write(self.style.ERROR(f"Error processing item {pk}: {str(e)}"))

        self.stdout.write(
            self.style.SUCCESS(f"\nSummary: {created_count} created, {updated_count} updated, {skipped_count} skipped")
        )
