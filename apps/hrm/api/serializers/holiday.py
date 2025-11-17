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
            "session",
            "notes",
            "status",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "holiday", "created_by", "updated_by", "created_at", "updated_at"]

    def validate(self, attrs):
        """Validate compensatory workday data."""
        # Get the holiday from attrs or instance
        holiday = attrs.get("holiday") or (self.instance.holiday if self.instance else None)
        date = attrs.get("date")
        session = attrs.get("session", CompensatoryWorkday.Session.FULL_DAY)

        if date:
            # Check if the date is Saturday (5) or Sunday (6)
            weekday = date.weekday()
            if weekday not in [5, 6]:  # 5 = Saturday, 6 = Sunday
                raise serializers.ValidationError(
                    {"date": _("Compensatory workday must be on Saturday or Sunday")}
                )

            # If Saturday, session can only be afternoon
            if weekday == 5 and session != CompensatoryWorkday.Session.AFTERNOON:
                raise serializers.ValidationError(
                    {"session": _("For Saturday compensatory workdays, only afternoon session is allowed")}
                )

            # Check if compensatory date overlaps with ANY active holiday
            overlapping_holidays = Holiday.objects.filter(
                deleted=False,
                status=Holiday.Status.ACTIVE,
                start_date__lte=date,
                end_date__gte=date,
            )
            if overlapping_holidays.exists():
                holiday_name = overlapping_holidays.first().name
                raise serializers.ValidationError(
                    {"date": _(f"Compensatory workday date overlaps with active holiday: {holiday_name}")}
                )

        if holiday and date:
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
    total_days = serializers.SerializerMethodField()
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
            "total_days",
            "compensatory_dates",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "compensatory_days_count",
            "total_days",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def get_compensatory_days_count(self, obj):
        """Get the count of compensatory days for this holiday."""
        return obj.compensatory_days.filter(deleted=False).count()

    def get_total_days(self, obj):
        """Get the total number of days in the holiday range."""
        if obj.start_date and obj.end_date:
            return (obj.end_date - obj.start_date).days + 1
        return 0

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

        # Validate compensatory_dates if provided
        compensatory_dates = attrs.get("compensatory_dates", [])
        if compensatory_dates:
            # Check if any compensatory date falls within any active holiday range
            for comp_date in compensatory_dates:
                # Validate that compensatory date is Saturday or Sunday
                weekday = comp_date.weekday()
                if weekday not in [5, 6]:  # 5 = Saturday, 6 = Sunday
                    raise serializers.ValidationError(
                        {"compensatory_dates": _(f"Compensatory date {comp_date} must be on Saturday or Sunday")}
                    )

                # Check against all active holidays (including the one being created/updated)
                overlapping_holidays = Holiday.objects.filter(
                    deleted=False,
                    status=Holiday.Status.ACTIVE,
                    start_date__lte=comp_date,
                    end_date__gte=comp_date,
                )
                
                # When updating, don't check against the current holiday being updated
                if self.instance:
                    overlapping_holidays = overlapping_holidays.exclude(id=self.instance.id)
                
                # When creating, also check against the date range being created
                if not self.instance and start_date and end_date:
                    if start_date <= comp_date <= end_date:
                        raise serializers.ValidationError(
                            {"compensatory_dates": _(f"Compensatory date {comp_date} falls within the holiday date range")}
                        )
                
                if overlapping_holidays.exists():
                    holiday_name = overlapping_holidays.first().name
                    raise serializers.ValidationError(
                        {"compensatory_dates": _(f"Compensatory date {comp_date} overlaps with active holiday: {holiday_name}")}
                    )
                
                # Check if compensatory date already exists as an active compensatory day for other holidays
                existing_comp_days = CompensatoryWorkday.objects.filter(
                    date=comp_date,
                    deleted=False,
                    status=CompensatoryWorkday.Status.ACTIVE,
                )
                
                # Exclude compensatory days from the current holiday when updating
                if self.instance:
                    existing_comp_days = existing_comp_days.exclude(holiday=self.instance)
                
                if existing_comp_days.exists():
                    raise serializers.ValidationError(
                        {"compensatory_dates": _(f"Compensatory date {comp_date} already exists as an active compensatory workday")}
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
                # Determine session based on day of week
                # Saturday (5) defaults to afternoon, Sunday (6) defaults to full day
                weekday = date.weekday()
                if weekday == 5:  # Saturday
                    session = CompensatoryWorkday.Session.AFTERNOON
                else:  # Sunday
                    session = CompensatoryWorkday.Session.FULL_DAY
                
                CompensatoryWorkday.objects.create(
                    holiday=holiday,
                    date=date,
                    session=session,
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
