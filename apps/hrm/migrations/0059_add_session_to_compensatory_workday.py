# Generated migration for adding session field to CompensatoryWorkday

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hrm', '0058_add_holiday_and_compensatory_workday'),
    ]

    operations = [
        migrations.AddField(
            model_name='compensatoryworkday',
            name='session',
            field=models.CharField(
                choices=[('morning', 'Morning'), ('afternoon', 'Afternoon'), ('full_day', 'Full Day')],
                default='full_day',
                max_length=20,
                verbose_name='Session'
            ),
        ),
    ]
