class AuditLogRegistry:
    """
    Registry for models that have audit logging enabled.

    This class tracks which models are registered for audit logging
    via the @audit_logging decorator. It provides methods to:
    - Register models when they're decorated
    - Query registered models
    - Get model information (app_label, model_name, ContentType)

    Usage:
        # Models are automatically registered when decorated
        @audit_logging
        class MyModel(models.Model):
            ...

        # Query registered models
        registered_models = AuditLogRegistry.get_all_models()
        is_registered = AuditLogRegistry.is_registered(MyModel)
        model_info = AuditLogRegistry.get_model_info(MyModel)
    """

    _registry: dict = {}  # {model_class: {'app_label': str, 'model_name': str, 'content_type': ContentType}}

    @classmethod
    def register(cls, model_class):
        """
        Register a model for audit logging.

        Args:
            model_class: The Django model class to register
        """
        if model_class not in cls._registry:
            app_label = model_class._meta.app_label
            model_name = model_class._meta.model_name

            cls._registry[model_class] = {
                "app_label": app_label,
                "model_name": model_name,
                "verbose_name": str(model_class._meta.verbose_name),
                "verbose_name_plural": str(model_class._meta.verbose_name_plural),
            }

    @classmethod
    def is_registered(cls, model_class):
        """
        Check if a model is registered for audit logging.

        Args:
            model_class: The Django model class to check

        Returns:
            bool: True if the model is registered, False otherwise
        """
        return model_class in cls._registry

    @classmethod
    def get_all_models(cls):
        """
        Get all registered model classes.

        Returns:
            list: List of registered model classes
        """
        return list(cls._registry.keys())

    @classmethod
    def get_model_info(cls, model_class):
        """
        Get information about a registered model.

        Args:
            model_class: The Django model class

        Returns:
            dict: Model information or None if not registered
        """
        return cls._registry.get(model_class)

    @classmethod
    def get_all_model_info(cls):
        """
        Get information about all registered models.

        Returns:
            dict: Dictionary mapping model classes to their info
        """
        return cls._registry.copy()

    @classmethod
    def get_content_type(cls, model_class):
        """
        Get the ContentType for a registered model.

        Args:
            model_class: The Django model class

        Returns:
            ContentType: The ContentType instance for the model
        """
        from django.contrib.contenttypes.models import ContentType

        if model_class in cls._registry:
            return ContentType.objects.get_for_model(model_class)
        return None

    @classmethod
    def clear(cls):
        """Clear the registry (useful for testing)."""
        cls._registry.clear()
