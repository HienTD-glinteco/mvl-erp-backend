from rest_framework import serializers

class CurrentEmployeeDefault:
    """
    Returns the current employee from the request context.
    """
    requires_context = True

    def __call__(self, serializer_field):
        request = serializer_field.context['request']
        if hasattr(request.user, 'employee'):
             return request.user.employee
        return None
