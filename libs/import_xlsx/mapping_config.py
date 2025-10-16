"""
Configuration parser for advanced XLSX imports.

This module provides the MappingConfigParser class that parses and validates
JSON/YAML configuration files for multi-model imports.
"""

import json
import logging

import yaml
from django.apps import apps
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

# Configuration error messages
ERROR_INVALID_CONFIG = "Invalid import configuration"
ERROR_MISSING_SHEETS = "Configuration must have 'sheets' key"
ERROR_INVALID_SHEET = "Invalid sheet configuration"
ERROR_MISSING_MODEL = "Sheet configuration must specify 'model'"
ERROR_MODEL_NOT_FOUND = "Model '{model}' not found in Django apps"
ERROR_INVALID_FIELD_CONFIG = "Invalid field configuration for '{field}'"
ERROR_MISSING_COMBINE_FIELDS = "Field '{field}' specifies 'combine' but missing field list"
ERROR_INVALID_RELATION_CONFIG = "Invalid relation configuration for '{relation}'"


class MappingConfigParser:
    """
    Parser and validator for import mapping configuration.
    
    Supports JSON and YAML formats for defining how Excel data maps to Django models.
    
    Example configuration:
        {
          "sheets": [
            {
              "name": "Employees",
              "model": "Employee",
              "app_label": "hrm",
              "fields": {
                "employee_code": "Employee Code",
                "name": "Name",
                "start_date": {
                  "combine": ["Start Day", "Start Month", "Start Year"],
                  "format": "YYYY-MM-DD"
                },
                "position": {
                  "model": "Position",
                  "lookup": "Position",
                  "create_if_not_found": true
                }
              },
              "relations": {
                "accounts": [
                  {
                    "model": "Account",
                    "fields": {
                      "bank": "VPBank",
                      "account_number": "VPBank Account"
                    }
                  }
                ]
              }
            }
          ]
        }
    """

    def __init__(self, config: dict | str):
        """
        Initialize parser with configuration.
        
        Args:
            config: Dictionary or JSON/YAML string
        """
        if isinstance(config, str):
            config = self._parse_string(config)

        self.config = config
        self.validate()

    def _parse_string(self, config_str: str) -> dict:
        """
        Parse configuration from JSON or YAML string.
        
        Args:
            config_str: JSON or YAML formatted string
            
        Returns:
            dict: Parsed configuration
            
        Raises:
            ValueError: If unable to parse
        """
        # Try JSON first
        try:
            return json.loads(config_str)
        except json.JSONDecodeError:
            pass

        # Try YAML
        try:
            return yaml.safe_load(config_str)
        except yaml.YAMLError as e:
            raise ValueError(f"{ERROR_INVALID_CONFIG}: {e}")

    def validate(self):
        """
        Validate the configuration structure.
        
        Raises:
            ValueError: If configuration is invalid
        """
        if not isinstance(self.config, dict):
            raise ValueError(ERROR_INVALID_CONFIG)

        if "sheets" not in self.config:
            raise ValueError(ERROR_MISSING_SHEETS)

        if not isinstance(self.config["sheets"], list):
            raise ValueError(ERROR_INVALID_CONFIG)

        for sheet_config in self.config["sheets"]:
            self._validate_sheet(sheet_config)

    def _validate_sheet(self, sheet_config: dict):
        """
        Validate a single sheet configuration.
        
        Args:
            sheet_config: Sheet configuration dictionary
            
        Raises:
            ValueError: If sheet configuration is invalid
        """
        if not isinstance(sheet_config, dict):
            raise ValueError(ERROR_INVALID_SHEET)

        if "model" not in sheet_config:
            raise ValueError(ERROR_MISSING_MODEL)

        # Validate model exists
        model_name = sheet_config["model"]
        app_label = sheet_config.get("app_label")

        try:
            if app_label:
                apps.get_model(app_label, model_name)
            else:
                # Try to find model in any app
                self._get_model_by_name(model_name)
        except LookupError:
            raise ValueError(_(ERROR_MODEL_NOT_FOUND).format(model=model_name))

        # Validate fields configuration
        if "fields" in sheet_config:
            self._validate_fields(sheet_config["fields"])

        # Validate relations configuration
        if "relations" in sheet_config:
            self._validate_relations(sheet_config["relations"])

    def _validate_fields(self, fields_config: dict):
        """
        Validate fields configuration.
        
        Args:
            fields_config: Fields configuration dictionary
            
        Raises:
            ValueError: If fields configuration is invalid
        """
        if not isinstance(fields_config, dict):
            raise ValueError(ERROR_INVALID_CONFIG)

        for field_name, field_config in fields_config.items():
            # Simple string mapping is always valid
            if isinstance(field_config, str):
                continue

            # Complex field configuration
            if isinstance(field_config, dict):
                # Validate combine fields
                if "combine" in field_config:
                    if not isinstance(field_config["combine"], list):
                        raise ValueError(_(ERROR_MISSING_COMBINE_FIELDS).format(field=field_name))
                    if len(field_config["combine"]) == 0:
                        raise ValueError(_(ERROR_MISSING_COMBINE_FIELDS).format(field=field_name))

                # Validate relation field
                if "model" in field_config:
                    if "lookup" not in field_config:
                        raise ValueError(_(ERROR_INVALID_FIELD_CONFIG).format(field=field_name))

                continue

            raise ValueError(_(ERROR_INVALID_FIELD_CONFIG).format(field=field_name))

    def _validate_relations(self, relations_config: dict):
        """
        Validate relations configuration.
        
        Args:
            relations_config: Relations configuration dictionary
            
        Raises:
            ValueError: If relations configuration is invalid
        """
        if not isinstance(relations_config, dict):
            raise ValueError(ERROR_INVALID_CONFIG)

        for relation_name, relation_list in relations_config.items():
            if not isinstance(relation_list, list):
                raise ValueError(_(ERROR_INVALID_RELATION_CONFIG).format(relation=relation_name))

            for relation_config in relation_list:
                if not isinstance(relation_config, dict):
                    raise ValueError(_(ERROR_INVALID_RELATION_CONFIG).format(relation=relation_name))

                if "model" not in relation_config:
                    raise ValueError(_(ERROR_INVALID_RELATION_CONFIG).format(relation=relation_name))

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
        for model in apps.get_models():
            if model.__name__ == model_name:
                return model

        raise LookupError(f"Model {model_name} not found")

    def get_sheets(self) -> list[dict]:
        """
        Get list of sheet configurations.
        
        Returns:
            list: List of sheet configuration dictionaries
        """
        return self.config["sheets"]

    def get_sheet_by_name(self, name: str) -> dict | None:
        """
        Get sheet configuration by name.
        
        Args:
            name: Sheet name
            
        Returns:
            dict or None: Sheet configuration if found
        """
        for sheet in self.get_sheets():
            if sheet.get("name") == name:
                return sheet
        return None

    def get_model_for_sheet(self, sheet_config: dict):
        """
        Get Django model for a sheet configuration.
        
        Args:
            sheet_config: Sheet configuration dictionary
            
        Returns:
            Model class
        """
        model_name = sheet_config["model"]
        app_label = sheet_config.get("app_label")

        if app_label:
            return apps.get_model(app_label, model_name)
        else:
            return self._get_model_by_name(model_name)
