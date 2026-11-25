"""Fail-closed lookup of trusted PostgreSQL profiling account approvals."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.orm import Session

from app.connectors.database.base import DatabaseConnectionConfig
from app.core.config import settings
from app.models.postgresql_profiling_account_approval import (
    PostgreSQLProfilingAccountApprovalRecord,
)
from app.services.postgresql_profiling_connection_authorization import (
    PostgreSQLProfilingConnectionSnapshot,
)
from app.services.postgresql_profiling_credential_authorization import (
    PostgreSQLProfilingAccountApproval,
)
from app.services.postgresql_profiling_execution_policy import (
    require_postgresql_profiling_execution_enabled,
)


class PostgreSQLProfilingAccountApprovalError(ValueError):
    """A trusted database account approval is unavailable or invalid."""


def require_postgresql_profiling_account_approval(
    *,
    db: Session,
    data_source_id: UUID,
    snapshot: PostgreSQLProfilingConnectionSnapshot,
    username: str,
) -> PostgreSQLProfilingAccountApproval:
    """Retrieve an active approval from trusted application metadata.

    The caller must supply an internally authorized connection snapshot
    and a suitable transaction without pending approval modifications.

    The caller must separately authorize the user and profiling request
    and revalidate the registered connection in the same transaction.
    Connection identity locking must precede approval record locking.

    The approval row is refreshed and locked. The caller owns the
    transaction and must release the lock. This function does not write,
    flush, commit, roll back, or connect to the client database.

    The returned snapshot is non-secret and is not an execution token.
    It must not be reused across transactions as proof of current
    approval.
    """
    require_postgresql_profiling_execution_enabled(settings)

    if not isinstance(data_source_id, UUID):
        raise PostgreSQLProfilingAccountApprovalError(
            "A valid profiling data source UUID is required."
        )

    if not isinstance(snapshot, PostgreSQLProfilingConnectionSnapshot):
        raise PostgreSQLProfilingAccountApprovalError(
            "A valid profiling connection snapshot is required."
        )

    if (
        not isinstance(snapshot.data_source_id, UUID)
        or snapshot.data_source_id != data_source_id
    ):
        raise PostgreSQLProfilingAccountApprovalError(
            "Profiling connection snapshot source mismatch."
        )

    revision = snapshot.connection_revision

    if type(revision) is not int or revision <= 0:
        raise PostgreSQLProfilingAccountApprovalError(
            "Profiling connection revision is invalid."
        )

    config = snapshot.config

    if not isinstance(config, DatabaseConnectionConfig):
        raise PostgreSQLProfilingAccountApprovalError(
            "Profiling connection configuration is invalid."
        )

    if not isinstance(username, str) or not username.strip():
        raise PostgreSQLProfilingAccountApprovalError(
            "A valid profiling database username is required."
        )

    if (
        not isinstance(config.username, str)
        or not config.username.strip()
        or config.username != username
    ):
        raise PostgreSQLProfilingAccountApprovalError(
            "Profiling connection username mismatch."
        )

    try:
        record = (
            db.query(PostgreSQLProfilingAccountApprovalRecord)
            .filter(
                PostgreSQLProfilingAccountApprovalRecord.data_source_id
                == data_source_id,
                PostgreSQLProfilingAccountApprovalRecord.connection_revision
                == revision,
                PostgreSQLProfilingAccountApprovalRecord.username
                == username,
                PostgreSQLProfilingAccountApprovalRecord.revoked_at.is_(None),
            )
            .execution_options(
                populate_existing=True,
                autoflush=False,
            )
            .with_for_update()
            .one_or_none()
        )
    except MultipleResultsFound:
        raise PostgreSQLProfilingAccountApprovalError(
            "Profiling account approval is ambiguous."
        ) from None

    if record is None:
        raise PostgreSQLProfilingAccountApprovalError(
            "An active profiling account approval is required."
        )

    if not isinstance(record.id, UUID):
        raise PostgreSQLProfilingAccountApprovalError(
            "Profiling account approval identity is invalid."
        )

    if (
        not isinstance(record.data_source_id, UUID)
        or record.data_source_id != data_source_id
    ):
        raise PostgreSQLProfilingAccountApprovalError(
            "Profiling account approval source mismatch."
        )

    if (
        type(record.connection_revision) is not int
        or record.connection_revision <= 0
        or record.connection_revision != revision
    ):
        raise PostgreSQLProfilingAccountApprovalError(
            "Profiling account approval revision is invalid or stale."
        )

    if (
        not isinstance(record.username, str)
        or not record.username.strip()
        or record.username != username
    ):
        raise PostgreSQLProfilingAccountApprovalError(
            "Profiling database account is not approved."
        )

    if not isinstance(record.approved_by_user_id, UUID):
        raise PostgreSQLProfilingAccountApprovalError(
            "Profiling account approval actor is invalid."
        )

    if (
        not isinstance(record.approved_at, datetime)
        or record.approved_at.tzinfo is None
        or record.approved_at.utcoffset() is None
    ):
        raise PostgreSQLProfilingAccountApprovalError(
            "Profiling account approval timestamp is invalid."
        )

    if (
        record.revoked_at is not None
        or record.revoked_by_user_id is not None
    ):
        raise PostgreSQLProfilingAccountApprovalError(
            "Profiling account approval is revoked or inconsistent."
        )

    return PostgreSQLProfilingAccountApproval(
        data_source_id=data_source_id,
        connection_revision=revision,
        username=username,
    )
