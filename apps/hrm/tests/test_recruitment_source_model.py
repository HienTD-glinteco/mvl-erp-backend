import pytest

from apps.hrm.models import RecruitmentSource
from libs.models import SafeTextField


@pytest.mark.django_db
class TestRecruitmentSourceModel:
    """Test cases for RecruitmentSource model field configuration"""

    def test_name_field_max_length_is_250(self):
        """Ensure the name field enforces a 250 character limit"""
        name_field = RecruitmentSource._meta.get_field("name")

        assert name_field.max_length == 250

    def test_description_field_is_safe_text_with_max_length(self):
        """Ensure the description field uses SafeTextField with 500 character limit"""
        description_field = RecruitmentSource._meta.get_field("description")

        assert isinstance(description_field, SafeTextField)
        assert description_field.max_length == 500

    def test_allow_referral_default_is_false(self):
        """Ensure allow_referral defaults to False at the model level"""
        source = RecruitmentSource(name="Test Source")

        assert source.allow_referral is False
