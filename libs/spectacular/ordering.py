from typing import List

from drf_spectacular.extensions import OpenApiFilterExtension, _SchemaType
from drf_spectacular.openapi import AutoSchema


class AutoDocOrderingFilterExtension(OpenApiFilterExtension):
    target_class = "rest_framework.filters.OrderingFilter"

    def __init__(self, target=None):
        # Allow instantiation without providing a target for testing purposes
        super().__init__(target or self.target_class)

    def get_schema_operation_parameters(self, auto_schema: "AutoSchema", *args, **kwargs) -> List[_SchemaType]:
        view = auto_schema.view
        ordering_fields = getattr(view, "ordering_fields", None)
        ordering = getattr(view, "ordering", None)

        if not ordering_fields:
            return []

        fields = ", ".join(f"`{f}`" for f in ordering_fields)
        description = (
            f"- Supported fields: {fields}.\n"
            "- Use a `-` prefix before a field for descending order.\n"
            "- Multiple fields can be specified, separated by a comma `,`; the ordering will be applied in the order the fields are listed."
        )

        default_ordering = ""
        if ordering:
            ordering = [ordering] if isinstance(ordering, str) else ordering
            default_ordering = ", ".join(f"`{f}`" for f in ordering)
            description = f"{description}\n- Default ordering: {default_ordering}"

        return [
            {
                "name": "ordering",
                "required": False,
                "in": "query",
                "schema": {"type": "string"},
                "description": description,
            }
        ]
