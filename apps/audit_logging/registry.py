class AuditLogRegistry:
    """
    Registry for models that have audit logging enabled.

    This class tracks which models are registered for audit logging
    via the @audit_logging decorator. It provides methods to:
    - Register models when they're decorated
    - Query registered models
    - Get model information (app_label, model_name, ContentType)
    - Track AUDIT_LOG_TARGET relationships for dependent models

    Usage:
        # Models are automatically registered when decorated
        @audit_logging
        class MyModel(models.Model):
            ...

        # Dependent models can declare an AUDIT_LOG_TARGET
        @audit_logging
        class DependentModel(models.Model):
            AUDIT_LOG_TARGET = 'app_label.ModelName'  # or reference to model class
            ...

        # Query registered models
        registered_models = AuditLogRegistry.get_all_models()
        is_registered = AuditLogRegistry.is_registered(MyModel)
        model_info = AuditLogRegistry.get_model_info(MyModel)
    """

    _registry: dict = {}  # {model_class: {'app_label': str, 'model_name': str, 'audit_log_target': model_class or str or None}}
    _targets_resolved: bool = False

    @classmethod
    def register(cls, model_class):
        """
        Register a model for audit logging.

        String AUDIT_LOG_TARGET references are stored as-is and resolved later
        in resolve_targets() after all models are loaded.

        Args:
            model_class: The Django model class to register
        """
        if model_class not in cls._registry:
            app_label = model_class._meta.app_label
            model_name = model_class._meta.model_name

            # Check if model has AUDIT_LOG_TARGET attribute
            # Store as-is (string or class reference), resolve later
            audit_log_target = getattr(model_class, "AUDIT_LOG_TARGET", None)

            cls._registry[model_class] = {
                "app_label": app_label,
                "model_name": model_name,
                "verbose_name": model_class._meta.verbose_name,
                "verbose_name_plural": model_class._meta.verbose_name_plural,
                "audit_log_target": audit_log_target,
            }

    @classmethod
    def resolve_targets(cls):
        """
        Resolve all string-based AUDIT_LOG_TARGET references to actual model classes.
        
        This should be called after all models are loaded (e.g., in AppConfig.ready()).
        
        Raises:
            ValueError: If any AUDIT_LOG_TARGET cannot be resolved
        """
        if cls._targets_resolved:
            return

        from django.apps import apps

        for model_class, info in cls._registry.items():
            audit_log_target = info.get("audit_log_target")
            
            if isinstance(audit_log_target, str):
                try:
                    resolved_target = apps.get_model(audit_log_target)
                    info["audit_log_target"] = resolved_target
                except (LookupError, ValueError) as e:
                    raise ValueError(
                        f"Invalid AUDIT_LOG_TARGET '{audit_log_target}' for model "
                        f"{model_class.__name__}: {e}"
                    )

        cls._targets_resolved = True

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
    def get_audit_log_target(cls, model_class):
        """
        Get the audit log target for a model (if it has one).

        Args:
            model_class: The Django model class

        Returns:
            The target model class if set, otherwise None
        """
        model_info = cls.get_model_info(model_class)
        if model_info:
            return model_info.get("audit_log_target")
        return None

    @classmethod
    def clear(cls):
        """Clear the registry (useful for testing)."""
        cls._registry.clear()
