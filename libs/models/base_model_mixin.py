from django.db import models
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["created_at"]


class AutoCodeMixin(models.Model):
    """Mixin that provides automatic temporary code generation for new instances.

    This mixin automatically generates a temporary code for new model instances
    that don't have a code yet. The temporary code uses a configurable prefix
    followed by a random string to avoid collisions.

    The temporary code is later replaced by the final code through a signal handler
    that uses the instance ID and the model's CODE_PREFIX attribute.

    Attributes:
        TEMP_CODE_PREFIX: Class attribute that defines the temporary code prefix.
                         Defaults to "TEMP_" if not specified.

    Example:
        class Branch(AutoCodeMixin, BaseModel):
            CODE_PREFIX = "CN"
            TEMP_CODE_PREFIX = "TEMP_"  # Optional, defaults to "TEMP_"
            code = models.CharField(max_length=50, unique=True)
            name = models.CharField(max_length=200)
    """

    TEMP_CODE_PREFIX: str = "TEMP_"
    CODE_PREFIX: str = ""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Override save to set temporary code for new instances."""
        # Set temporary code for new instances that don't have a code yet
        # Use random string to avoid collisions, not all, but most of the time.
        if self._state.adding and hasattr(self, "code") and not self.code:
            temp_prefix = getattr(self.__class__, "TEMP_CODE_PREFIX", "TEMP_")
            self.code = f"{temp_prefix}{get_random_string(20)}"
        super().save(*args, **kwargs)


class BaseReportModel(BaseModel):
    """Base model for all report models.

    Provides common fields and behavior for report models including
    report_date, need_refresh flag, and standard ordering by report_date descending.
    
    The need_refresh field is used by batch tasks to identify reports that need
    recalculation due to source data changes (including deletions).
    """

    report_date = models.DateField(verbose_name=_("Report date"))
    need_refresh = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Needs refresh"),
        help_text=_("Indicates if this report needs to be recalculated by batch task"),
    )

    class Meta:
        abstract = True
        ordering = ["-report_date"]
