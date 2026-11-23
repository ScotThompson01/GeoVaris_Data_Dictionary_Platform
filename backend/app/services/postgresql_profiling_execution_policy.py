"""Fail-closed deployment gate for PostgreSQL profiling execution.

Passing this gate does not grant user, scan, source, or connection
authorization. Those checks belong to the future orchestration workflow.
"""

from app.core.config import Settings


class PostgreSQLProfilingExecutionDisabledError(ValueError):
    """PostgreSQL profiling execution is not enabled for this installation."""


def require_postgresql_profiling_execution_enabled(
    settings: Settings,
) -> None:
    """Reject execution unless explicitly enabled by deployment policy."""
    if settings.postgresql_profiling_execution_enabled is not True:
        raise PostgreSQLProfilingExecutionDisabledError(
            "PostgreSQL profiling execution is disabled."
        )
