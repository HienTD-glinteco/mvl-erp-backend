from __future__ import annotations

from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.views import SpectacularAPIView


class _ClientFilteredSchemaGenerator(SchemaGenerator):
    client: str

    def get_schema(self, request=None, public=False):  # noqa: ANN001
        schema = super().get_schema(request=request, public=public)
        if not isinstance(schema, dict):
            return schema

        paths = schema.get("paths") or {}
        filtered_paths = {}

        for path, item in paths.items():
            if self.client == "mobile":
                if not path.startswith("/api/mobile/"):
                    continue
            else:
                if not path.startswith("/api/"):
                    continue
                if path.startswith("/api/mobile/"):
                    continue

            # Prefix tags to make the split explicit in Swagger UI.
            for method, operation in item.items():
                if method.lower() not in {
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "head",
                    "options",
                    "trace",
                }:
                    continue
                tags = operation.get("tags") or []
                if tags:
                    operation["tags"] = [f"{self.client.capitalize()}: {t}" for t in tags]

            filtered_paths[path] = item

        schema["paths"] = filtered_paths
        return schema


class WebSchemaGenerator(_ClientFilteredSchemaGenerator):
    client = "web"


class MobileSchemaGenerator(_ClientFilteredSchemaGenerator):
    client = "mobile"


class WebSpectacularAPIView(SpectacularAPIView):
    generator_class = WebSchemaGenerator


class MobileSpectacularAPIView(SpectacularAPIView):
    generator_class = MobileSchemaGenerator
