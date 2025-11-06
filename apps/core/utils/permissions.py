def register_permission(code: str, description: str, module: str = "", submodule: str = "", name: str = ""):
    """
    Decorator to register permission metadata on a view function or method.

    This decorator attaches permission code, name, description, module and submodule to the view,
    which will be collected by the collect_permissions management command
    and checked by the RoleBasedPermission class.

    IMPORTANT: When using with @api_view, @register_permission must be applied BEFORE @api_view:
        @register_permission(...)  # This must come FIRST
        @api_view([...])           # Then this
        @permission_classes([...]) # Then this

    Args:
        code: Unique permission code (e.g., "document.create")
        description: Human-readable description of the permission
        module: Module/system the permission belongs to (e.g., "HRM", "Document Management")
        submodule: Sub-module within the main module (e.g., "Employee Profile", "Payroll")
        name: Human-readable name of the permission (e.g., "Create Document")

    Example:
        @register_permission(
            "document.create",
            "Create document",
            module="Document Management",
            submodule="Documents",
            name="Create Document"
        )
        @api_view(["POST"])
        @permission_classes([RoleBasedPermission])
        def document_create(request):
            ...
    """

    def decorator(view_func):
        # Set attributes on the original function
        view_func._permission_code = code
        view_func._permission_description = description
        view_func._permission_module = module
        view_func._permission_submodule = submodule
        view_func._permission_name = name

        # If view_func is already wrapped by @api_view (has cls attribute)
        # also set attributes on the cls (the wrapped view class)
        if hasattr(view_func, "cls"):
            view_func.cls._permission_code = code
            view_func.cls._permission_description = description
            view_func.cls._permission_module = module
            view_func.cls._permission_submodule = submodule
            view_func.cls._permission_name = name

        # Return the original function (no need to wrap again)
        return view_func

    return decorator
