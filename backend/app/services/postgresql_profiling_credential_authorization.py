"""Validate request-scoped PostgreSQL profiling credentials.

This module validates credential eligibility against a trusted
connection snapshot and independently established account approval.

It does not establish account approval, authenticate a database
account, verify database privileges, connect to a source database,
persist credentials, or authorize profiling execution.

The future orchestration layer must obtain trusted account approval,
enforce request authorization, revalidate the registered connection,
and satisfy all remaining execution requirements.
"""

from dataclasses import dataclass
from uuid import UUID

from pydantic import SecretStr

from app.connectors.database.base import DatabaseConnectionConfig
from app.core.config import settings
from app.services.postgresql_profiling_connection_authorization import (
    PostgreSQLProfilingConnectionSnapshot,
)
from app.services.postgresql_profiling_execution_policy import (
    require_postgresql_profiling_execution_enabled,
)


class PostgreSQLProfilingCredentialAuthorizationError(ValueError):
    """Supplied credentials are not eligible for profiling."""


@dataclass(frozen=True)
class PostgreSQLProfilingAccountApproval:
    """Non-secret account approval information from a trusted caller.

    This object represents an independently established approval
    bound to a source and registered connection revision.

    Constructing this object does not establish approval.

    It must never be populated directly from untrusted request
    parameters or treated as an execution authorization token.
    """

    data_source_id: UUID
    connection_revision: int
    username: str


def validate_postgresql_profiling_credentials(
    *,
    data_source_id: UUID,
    snapshot: PostgreSQLProfilingConnectionSnapshot,
    account_approval: PostgreSQLProfilingAccountApproval,
    username: str,
    password: SecretStr,
) -> None:
    """Validate credentials without extracting the plaintext password.

    The caller must supply a trusted internal connection snapshot
    and independently established account approval.

    This function checks identity consistency and requires a
    nonempty request-scoped password.

    It does not authenticate credentials, establish account
    approval, or prove that database privileges are read-only.

    Successful validation is not permission to execute profiling.
    """

    require_postgresql_profiling_execution_enabled(settings)

    if not isinstance(data_source_id, UUID):
        raise PostgreSQLProfilingCredentialAuthorizationError(
            "A valid profiling data source UUID is required."
        )

    if not isinstance(
        snapshot,
        PostgreSQLProfilingConnectionSnapshot,
    ):
        raise PostgreSQLProfilingCredentialAuthorizationError(
            "A valid profiling connection snapshot is required."
        )

    if (
        not isinstance(snapshot.data_source_id, UUID)
        or snapshot.data_source_id != data_source_id
    ):
        raise PostgreSQLProfilingCredentialAuthorizationError(
            "Profiling connection snapshot source mismatch."
        )

    if (
        type(snapshot.connection_revision) is not int
        or snapshot.connection_revision <= 0
    ):
        raise PostgreSQLProfilingCredentialAuthorizationError(
            "Profiling connection snapshot revision is invalid."
        )

    config = snapshot.config

    if not isinstance(config, DatabaseConnectionConfig):
        raise PostgreSQLProfilingCredentialAuthorizationError(
            "Profiling connection snapshot configuration is invalid."
        )

    if not isinstance(
        account_approval,
        PostgreSQLProfilingAccountApproval,
    ):
        raise PostgreSQLProfilingCredentialAuthorizationError(
            "Trusted profiling account approval is required."
        )

    if (
        not isinstance(account_approval.data_source_id, UUID)
        or account_approval.data_source_id != data_source_id
    ):
        raise PostgreSQLProfilingCredentialAuthorizationError(
            "Profiling account approval source mismatch."
        )

    if (
        type(account_approval.connection_revision) is not int
        or account_approval.connection_revision <= 0
        or account_approval.connection_revision
        != snapshot.connection_revision
    ):
        raise PostgreSQLProfilingCredentialAuthorizationError(
            "Profiling account approval revision is invalid or stale."
        )

    if not isinstance(username, str) or not username.strip():
        raise PostgreSQLProfilingCredentialAuthorizationError(
            "A valid profiling database username is required."
        )

    if (
        not isinstance(config.username, str)
        or not config.username.strip()
        or config.username != username
    ):
        raise PostgreSQLProfilingCredentialAuthorizationError(
            "Profiling connection snapshot username mismatch."
        )

    if (
        not isinstance(account_approval.username, str)
        or not account_approval.username.strip()
        or account_approval.username != username
    ):
        raise PostgreSQLProfilingCredentialAuthorizationError(
            "Profiling database account is not approved."
        )

    if type(password) is not SecretStr or len(password) == 0:
        raise PostgreSQLProfilingCredentialAuthorizationError(
            "A nonempty profiling database password is required."
        )

    return None
