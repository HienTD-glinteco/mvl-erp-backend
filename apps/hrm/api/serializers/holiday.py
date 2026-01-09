from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.models import CompensatoryWorkday, Holiday
from libs.drf.serializers.mixins import FieldFilteringSerializerMixin


class CompensatoryWorkdaySerializer(serializers.ModelSerializer):
    """Serializer for CompensatoryWorkday model."""

    morning_time = serializers.SerializerMethodField()
    afternoon_time = serializers.SerializerMethodField()

    class Meta:
        model = CompensatoryWorkday
        fields = [
            "id",
            "holiday",
            "date",
            "session",
            "notes",
            "morning_time",
            "afternoon_time",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "holiday", "morning_time", "afternoon_time", "created_at", "updated_at"]

    def get_morning_time(self, obj):
        """Get morning time range if session is morning or full_day."""
        if obj.session in [CompensatoryWorkday.Session.MORNING, CompensatoryWorkday.Session.FULL_DAY]:
            return "08:00-12:00"
        return ""

    def get_afternoon_time(self, obj):
        """Get afternoon time range if session is afternoon or full_day."""
        if obj.session in [CompensatoryWorkday.Session.AFTERNOON, CompensatoryWorkday.Session.FULL_DAY]:
            return "13:30-17:30"
        return ""

    def _get_holiday(self, attrs):
        """Get holiday from attrs, instance, or context."""
        holiday = attrs.get("holiday")
        if not holiday and self.instance:
            holiday = self.instance.holiday
        if not holiday and hasattr(self, "context") and "holiday" in self.context:
            holiday = self.context["holiday"]
        return holiday

    def _validate_weekend_and_session(self, date, session):
        """Validate that date is weekend and session is valid for the day."""
        weekday = date.weekday()
        if weekday not in [5, 6]:
            raise serializers.ValidationError({"date": _("Compensatory workday must be on Saturday or Sunday")})

        if weekday == 5 and session != CompensatoryWorkday.Session.AFTERNOON:
            raise serializers.ValidationError(
                {"session": _("For Saturday compensatory workdays, only afternoon session is allowed")}
            )

    def _validate_no_holiday_overlap(self, date):
        """Validate that compensatory date doesn't overlap with holidays."""
        overlapping_holidays = Holiday.objects.filter(
            start_date__lte=date,
            end_date__gte=date,
        )
        if overlapping_holidays.exists():
            holiday_name = overlapping_holidays.first().name
            raise serializers.ValidationError(
                {
                    "date": _("Compensatory workday date overlaps with holiday: {holiday_name}").format(
                        holiday_name=holiday_name
                    )
                }
            )

    def _validate_no_duplicate_for_holiday(self, holiday, date):
        """Validate no duplicate compensatory workday for the same holiday and date."""
        queryset = CompensatoryWorkday.objects.filter(holiday=holiday, date=date)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)

        if queryset.exists():
            raise serializers.ValidationError(
                {"date": _("A compensatory workday with this date already exists for this holiday")}
            )

    def _validate_no_session_conflicts(self, holiday, date, session):
        """Validate no session conflicts with compensatory workdays from other holidays."""
        conflicting_comp_days = CompensatoryWorkday.objects.filter(
            date=date,
        ).exclude(holiday=holiday)

        if self.instance:
            conflicting_comp_days = conflicting_comp_days.exclude(id=self.instance.id)

        for comp_day in conflicting_comp_days:
            if comp_day.session == session:
                raise serializers.ValidationError(
                    {
                        "session": _(
                            "A compensatory workday with the same date and session already exists for holiday '{holiday_name}'"
                        ).format(holiday_name=comp_day.holiday.name)
                    }
                )
            elif (
                session == CompensatoryWorkday.Session.FULL_DAY
                or comp_day.session == CompensatoryWorkday.Session.FULL_DAY
            ):
                raise serializers.ValidationError(
                    {
                        "session": _(
                            "A compensatory workday with full_day session conflicts with existing session for holiday '{holiday_name}'"
                        ).format(holiday_name=comp_day.holiday.name)
                    }
                )

    def _validate_future_date(self, date_value):
        """Validate date is strictly in the future."""
        today = timezone.localdate()
        if date_value <= today:
            raise serializers.ValidationError(
                {"date": _("Cannot create/edit compensatory workdays in the past or present")}
            )

    def validate(self, attrs):
        """Validate compensatory workday data."""
        holiday = self._get_holiday(attrs)
        date = attrs.get("date")
        session = attrs.get("session", CompensatoryWorkday.Session.FULL_DAY)

        # Check if existing record is past/present
        if self.instance:
            self._validate_future_date(self.instance.date)

        if date:
            self._validate_future_date(date)
            self._validate_weekend_and_session(date, session)
            self._validate_no_holiday_overlap(date)

        if holiday and date:
            self._validate_no_duplicate_for_holiday(holiday, date)
            self._validate_no_session_conflicts(holiday, date, session)

        return attrs


