from rest_framework import serializers

from apps.hrm.models import RecruitmentExpense


class RecruitmentExpenseExportSerializer(serializers.ModelSerializer):
    """Serializer for exporting RecruitmentExpense data to Excel.

    This serializer flattens related objects (recruitment_source, recruitment_channel)
    to include their names directly in the export.
    """

    recruitment_source__name = serializers.CharField(source="recruitment_source.name", read_only=True)
    recruitment_channel__name = serializers.CharField(source="recruitment_channel.name", read_only=True)

    class Meta:
        model = RecruitmentExpense
        fields = [
            "date",
            "recruitment_source__name",
            "recruitment_channel__name",
            "num_candidates_participated",
            "total_cost",
            "num_candidates_hired",
            "avg_cost",
        ]
