# Generated migration file

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hrm", "0050_remove_organization_chart"),
    ]

    operations = [
        migrations.AlterField(
            model_name="employeeworkhistory",
            name="name",
            field=models.CharField(
                choices=[
                    ("Change Position", "Change Position"),
                    ("Change Status", "Change Status"),
                    ("Transfer", "Transfer"),
                    ("Change Contract", "Change Contract"),
                    ("Return to Work", "Return to Work"),
                ],
                help_text="Type of the work history event",
                max_length=50,
                verbose_name="Event type",
            ),
        ),
    ]
