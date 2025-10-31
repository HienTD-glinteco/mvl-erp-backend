from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets.employee_certificate import EmployeeCertificateFilterSet
from apps.hrm.api.serializers.employee_certificate import EmployeeCertificateSerializer
from apps.hrm.models import EmployeeCertificate
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List employee certificates",
        description="Retrieve a paginated list of employee certificates with filtering by certificate type, employee, dates, and more",
        tags=["Employee Certificates"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "employee": 1,
                                "certificate_type": "foreign_language",
                                "certificate_type_display": "Foreign language certificate",
                                "certificate_code": "IELTS-123456789",
                                "certificate_name": "IELTS 7.0",
                                "issue_date": "2024-06-01",
                                "expiry_date": "2026-06-01",
                                "issuing_organization": "British Council",
                                "file": 1,
                                "notes": "English proficiency certificate",
                                "created_at": "2024-01-01T00:00:00Z",
                                "updated_at": "2024-01-01T00:00:00Z",
                            },
                            {
                                "id": 2,
                                "employee": 1,
                                "certificate_type": "real_estate_practice_license",
                                "certificate_type_display": "Real estate practice license",
                                "certificate_code": "BDS-2023-001234",
                                "certificate_name": "Real Estate Broker License",
                                "issue_date": "2023-01-15",
                                "expiry_date": "2028-01-15",
                                "issuing_organization": "Ministry of Construction",
                                "file": 2,
                                "notes": "Official broker license",
                                "created_at": "2024-01-01T00:00:00Z",
                                "updated_at": "2024-01-01T00:00:00Z",
                            },
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    create=extend_schema(
        summary="Create employee certificate",
        description="Create a new employee certificate record. The certificate_code is the actual certificate number from the certifying organization. Files are uploaded via presigned URLs and confirmed using file tokens.",
        tags=["Employee Certificates"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "employee": 1,
                    "certificate_type": "foreign_language",
                    "certificate_code": "IELTS-123456789",
                    "certificate_name": "IELTS 7.0",
                    "issue_date": "2024-06-01",
                    "expiry_date": "2026-06-01",
                    "issuing_organization": "British Council",
                    "files": {"file": "abc123"},
                    "notes": "English proficiency certificate",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": 1,
                        "certificate_type": "foreign_language",
                        "certificate_type_display": "Foreign language certificate",
                        "certificate_code": "IELTS-123456789",
                        "certificate_name": "IELTS 7.0",
                        "issue_date": "2024-06-01",
                        "expiry_date": "2026-06-01",
                        "issuing_organization": "British Council",
                        "file": {
                            "id": 1,
                            "purpose": "employee_certificate",
                            "file_name": "ielts_certificate.pdf",
                            "file_path": "certificates/ielts_certificate.pdf",
                            "size": 1024000,
                            "is_confirmed": True,
                            "view_url": "https://s3.amazonaws.com/...",
                            "download_url": "https://s3.amazonaws.com/...",
                        },
                        "notes": "English proficiency certificate",
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error",
                value={"success": False, "data": None, "error": {"certificate_type": ["Invalid certificate type"]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get certificate details",
        description="Retrieve detailed information about a specific employee certificate",
        tags=["Employee Certificates"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": 1,
                        "certificate_type": "foreign_language",
                        "certificate_type_display": "Foreign language certificate",
                        "certificate_code": "IELTS-123456789",
                        "certificate_name": "IELTS 7.0",
                        "issue_date": "2024-06-01",
                        "expiry_date": "2026-06-01",
                        "issuing_organization": "British Council",
                        "file": 1,
                        "notes": "English proficiency certificate",
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    update=extend_schema(
        summary="Update certificate",
        description="Update employee certificate information including the certificate code from the issuing organization",
        tags=["Employee Certificates"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "employee": 1,
                    "certificate_type": "foreign_language",
                    "certificate_code": "TOEIC-987654321",
                    "certificate_name": "TOEIC 850",
                    "issue_date": "2024-08-15",
                    "expiry_date": "2026-08-15",
                    "issuing_organization": "ETS",
                    "file": 1,
                    "notes": "Updated certificate information",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": 1,
                        "certificate_type": "foreign_language",
                        "certificate_type_display": "Foreign language certificate",
                        "certificate_code": "TOEIC-987654321",
                        "certificate_name": "TOEIC 850",
                        "issue_date": "2024-08-15",
                        "expiry_date": "2026-08-15",
                        "issuing_organization": "ETS",
                        "file": 1,
                        "notes": "Updated certificate information",
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-08-15T10:30:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update certificate",
        description="Partially update employee certificate information",
        tags=["Employee Certificates"],
    ),
    destroy=extend_schema(
        summary="Delete certificate",
        description="Remove an employee certificate from the system",
        tags=["Employee Certificates"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None, "error": None},
                response_only=True,
            ),
        ],
    ),
)
class EmployeeCertificateViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for EmployeeCertificate model."""

    queryset = EmployeeCertificate.objects.select_related("employee", "file").all()
    serializer_class = EmployeeCertificateSerializer
    filterset_class = EmployeeCertificateFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["certificate_name", "issuing_organization", "notes", "certificate_code"]
    ordering_fields = ["certificate_type", "certificate_code", "issue_date", "expiry_date", "created_at"]
    ordering = ["certificate_type", "-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Employee Certificate Management"
    permission_prefix = "employee_certificate"
