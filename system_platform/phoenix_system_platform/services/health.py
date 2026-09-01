"""
Phoenix System Platform
Health Service V1.0.

Framework-neutral health/readiness information.

This service does not access the database and does not
perform authentication or authorization.
"""


class SystemPlatformHealthService:

    def get_health(self):
        return {
            "status": "ok",
            "platform": "phoenix-system-platform",
            "version": "1.0.0",
        }
