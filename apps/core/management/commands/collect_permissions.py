from django.apps import apps
from django.core.management.base import BaseCommand
from django.urls import get_resolver

from apps.core.models import Permission


class Command(BaseCommand):
    help = "Collect all registered permissions from views and sync to database"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Collecting permissions from views..."))

        found_permissions = []

        # 1. Collect permissions from BaseModelViewSet subclasses
        self.stdout.write("Scanning BaseModelViewSet subclasses...")
        viewset_permissions = self._collect_from_base_viewsets()
        found_permissions.extend(viewset_permissions)
        self.stdout.write(f"  Found {len(viewset_permissions)} permissions from BaseModelViewSet subclasses")

        # 2. Collect permissions from URL patterns (legacy decorator-based)
        self.stdout.write("Scanning URL patterns for decorator-based permissions...")
        url_patterns = self._get_all_url_patterns(get_resolver().url_patterns)
        for pattern in url_patterns:
            permissions = self._extract_permissions_from_pattern(pattern)
            found_permissions.extend(permissions)

        # Remove duplicates (keep first occurrence)
        unique_permissions = []
        seen_codes = set()

        for perm in found_permissions:
            if perm["code"] not in seen_codes:
                unique_permissions.append(perm)
                seen_codes.add(perm["code"])

        # Sync permissions to database
        created_count = 0
        updated_count = 0

        for perm_data in unique_permissions:
            code = perm_data["code"]
            description = perm_data.get("description", "")
            module = perm_data.get("module", "")
            submodule = perm_data.get("submodule", "")
            name = perm_data.get("name", "")
            name = f"[{module}] [{submodule}] {name}"

            permission, created = Permission.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": description,
                    "module": module,
                    "submodule": submodule,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully collected {len(unique_permissions)} permissions "
                f"({created_count} created, {updated_count} updated)"
            )
        )

    def _get_all_url_patterns(self, url_patterns, parent_pattern=""):
        """Recursively get all URL patterns including nested ones"""
        patterns = []
        for pattern in url_patterns:
            # Check if it's a nested URLconf (has url_patterns attribute)
            if hasattr(pattern, "url_patterns"):
                # Recursively process nested patterns
                patterns.extend(self._get_all_url_patterns(pattern.url_patterns, parent_pattern))
            else:
                patterns.append(pattern)
        return patterns

    def _extract_permissions_from_pattern(self, pattern):
        """Extract permission metadata from a URL pattern"""
        permissions = []

        callback = pattern.callback
        if callback is None:
            return permissions

        # For function-based views
        if hasattr(callback, "_permission_code"):
            permissions.append(self._get_permission_tuple(callback))
            return permissions

        # For class-based views
        if hasattr(callback, "view_class"):
            permissions.extend(self._extract_from_view_class(callback.view_class))

        # For ViewSets (DRF routers)
        if hasattr(callback, "cls"):
            permissions.extend(self._extract_from_viewset(callback.cls))

        return permissions

    def _get_permission_tuple(self, obj):
        """Get permission code, name, description, module and submodule from an object"""
        code = obj._permission_code
        name = getattr(obj, "_permission_name", "")
        description = getattr(obj, "_permission_description", "")
        module = getattr(obj, "_permission_module", "")
        submodule = getattr(obj, "_permission_submodule", "")
        return {
            "code": code,
            "name": name,
            "description": description,
            "module": module,
            "submodule": submodule,
        }

    def _extract_from_view_class(self, view_class):
        """Extract permissions from a class-based view"""
        permissions = []
        http_methods = ["get", "post", "put", "patch", "delete", "head", "options"]

        for method_name in http_methods:
            if hasattr(view_class, method_name):
                method = getattr(view_class, method_name)
                if hasattr(method, "_permission_code"):
                    permissions.append(self._get_permission_tuple(method))

        return permissions

    def _extract_from_viewset(self, view_class):
        """Extract permissions from a viewset"""
        permissions = []
        standard_actions = ["list", "retrieve", "create", "update", "partial_update", "destroy"]

        # Check standard viewset actions
        for action_name in standard_actions:
            if hasattr(view_class, action_name):
                action = getattr(view_class, action_name)
                if hasattr(action, "_permission_code"):
                    permissions.append(self._get_permission_tuple(action))

        # Check custom actions
        for attr_name in dir(view_class):
            if not attr_name.startswith("_"):
                attr = getattr(view_class, attr_name)
                if callable(attr) and hasattr(attr, "_permission_code"):
                    perm_tuple = self._get_permission_tuple(attr)
                    if perm_tuple not in permissions:
                        permissions.append(perm_tuple)

        return permissions

    def _collect_from_base_viewsets(self):
        """Collect permissions from all BaseModelViewSet and BaseReadOnlyModelViewSet subclasses"""
        from libs.drf.mixin.permission import PermissionRegistrationMixin

        permissions = []

        # Iterate through all installed apps
        for app_config in apps.get_app_configs():
            # Only process internal apps
            if not app_config.name.startswith("apps."):
                continue

            # Try to import views module from the app (check both api.views and views)
            views_modules = []

            # Try api.views first
            try:
                views_module = __import__(f"{app_config.name}.api.views", fromlist=[""])
                views_modules.append(views_module)
            except (ImportError, ModuleNotFoundError):
                pass

            # Also try views directly in the app
            try:
                views_module = __import__(f"{app_config.name}.views", fromlist=[""])
                views_modules.append(views_module)
            except (ImportError, ModuleNotFoundError):
                pass

            # Find all PermissionRegistrationMixin subclasses in the modules
            for views_module in views_modules:
                for attr_name in dir(views_module):
                    attr = getattr(views_module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, PermissionRegistrationMixin)
                        and attr is not PermissionRegistrationMixin
                        and hasattr(attr, "get_registered_permissions")
                    ):
                        # Get registered permissions from the viewset
                        viewset_permissions = attr.get_registered_permissions()
                        permissions.extend(viewset_permissions)

        return permissions
