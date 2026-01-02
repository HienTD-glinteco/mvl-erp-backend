from django.core.management.base import BaseCommand
from django.db import transaction

from apps.hrm.models.contract import ContractType


class Command(BaseCommand):
    help = "Create ContractType for appendix if it does not exist."

    def handle(self, *args, **options):
        with transaction.atomic():
            obj, created = ContractType.objects.get_or_create(
                category=ContractType.Category.APPENDIX,
                defaults={
                    "name": "Appendix type",
                    "symbol": "PLHD",
                },
            )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created ContractType id={obj.id} symbol={obj.symbol}"))
        else:
            self.stdout.write(f"ContractType already exists: id={obj.id} symbol={obj.symbol}")
