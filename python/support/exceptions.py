"""Exceptions the CLI entrypoint catches to choose an exit code."""


class SupportToolError(Exception):
    """Base class for expected, user-facing support_tool errors."""


class ConfigError(SupportToolError):
    """Required configuration is missing or invalid."""


class DependencyError(SupportToolError):
    """A required dependency (database, or API when configured) is unreachable."""
