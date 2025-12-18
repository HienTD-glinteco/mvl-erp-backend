from pathlib import Path
from typing import Any, Dict, List

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Permission, Role


class Command(BaseCommand):
    help = "Import system roles and permissions from YAML fixtures. Detaches stale permissions from roles."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.verbose = False
        self.dry_run = False

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose output",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the import without making changes to the database",
        )

    def handle(self, *args, **options):
        self.verbose = options.get("verbose", False)
        self.dry_run = options.get("dry_run", False)

        if self.dry_run:
            self._log("info", "Running in DRY-RUN mode - no changes will be made to the database")

        # Run migrations first to ensure tables exist
        self._log("debug", "Running database migrations...")
        from django.core.management import call_command

        try:
            call_command("migrate", verbosity=0, interactive=False)
            self._log("debug", "Migrations completed")
        except Exception as e:
            self._log("debug", f"Migration check: {e}")

        fixtures_dir = Path(__file__).resolve().parents[2] / "fixtures"
        permission_sets_file = fixtures_dir / "permission_sets.yaml"
        system_roles_file = fixtures_dir / "system_roles.yaml"

        # Validate files exist
        if not permission_sets_file.exists():
            raise CommandError(f"Permission sets fixture not found: {permission_sets_file}")
        if not system_roles_file.exists():
            raise CommandError(f"System roles fixture not found: {system_roles_file}")

        self._log("info", f"Loading permission sets from {permission_sets_file.name}")
        raw_sets = self._load_permission_sets(permission_sets_file)
        self._log("info", f"Loaded {len(raw_sets)} permission sets")

        self._log("info", f"Loading roles from {system_roles_file.name}")
        raw_roles = self._load_roles(system_roles_file)
        self._log("info", f"Loaded {len(raw_roles)} roles")

        if not raw_roles:
            self._log("warning", "No roles found in fixture file")
            return

        # Resolve permission set inheritance
        self._log("debug", "Resolving permission set inheritance...")
        resolved_sets = self._resolve_permission_sets(raw_sets)
        self._log("debug", f"Resolved {len(resolved_sets)} permission sets")

        # Import roles within transaction (will rollback if dry-run)
        try:
            with transaction.atomic():
                self._log("info", "Importing roles and permissions...")
                stats = self._import_roles(raw_roles, resolved_sets)

                # Rollback if dry-run
                if self.dry_run:
                    transaction.set_rollback(True)
        except Exception as e:
            raise

        # Summary
        self._print_summary(stats)

    def _load_permission_sets(self, file_path: Path) -> dict:
        """Load permission sets from YAML file."""
        try:
            with open(file_path) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict) or "permission_sets" not in data:
                raise CommandError(f"Invalid permission_sets structure in {file_path.name}")
            return data["permission_sets"]
        except yaml.YAMLError as e:
            raise CommandError(f"Failed to parse YAML in {file_path.name}: {e}") from e
        except Exception as e:
            raise CommandError(f"Failed to load {file_path.name}: {e}") from e

    def _load_roles(self, file_path: Path) -> list:
        """Load roles from YAML file."""
        try:
            with open(file_path) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict) or "roles" not in data:
                raise CommandError(f"Invalid roles structure in {file_path.name}")
            roles = data["roles"]
            if not isinstance(roles, list):
                raise CommandError(f"'roles' must be a list in {file_path.name}")
            return roles
        except yaml.YAMLError as e:
            raise CommandError(f"Failed to parse YAML in {file_path.name}: {e}") from e
        except Exception as e:
            raise CommandError(f"Failed to load {file_path.name}: {e}") from e

    def _resolve_permission_sets(self, raw_sets: dict) -> dict:  # NOQA: C901
        """Resolve permission set inheritance with multi-parent support."""
        resolved_sets: Dict[str, Any] = {}

        def resolve_set(name, stack=None):  # NOQA: C901
            if name in resolved_sets:
                return resolved_sets[name]
            if name not in raw_sets:
                raise CommandError(f"Permission set '{name}' is not defined")
            if stack is None:
                stack = []
            if name in stack:
                raise CommandError(f"Circular permission_set inheritance: {' -> '.join(stack + [name])}")

            stack.append(name)
            val = raw_sets[name]

            # Handle wildcard
            if val == "*" or val == ["*"]:
                resolved = "*"
            # Handle list of permissions
            elif isinstance(val, list):
                resolved = [str(x).strip() for x in val if str(x).strip()]
            # Handle inheritance
            elif isinstance(val, dict):
                parents = val.get("extends")
                add = val.get("add") or []
                if not parents:
                    raise CommandError(f"permission_set '{name}' must have 'extends' when object is provided")

                # Support both single parent (string) and multiple parents (list)
                if isinstance(parents, str):
                    parents = [parents]
                elif not isinstance(parents, list):
                    raise CommandError(f"permission_set '{name}' 'extends' must be a string or list")

                resolved = []
                for parent in parents:
                    parent = str(parent).strip()
                    if not parent:
                        continue
                    parent_resolved = resolve_set(parent, stack.copy())
                    if parent_resolved == "*":
                        resolved = "*"
                        break
                    resolved.extend(parent_resolved if isinstance(parent_resolved, list) else [parent_resolved])

                if resolved != "*":
                    resolved.extend([str(x).strip() for x in add if str(x).strip()])
            else:
                raise CommandError(f"Unsupported value for permission_set '{name}'")

            resolved_sets[name] = resolved
            stack.pop()
            return resolved

        # Resolve all sets
        for set_name in list(raw_sets.keys()):
            resolve_set(set_name)

        return resolved_sets

    def _import_roles(self, raw_roles: list, resolved_sets: dict) -> Dict[str, Any]:  # NOQA: C901
        """Import roles and assign permissions."""
        stats: Dict[str, Any] = {"created": 0, "updated": 0, "processed": 0, "roles": []}

        for role_item in raw_roles:
            stats["processed"] = int(stats["processed"]) + 1

            if not isinstance(role_item, dict):
                raise CommandError(f"Role #{stats['processed']} is not an object")

            code = (role_item.get("code") or "").strip()
            name = (role_item.get("name") or "").strip()
            if not code or not name:
                raise CommandError(f"Role #{stats['processed']} missing 'code' or 'name'")

            # Create or update role
            role, was_created = Role.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "is_system_role": True,
                },
            )

            if was_created:
                stats["created"] = int(stats["created"]) + 1
                self._log("debug", f"Created role: {code} ({name})")
            else:
                updates: List[str] = []
                if role.name != name:
                    role.name = name
                    updates.append("name")
                if role.is_system_role is not True:
                    role.is_system_role = True
                    updates.append("is_system_role")
                if updates:
                    role.save(update_fields=updates)
                    stats["updated"] = int(stats["updated"]) + 1
                    self._log("debug", f"Updated role: {code} (fields: {', '.join(updates)})")

            # Resolve and assign permissions
            perms = self._resolve_permissions(role_item, resolved_sets)
            old_perms_count = role.permissions.count()
            role.permissions.set(perms)
            new_perms_count = role.permissions.count()

            role_stats: Dict[str, Any] = {
                "code": code,
                "name": name,
                "permissions_count": new_perms_count,
                "permissions_changed": old_perms_count != new_perms_count,
            }
            stats["roles"].append(role_stats)

            self._log("debug", f"Assigned {new_perms_count} permissions to {code}")

        return stats

    def _resolve_permissions(self, role_item: dict, resolved_sets: dict) -> list:  # NOQA: C901
        """Resolve permissions from role definition."""
        perm_codes_raw = role_item.get("permissions") or role_item.get("permission_codes")
        final_codes = []

        if perm_codes_raw:
            if isinstance(perm_codes_raw, str):
                perm_codes_raw = [perm_codes_raw]

            for entry in perm_codes_raw:
                if not isinstance(entry, str):
                    continue
                e = entry.strip()
                if not e:
                    continue

                # Handle wildcard for all permissions
                if e == "*":
                    final_codes = ["*"]
                    break
                # Handle permission set reference
                elif e in resolved_sets:
                    resolved = resolved_sets[e]
                    if resolved == "*":
                        final_codes = ["*"]
                        break
                    final_codes.extend(resolved)
                # Handle direct permission code or wildcard
                else:
                    final_codes.append(e)

        # Convert permission codes to Permission objects
        perms = []
        if final_codes:
            if "*" in final_codes:
                perms = list(Permission.objects.all())
            else:
                exact_codes = [c for c in final_codes if not c.endswith("*")]
                if exact_codes:
                    perms.extend(list(Permission.objects.filter(code__in=exact_codes)))
                prefixes = [c[:-1] for c in final_codes if c.endswith("*")]
                for pfx in prefixes:
                    if pfx:
                        perms.extend(list(Permission.objects.filter(code__startswith=pfx)))

        # Remove duplicates
        return list({p.id: p for p in perms}.values())

    def _log(self, level: str, message: str):
        """Log message with smart formatting."""
        if level == "info":
            self.stdout.write(self.style.SUCCESS(f"✓ {message}"))
        elif level == "warning":
            self.stdout.write(self.style.WARNING(f"⚠ {message}"))
        elif level == "error":
            self.stdout.write(self.style.ERROR(f"✗ {message}"))
        elif level == "debug":
            # Only show debug if verbose is enabled
            if self.verbose:
                self.stdout.write(f"  → {message}")

    def _print_summary(self, stats: dict):
        """Print import summary."""
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS("IMPORT SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 70))

        self.stdout.write(f"Total roles processed: {stats['processed']}")
        self.stdout.write(f"  ✓ Created: {stats['created']}")
        self.stdout.write(f"  ✓ Updated: {stats['updated']}")

        # Print per-role details
        if stats["roles"]:
            self.stdout.write("")
            self.stdout.write("Roles:")
            for role in stats["roles"]:
                status = "✓" if not role["permissions_changed"] else "↻"
                self.stdout.write(f"  {status} {role['code']}: {role['name']} ({role['permissions_count']} perms)")

        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS("Import completed successfully!"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