class CompensatoryDateInputSerializer(serializers.Serializer):
    """Nested serializer for compensatory date input when creating holidays."""

    date = serializers.DateField(required=True, help_text="Date of the compensatory workday")
    session = serializers.ChoiceField(
        choices=CompensatoryWorkday.Session.choices,
        required=False,
        help_text="Work session (morning, afternoon, or full_day). Auto-set based on weekday if not provided.",
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Additional notes about the compensatory workday",
    )

    def validate_date(self, value):
        """Validate date is strictly in the future."""
        today = timezone.localdate()
        if value <= today:
            raise serializers.ValidationError(_("Cannot create compensatory workdays in the past or present"))
        return value


class HolidaySerializer(serializers.ModelSerializer):
    """Serializer for Holiday model."""

    compensatory_days_count = serializers.SerializerMethodField()
    total_days = serializers.SerializerMethodField()
    compensatory_dates = CompensatoryDateInputSerializer(
        many=True,
        write_only=True,
        required=False,
        help_text="List of compensatory workdays to create with the holiday (date, session, notes)",
    )

    class Meta:
        model = Holiday
        fields = [
            "id",
            "name",
            "start_date",
            "end_date",
            "notes",
            "compensatory_days_count",
            "total_days",
            "compensatory_dates",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "compensatory_days_count",
            "total_days",
            "created_at",
            "updated_at",
        ]

    def get_compensatory_days_count(self, obj):
        """Get the count of compensatory days for this holiday."""
        return obj.compensatory_days.count()

    def get_total_days(self, obj):
        """Get the total number of days in the holiday range."""
        if obj.start_date and obj.end_date:
            return (obj.end_date - obj.start_date).days + 1
        return 0

    def _validate_date_range(self, start_date, end_date):
        """Validate that end date is not before start date."""
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({"end_date": _("End date must be greater than or equal to start date")})

    def _validate_no_overlapping_holidays(self, start_date, end_date):
        """Validate no overlapping holidays."""
        if start_date and end_date:
            overlapping = Holiday.objects.filter(
                start_date__lte=end_date,
                end_date__gte=start_date,
            )

            if self.instance:
                overlapping = overlapping.exclude(id=self.instance.id)

            if overlapping.exists():
                raise serializers.ValidationError({"start_date": _("This holiday overlaps with an existing holiday")})

    def _validate_comp_date_is_weekend(self, comp_date, weekday):
        """Validate compensatory date is on weekend."""
        if weekday not in [5, 6]:
            raise serializers.ValidationError(
                {
                    "compensatory_dates": _("Compensatory date {comp_date} must be on Saturday or Sunday").format(
                        comp_date=comp_date
                    )
                }
            )

    def _auto_set_session(self, comp_entry, weekday):
        """Auto-set session based on weekday if not provided."""
        comp_session = comp_entry.get("session") if isinstance(comp_entry, dict) else None
        if not comp_session:
            comp_session = (
                CompensatoryWorkday.Session.AFTERNOON if weekday == 5 else CompensatoryWorkday.Session.FULL_DAY
            )
            if isinstance(comp_entry, dict):
                comp_entry["session"] = comp_session
        return comp_session

    def _validate_saturday_session(self, comp_date, weekday, comp_session):
        """Validate Saturday only allows afternoon session."""
        if weekday == 5 and comp_session != CompensatoryWorkday.Session.AFTERNOON:
            raise serializers.ValidationError(
                {
                    "compensatory_dates": _(
                        "For Saturday compensatory workday {comp_date}, only afternoon session is allowed"
                    ).format(comp_date=comp_date)
                }
            )

    def _validate_comp_date_not_in_holiday_range(self, comp_date, start_date, end_date):
        """Validate compensatory date doesn't fall within the holiday range."""
        if not self.instance and start_date and end_date:
            if start_date <= comp_date <= end_date:
                raise serializers.ValidationError(
                    {
                        "compensatory_dates": _(
                            "Compensatory date {comp_date} falls within the holiday date range"
                        ).format(comp_date=comp_date)
                    }
                )

    def _validate_comp_date_no_holiday_overlap(self, comp_date):
        """Validate compensatory date doesn't overlap with other holidays."""
        overlapping_holidays = Holiday.objects.filter(
            start_date__lte=comp_date,
            end_date__gte=comp_date,
        )

        if self.instance:
            overlapping_holidays = overlapping_holidays.exclude(id=self.instance.id)

        if overlapping_holidays.exists():
            holiday_name = overlapping_holidays.first().name
            raise serializers.ValidationError(
                {
                    "compensatory_dates": _(
                        "Compensatory date {comp_date} overlaps with holiday: {holiday_name}"
                    ).format(comp_date=comp_date, holiday_name=holiday_name)
                }
            )

    def _validate_comp_date_no_session_conflicts(self, comp_date, comp_session):
        """Validate no session conflicts with existing compensatory workdays."""
        conflicting_comp_days = CompensatoryWorkday.objects.filter(
            date=comp_date,
        )

        if self.instance:
            conflicting_comp_days = conflicting_comp_days.exclude(holiday=self.instance)

        for comp_day in conflicting_comp_days:
            if comp_day.session == comp_session:
                raise serializers.ValidationError(
                    {
                        "compensatory_dates": _(
                            "Compensatory date {comp_date} with session {comp_session} already exists for holiday '{holiday_name}'"
                        ).format(
                            comp_date=comp_date,
                            comp_session=comp_session,
                            holiday_name=comp_day.holiday.name,
                        )
                    }
                )
            elif (
                comp_session == CompensatoryWorkday.Session.FULL_DAY
                or comp_day.session == CompensatoryWorkday.Session.FULL_DAY
            ):
                raise serializers.ValidationError(
                    {
                        "compensatory_dates": _(
                            "Compensatory date {comp_date} with full_day session conflicts with existing {comp_session} session for holiday '{holiday_name}'"
                        ).format(
                            comp_date=comp_date,
                            comp_session=comp_day.session,
                            holiday_name=comp_day.holiday.name,
                        )
                    }
                )

    def _validate_compensatory_date_entry(self, comp_entry, start_date, end_date):
        """Validate a single compensatory date entry."""
        comp_date = comp_entry.get("date") if isinstance(comp_entry, dict) else comp_entry
        weekday = comp_date.weekday()

        self._validate_comp_date_is_weekend(comp_date, weekday)
        comp_session = self._auto_set_session(comp_entry, weekday)
        self._validate_saturday_session(comp_date, weekday, comp_session)
        self._validate_comp_date_not_in_holiday_range(comp_date, start_date, end_date)
        self._validate_comp_date_no_holiday_overlap(comp_date)
        self._validate_comp_date_no_session_conflicts(comp_date, comp_session)

    def validate(self, attrs):
        """Validate holiday data."""
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        today = timezone.localdate()

        # Check if existing record is past/present (Create doesn't have instance yet, so this only runs on Update)
        if self.instance and self.instance.start_date <= today:
            raise serializers.ValidationError(
                {"start_date": _("Cannot modify holidays that are in the past or present")}
            )

        # Check if new start_date is past/present
        if start_date and start_date <= today:
            raise serializers.ValidationError({"start_date": _("Cannot create/edit holidays in the past or present")})

        self._validate_date_range(start_date, end_date)
        self._validate_no_overlapping_holidays(start_date, end_date)

        compensatory_dates = attrs.get("compensatory_dates", [])
        for comp_entry in compensatory_dates:
            self._validate_compensatory_date_entry(comp_entry, start_date, end_date)

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create holiday and optionally create compensatory workdays."""
        compensatory_dates = validated_data.pop("compensatory_dates", [])
        holiday = super().create(validated_data)

        # Create compensatory workdays if provided
        if compensatory_dates:
            for comp_entry in compensatory_dates:
                # Extract fields from the entry (dict structure)
                comp_date = comp_entry.get("date")
                comp_session = comp_entry.get("session")
                comp_notes = comp_entry.get("notes", "")

                # Determine session based on day of week if not provided
                if not comp_session:
                    weekday = comp_date.weekday()
                    if weekday == 5:  # Saturday
                        comp_session = CompensatoryWorkday.Session.AFTERNOON
                    else:  # Sunday
                        comp_session = CompensatoryWorkday.Session.FULL_DAY

                CompensatoryWorkday.objects.create(
                    holiday=holiday,
                    date=comp_date,
                    session=comp_session,
                    notes=comp_notes,
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


class HolidayExportXLSXSerializer(FieldFilteringSerializerMixin, HolidaySerializer):
    """Detailed serializer for Holiday with compensatory days."""

    compensatory_days = serializers.SerializerMethodField(label=_("Compensatory Workdays"))

    default_fields = [
        "name",
        "start_date",
        "end_date",
        "notes",
        "compensatory_days",
    ]

    class Meta(HolidaySerializer.Meta):
        fields = HolidaySerializer.Meta.fields + ["compensatory_days"]

    def get_compensatory_days(self, obj: Holiday) -> str:
        """Get serialized compensatory days for export."""
        compensatory_days_qs = obj.compensatory_days.all().order_by("date")
        compensatory_days_list = [
            f"{comp.date} ({comp.get_session_display()})" + (f": {comp.notes}" if comp.notes else "")
            for comp in compensatory_days_qs
        ]
        return ", ".join(compensatory_days_list)
