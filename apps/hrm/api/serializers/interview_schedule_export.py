from rest_framework import serializers

from apps.hrm.models import InterviewSchedule


class InterviewScheduleExportSerializer(serializers.ModelSerializer):
    """Serializer for exporting InterviewSchedule data to Excel.

    This serializer flattens related objects (recruitment_request and its nested job_description)
    to include their fields directly in the export.
    """

    recruitment_request__name = serializers.CharField(source="recruitment_request.name", read_only=True)
    recruitment_request__job_description__position_title = serializers.CharField(
        source="recruitment_request.job_description.position_title", read_only=True
    )
    recruitment_request__number_of_positions = serializers.IntegerField(
        source="recruitment_request.number_of_positions", read_only=True
    )

    class Meta:
        model = InterviewSchedule
        fields = [
            "title",
            "recruitment_request__name",
            "recruitment_request__job_description__position_title",
            "recruitment_request__number_of_positions",
            "time",
        ]
