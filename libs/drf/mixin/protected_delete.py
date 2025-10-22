"""
Mixin for Django REST Framework ViewSets to validate protected related objects before deletion.

This mixin ensures that objects with protected foreign key relationships cannot be
accidentally deleted without proper warning to the user.
"""

from django.db.models import ProtectedError
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response


class ProtectedDeleteMixin:
    """
    Mixin for DRF ViewSets to validate protected related objects before deletion.

    This mixin overrides the destroy() method to catch ProtectedError exceptions
    and return a user-friendly error message when attempting to delete an object
    that has protected related objects.

    Usage:
        class RoleViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
            queryset = Role.objects.all()
            serializer_class = RoleSerializer

    When a user tries to delete an object with protected relationships, they will
    receive a 400 Bad Request response with a clear message indicating which
    related objects are preventing the deletion.

    Example error response:
        {
            "success": false,
            "error": {
                "detail": "Cannot delete this Role because it is referenced by: 5 Users",
                "protected_objects": [
                    {
                        "count": 5,
                        "name": "Users",
                        "protected_object_ids": [1, 2, 3, 4, 5]
                    }
                ]
            }
        }
    """

    def destroy(self, request, *args, **kwargs):
        """
        Delete an object with validation for protected relationships.

        Attempts to delete the object and catches ProtectedError if the object
        has protected related objects. Returns a user-friendly error message
        with details about which objects are preventing deletion.

        Args:
            request: The HTTP request object
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments

        Returns:
            Response: HTTP 204 on success, HTTP 400 if protected objects exist
        """
        instance = self.get_object()

        try:
            self.perform_destroy(instance)
        except ProtectedError as e:
            # Build a user-friendly error message
            error_detail = self._format_protected_error(instance, e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def _format_protected_error(self, instance, error):
        """
        Format a ProtectedError into a user-friendly error message.

        Args:
            instance: The model instance being deleted
            error: The ProtectedError exception

        Returns:
            dict: Formatted error response with details about protected objects
        """
        # Get the model name for the instance being deleted
        model_name = instance._meta.verbose_name

        # Extract protected objects from the error
        protected_objects = error.protected_objects

        # Group protected objects by model type
        objects_by_model = {}
        for obj in protected_objects:
            model_class = obj.__class__
            model_verbose_name = model_class._meta.verbose_name_plural

            if model_verbose_name not in objects_by_model:
                objects_by_model[model_verbose_name] = {
                    "count": 0,
                    "name": str(model_verbose_name),
                    "protected_object_ids": [],
                }
            objects_by_model[model_verbose_name]["count"] += 1
            objects_by_model[model_verbose_name]["protected_object_ids"].append(obj.pk)

        # Build the main error message
        protected_list = objects_by_model.values()
        if protected_list:
            # Create a human-readable list of protected relationships
            relationship_descriptions = []
            for protected_info in protected_list:
                count = protected_info["count"]
                name = protected_info["name"]
                relationship_descriptions.append(f"{count} {name}")

            relationships_text = ", ".join(relationship_descriptions)
            detail_message = _("Cannot delete this {model_name} because it is referenced by: {relationships}").format(
                model_name=model_name, relationships=relationships_text
            )
        else:
            detail_message = _("Cannot delete this {model_name} because it has protected relationships").format(
                model_name=model_name
            )

        return {"detail": detail_message, "protected_objects": list(protected_list)}
