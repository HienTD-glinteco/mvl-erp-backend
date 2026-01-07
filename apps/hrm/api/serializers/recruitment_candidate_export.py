from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.hrm.models import RecruitmentCandidate


class RecruitmentCandidateExportSerializer(serializers.ModelSerializer):
    """Serializer for exporting RecruitmentCandidate data to Excel.

    This serializer flattens related objects (recruitment_request, recruitment_source,
    recruitment_channel) to include their names directly in the export.
    """

    recruitment_request__name = serializers.CharField(
        source="recruitment_request.name", read_only=True, label=_("Recruitment Request")
    )
    recruitment_source__name = serializers.CharField(
        source="recruitment_source.name", read_only=True, label=_("Recruitment Source")
    )
    recruitment_channel__name = serializers.CharField(
        source="recruitment_channel.name", read_only=True, label=_("Recruitment Channel")
    )
    status = serializers.CharField(source="get_status_display", read_only=True, label=_("Status"))

    class Meta:
        model = RecruitmentCandidate
        fields = [
            "code",
            "name",
            "recruitment_request__name",
            "recruitment_source__name",
            "recruitment_channel__name",
            "phone",
            "status",
        ]
