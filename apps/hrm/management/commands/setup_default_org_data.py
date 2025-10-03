from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from apps.hrm.models import Block, Branch, Department, Position


class Command(BaseCommand):
    help = _("Setup default organizational data")

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(_("Setting up default organizational data...")))

        # Create default positions
        positions_data = [
            {
                "code": "TGD",
                "name": _("Chief Executive Officer"),
                "level": Position.PositionLevel.CEO,
            },
            {
                "code": "GD_KD",
                "name": _("Business Block Director"),
                "level": Position.PositionLevel.DIRECTOR,
            },
            {
                "code": "GD_HT",
                "name": _("Support Block Director"),
                "level": Position.PositionLevel.DIRECTOR,
            },
            {
                "code": "PGD_KD",
                "name": _("Deputy Business Block Director"),
                "level": Position.PositionLevel.DEPUTY_DIRECTOR,
            },
            {
                "code": "PGD_HT",
                "name": _("Deputy Support Block Director"),
                "level": Position.PositionLevel.DEPUTY_DIRECTOR,
            },
            {
                "code": "TP",
                "name": _("Department Manager"),
                "level": Position.PositionLevel.MANAGER,
            },
            {
                "code": "PTP",
                "name": _("Deputy Department Manager"),
                "level": Position.PositionLevel.DEPUTY_MANAGER,
            },
            {
                "code": "GS",
                "name": _("Supervisor"),
                "level": Position.PositionLevel.SUPERVISOR,
            },
            {"code": "NV", "name": _("Staff"), "level": Position.PositionLevel.STAFF},
            {
                "code": "TTS",
                "name": _("Intern"),
                "level": Position.PositionLevel.INTERN,
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

        # Create default branch
        branch, created = Branch.objects.get_or_create(
            code="HQ",
            defaults={
                "name": _("MaiVietLand Headquarters"),
                "address": _("Hanoi, Vietnam"),
                "is_active": True,
            },
        )
        if created:
            self.stdout.write(_("Created branch: %s") % branch.name)
        else:
            self.stdout.write(_("Branch already exists: %s") % branch.name)

        # Create default blocks
        blocks_data = [
            {
                "code": "BKD",
                "name": _("Business Block"),
                "block_type": Block.BlockType.BUSINESS,
            },
            {
                "code": "BHT",
                "name": _("Support Block"),
                "block_type": Block.BlockType.SUPPORT,
            },
        ]

        blocks = {}
        for block_data in blocks_data:
            block, created = Block.objects.get_or_create(
                code=block_data["code"],
                branch=branch,
                defaults={
                    "name": block_data["name"],
                    "block_type": block_data["block_type"],
                    "is_active": True,
                },
            )
            blocks[block_data["code"]] = block
            if created:
                self.stdout.write(_("Created block: %s") % block.name)
            else:
                self.stdout.write(_("Block already exists: %s") % block.name)

        # Create default departments with new fields
        departments_data = [
            # Business departments - function will be auto-set to 'business'
            {
                "code": "KD01",
                "name": _("Business Department 1"),
                "block": "BKD",
                "is_main": True,
            },
            {
                "code": "KD02",
                "name": _("Business Department 2"),
                "block": "BKD",
                "is_main": False,
            },
            {
                "code": "MKT",
                "name": _("Marketing Department"),
                "block": "BKD",
                "is_main": False,
            },
            # Support departments with specific functions
            {
                "code": "HC",
                "name": _("HR Administration Department"),
                "block": "BHT",
                "function": "hr_admin",
                "is_main": True,
            },
            {
                "code": "KT",
                "name": _("Accounting Department"),
                "block": "BHT",
                "function": "accounting",
                "is_main": True,
            },
            {
                "code": "IT",
                "name": _("IT Department"),
                "block": "BHT",
                "function": "project_development",
                "is_main": True,
            },
            {
                "code": "PL",
                "name": _("Legal Department"),
                "block": "BHT",
                "function": "project_promotion",
                "is_main": True,
            },
        ]

        for dept_data in departments_data:
            defaults = {
                "name": dept_data["name"],
                "is_active": True,
                "is_main_department": dept_data.get("is_main", False),
            }

            # Set function for support departments (business departments auto-set in model)
            if dept_data.get("function"):
                defaults["function"] = dept_data["function"]

            department, created = Department.objects.get_or_create(
                code=dept_data["code"],
                block=blocks[dept_data["block"]],
                defaults=defaults,
            )
            if created:
                self.stdout.write(_("Created department: %s") % department.name)
            else:
                self.stdout.write(_("Department already exists: %s") % department.name)

        self.stdout.write(self.style.SUCCESS(_("Successfully set up default organizational data!")))
