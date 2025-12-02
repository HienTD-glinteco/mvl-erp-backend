"""Data migration to create the system-managed appendix contract type."""

from django.db import migrations


def create_appendix_contract_type(apps, schema_editor):
    """Create the appendix contract type if it doesn't exist."""
    ContractType = apps.get_model("hrm", "ContractType")

    # Check if appendix contract type already exists
    if not ContractType.objects.filter(category="appendix").exists():
        ContractType.objects.create(
            code="PLHD",
            name="Phụ lục hợp đồng",
            symbol="PLHD",
            category="appendix",
            duration_type="indefinite",
            base_salary=0,
            net_percentage="100",
            tax_calculation_method="progressive",
            working_time_type="full_time",
            annual_leave_days=12,
            has_social_insurance=True,
            working_conditions="",
            rights_and_obligations="",
            terms="",
            note="System-managed contract type for appendices. Do not delete.",
        )


def reverse_create_appendix_contract_type(apps, schema_editor):
    """Remove the appendix contract type."""
    ContractType = apps.get_model("hrm", "ContractType")
    ContractType.objects.filter(category="appendix", code="PLHD").delete()


class Migration(migrations.Migration):
    """Data migration to create appendix contract type."""

    dependencies = [
        ("hrm", "0089_add_effective_date_to_employee_certificate"),
    ]

    operations = [
        migrations.RunPython(
            create_appendix_contract_type,
            reverse_create_appendix_contract_type,
        ),
    ]
