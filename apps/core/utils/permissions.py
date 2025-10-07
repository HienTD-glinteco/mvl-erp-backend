from functools import wraps


def register_permission(code: str, description: str, module: str = "", submodule: str = ""):
    """
    Decorator to register permission metadata on a view function or method.

    This decorator attaches permission code, description, module and submodule to the view,
    which will be collected by the collect_permissions management command
    and checked by the RoleBasedPermission class.

    Args:
        code: Unique permission code (e.g., "document.create")
        description: Human-readable description of the permission
        module: Module/system the permission belongs to (e.g., "HRM", "Document Management")
        submodule: Sub-module within the main module (e.g., "Employee Profile", "Payroll")

    Example:
        @api_view(["POST"])
        @register_permission(
            "document.create",
            "Create document",
            module="Document Management",
            submodule="Documents"
        )
        def document_create(request):
            ...
    """

    def decorator(view_func):
        view_func._permission_code = code
        view_func._permission_description = description
        view_func._permission_module = module
        view_func._permission_submodule = submodule

        @wraps(view_func)
        def wrapper(*args, **kwargs):
            return view_func(*args, **kwargs)

        return wrapper

    return decorator
