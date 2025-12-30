from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from apps.hrm.models import Position


class Command(BaseCommand):
    help = _("Setup default organizational data")

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(_("Setting up default organizational data...")))

        # Create default positions
        positions_data = [
            {
                "code": "TGD",
                "name": _("Chief Executive Officer"),
                "is_active": True,
                "include_in_employee_report": True,
                "is_leadership": True,
            },
            {
                "code": "GD_KD",
                "name": _("Business Block Director"),
                "is_active": True,
                "include_in_employee_report": True,
                "is_leadership": True,
            },
            {
                "code": "GD_HT",
                "name": _("Support Block Director"),
                "is_active": True,
                "include_in_employee_report": True,
                "is_leadership": True,
            },
            {
                "code": "PGD_KD",
                "name": _("Deputy Business Block Director"),
                "is_active": True,
                "include_in_employee_report": True,
                "is_leadership": True,
            },
            {
                "code": "PGD_HT",
                "name": _("Deputy Support Block Director"),
                "is_active": True,
                "include_in_employee_report": True,
                "is_leadership": True,
            },
            {
                "code": "TP",
                "name": _("Department Manager"),
                "is_active": True,
                "include_in_employee_report": True,
                "is_leadership": True,
            },
            {
                "code": "PTP",
                "name": _("Deputy Department Manager"),
                "is_active": True,
                "include_in_employee_report": True,
                "is_leadership": True,
            },
            {
                "code": "GS",
                "name": _("Supervisor"),
                "is_active": True,
                "include_in_employee_report": True,
                "is_leadership": True,
            },
            {
                "code": "NV",
                "name": _("Staff"),
                "is_active": True,
                "include_in_employee_report": True,
                "is_leadership": True,
            },
            {
                "code": "TTS",
                "name": _("Intern"),
                "is_active": True,
                "include_in_employee_report": True,
                "is_leadership": True,
            },
        ]

        for position_data in positions_data:
            position, created = Position.objects.get_or_create(
                code=position_data["code"],
                defaults={
                    "name": position_data["name"],
                    "level": position_data["level"],
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write(_("Created position: %s") % position.name)
            else:
                self.stdout.write(_("Position already exists: %s") % position.name)

        self.stdout.write(self.style.SUCCESS(_("Successfully set up default organizational data!")))
