from django.core.management.base import BaseCommand
from apps.hrm.models import Branch, Block, Department, Position


class Command(BaseCommand):
    help = "Setup default organizational data"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("Setting up default organizational data...")
        )

        # Create default positions
        positions_data = [
            {
                "code": "TGD",
                "name": "Tổng Giám đốc",
                "level": Position.PositionLevel.CEO,
            },
            {
                "code": "GD_KD",
                "name": "Giám đốc Khối Kinh doanh",
                "level": Position.PositionLevel.DIRECTOR,
            },
            {
                "code": "GD_HT",
                "name": "Giám đốc Khối Hỗ trợ",
                "level": Position.PositionLevel.DIRECTOR,
            },
            {
                "code": "PGD_KD",
                "name": "Phó Giám đốc Khối Kinh doanh",
                "level": Position.PositionLevel.DEPUTY_DIRECTOR,
            },
            {
                "code": "PGD_HT",
                "name": "Phó Giám đốc Khối Hỗ trợ",
                "level": Position.PositionLevel.DEPUTY_DIRECTOR,
            },
            {
                "code": "TP",
                "name": "Trưởng phòng",
                "level": Position.PositionLevel.MANAGER,
            },
            {
                "code": "PTP",
                "name": "Phó Trưởng phòng",
                "level": Position.PositionLevel.DEPUTY_MANAGER,
            },
            {
                "code": "GS",
                "name": "Giám sát",
                "level": Position.PositionLevel.SUPERVISOR,
            },
            {"code": "NV", "name": "Nhân viên", "level": Position.PositionLevel.STAFF},
            {
                "code": "TTS",
                "name": "Thực tập sinh",
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
                self.stdout.write(f"Created position: {position.name}")
            else:
                self.stdout.write(f"Position already exists: {position.name}")

        # Create default branch
        branch, created = Branch.objects.get_or_create(
            code="HQ",
            defaults={
                "name": "Trụ sở chính MaiVietLand",
                "address": "Hà Nội, Việt Nam",
                "is_active": True,
            },
        )
        if created:
            self.stdout.write(f"Created branch: {branch.name}")
        else:
            self.stdout.write(f"Branch already exists: {branch.name}")

        # Create default blocks
        blocks_data = [
            {
                "code": "BKD",
                "name": "Khối Kinh doanh",
                "block_type": Block.BlockType.BUSINESS,
            },
            {
                "code": "BHT",
                "name": "Khối Hỗ trợ",
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
                self.stdout.write(f"Created block: {block.name}")
            else:
                self.stdout.write(f"Block already exists: {block.name}")

        # Create default departments with new fields
        departments_data = [
            # Business departments - function will be auto-set to 'business'
            {
                "code": "KD01",
                "name": "Phòng Kinh doanh 1",
                "block": "BKD",
                "is_main": True,
            },
            {
                "code": "KD02",
                "name": "Phòng Kinh doanh 2",
                "block": "BKD",
                "is_main": False,
            },
            {
                "code": "MKT",
                "name": "Phòng Marketing",
                "block": "BKD",
                "is_main": False,
            },
            # Support departments with specific functions
            {
                "code": "HC",
                "name": "Phòng Hành chính Nhân sự",
                "block": "BHT",
                "function": "hr_admin",
                "is_main": True,
            },
            {
                "code": "KT",
                "name": "Phòng Kế toán",
                "block": "BHT",
                "function": "accounting",
                "is_main": True,
            },
            {
                "code": "IT",
                "name": "Phòng Công nghệ thông tin",
                "block": "BHT",
                "function": "project_development",
                "is_main": True,
            },
            {
                "code": "PL",
                "name": "Phòng Pháp lý",
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
                self.stdout.write(f"Created department: {department.name}")
            else:
                self.stdout.write(f"Department already exists: {department.name}")

        self.stdout.write(
            self.style.SUCCESS("Successfully set up default organizational data!")
        )
