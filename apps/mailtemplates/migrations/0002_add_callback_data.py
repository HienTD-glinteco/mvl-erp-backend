# Generated manually for mailtemplates

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mailtemplates', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailsendjob',
            name='callback_data',
            field=models.JSONField(blank=True, help_text='Callback function and object reference to call after successful send', null=True, verbose_name='Callback data'),
        ),
    ]
