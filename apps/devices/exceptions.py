"""Exception classes for device operations."""


class DeviceConnectionError(Exception):
    """Exception raised when connection to a device fails."""

    pass


class DeviceOperationError(Exception):
    """Exception raised when a device operation fails."""

    pass
