# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_change_user_roles_to_single_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="code",
            field=models.CharField(default="VT001", max_length=50, unique=True, verbose_name="Mã vai trò"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="role",
            name="is_system_role",
            field=models.BooleanField(default=False, verbose_name="Vai trò hệ thống"),
        ),
        migrations.AlterModelOptions(
            name="role",
            options={"ordering": ["code"], "verbose_name": "Vai trò", "verbose_name_plural": "Vai trò"},
        ),
    ]
