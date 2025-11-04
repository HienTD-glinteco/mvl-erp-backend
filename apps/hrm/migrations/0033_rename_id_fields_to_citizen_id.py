# Generated manually on 2025-11-03

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("hrm", "0032_add_employee_dependent"),
    ]

    operations = [
        # Rename id_number to citizen_id in EmployeeDependent
        migrations.RenameField(
            model_name="employeedependent",
            old_name="id_number",
            new_name="citizen_id",
        ),
        # Rename national_id to citizen_id in EmployeeRelationship
        migrations.RenameField(
            model_name="employeerelationship",
            old_name="national_id",
            new_name="citizen_id",
        ),
    ]
