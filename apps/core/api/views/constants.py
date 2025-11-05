import importlib
import inspect
from typing import Any

from django.apps import apps
from django.db import models
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api.serializers import ConstantsResponseSerializer


class ConstantsView(APIView):
    """
    API endpoint to retrieve application constants from constants.py files
    and model field choices/enums across all installed apps.
    """

    serializer_class = ConstantsResponseSerializer

    @extend_schema(
        summary="Get application constants",
        description="Retrieve all application constants from constants.py files and model choices/enums. "
        "Supports filtering by module names using the 'modules' query parameter.",
        parameters=[
            OpenApiParameter(
                name="modules",
                description="Comma-separated list of module names to filter constants (e.g., 'core,hrm')",
                required=False,
                type=str,
            ),
        ],
        tags=["Constants"],
    )
    def get(self, request):
        """Get constants from all apps or filtered by module names"""
        modules_param = request.query_params.get("modules")
        filter_modules = set(modules_param.split(",")) if modules_param else None

        constants_data = {}

        # Get all internal apps (those starting with 'apps.')
        for app_config in apps.get_app_configs():
            if not app_config.name.startswith("apps."):
                continue

            # Extract app name (e.g., 'core' from 'apps.core')
            app_name = app_config.name.split(".")[-1]

            # Apply module filter if specified
            if filter_modules and app_name not in filter_modules:
                continue

            # Collect constants from this app
            app_constants = {}

            # 1. Try to import constants.py from the app
            try:
                constants_module = importlib.import_module(f"{app_config.name}.constants")
                app_constants.update(self._extract_constants_from_module(constants_module))
            except ModuleNotFoundError:
                # No constants.py file in this app, skip
                pass

            # 2. Extract choices/enums from models
            models_constants = self._extract_model_constants(app_config)
            app_constants.update(models_constants)

            # Only add to result if we found any constants
            if app_constants:
                constants_data[app_name] = app_constants

        # Return empty dict if no constants found (middleware will convert to None)
        return Response(constants_data if constants_data else {}, status=status.HTTP_200_OK)

    def _extract_constants_from_module(self, module) -> dict[str, Any]:
        """
        Extract constants from a constants.py module.
        Returns constants that are uppercase and not private.
        """
        constants: dict[str, Any] = {}

        for name in dir(module):
            if name.startswith("_"):
                continue

            value = getattr(module, name)

            # If it's a class, collect its public non-callable attributes as nested constants
            if inspect.isclass(value):
                class_constants = self._extract_public_class_attrs(value)
                if class_constants:
                    constants[name] = class_constants
                continue

            # Module-level constants: keep existing rule (uppercase, non-callable, non-module)
            if name.isupper() and not (inspect.ismodule(value) or callable(value)):
                # Convert sets to lists for JSON serialization
                if isinstance(value, set):
                    value = list(value)
                constants[name] = value

        return constants

    def _extract_public_class_attrs(self, cls_obj) -> dict[str, Any]:
        """Extract public, non-callable, non-module/class attributes from a class.

        If the class implements a lazy population method named `refresh`, it will
        be invoked once before extracting attributes (best-effort; exceptions are swallowed).
        """
        # Attempt lazy population if available
        refresh = getattr(cls_obj, "refresh", None)

        if callable(refresh):
            refresh()

        result: dict[str, Any] = {}

        # Support django enum
        if hasattr(cls_obj, "_member_map_"):
            for member in cls_obj._member_map_.values():
                attr_name = member.value
                attr_value = member.label
                result[attr_name] = attr_value
        else:
            for attr_name, attr_value in vars(cls_obj).items():
                if attr_name.startswith("_"):
                    continue
                if (
                    inspect.isroutine(attr_value)
                    or isinstance(attr_value, (staticmethod, classmethod, property))
                    or inspect.isclass(attr_value)
                    or inspect.ismodule(attr_value)
                ):
                    continue
                result[attr_name] = attr_value

        return result

    def _extract_model_constants(self, app_config) -> dict[str, Any]:
        """
        Extract choices and enums from Django model fields.
        """
        model_constants = {}

        for model in app_config.get_models():
            model_name = model.__name__

            # Check each field for choices
            for field in model._meta.get_fields():
                if not hasattr(field, "choices") or not field.choices:
                    continue

                # Get the choices
                choices = field.choices

                # Determine the constant name
                # First check if there's a nested Choices class
                choices_class = None
                field_name_upper = field.name.upper()

                # Look for IntegerChoices or TextChoices inner classes
                for attr_name in dir(model):
                    attr = getattr(model, attr_name)
                    if (
                        inspect.isclass(attr)
                        and issubclass(attr, models.Choices)
                        and hasattr(field, "choices")
                        and attr.choices == field.choices
                    ):
                        choices_class = attr
                        break

                if choices_class:
                    # Use the class name for the constant
                    constant_name = f"{model_name}_{choices_class.__name__}"
                else:
                    # Fallback to field name
                    constant_name = f"{model_name}_{field_name_upper}_CHOICES"

                # Format choices as list of dicts with value and label
                formatted_choices = [{value: str(label)} for value, label in choices]

                model_constants[constant_name] = formatted_choices

        return model_constants
