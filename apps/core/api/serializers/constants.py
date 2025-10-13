from rest_framework import serializers


class ConstantsResponseSerializer(serializers.Serializer):
    # This is a generic mapping: {app_name: {constant_name: value}}
    # For OpenAPI, we use a DictField of DictFields
    constants = serializers.DictField(
        child=serializers.DictField(child=serializers.JSONField()),
        help_text="Mapping of app names to their constants and choices.",
    )
