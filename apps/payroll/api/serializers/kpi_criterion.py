from decimal import Decimal

from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.payroll.models import KPICriterion


class KPICriterionSerializer(serializers.ModelSerializer):
    """Serializer for KPICriterion model.

    Handles validation and serialization of KPI criteria.
    The created_by and updated_by fields are set automatically
    by the viewset and are read-only in the serializer.
    """

    class Meta:
        model = KPICriterion
        fields = [
            "id",
            "target",
            "evaluation_type",
            "name",
            "description",
            "component_total_score",
            "ordering",
            "active",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "updated_by", "created_at", "updated_at"]

    def validate_component_total_score(self, value):
        """Validate that component_total_score is between 0 and 100."""
        if value < Decimal("0.00") or value > Decimal("100.00"):
            raise serializers.ValidationError(_("Component total score must be between 0 and 100"))
        return value

    def validate(self, data):
        """Perform cross-field validation."""
        # Check for unique constraint if creating or updating with changed fields
        if self.instance:
            # Update case - check if the unique fields are being changed
            target = data.get("target", self.instance.target)
            evaluation_type = data.get("evaluation_type", self.instance.evaluation_type)
            name = data.get("name", self.instance.name)
        else:
            # Create case
            target = data.get("target")
            evaluation_type = data.get("evaluation_type")
            name = data.get("name")

        # Check if a criterion with the same target, evaluation_type, and name already exists
        if target and evaluation_type and name:
            queryset = KPICriterion.objects.filter(
                target=target,
                evaluation_type=evaluation_type,
                name=name,
            )
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise serializers.ValidationError(
                    _("A criterion with this target, evaluation type, and name already exists")
                )

        return data
