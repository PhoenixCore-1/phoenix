"""System Platform service-layer errors."""


class SystemPlatformError(Exception):
    """Base System Platform error."""


class CoreBoundaryError(SystemPlatformError):
    """Raised when a Core boundary operation fails."""


class PlatformAuthorizationError(SystemPlatformError):
    """Raised when platform authorization fails."""
