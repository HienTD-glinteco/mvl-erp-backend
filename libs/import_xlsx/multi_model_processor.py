"""
Multi-model processor for advanced XLSX imports.

This module provides the MultiModelProcessor class that handles importing
data for multiple related models from a single Excel file.
"""

import logging
from typing import Any

from django.core.exceptions import FieldDoesNotExist
from django.db import models as django_models
from django.db import transaction
from django.utils.translation import gettext as _

from .field_transformer import FieldTransformer
from .mapping_config import MappingConfigParser
from .relationship_resolver import RelationshipResolver

logger = logging.getLogger(__name__)


class MultiModelProcessor:
    """
    Process multi-model imports from XLSX files.
    
    Handles:
    - Processing multiple sheets or models from single sheet
    - Resolving dependencies between models
    - Creating/updating related model instances
    - Transaction management per row
    - Error tracking and reporting
    
    Example usage:
        processor = MultiModelProcessor(config)
        
        results = processor.process_file(
            workbook=wb,
            preview=False,
            user=request.user,
            request=request
        )
        
        # Results contain:
        # {
        #     "success_count": 100,
        #     "error_count": 5,
        #     "errors": [...],
        #     "imported_objects": [...]
        # }
    """
    
    def __init__(self, config: dict | str | MappingConfigParser):
        """
        Initialize processor with configuration.
        
        Args:
            config: Configuration dict, JSON/YAML string, or MappingConfigParser instance
        """
        if isinstance(config, MappingConfigParser):
            self.config_parser = config
        else:
            self.config_parser = MappingConfigParser(config)
        
        self.transformer = FieldTransformer()
        self.resolver = RelationshipResolver()
    
    def process_file(
        self,
        workbook,
        preview: bool = False,
        user=None,
        request=None,
    ) -> dict:
        """
        Process entire workbook according to configuration.
        
        Args:
            workbook: openpyxl Workbook instance
            preview: If True, don't save to database
            user: User performing the import (for audit logging)
            request: Request object (for audit logging)
            
        Returns:
            dict: Results with success_count, error_count, errors, imported_objects
        """
        results = {
            "success_count": 0,
            "error_count": 0,
            "errors": [],
            "imported_objects": [],
            "preview_data": [] if preview else None,
        }
        
        # Process each sheet configuration
        for sheet_config in self.config_parser.get_sheets():
            sheet_results = self.process_sheet(
                workbook=workbook,
                sheet_config=sheet_config,
                preview=preview,
                user=user,
                request=request,
            )
            
            # Aggregate results
            results["success_count"] += sheet_results["success_count"]
            results["error_count"] += sheet_results["error_count"]
            results["errors"].extend(sheet_results["errors"])
            results["imported_objects"].extend(sheet_results.get("imported_objects", []))
            
            if preview and sheet_results.get("preview_data"):
                results["preview_data"].extend(sheet_results["preview_data"])
        
        return results
    
    def process_sheet(
        self,
        workbook,
        sheet_config: dict,
        preview: bool = False,
        user=None,
        request=None,
    ) -> dict:
        """
        Process a single sheet according to configuration.
        
        Args:
            workbook: openpyxl Workbook instance
            sheet_config: Sheet configuration dictionary
            preview: If True, don't save to database
            user: User performing the import
            request: Request object
            
        Returns:
            dict: Results for this sheet
        """
        results = {
            "success_count": 0,
            "error_count": 0,
            "errors": [],
            "imported_objects": [],
            "preview_data": [] if preview else None,
        }
        
        # Get sheet by name or use active sheet
        sheet_name = sheet_config.get("name")
        if sheet_name and sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
        else:
            worksheet = workbook.active
        
        # Get model
        model = self.config_parser.get_model_for_sheet(sheet_config)
        
        # Extract headers and data
        rows = list(worksheet.iter_rows(values_only=True))
        if not rows:
            return results
        
        headers = [str(h) if h else "" for h in rows[0]]
        data_rows = rows[1:]
        
        # Process each row
        for row_num, row_values in enumerate(data_rows, start=2):
            # Skip empty rows
            if all(v is None or v == "" for v in row_values):
                continue
            
            # Build row data dictionary
            row_data = dict(zip(headers, row_values))
            
            # Process row
            row_result = self.process_row(
                row_num=row_num,
                row_data=row_data,
                sheet_config=sheet_config,
                model=model,
                preview=preview,
                user=user,
                request=request,
            )
            
            if row_result["success"]:
                results["success_count"] += 1
                if row_result.get("instance"):
                    results["imported_objects"].append(row_result["instance"])
                if preview and row_result.get("preview_data"):
                    results["preview_data"].append(row_result["preview_data"])
            else:
                results["error_count"] += 1
                results["errors"].append({
                    "row": row_num,
                    "errors": row_result.get("errors", {}),
                })
        
        return results
    
    def process_row(
        self,
        row_num: int,
        row_data: dict,
        sheet_config: dict,
        model: type[django_models.Model],
        preview: bool = False,
        user=None,
        request=None,
    ) -> dict:
        """
        Process a single row of data.
        
        Args:
            row_num: Row number (for error reporting)
            row_data: Dictionary of row data
            sheet_config: Sheet configuration
            model: Django model class
            preview: If True, don't save to database
            user: User performing the import
            request: Request object
            
        Returns:
            dict: Result with success flag, instance/errors
        """
        try:
            with transaction.atomic():
                # Transform fields according to configuration
                fields_config = sheet_config.get("fields", {})
                transformed_data = {}
                related_foreign_keys = {}
                related_many_to_many = {}
                
                # Process each field
                for field_name, field_config in fields_config.items():
                    # Check if field is a ForeignKey or ManyToMany
                    if isinstance(field_config, dict) and "model" in field_config:
                        # Get related model
                        from django.apps import apps
                        
                        related_model_name = field_config["model"]
                        related_app_label = field_config.get("app_label")
                        
                        if related_app_label:
                            related_model = apps.get_model(related_app_label, related_model_name)
                        else:
                            related_model = self.resolver._get_model_by_name(related_model_name)
                        
                        # Check if it's a ManyToMany field
                        try:
                            field_obj = model._meta.get_field(field_name)
                            if isinstance(field_obj, django_models.ManyToManyField):
                                # Handle M2M later (after instance creation)
                                related_many_to_many[field_name] = (related_model, field_config)
                                continue
                        except (FieldDoesNotExist, AttributeError):
                            pass
                        
                        # Handle ForeignKey with relations
                        related_obj = self.resolver.resolve_with_relations(
                            model=related_model,
                            field_config=field_config,
                            row_data=row_data,
                            transformer=self.transformer,
                        )
                        
                        if related_obj:
                            related_foreign_keys[field_name] = related_obj
                        
                        continue
                    
                    # Regular field transformation
                    value = self.transformer.transform_field(
                        field_name=field_name,
                        field_config=field_config,
                        row_data=row_data,
                    )
                    transformed_data[field_name] = value
                
                # Add related foreign keys to transformed data
                transformed_data.update(related_foreign_keys)
                
                # Create/update main instance
                if preview:
                    # In preview mode, just validate
                    instance = model(**transformed_data)
                    instance.full_clean()
                    
                    return {
                        "success": True,
                        "preview_data": {
                            "model": model.__name__,
                            "data": transformed_data,
                            "row": row_num,
                        },
                    }
                else:
                    # Create instance
                    instance = model.objects.create(**transformed_data)
                    
                    # Handle ManyToMany fields
                    for m2m_field_name, (m2m_model, m2m_config) in related_many_to_many.items():
                        m2m_instances = self.resolver.resolve_many_to_many(
                            model=m2m_model,
                            field_config=m2m_config,
                            row_data=row_data,
                        )
                        if m2m_instances:
                            getattr(instance, m2m_field_name).set(m2m_instances)
                    
                    # Process additional relations (accounts, work_events, etc.)
                    relations_config = sheet_config.get("relations", {})
                    self.process_relations(
                        main_instance=instance,
                        relations_config=relations_config,
                        row_data=row_data,
                        user=user,
                        request=request,
                    )
                    
                    # Log audit event if applicable
                    if user:
                        self._log_audit(instance, user, request)
                    
                    return {
                        "success": True,
                        "instance": instance,
                    }
        
        except Exception as e:
            logger.error(f"Error processing row {row_num}: {e}")
            return {
                "success": False,
                "errors": {"general": [str(e)]},
            }
    
    def process_relations(
        self,
        main_instance: django_models.Model,
        relations_config: dict,
        row_data: dict,
        user=None,
        request=None,
    ):
        """
        Process additional relations (like accounts, work_events).
        
        Args:
            main_instance: Main model instance (e.g., Employee)
            relations_config: Relations configuration
            row_data: Dictionary of row data
            user: User performing the import
            request: Request object
        """
        for relation_name, relation_list in relations_config.items():
            for relation_config in relation_list:
                # Check condition if specified
                condition = relation_config.get("condition")
                if condition:
                    condition_field = condition.get("field")
                    if condition.get("exists"):
                        # Only create if field has value
                        if not row_data.get(condition_field):
                            continue
                
                # Get related model
                from django.apps import apps
                
                related_model_name = relation_config["model"]
                related_app_label = relation_config.get("app_label")
                
                if related_app_label:
                    related_model = apps.get_model(related_app_label, related_model_name)
                else:
                    related_model = self.resolver._get_model_by_name(related_model_name)
                
                # Transform fields for related instance
                related_fields = relation_config.get("fields", {})
                related_data = {}
                
                for field_name, field_config in related_fields.items():
                    value = self.transformer.transform_field(
                        field_name=field_name,
                        field_config=field_config,
                        row_data=row_data,
                    )
                    related_data[field_name] = value
                
                # Add defaults (static values)
                defaults = relation_config.get("defaults", {})
                for field_name, field_value in defaults.items():
                    # Only set default if field not already set from fields config
                    if field_name not in related_data:
                        related_data[field_name] = field_value
                
                # Link to main instance (assuming foreign key field name matches)
                main_model_name = main_instance.__class__.__name__.lower()
                related_data[main_model_name] = main_instance
                
                # Create related instance
                try:
                    if relation_config.get("create_if_not_found", True):
                        related_instance = related_model.objects.create(**related_data)
                        
                        # Log audit if applicable
                        if user:
                            self._log_audit(related_instance, user, request)
                except Exception as e:
                    logger.warning(f"Failed to create related {related_model_name}: {e}")
    
    def _log_audit(self, instance: django_models.Model, user, request):
        """
        Log audit event for imported instance.
        
        Args:
            instance: Model instance
            user: User performing the import
            request: Request object
        """
        try:
            from apps.audit_logging import LogAction, log_audit_event
            
            log_audit_event(
                action=LogAction.IMPORT,
                modified_object=instance,
                user=user,
                request=request,
            )
        except ImportError:
            # Audit logging not available
            pass
        except Exception as e:
            logger.warning(f"Failed to log audit event: {e}")
