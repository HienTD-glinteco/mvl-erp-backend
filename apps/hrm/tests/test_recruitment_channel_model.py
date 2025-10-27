from django.test import TestCase

from apps.hrm.models import RecruitmentChannel


class RecruitmentChannelModelTest(TestCase):
    """Test cases for RecruitmentChannel model"""

    def test_belong_to_choices_include_all_options(self):
        """Test that BelongTo choices include all expected options"""
        # Arrange
        expected_choices = ["job_website", "marketing", "hunt", "school"]

        # Act
        actual_choices = [choice[0] for choice in RecruitmentChannel.BelongTo.choices]

        # Assert
        self.assertEqual(len(actual_choices), 4)
        for expected in expected_choices:
            self.assertIn(expected, actual_choices)

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
        self.assertIsNotNone(channel.id)
        self.assertEqual(channel.belong_to, "hunt")
        self.assertEqual(channel.name, "LinkedIn Recruiter")

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
        self.assertIsNotNone(channel.id)
        self.assertEqual(channel.belong_to, "school")
        self.assertEqual(channel.name, "University Job Fair")

    def test_create_channel_with_job_website_belong_to(self):
        """Test creating a recruitment channel with JOB_WEBSITE belong_to option"""
        # Arrange & Act
        channel = RecruitmentChannel.objects.create(
            name="Indeed",
            code="INDEED",
            belong_to=RecruitmentChannel.BelongTo.JOB_WEBSITE,
        )

        # Assert
        self.assertIsNotNone(channel.id)
        self.assertEqual(channel.belong_to, "job_website")

    def test_create_channel_with_marketing_belong_to(self):
        """Test creating a recruitment channel with MARKETING belong_to option"""
        # Arrange & Act
        channel = RecruitmentChannel.objects.create(
            name="Facebook Ads",
            code="FB-ADS",
            belong_to=RecruitmentChannel.BelongTo.MARKETING,
        )

        # Assert
        self.assertIsNotNone(channel.id)
        self.assertEqual(channel.belong_to, "marketing")

    def test_belong_to_field_is_optional(self):
        """Test that belong_to field can be left blank"""
        # Arrange & Act
        channel = RecruitmentChannel.objects.create(
            name="Generic Channel",
            code="GENERIC",
            belong_to="",
        )

        # Assert
        self.assertIsNotNone(channel.id)
        self.assertEqual(channel.belong_to, "")

    def test_belong_to_enum_values(self):
        """Test that BelongTo enum has correct values"""
        # Assert
        self.assertEqual(RecruitmentChannel.BelongTo.JOB_WEBSITE, "job_website")
        self.assertEqual(RecruitmentChannel.BelongTo.MARKETING, "marketing")
        self.assertEqual(RecruitmentChannel.BelongTo.HUNT, "hunt")
        self.assertEqual(RecruitmentChannel.BelongTo.SCHOOL, "school")
