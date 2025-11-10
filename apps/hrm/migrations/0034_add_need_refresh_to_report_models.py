# Generated manually for need_refresh field implementation
# This migration adds the need_refresh field to all report models to support
# deleted record tracking in batch tasks

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hrm", "0033_rename_id_fields_to_citizen_id"),
    ]

    operations = [
        # Add need_refresh to EmployeeStatusBreakdownReport
        migrations.AddField(
            model_name="employeestatusbreakdownreport",
            name="need_refresh",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Indicates if this report needs to be recalculated by batch task",
                verbose_name="Needs refresh",
            ),
        ),
        # Add need_refresh to StaffGrowthReport
        migrations.AddField(
            model_name="staffgrowthreport",
            name="need_refresh",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Indicates if this report needs to be recalculated by batch task",
                verbose_name="Needs refresh",
            ),
        ),
        # Add need_refresh to RecruitmentSourceReport
        migrations.AddField(
            model_name="recruitmentsourcereport",
            name="need_refresh",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Indicates if this report needs to be recalculated by batch task",
                verbose_name="Needs refresh",
            ),
        ),
        # Add need_refresh to RecruitmentChannelReport
        migrations.AddField(
            model_name="recruitmentchannelreport",
            name="need_refresh",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Indicates if this report needs to be recalculated by batch task",
                verbose_name="Needs refresh",
            ),
        ),
        # Add need_refresh to RecruitmentCostReport
        migrations.AddField(
            model_name="recruitmentcostreport",
            name="need_refresh",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Indicates if this report needs to be recalculated by batch task",
                verbose_name="Needs refresh",
            ),
        ),
        # Add need_refresh to HiredCandidateReport
        migrations.AddField(
            model_name="hiredcandidatereport",
            name="need_refresh",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Indicates if this report needs to be recalculated by batch task",
                verbose_name="Needs refresh",
            ),
        ),
    ]
