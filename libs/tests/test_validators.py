import pytest
from django.core.exceptions import ValidationError

from libs.drf.validators import HTMLContentMaxLengthValidator


class TestHTMLContentMaxLengthValidator:
    def test_clean_extracts_text_length(self):
        validator = HTMLContentMaxLengthValidator(limit_value=10)
        html = "<p>12345</p>"
        # Text is "12345" (length 5)
        length = validator.clean(html)
        assert length == 5

    def test_clean_handles_empty_value(self):
        validator = HTMLContentMaxLengthValidator(limit_value=10)
        assert validator.clean("") == 0
        assert validator.clean(None) == 0

    def test_clean_strips_tags_for_length_calculation(self):
        validator = HTMLContentMaxLengthValidator(limit_value=10)
        html = "<p><b>123</b>45</p>"
        # get_text(separator=" ") inserts space between boolean element and text node
        length = validator.clean(html)
        assert length == 6  # "123 45"

    def test_compare_logic(self):
        validator = HTMLContentMaxLengthValidator(limit_value=5)
        # 6 > 5 should return True (error)
        assert validator.compare(6, 5) is True
        # 5 > 5 should return False (ok)
        assert validator.compare(5, 5) is False
        # 4 > 5 should return False (ok)
        assert validator.compare(4, 5) is False

    def test_call_raises_validation_error_on_exceed(self):
        validator = HTMLContentMaxLengthValidator(limit_value=5)
        html = "<p>123456</p>"  # length 6
        with pytest.raises(ValidationError) as ex:
            validator(html)
            assert "Ensure this value has at most 5 characters" in str(ex)
            assert "it has 6" in str(ex)

    def test_call_passes_valid_length(self):
        validator = HTMLContentMaxLengthValidator(limit_value=10)
        html = "<p>12345</p>"
        validator(html)  # Should not raise
