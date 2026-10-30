import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.routes.postgresql_connections import put_postgresql_connection_identity
from app.models.data_source import DataSource
from app.models.postgresql_connection_identity import PostgreSQLConnectionIdentity
from app.schemas.postgresql_connection_identity import PostgreSQLConnectionIdentityUpdate


@pytest.fixture
def context():
    source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    session = SimpleNamespace(user=SimpleNamespace(id=uuid.uuid4()))
    source = SimpleNamespace(
        id=source_id,
        project_id=project_id,
        source_type="postgresql",
        connection_mode="database",
    )
    db = MagicMock()
    db.scalar.return_value = source
    db.get.return_value = None
    payload = PostgreSQLConnectionIdentityUpdate(
        host="database.internal",
        port=5432,
        database_name="client_data",
        expected_current_host="database.internal",
        expected_current_port=5432,
        expected_current_database_name="client_data",
    )
    return db, session, source, payload


def execute(context):
    db, session, source, payload = context
    return put_postgresql_connection_identity(
        source.id, payload, db=db, session=session
    )


def test_missing_source_rejected(context):
    db, session, source, payload = context
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc:
        execute(context)

    assert exc.value.status_code == 404
    db.commit.assert_not_called()


@pytest.mark.parametrize("code", [403, 404])
def test_unauthorized_registration_rejected(context, code):
    db, session, source, payload = context

    with patch(
        "app.api.routes.postgresql_connections.require_data_source_connection_manager",
        side_effect=HTTPException(status_code=code, detail="Denied"),
    ):
        with pytest.raises(HTTPException) as exc:
            execute(context)

    assert exc.value.status_code == code
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "source_type,connection_mode",
    [("csv", "file"), ("postgresql", "file")],
)
def test_incompatible_source_rejected(context, source_type, connection_mode):
    db, session, source, payload = context
    source.source_type = source_type
    source.connection_mode = connection_mode

    with patch(
        "app.api.routes.postgresql_connections.require_data_source_connection_manager"
    ):
        with pytest.raises(HTTPException) as exc:
            execute(context)

    assert exc.value.status_code == 400
    db.commit.assert_not_called()


def test_new_identity_starts_unverified(context):
    db, session, source, payload = context

    with patch(
        "app.api.routes.postgresql_connections.require_data_source_connection_manager"
    ):
        identity = execute(context)

    assert isinstance(identity, PostgreSQLConnectionIdentity)
    assert identity.is_verified is False
    assert identity.verified_at is None
    assert identity.connection_revision == 1
    db.add.assert_called_once_with(identity)
    db.commit.assert_called_once()


@pytest.mark.parametrize("changed_field", ["host", "port", "database_name"])
def test_destination_change_invalidates_verification(context, changed_field):
    db, session, source, payload = context
    identity = SimpleNamespace(
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        connection_revision=1,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )
    changes = {
        "host": "another.internal",
        "port": 5433,
        "database_name": "another_database",
    }
    setattr(identity, changed_field, changes[changed_field])
    db.get.return_value = identity

    # Expected values describe the destination currently stored in the database.
    payload.expected_current_host = identity.host
    payload.expected_current_port = identity.port
    payload.expected_current_database_name = identity.database_name

    with patch(
        "app.api.routes.postgresql_connections.require_data_source_connection_manager"
    ):
        result = execute(context)

    assert result is identity
    assert identity.is_verified is False
    assert identity.verified_at is None
    assert identity.connection_revision == 2
    db.commit.assert_called_once()


def test_unchanged_destination_preserves_verification(context):
    db, session, source, payload = context
    verified_at = datetime.now(timezone.utc)
    identity = SimpleNamespace(
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        connection_revision=1,
        is_verified=True,
        verified_at=verified_at,
    )
    db.get.return_value = identity

    with patch(
        "app.api.routes.postgresql_connections.require_data_source_connection_manager"
    ):
        execute(context)

    assert identity.is_verified is True
    assert identity.verified_at == verified_at
    assert identity.connection_revision == 1
    db.commit.assert_called_once()



def test_registration_locks_parent_data_source(context):
    db, session, source, payload = context

    with patch(
        "app.api.routes.postgresql_connections.require_data_source_connection_manager"
    ):
        execute(context)

    db.scalar.assert_called_once()
    statement = db.scalar.call_args.args[0]
    assert statement._for_update_arg is not None
    db.commit.assert_called_once()



def test_stale_expected_values_return_409(context):
    db, session, source, payload = context
    identity = SimpleNamespace(
        host="newer.internal",
        port=5432,
        database_name="client_data",
        connection_revision=1,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )
    db.get.return_value = identity

    with patch(
        "app.api.routes.postgresql_connections.require_data_source_connection_manager"
    ):
        with pytest.raises(HTTPException) as exc:
            execute(context)

    assert exc.value.status_code == 409
    db.commit.assert_not_called()


def test_missing_expected_values_return_409(context):
    db, session, source, payload = context
    identity = SimpleNamespace(
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        connection_revision=1,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )
    payload.expected_current_host = None
    payload.expected_current_port = None
    payload.expected_current_database_name = None
    db.get.return_value = identity

    with patch(
        "app.api.routes.postgresql_connections.require_data_source_connection_manager"
    ):
        with pytest.raises(HTTPException) as exc:
            execute(context)

    assert exc.value.status_code == 409
    db.commit.assert_not_called()



def test_destination_change_and_revert_increments_revision(context):
    db, session, source, payload = context

    identity = SimpleNamespace(
        host="database.internal",
        port=5432,
        database_name="client_data",
        connection_revision=1,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )
    db.get.return_value = identity

    with patch(
        "app.api.routes.postgresql_connections.require_data_source_connection_manager"
    ):
        # First update: destination A -> B.
        payload.host = "another.internal"
        result = execute(context)

        assert result is identity
        assert identity.host == "another.internal"
        assert identity.connection_revision == 2
        assert identity.is_verified is False
        assert identity.verified_at is None

        # Second update: destination B -> A.
        payload.expected_current_host = "another.internal"
        payload.host = "database.internal"
        result = execute(context)

    assert result is identity
    assert identity.host == "database.internal"
    assert identity.connection_revision == 3
    assert identity.is_verified is False
    assert identity.verified_at is None
    assert db.commit.call_count == 2
