from bs4 import BeautifulSoup
from django.core.validators import MaxLengthValidator
from django.utils.deconstruct import deconstructible


@deconstructible
class HTMLContentMaxLengthValidator(MaxLengthValidator):
    def compare(self, a, b):
        return a > b

    def clean(self, x):
        if not x:
            return 0
        soup = BeautifulSoup(x, "html.parser")
        text_content = soup.get_text(separator=" ", strip=True)
        return len(text_content)
