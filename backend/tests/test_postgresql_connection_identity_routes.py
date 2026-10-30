import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.routes.postgresql_connections import get_postgresql_connection_identity
from app.models.data_source import DataSource
from app.models.postgresql_connection_identity import PostgreSQLConnectionIdentity


@pytest.fixture
def context():
    db = MagicMock()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    source_id = uuid.uuid4()
    session = SimpleNamespace(user=SimpleNamespace(id=user_id))
    source = SimpleNamespace(
        id=source_id,
        project_id=project_id,
        source_type="postgresql",
    )
    identity = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        is_verified=False,
    )

    def get_record(model, record_id):
        if model is DataSource:
            return source
        if model is PostgreSQLConnectionIdentity:
            return identity
        return None

    db.get.side_effect = get_record
    return db, session, source, identity


def test_missing_data_source_returns_404(context):
    db, session, source, identity = context
    db.get.return_value = None
    db.get.side_effect = lambda model, record_id: None

    with pytest.raises(HTTPException) as exc:
        get_postgresql_connection_identity(
            source.id, db=db, session=session
        )

    assert exc.value.status_code == 404


def test_missing_project_membership_returns_404(context):
    db, session, source, identity = context

    with patch(
        "app.api.routes.postgresql_connections.require_data_source_connection_manager",
        side_effect=HTTPException(status_code=404, detail="Project not found."),
    ):
        with pytest.raises(HTTPException) as exc:
            get_postgresql_connection_identity(
                source.id, db=db, session=session
            )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Data source not found."


def test_missing_management_permission_returns_403(context):
    db, session, source, identity = context

    with patch(
        "app.api.routes.postgresql_connections.require_data_source_connection_manager",
        side_effect=HTTPException(status_code=403, detail="Permission required."),
    ):
        with pytest.raises(HTTPException) as exc:
            get_postgresql_connection_identity(
                source.id, db=db, session=session
            )

    assert exc.value.status_code == 403


def test_non_postgresql_source_returns_400(context):
    db, session, source, identity = context
    source.source_type = "csv"

    with patch(
        "app.api.routes.postgresql_connections.require_data_source_connection_manager"
    ):
        with pytest.raises(HTTPException) as exc:
            get_postgresql_connection_identity(
                source.id, db=db, session=session
            )

    assert exc.value.status_code == 400


def test_unregistered_identity_returns_404(context):
    db, session, source, identity = context
    db.get.side_effect = (
        lambda model, record_id:
        source if model is DataSource else None
    )

    with patch(
        "app.api.routes.postgresql_connections.require_data_source_connection_manager"
    ):
        with pytest.raises(HTTPException) as exc:
            get_postgresql_connection_identity(
                source.id, db=db, session=session
            )

    assert exc.value.status_code == 404


def test_authorized_manager_can_read_identity(context):
    db, session, source, identity = context

    with patch(
        "app.api.routes.postgresql_connections.require_data_source_connection_manager"
    ) as authorize:
        result = get_postgresql_connection_identity(
            source.id, db=db, session=session
        )

    assert result is identity
    authorize.assert_called_once_with(
        db,
        user_id=session.user.id,
        project_id=source.project_id,
    )
    assert identity.is_verified is False
