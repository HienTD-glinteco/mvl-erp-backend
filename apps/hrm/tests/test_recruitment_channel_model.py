import pytest

from apps.hrm.models import RecruitmentChannel
from libs.models import SafeTextField


@pytest.mark.django_db
class TestRecruitmentChannelModel:
    """Test cases for RecruitmentChannel model"""

    def test_belong_to_choices_include_all_options(self):
        """Test that BelongTo choices include all expected options"""
        # Arrange
        expected_choices = ["job_website", "marketing", "hunt", "school", "other"]

        # Act
        actual_choices = [choice[0] for choice in RecruitmentChannel.BelongTo.choices]

        # Assert
        assert len(actual_choices) == 5
        for expected in expected_choices:
            assert expected in actual_choices

    def test_create_channel_with_hunt_belong_to(self):
        """Test creating a recruitment channel with HUNT belong_to option"""
        # Arrange & Act
        channel = RecruitmentChannel.objects.create(
            name="LinkedIn Recruiter",
            code="LI-HUNT",
            belong_to=RecruitmentChannel.BelongTo.HUNT,
            description="Headhunting via LinkedIn",
        )

        # Assert
        assert channel.id is not None
        assert channel.belong_to == "hunt"
        assert channel.name == "LinkedIn Recruiter"

    def test_create_channel_with_school_belong_to(self):
        """Test creating a recruitment channel with SCHOOL belong_to option"""
        # Arrange & Act
        channel = RecruitmentChannel.objects.create(
            name="University Job Fair",
            code="UNI-FAIR",
            belong_to=RecruitmentChannel.BelongTo.SCHOOL,
            description="Recruiting from universities",
        )

        # Assert
        assert channel.id is not None
        assert channel.belong_to == "school"
        assert channel.name == "University Job Fair"

    def test_create_channel_with_job_website_belong_to(self):
        """Test creating a recruitment channel with JOB_WEBSITE belong_to option"""
        # Arrange & Act
        channel = RecruitmentChannel.objects.create(
            name="Indeed",
            code="INDEED",
            belong_to=RecruitmentChannel.BelongTo.JOB_WEBSITE,
        )

        # Assert
        assert channel.id is not None
        assert channel.belong_to == "job_website"

    def test_create_channel_with_marketing_belong_to(self):
        """Test creating a recruitment channel with MARKETING belong_to option"""
        # Arrange & Act
        channel = RecruitmentChannel.objects.create(
            name="Facebook Ads",
            code="FB-ADS",
            belong_to=RecruitmentChannel.BelongTo.MARKETING,
        )

        # Assert
        assert channel.id is not None
        assert channel.belong_to == "marketing"

    def test_belong_to_field_is_optional(self):
        """Test that belong_to field can be left blank"""
        # Arrange & Act
        channel = RecruitmentChannel.objects.create(
            name="Generic Channel",
            code="GENERIC",
            belong_to="",
        )

        # Assert
        assert channel.id is not None
        assert channel.belong_to == ""

    def test_create_channel_with_other_belong_to(self):
        """Test creating a recruitment channel with OTHER belong_to option"""
        # Arrange & Act
        channel = RecruitmentChannel.objects.create(
            name="Employee Referral",
            code="EMP-REF",
            belong_to=RecruitmentChannel.BelongTo.OTHER,
            description="Referrals from current employees",
        )

        # Assert
        assert channel.id is not None
        assert channel.belong_to == "other"
        assert channel.name == "Employee Referral"

    def test_belong_to_enum_values(self):
        """Test that BelongTo enum has correct values"""
        # Assert
        assert RecruitmentChannel.BelongTo.JOB_WEBSITE == "job_website"
        assert RecruitmentChannel.BelongTo.MARKETING == "marketing"
        assert RecruitmentChannel.BelongTo.HUNT == "hunt"
        assert RecruitmentChannel.BelongTo.SCHOOL == "school"
        assert RecruitmentChannel.BelongTo.OTHER == "other"

    def test_name_field_max_length_is_250(self):
        """Test that name field enforces the 250 character limit"""
        name_field = RecruitmentChannel._meta.get_field("name")

        assert name_field.max_length == 250

    def test_description_field_is_safe_text_with_max_length(self):
        """Test that description uses SafeTextField with 500 character limit"""
        description_field = RecruitmentChannel._meta.get_field("description")

        assert isinstance(description_field, SafeTextField)
        assert description_field.max_length == 500
