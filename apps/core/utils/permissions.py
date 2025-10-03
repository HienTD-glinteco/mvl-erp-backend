from functools import wraps


def register_permission(code: str, description: str):
    """
    Decorator to register permission metadata on a view function or method.

    This decorator attaches permission code and description to the view,
    which will be collected by the collect_permissions management command
    and checked by the RoleBasedPermission class.

    Args:
        code: Unique permission code (e.g., "document.create")
        description: Human-readable description of the permission

    Example:
        @api_view(["POST"])
        @register_permission("document.create", "Tạo tài liệu")
        def document_create(request):
            ...
    """

    def decorator(view_func):
        view_func._permission_code = code
        view_func._permission_description = description

        @wraps(view_func)
        def wrapper(*args, **kwargs):
            return view_func(*args, **kwargs)

        return wrapper

    return decorator
