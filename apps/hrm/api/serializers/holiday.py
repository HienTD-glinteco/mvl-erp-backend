from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.models import CompensatoryWorkday, Holiday


class CompensatoryWorkdaySerializer(serializers.ModelSerializer):
    """Serializer for CompensatoryWorkday model."""

    class Meta:
        model = CompensatoryWorkday
        fields = [
            "id",
            "holiday",
            "date",
            "notes",
            "status",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "updated_by", "created_at", "updated_at"]
        extra_kwargs = {
            "holiday": {"required": False},  # Not required since it's set from URL context
        }

    def validate(self, attrs):
        """Validate compensatory workday data."""
        # Get the holiday from attrs or instance
        holiday = attrs.get("holiday") or (self.instance.holiday if self.instance else None)
        date = attrs.get("date")

        if holiday and date:
            # Check if date falls within holiday range
            if holiday.start_date <= date <= holiday.end_date:
                raise serializers.ValidationError(
                    {"date": _("Compensatory workday date cannot fall within the holiday date range")}
                )

            # Check for existing compensatory workdays with same date for this holiday
            # Exclude current instance if updating
            queryset = CompensatoryWorkday.objects.filter(holiday=holiday, date=date, deleted=False)
            if self.instance:
                queryset = queryset.exclude(id=self.instance.id)

            if queryset.exists():
                raise serializers.ValidationError(
                    {"date": _("A compensatory workday with this date already exists for this holiday")}
                )

        return attrs


class HolidaySerializer(serializers.ModelSerializer):
    """Serializer for Holiday model."""

    compensatory_days_count = serializers.SerializerMethodField()
    compensatory_dates = serializers.ListField(
        child=serializers.DateField(),
        write_only=True,
        required=False,
        help_text=_("List of compensatory workday dates to create with the holiday"),
    )

    class Meta:
        model = Holiday
        fields = [
            "id",
            "name",
            "start_date",
            "end_date",
            "notes",
            "status",
            "compensatory_days_count",
            "compensatory_dates",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "compensatory_days_count",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def get_compensatory_days_count(self, obj):
        """Get the count of compensatory days for this holiday."""
        return obj.compensatory_days.filter(deleted=False).count()

    def validate(self, attrs):
        """Validate holiday data."""
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        # Validate date range
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({"end_date": _("End date must be greater than or equal to start date")})

        # Check for overlapping holidays (only for active status)
        status = attrs.get("status", Holiday.Status.ACTIVE)
        if status == Holiday.Status.ACTIVE and start_date and end_date:
            # Build queryset for overlapping holidays
            overlapping = Holiday.objects.filter(
                deleted=False,
                status=Holiday.Status.ACTIVE,
                start_date__lte=end_date,
                end_date__gte=start_date,
            )

            # Exclude current instance if updating
            if self.instance:
                overlapping = overlapping.exclude(id=self.instance.id)

            if overlapping.exists():
                raise serializers.ValidationError(
                    {"start_date": _("This holiday overlaps with an existing active holiday")}
                )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create holiday and optionally create compensatory workdays."""
        compensatory_dates = validated_data.pop("compensatory_dates", [])
        holiday = super().create(validated_data)

        # Create compensatory workdays if provided
        if compensatory_dates:
            user = self.context["request"].user
            for date in compensatory_dates:
                CompensatoryWorkday.objects.create(
                    holiday=holiday,
                    date=date,
                    created_by=user,
                    updated_by=user,
                )

        return holiday

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update holiday."""
        # Remove compensatory_dates if present (not supported in update)
        validated_data.pop("compensatory_dates", None)
        return super().update(instance, validated_data)


class HolidayDetailSerializer(HolidaySerializer):
    """Detailed serializer for Holiday with compensatory days."""

    compensatory_days = CompensatoryWorkdaySerializer(many=True, read_only=True)

    class Meta(HolidaySerializer.Meta):
        fields = HolidaySerializer.Meta.fields + ["compensatory_days"]
