"""Security and behavior tests for draft Data Quality rule creation."""

from fastapi.testclient import TestClient

from app.main import app


def test_unauthenticated_user_cannot_create_range_rule():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/data-quality-rules",
            json={
                "data_field_id": "00000000-0000-4000-8000-000000000001",
                "rule_name": "Latitude Range",
                "min_value": "-90",
                "max_value": "90",
                "null_allowed": False,
            },
        )

    assert response.status_code == 401


def test_authenticated_user_can_create_draft_range_rule():
    """Draft creation must return identifiers without activating a rule."""
    import uuid
    from unittest.mock import MagicMock

    from app.api.dependencies.auth import (
        AuthenticatedSession,
        require_authenticated_session,
    )
    from app.db.session import get_db
    from app.models.user import User

    field_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="dq_rule_create_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )
    from app.models.data_field import DataField
    from app.models.source_object import SourceObject
    from app.models.data_source import DataSource

    object_id = uuid.uuid4()
    source_id = uuid.uuid4()
    project_id = uuid.uuid4()

    data_field = DataField(
        id=field_id,
        source_object_id=object_id,
        field_name="latitude",
        ordinal_position=1,
    )
    source_object = SourceObject(
        id=object_id,
        data_source_id=source_id,
        object_type="table",
        object_name="locations",
    )
    data_source = DataSource(
        id=source_id,
        project_id=project_id,
        name="Synthetic test source",
        source_type="postgresql",
        connection_mode="read_only",
    )

    db = MagicMock()
    db.get.side_effect = [data_field, source_object, data_source]
    db.scalar.return_value = uuid.uuid4()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="dq-rule-create-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/data-quality-rules",
                json={
                    "data_field_id": str(field_id),
                    "rule_name": "Latitude Range",
                    "min_value": "-90",
                    "max_value": "90",
                    "null_allowed": False,
                },
            )

        assert response.status_code == 201
        result = response.json()
        assert result["data_field_id"] == str(field_id)
        assert result["version_number"] == 1
        assert result["rule_status"] == "draft"
        assert result["version_status"] == "draft"
        assert result["active_version_id"] is None
        assert uuid.UUID(result["rule_id"])
        assert uuid.UUID(result["version_id"])
        db.commit.assert_called_once()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)



def test_user_without_project_access_cannot_create_range_rule():
    """A field UUID must not bypass explicit project authorization."""
    import uuid
    from unittest.mock import MagicMock

    from app.api.dependencies.auth import (
        AuthenticatedSession,
        require_authenticated_session,
    )
    from app.db.session import get_db
    from app.models.data_field import DataField
    from app.models.data_source import DataSource
    from app.models.source_object import SourceObject
    from app.models.user import User

    field_id = uuid.uuid4()
    object_id = uuid.uuid4()
    source_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="dq_no_project_access_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )

    db = MagicMock()
    db.get.side_effect = [
        DataField(
            id=field_id,
            source_object_id=object_id,
            field_name="latitude",
            ordinal_position=1,
        ),
        SourceObject(
            id=object_id,
            data_source_id=source_id,
            object_type="table",
            object_name="locations",
        ),
        DataSource(
            id=source_id,
            project_id=uuid.uuid4(),
            name="Restricted synthetic source",
            source_type="postgresql",
            connection_mode="read_only",
        ),
    ]
    db.scalar.return_value = None

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="dq-no-access-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/data-quality-rules",
                json={
                    "data_field_id": str(field_id),
                    "rule_name": "Latitude Range",
                    "min_value": "-90",
                    "max_value": "90",
                },
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "Data field not found."}
        db.add.assert_not_called()
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_draft_range_rule_creation_rolls_back_on_commit_failure():
    """A failed commit must roll back the draft rule transaction."""
    import uuid
    from unittest.mock import MagicMock

    import pytest

    from app.api.dependencies.auth import (
        AuthenticatedSession,
        require_authenticated_session,
    )
    from app.db.session import get_db
    from app.models.data_field import DataField
    from app.models.data_source import DataSource
    from app.models.source_object import SourceObject
    from app.models.user import User

    field_id = uuid.uuid4()
    object_id = uuid.uuid4()
    source_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="dq_rollback_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )

    db = MagicMock()
    db.get.side_effect = [
        DataField(
            id=field_id,
            source_object_id=object_id,
            field_name="latitude",
            ordinal_position=1,
        ),
        SourceObject(
            id=object_id,
            data_source_id=source_id,
            object_type="table",
            object_name="locations",
        ),
        DataSource(
            id=source_id,
            project_id=uuid.uuid4(),
            name="Rollback synthetic source",
            source_type="postgresql",
            connection_mode="read_only",
        ),
    ]
    db.scalar.return_value = uuid.uuid4()
    db.commit.side_effect = RuntimeError("Simulated database commit failure")

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="dq-rollback-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with pytest.raises(RuntimeError, match="Simulated database commit failure"):
            with TestClient(app) as client:
                client.post(
                    "/api/v1/data-quality-rules",
                    json={
                        "data_field_id": str(field_id),
                        "rule_name": "Latitude Range",
                        "min_value": "-90",
                        "max_value": "90",
                    },
                )

        assert db.add.call_count == 2
        db.commit.assert_called_once()
        db.rollback.assert_called_once()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)
