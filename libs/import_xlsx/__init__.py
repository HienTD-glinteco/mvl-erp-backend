"""
XLSX Import functionality for Django REST Framework ViewSets.
"""

from .error_report import ErrorReportGenerator
from .field_transformer import FieldTransformer
from .import_mixin import ImportXLSXMixin
from .mapping_config import MappingConfigParser
from .multi_model_processor import MultiModelProcessor
from .relationship_resolver import RelationshipResolver
from .serializers import ImportAsyncResponseSerializer, ImportPreviewResponseSerializer, ImportResultSerializer
from .storage import ImportStorage, get_storage_backend
from .tasks import import_xlsx_task
from .utils import (
    bulk_import_data,
    extract_headers,
    log_import_audit,
    map_headers_to_fields,
    process_row,
    resolve_foreign_key,
    resolve_many_to_many,
)

__all__ = [
    # Main mixin
    "ImportXLSXMixin",
    # Advanced import components
    "MappingConfigParser",
    "FieldTransformer",
    "RelationshipResolver",
    "MultiModelProcessor",
    # Serializers
    "ImportAsyncResponseSerializer",
    "ImportPreviewResponseSerializer",
    "ImportResultSerializer",
    # Storage
    "ImportStorage",
    "get_storage_backend",
    # Error reporting
    "ErrorReportGenerator",
    # Tasks
    "import_xlsx_task",
    # Utilities
    "bulk_import_data",
    "extract_headers",
    "log_import_audit",
    "map_headers_to_fields",
    "process_row",
    "resolve_foreign_key",
    "resolve_many_to_many",
]
