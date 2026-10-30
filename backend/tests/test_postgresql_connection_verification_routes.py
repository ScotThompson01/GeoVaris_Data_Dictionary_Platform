"""Security tests for the PostgreSQL connection verification API."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.data_source import DataSource
from app.schemas.postgresql_connection_identity import (
    PostgreSQLConnectionVerificationRequest,
)


@pytest.fixture
def context():
    """Create an isolated authorized PostgreSQL source test context."""
    db = MagicMock()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    source_id = uuid.uuid4()

    session = SimpleNamespace(
        user=SimpleNamespace(id=user_id)
    )

    source = SimpleNamespace(
        id=source_id,
        project_id=project_id,
        source_type="postgresql",
        connection_mode="database",
        is_active=True,
    )

    db.get.side_effect = (
        lambda model, record_id:
        source
        if model is DataSource and record_id == source_id
        else None
    )

    payload = PostgreSQLConnectionVerificationRequest(
        username="readonly_user",
        password="runtime_secret",
        connect_timeout_seconds=10,
    )

    return db, session, source, payload



def test_verification_missing_source_returns_404(context):
    from app.api.routes.postgresql_connections import (
        verify_postgresql_connection_route,
    )

    db, session, source, payload = context
    db.get.return_value = None
    db.get.side_effect = lambda model, record_id: None

    with patch(
        "app.api.routes.postgresql_connections.verify_postgresql_connection"
    ) as verify:
        with pytest.raises(HTTPException) as exc:
            verify_postgresql_connection_route(
                source.id, payload, db=db, session=session
            )

    assert exc.value.status_code == 404
    verify.assert_not_called()


def test_verification_missing_project_membership_returns_404(context):
    from app.api.routes.postgresql_connections import (
        verify_postgresql_connection_route,
    )

    db, session, source, payload = context

    with (
        patch(
            "app.api.routes.postgresql_connections."
            "require_data_source_connection_manager",
            side_effect=HTTPException(
                status_code=404,
                detail="Project not found.",
            ),
        ),
        patch(
            "app.api.routes.postgresql_connections."
            "verify_postgresql_connection"
        ) as verify,
    ):
        with pytest.raises(HTTPException) as exc:
            verify_postgresql_connection_route(
                source.id, payload, db=db, session=session
            )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Data source not found."
    verify.assert_not_called()


def test_verification_missing_management_permission_returns_403(context):
    from app.api.routes.postgresql_connections import (
        verify_postgresql_connection_route,
    )

    db, session, source, payload = context

    with (
        patch(
            "app.api.routes.postgresql_connections."
            "require_data_source_connection_manager",
            side_effect=HTTPException(
                status_code=403,
                detail="Permission required.",
            ),
        ),
        patch(
            "app.api.routes.postgresql_connections."
            "verify_postgresql_connection"
        ) as verify,
    ):
        with pytest.raises(HTTPException) as exc:
            verify_postgresql_connection_route(
                source.id, payload, db=db, session=session
            )

    assert exc.value.status_code == 403
    verify.assert_not_called()



@pytest.mark.parametrize(
    ("attribute", "invalid_value"),
    [
        ("source_type", "sqlserver"),
        ("connection_mode", "file"),
        ("is_active", False),
    ],
)
def test_verification_rejects_invalid_source_configuration(
    context, attribute, invalid_value
):
    from app.api.routes.postgresql_connections import (
        verify_postgresql_connection_route,
    )

    db, session, source, payload = context
    setattr(source, attribute, invalid_value)

    with (
        patch(
            "app.api.routes.postgresql_connections."
            "require_data_source_connection_manager"
        ) as authorize,
        patch(
            "app.api.routes.postgresql_connections."
            "verify_postgresql_connection"
        ) as verify,
    ):
        with pytest.raises(HTTPException) as exc:
            verify_postgresql_connection_route(
                source.id,
                payload,
                db=db,
                session=session,
            )

    assert exc.value.status_code == 400
    authorize.assert_called_once_with(
        db,
        user_id=session.user.id,
        project_id=source.project_id,
    )
    verify.assert_not_called()



def test_authorized_manager_can_request_verification(context):
    from app.api.routes.postgresql_connections import (
        verify_postgresql_connection_route,
    )

    db, session, source, payload = context
    verified_identity = SimpleNamespace(
        data_source_id=source.id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        is_verified=True,
    )

    with (
        patch(
            "app.api.routes.postgresql_connections."
            "require_data_source_connection_manager"
        ) as authorize,
        patch(
            "app.api.routes.postgresql_connections."
            "verify_postgresql_connection",
            return_value=verified_identity,
        ) as verify,
    ):
        result = verify_postgresql_connection_route(
            source.id,
            payload,
            db=db,
            session=session,
        )

    authorize.assert_called_once_with(
        db,
        user_id=session.user.id,
        project_id=source.project_id,
    )
    verify.assert_called_once_with(
        db,
        data_source_id=source.id,
        username="readonly_user",
        password="runtime_secret",
        connect_timeout_seconds=10,
    )
    assert result is verified_identity
    assert source.is_active is True
    assert source.source_type == "postgresql"
    assert source.connection_mode == "database"
    db.commit.assert_not_called()



def test_verification_failure_does_not_disclose_credentials(context):
    from app.api.routes.postgresql_connections import (
        verify_postgresql_connection_route,
    )

    db, session, source, payload = context
    sensitive_details = (
        "runtime_secret host=database.internal "
        "user=readonly_user"
    )

    with (
        patch(
            "app.api.routes.postgresql_connections."
            "require_data_source_connection_manager"
        ),
        patch(
            "app.api.routes.postgresql_connections."
            "verify_postgresql_connection",
            side_effect=RuntimeError(sensitive_details),
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            verify_postgresql_connection_route(
                source.id,
                payload,
                db=db,
                session=session,
            )

    assert exc.value.status_code == 502
    response_detail = str(exc.value.detail)
    assert response_detail == "PostgreSQL connection verification failed."
    assert "runtime_secret" not in response_detail
    assert "database.internal" not in response_detail
    assert "readonly_user" not in response_detail



def test_verification_configuration_failure_is_sanitized(context):
    from app.api.routes.postgresql_connections import (
        verify_postgresql_connection_route,
    )
    from app.services.postgresql_verification_policy import (
        PostgreSQLVerificationPolicyError,
    )

    db, session, source, payload = context

    with (
        patch(
            "app.api.routes.postgresql_connections."
            "require_data_source_connection_manager"
        ),
        patch(
            "app.api.routes.postgresql_connections."
            "verify_postgresql_connection",
            side_effect=PostgreSQLVerificationPolicyError(
                "runtime_secret database.internal "
                "invalid private CA configuration"
            ),
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            verify_postgresql_connection_route(
                source.id,
                payload,
                db=db,
                session=session,
            )

    assert exc.value.status_code == 503
    assert exc.value.detail == (
        "PostgreSQL connection verification is unavailable."
    )
    assert "runtime_secret" not in str(exc.value.detail)
    assert "database.internal" not in str(exc.value.detail)
    assert "private CA" not in str(exc.value.detail)



def test_verification_unregistered_identity_returns_404(context):
    from app.api.routes.postgresql_connections import (
        verify_postgresql_connection_route,
    )

    from app.services.postgresql_connection_verification import (
        PostgreSQLConnectionIdentityNotRegisteredError,
    )

    db, session, source, payload = context

    with (
        patch(
            "app.api.routes.postgresql_connections."
            "require_data_source_connection_manager"
        ),
        patch(
            "app.api.routes.postgresql_connections."
            "verify_postgresql_connection",
            side_effect=PostgreSQLConnectionIdentityNotRegisteredError(
                "PostgreSQL connection identity not registered."
            ),
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            verify_postgresql_connection_route(
                source.id,
                payload,
                db=db,
                session=session,
            )

    assert exc.value.status_code == 404
    assert exc.value.detail == (
        "PostgreSQL connection identity not registered."
    )
    db.rollback.assert_called_once()



def test_verification_concurrent_change_returns_409(context):
    from app.api.routes.postgresql_connections import (
        verify_postgresql_connection_route,
    )
    from app.services.postgresql_connection_verification import (
        PostgreSQLConnectionDestinationChangedError,
    )

    db, session, source, payload = context

    with (
        patch(
            "app.api.routes.postgresql_connections."
            "require_data_source_connection_manager"
        ),
        patch(
            "app.api.routes.postgresql_connections."
            "verify_postgresql_connection",
            side_effect=PostgreSQLConnectionDestinationChangedError(
                "runtime_secret database.internal "
                "destination changed during verification"
            ),
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            verify_postgresql_connection_route(
                source.id,
                payload,
                db=db,
                session=session,
            )

    assert exc.value.status_code == 409
    assert exc.value.detail == (
        "PostgreSQL connection settings changed. "
        "Reload the connection settings and try again."
    )
    assert "runtime_secret" not in str(exc.value.detail)
    assert "database.internal" not in str(exc.value.detail)
    db.rollback.assert_called_once()
