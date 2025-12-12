"""Helper functions for generating model codes."""

from django.db.models.signals import post_save


def generate_model_code(instance) -> str:
    """Generate a code for a model instance based on its ID and class prefix.

    The code format is: {PREFIX}{subcode}
    where subcode is the instance ID zero-padded to at least 3 digits.

    Args:
        instance: Model instance that has a CODE_PREFIX class attribute.
                  The instance must have an id attribute.

    Returns:
        Generated code string (e.g., "BL001", "BL012", "BL444", "BL5555")

    Example:
        class Block(models.Model):
            CODE_PREFIX = "BL"
            ...

        block = Block(id=1)
        code = generate_model_code(block)  # Returns "BL000000001"
    """
    if not hasattr(instance.__class__, "CODE_PREFIX"):
        raise AttributeError(f"{instance.__class__.__name__} must have a CODE_PREFIX class attribute")

    if not hasattr(instance, "id") or instance.id is None:
        raise ValueError("Instance must have an id to generate code")

    prefix = instance.__class__.CODE_PREFIX
    instance_id = instance.id
    subcode = str(instance_id).zfill(9)

    return f"{prefix}{subcode}"


def create_auto_code_signal_handler(temp_code_prefix: str, custom_generate_code=None):
    """Factory that returns a post-save signal handler for auto-generating model codes.

    The returned handler will, for newly created instances whose current `code`
    value starts with `temp_code_prefix`, generate a final code and persist it.

    Behavior and side-effects:
    - When `created` is True and `instance.code` exists and begins with
      `temp_code_prefix`, the handler will attempt to generate a permanent code.
    - If `custom_generate_code` is provided, it will be called with the
      instance and is responsible for assigning and saving `instance.code`.
      The custom function may implement retries or alternate persistence logic.
    - If no custom generator is provided, `generate_model_code(instance)` will be
      used and `instance.save(update_fields=["code"])` will be called to persist
      only the `code` field, avoiding recursive signal invocation.

    Args:
        temp_code_prefix: Prefix identifying temporary placeholder codes (e.g. "TEMP_").
        custom_generate_code: Optional callable(instance) -> None or str. If it
            returns a string it will be used as the code; if it handles saving
            itself it may return None.

    Returns:
        Callable[[type, object, bool], None]: A signal handler function with
        the signature `(sender, instance, created, **kwargs)` suitable for
        connecting to `post_save`.

    Example:
        auto_code_handler = create_auto_code_signal_handler("TEMP_")
        post_save.connect(auto_code_handler, sender=Branch)
    """

    def signal_handler(sender, instance, created, **kwargs):
        """Auto-generate code for model instances when created.

        This signal handler generates a unique code for newly created instances.
        It uses the instance ID to create a code in the format: {PREFIX}{subcode}

        Args:
            sender: The model class
            instance: The model instance being saved
            created: Boolean indicating if this is a new instance
            **kwargs: Additional keyword arguments from the signal

        Note:
            We use update_fields parameter and check if code starts with temp_code_prefix
            to prevent infinite loop from the save() call inside the signal.
        """
        # Only generate code for new instances that have a temporary code
        if created and hasattr(instance, "code") and instance.code and instance.code.startswith(temp_code_prefix):
            if custom_generate_code:
                # let custom_generate_code handle the code generation and saving, or even retry logic
                custom_generate_code(instance)
            else:
                instance.code = generate_model_code(instance)
                # Use update_fields to prevent triggering the signal again (avoid infinite loop)
                instance.save(update_fields=["code"])

    return signal_handler


def register_auto_code_signal(*models, temp_code_prefix: str = "TEMP_", custom_generate_code=None):
    """Connect an auto-code generation handler to `post_save` for models.

    This convenience wrapper constructs the handler via
    `create_auto_code_signal_handler` and connects it to Django's
    `post_save` signal for each supplied model class.

    Behavior:
    - For every provided `model`, the returned handler will be connected as a
      receiver for `post_save(sender=model)`. The handler will only act when
      a new instance is created and its `code` value starts with
      `temp_code_prefix`.
    - If `custom_generate_code` is provided it will be invoked with the
      instance; otherwise a default generator (`generate_model_code`) will be
      used and the code persisted with `instance.save(update_fields=["code"])`.

    Args:
        *models: One or more Django model classes to register the handler for.
        temp_code_prefix: Prefix that identifies placeholder/temporary codes
            that should be replaced (default: "TEMP_").
        custom_generate_code: Optional callable(instance) used to generate and
            optionally persist the final code. If it returns a string, the
            handler will assign that string to `instance.code` and save it;
            if it performs its own save it may return None.

    Returns:
        None

    Example:
        from apps.hrm.models import Branch, Block
        register_auto_code_signal(Branch, Block, temp_code_prefix="TEMP_")
    """
    handler = create_auto_code_signal_handler(temp_code_prefix, custom_generate_code=custom_generate_code)

    for model in models:
        post_save.connect(handler, sender=model, weak=False)
