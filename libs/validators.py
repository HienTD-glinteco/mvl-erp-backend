from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

CitizenIdValidator = RegexValidator(
    regex=r"^\d{12}$",
    message=_("Citizen ID must contain exactly 12 digits"),
)
