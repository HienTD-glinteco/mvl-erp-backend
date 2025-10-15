"""
Relationship resolver for advanced XLSX imports.

This module provides the RelationshipResolver class that handles lookup and
creation of related model instances based on mapping configuration.
"""

import logging
from typing import Any, cast

from django.db import models as django_models
from django.db import transaction
from django.utils.translation import gettext as _

from .import_constants import ERROR_PARENT_NOT_FOUND, ERROR_RELATED_CREATE_FAILED

logger = logging.getLogger(__name__)


class RelationshipResolver:
    """
    Resolve and create related model instances.
    
    Handles complex relationships including:
    - ForeignKey lookup with create-if-not-found
    - Multi-level hierarchies (e.g., Department → Division → Branch)
    - Nested relationships with parent dependencies
    
    Example usage:
        resolver = RelationshipResolver()
        
        # Resolve ForeignKey with create-if-not-found
        position = resolver.resolve_foreign_key(
            model=Position,
            lookup_value="Software Engineer",
            lookup_field="name",
            create_if_not_found=True,
            defaults={"code": "SE", "level": "Junior"}
        )
        
        # Resolve with nested relations
        department = resolver.resolve_with_relations(
            model=Department,
            field_config={
                "model": "Department",
                "lookup": "Engineering",
                "create_if_not_found": true,
                "relations": {
                    "division": {
                        "model": "Division",
                        "lookup": "Technology"
                    },
                    "branch": {
                        "model": "Branch",
                        "lookup": "HQ"
                    }
                }
            },
            row_data={"Department": "Engineering", "Division": "Technology", "Branch": "HQ"}
        )
    """
    
    def resolve_foreign_key(
        self,
        model: type[django_models.Model],
        lookup_value: Any,
        lookup_field: str = "name",
        create_if_not_found: bool = False,
        defaults: dict | None = None,
        related_objects: dict | None = None,
    ) -> django_models.Model | None:  # type: ignore[type-arg]
        """
        Resolve a ForeignKey relationship.
        
        Args:
            model: Django model class to lookup/create
            lookup_value: Value to search for
            lookup_field: Field name to use for lookup (default: "name")
            create_if_not_found: If True, create instance if not found
            defaults: Default values for creation
            related_objects: Dict of related objects to link (e.g., {"division": division_obj})
            
        Returns:
            Model instance or None
            
        Raises:
            ValueError: If object not found and create_if_not_found is False
        """
        if lookup_value is None or lookup_value == "":
            return None
        
        # Try to find existing instance
        # Type ignore needed because mypy doesn't recognize model.objects and model.DoesNotExist
        # for generic type[Model]
        try:
            # Try by primary key first if value is numeric
            if isinstance(lookup_value, (int, float)):
                return model.objects.get(pk=int(lookup_value))  # type: ignore[attr-defined]
        except (Exception, ValueError):  # type: ignore[misc]
            pass
        
        # Try by specified lookup field
        try:
            return model.objects.get(**{lookup_field: lookup_value})  # type: ignore[attr-defined]
        except Exception:  # type: ignore[misc]
            pass
        
        # Try common natural key fields
        for field_name in ["name", "code", "email", "username"]:
            if field_name != lookup_field and hasattr(model, field_name):
                try:
                    return model.objects.get(**{field_name: lookup_value})  # type: ignore[attr-defined]
                except Exception:  # type: ignore[misc]
                    continue
        
        # Try case-insensitive lookup as last resort
        try:
            return model.objects.get(**{f"{lookup_field}__iexact": str(lookup_value)})  # type: ignore[attr-defined]
        except Exception:  # type: ignore[misc]
            pass
        
        # If not found and create_if_not_found is True, create new instance
        if create_if_not_found:
            return self._create_instance(
                model=model,
                lookup_field=lookup_field,
                lookup_value=lookup_value,
                defaults=defaults,
                related_objects=related_objects,
            )
        
        # Otherwise, raise error
        raise ValueError(
            _(ERROR_PARENT_NOT_FOUND).format(
                model=model.__name__,
                value=lookup_value,
            )
        )
    
    def _create_instance(
        self,
        model: type[django_models.Model],
        lookup_field: str,
        lookup_value: Any,
        defaults: dict | None = None,
        related_objects: dict | None = None,
    ) -> django_models.Model:
        """
        Create a new model instance.
        
        Args:
            model: Django model class
            lookup_field: Field name used for lookup
            lookup_value: Value to set for lookup field
            defaults: Default values for other fields
            related_objects: Dict of related objects to link
            
        Returns:
            Created model instance
            
        Raises:
            ValueError: If creation fails
        """
        try:
            # Build create kwargs
            create_kwargs = {lookup_field: lookup_value}
            
            # Add defaults
            if defaults:
                create_kwargs.update(defaults)
            
            # Add related objects (ForeignKey fields)
            if related_objects:
                create_kwargs.update(related_objects)
            
            # Create instance
            with transaction.atomic():
                instance = model.objects.create(**create_kwargs)  # type: ignore[attr-defined]
                logger.info(f"Created {model.__name__} instance: {instance}")
                return instance
        
        except Exception as e:
            logger.error(f"Failed to create {model.__name__}: {e}")
            raise ValueError(
                _(ERROR_RELATED_CREATE_FAILED).format(
                    model=model.__name__,
                    error=str(e),
                )
            )
    
    def resolve_with_relations(
        self,
        model: type[django_models.Model],
        field_config: dict,
        row_data: dict,
        transformer=None,
    ) -> django_models.Model | None:
        """
        Resolve a relationship with nested relations.
        
        This method handles complex relationships where the target object
        depends on other related objects (e.g., Department → Division → Branch).
        
        Args:
            model: Django model class to resolve
            field_config: Field configuration with relations
            row_data: Dictionary of row data
            transformer: FieldTransformer instance (optional)
            
        Returns:
            Model instance or None
            
        Example field_config:
            {
                "model": "Department",
                "lookup": "Engineering",
                "fields": {
                    "code": "Dept Code",
                    "name": "Department"
                },
                "create_if_not_found": true,
                "relations": {
                    "division": {
                        "model": "Division",
                        "lookup": "Technology",
                        "fields": {
                            "code": "Div Code",
                            "name": "Division"
                        },
                        "create_if_not_found": true
                    },
                    "branch": {
                        "model": "Branch",
                        "lookup": "HQ"
                    },
                    "parent_department": {
                        "model": "Department",
                        "lookup": "Parent Dept"
                    }
                }
            }
        """
        # Get lookup value
        lookup_column = field_config.get("lookup")
        if not lookup_column:
            return None
        
        lookup_value = row_data.get(lookup_column)
        if lookup_value is None or lookup_value == "":
            return None
        
        # Resolve nested relations first
        related_objects = {}
        relations_config = field_config.get("relations", {})
        
        for relation_field_name, relation_config in relations_config.items():
            # Get related model
            from django.apps import apps
            
            relation_model_name = relation_config.get("model")
            relation_app_label = relation_config.get("app_label")
            
            if relation_app_label:
                relation_model = apps.get_model(relation_app_label, relation_model_name)
            else:
                relation_model = self._get_model_by_name(relation_model_name)
            
            # Recursively resolve related object
            related_obj = self.resolve_with_relations(
                model=relation_model,
                field_config=relation_config,
                row_data=row_data,
                transformer=transformer,
            )
            
            if related_obj:
                related_objects[relation_field_name] = related_obj
        
        # Build defaults from fields mapping if provided
        defaults = field_config.get("defaults", {}).copy()
        fields_mapping = field_config.get("fields", {})
        
        if fields_mapping:
            # Map Excel columns to model fields
            for model_field, excel_column in fields_mapping.items():
                if excel_column in row_data:
                    value = row_data.get(excel_column)
                    if value is not None and value != "":
                        defaults[model_field] = value
        
        # Now resolve the main object with related objects
        lookup_field = field_config.get("lookup_field", "name")
        create_if_not_found = field_config.get("create_if_not_found", False)
        
        return self.resolve_foreign_key(
            model=model,
            lookup_value=lookup_value,
            lookup_field=lookup_field,
            create_if_not_found=create_if_not_found,
            defaults=defaults,
            related_objects=related_objects,
        )
    
    def _get_model_by_name(self, model_name: str):
        """
        Find Django model by name across all apps.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Model class
            
        Raises:
            LookupError: If model not found
        """
        from django.apps import apps
        
        for model in apps.get_models():
            if model.__name__ == model_name:
                return model
        
        raise LookupError(f"Model {model_name} not found")
    
    def resolve_many_to_many(
        self,
        model: type[django_models.Model],
        field_config: dict,
        row_data: dict,
    ) -> list[django_models.Model]:
        """
        Resolve ManyToMany relationships.
        
        Args:
            model: Django model class
            field_config: Field configuration
            row_data: Dictionary of row data
            
        Returns:
            List of related model instances
        """
        lookup_column = field_config.get("lookup")
        if not lookup_column:
            return []
        
        value = row_data.get(lookup_column)
        if value is None or value == "":
            return []
        
        # Split by comma for multiple values
        values = [v.strip() for v in str(value).split(",") if v.strip()]
        
        instances = []
        lookup_field = field_config.get("lookup_field", "name")
        create_if_not_found = field_config.get("create_if_not_found", False)
        
        for val in values:
            try:
                instance = self.resolve_foreign_key(
                    model=model,
                    lookup_value=val,
                    lookup_field=lookup_field,
                    create_if_not_found=create_if_not_found,
                )
                if instance:
                    instances.append(instance)
            except ValueError as e:
                logger.warning(f"Could not resolve M2M value '{val}': {e}")
                continue
        
        return instances
