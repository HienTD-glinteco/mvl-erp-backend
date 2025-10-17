import pytest

from libs.strings import clean_html


@pytest.mark.parametrize(
    "html,expected",
    [
        ("<b>Bold</b>", "<b>Bold</b>"),
        ("<script>alert('x')</script>Safe", "Safe"),
        ("<a href='http://example.com'>Link</a>", '<a href="http://example.com" rel="noopener noreferrer">Link</a>'),
        ("Plain text", "Plain text"),
        ("<div>Test<br>Line</div>", "<div>Test<br>Line</div>"),
        ("<img src='x' onerror='alert(1)'>", '<img src="x">'),
        ("<p>Allowed <strong>strong</strong></p>", "<p>Allowed <strong>strong</strong></p>"),
    ],
)
def test_clean_html_removes_unsafe_tags(html, expected):
    # Arrange is handled by parametrize

    # Act
    result = clean_html(html)

    # Assert
    assert result == expected
