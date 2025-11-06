from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

CitizenIdValidator = RegexValidator(
    regex=r"^\d{9,12}$",
    message=_("Citizen ID must contain from 9 to 12 digits"),
)
