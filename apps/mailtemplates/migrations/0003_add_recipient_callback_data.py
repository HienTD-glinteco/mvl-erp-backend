# Generated manually for mailtemplates

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("mailtemplates", "0002_add_callback_data"),
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
