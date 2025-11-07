# Generated manually for mailtemplates

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("mailtemplates", "0003_rename_mailtemplat_created_62c62e_idx_mailtemplat_created_992fa7_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailsendrecipient",
            name="callback_data",
            field=models.JSONField(
                blank=True,
                help_text="Per-recipient callback data to use after successful send",
                null=True,
                verbose_name="Callback data",
            ),
        ),
    ]
