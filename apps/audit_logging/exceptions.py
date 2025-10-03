class AuditLogException(Exception):
    """Base exception for this module."""

    pass


class S3UploadFailedError(AuditLogException):
    """Raised when an S3 upload fails."""

    pass
