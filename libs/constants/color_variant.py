"""Color variants for status display."""

from django.db import models


class ColorVariant(models.TextChoices):
    """Available color variants for status representation"""

    GREEN = "GREEN", "Green"
    BLUE = "BLUE", "Blue"
    YELLOW = "YELLOW", "Yellow"
    PURPLE = "PURPLE", "Purple"
    RED = "RED", "Red"
    ORANGE = "ORANGE", "Orange"
    GREY = "GREY", "Grey"
