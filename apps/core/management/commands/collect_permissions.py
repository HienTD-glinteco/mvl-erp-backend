from django.core.management.base import BaseCommand
from django.urls import get_resolver

from apps.core.models import Permission


class Command(BaseCommand):
    help = "Collect all registered permissions from views and sync to database"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Collecting permissions from views..."))

        found_permissions = []
        url_patterns = self._get_all_url_patterns(get_resolver().url_patterns)

        for pattern in url_patterns:
            permissions = self._extract_permissions_from_pattern(pattern)
            found_permissions.extend(permissions)

        # Sync permissions to database
        created_count = 0
        updated_count = 0

        for code, description in found_permissions:
            permission, created = Permission.objects.update_or_create(
                code=code,
                defaults={"description": description},
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully collected {len(found_permissions)} permissions "
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
        """Get permission code and description from an object"""
        code = obj._permission_code
        description = getattr(obj, "_permission_description", "")
        return (code, description)

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
