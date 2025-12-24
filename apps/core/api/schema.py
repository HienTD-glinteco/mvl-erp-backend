from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ClientAwareJWTAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = "apps.core.api.authentication.ClientAwareJWTAuthentication"
    name = "clientAwareJWTAuthentication"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT authentication with client validation",
        }
