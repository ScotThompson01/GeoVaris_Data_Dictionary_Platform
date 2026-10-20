"""HTTP tests for authorized field-governance behavior."""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.main import app
from app.models.user import User


client = TestClient(app)


@pytest.fixture(autouse=True)
def authenticated_field_governance_requests():
    """Authenticate requests in this module without creating a real user."""
    test_user = User(
        id=uuid.uuid4(),
        username="field_governance_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )

    def override_authentication():
        return AuthenticatedSession(
            user=test_user,
            token="field-governance-test-only-token",
        )

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )

    try:
        yield
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session,
            None,
        )


def test_authorized_get_returns_defaults_when_governance_does_not_exist():
    from app.models.data_field import DataField
    from app.models.data_source import DataSource
    from app.models.source_object import SourceObject

    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()

    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
    )
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )

    db = MagicMock()
    db.get.side_effect = [
        data_field,
        source_object,
        data_source,
    ]
    db.scalar.side_effect = [
        uuid.uuid4(),  # Authorized project-access grant.
        None,  # No governance record exists yet.
    ]

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get(
            f"/api/v1/field-governance/{data_field_id}"
        )

        assert response.status_code == 200

        body = response.json()
        assert body["data_field_id"] == str(data_field_id)
        assert body["is_cde"] is False
        assert body["approval_status"] == "draft"
        assert body["business_name"] is None
        assert body["business_definition"] is None

        db.add.assert_not_called()
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_authorized_get_returns_defaults_when_governance_does_not_exist():
    from app.models.data_field import DataField
    from app.models.data_source import DataSource
    from app.models.source_object import SourceObject

    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()

    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
    )
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )

    db = MagicMock()
    db.get.side_effect = [
        data_field,
        source_object,
        data_source,
    ]
    db.scalar.side_effect = [
        uuid.uuid4(),  # Authorized project-access grant.
        None,  # No governance record exists yet.
    ]

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get(
            f"/api/v1/field-governance/{data_field_id}"
        )

        assert response.status_code == 200

        body = response.json()
        assert body["data_field_id"] == str(data_field_id)
        assert body["is_cde"] is False
        assert body["approval_status"] == "draft"
        assert body["business_name"] is None
        assert body["business_definition"] is None

        db.add.assert_not_called()
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_authorized_get_returns_existing_governance_metadata():
    from app.models.data_field import DataField
    from app.models.data_source import DataSource
    from app.models.field_governance_metadata import FieldGovernanceMetadata
    from app.models.source_object import SourceObject

    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()

    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
    )
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )
    governance = FieldGovernanceMetadata(
        id=uuid.uuid4(),
        data_field_id=data_field_id,
        business_name="Customer Identifier",
        business_definition="Unique identifier for a customer.",
        department="Customer Operations",
        data_owner="Operations Director",
        data_steward="Customer Data Steward",
        business_process="Customer Management",
        system_of_record="CRM",
        is_cde=True,
        classification="Confidential",
        approval_status="steward_review",
        notes="Reviewed for Phase 4 testing.",
    )

    db = MagicMock()
    db.get.side_effect = [
        data_field,
        source_object,
        data_source,
    ]
    db.scalar.side_effect = [
        uuid.uuid4(),  # Authorized project-access grant.
        governance,
    ]

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get(
            f"/api/v1/field-governance/{data_field_id}"
        )

        assert response.status_code == 200

        body = response.json()
        assert body["data_field_id"] == str(data_field_id)
        assert body["business_name"] == "Customer Identifier"
        assert body["business_definition"] == "Unique identifier for a customer."
        assert body["department"] == "Customer Operations"
        assert body["data_owner"] == "Operations Director"
        assert body["data_steward"] == "Customer Data Steward"
        assert body["business_process"] == "Customer Management"
        assert body["system_of_record"] == "CRM"
        assert body["is_cde"] is True
        assert body["classification"] == "Confidential"
        assert body["approval_status"] == "steward_review"
        assert body["notes"] == "Reviewed for Phase 4 testing."

        db.add.assert_not_called()
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_authorized_put_creates_governance_metadata():
    from app.models.data_field import DataField
    from app.models.data_source import DataSource
    from app.models.field_governance_metadata import FieldGovernanceMetadata
    from app.models.source_object import SourceObject

    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()

    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
    )
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )

    db = MagicMock()
    db.get.side_effect = [
        data_field,
        source_object,
        data_source,
    ]
    db.scalar.side_effect = [
        uuid.uuid4(),  # Authorized project-access grant.
        None,  # No governance record exists yet.
    ]

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    payload = {
        "business_name": "Customer Identifier",
        "business_definition": "Unique identifier for a customer.",
        "department": "Customer Operations",
        "data_owner": "Operations Director",
        "data_steward": "Customer Data Steward",
        "business_process": "Customer Management",
        "system_of_record": "CRM",
        "is_cde": True,
        "classification": "Confidential",
        "approval_status": "steward_review",
        "notes": "Created through the governance API.",
    }

    try:
        response = client.put(
            f"/api/v1/field-governance/{data_field_id}",
            json=payload,
        )

        assert response.status_code == 200

        body = response.json()
        assert body["data_field_id"] == str(data_field_id)

        for field_name, expected_value in payload.items():
            assert body[field_name] == expected_value

        db.add.assert_called_once()
        created = db.add.call_args.args[0]

        assert isinstance(created, FieldGovernanceMetadata)
        assert created.data_field_id == data_field_id

        for field_name, expected_value in payload.items():
            assert getattr(created, field_name) == expected_value

        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(created)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_authorized_put_creates_governance_metadata():
    from app.models.data_field import DataField
    from app.models.data_source import DataSource
    from app.models.field_governance_metadata import FieldGovernanceMetadata
    from app.models.source_object import SourceObject

    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()

    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
    )
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )

    db = MagicMock()
    db.get.side_effect = [
        data_field,
        source_object,
        data_source,
    ]
    db.scalar.side_effect = [
        uuid.uuid4(),  # Authorized project-access grant.
        None,  # No governance record exists yet.
    ]

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    payload = {
        "business_name": "Customer Identifier",
        "business_definition": "Unique identifier for a customer.",
        "department": "Customer Operations",
        "data_owner": "Operations Director",
        "data_steward": "Customer Data Steward",
        "business_process": "Customer Management",
        "system_of_record": "CRM",
        "is_cde": True,
        "classification": "Confidential",
        "approval_status": "steward_review",
        "notes": "Created through the governance API.",
    }

    try:
        response = client.put(
            f"/api/v1/field-governance/{data_field_id}",
            json=payload,
        )

        assert response.status_code == 200

        body = response.json()
        assert body["data_field_id"] == str(data_field_id)

        for field_name, expected_value in payload.items():
            assert body[field_name] == expected_value

        db.add.assert_called_once()
        created = db.add.call_args.args[0]

        assert isinstance(created, FieldGovernanceMetadata)
        assert created.data_field_id == data_field_id

        for field_name, expected_value in payload.items():
            assert getattr(created, field_name) == expected_value

        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(created)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_authorized_put_updates_existing_governance_metadata():
    from app.models.data_field import DataField
    from app.models.data_source import DataSource
    from app.models.field_governance_metadata import FieldGovernanceMetadata
    from app.models.source_object import SourceObject

    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()

    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
    )
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )
    governance = FieldGovernanceMetadata(
        id=uuid.uuid4(),
        data_field_id=data_field_id,
        business_name="Old Name",
        department="Old Department",
        data_owner="Old Owner",
        is_cde=False,
        approval_status="draft",
    )

    db = MagicMock()
    db.get.side_effect = [
        data_field,
        source_object,
        data_source,
    ]
    db.scalar.side_effect = [
        uuid.uuid4(),  # Authorized project-access grant.
        governance,
    ]

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    payload = {
        "business_name": "Customer Identifier",
        "department": "Customer Operations",
        "data_owner": "Operations Director",
        "is_cde": True,
        "approval_status": "owner_approval",
    }

    try:
        response = client.put(
            f"/api/v1/field-governance/{data_field_id}",
            json=payload,
        )

        assert response.status_code == 200

        body = response.json()
        assert body["business_name"] == "Customer Identifier"
        assert body["department"] == "Customer Operations"
        assert body["data_owner"] == "Operations Director"
        assert body["is_cde"] is True
        assert body["approval_status"] == "owner_approval"

        assert governance.business_name == "Customer Identifier"
        assert governance.department == "Customer Operations"
        assert governance.data_owner == "Operations Director"
        assert governance.is_cde is True
        assert governance.approval_status == "owner_approval"

        db.add.assert_not_called()
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(governance)
    finally:
        app.dependency_overrides.pop(get_db, None)

def test_rejects_steward_assignment_from_another_client():
    from app.models.data_field import DataField
    from app.models.data_source import DataSource
    from app.models.source_object import SourceObject
    from app.models.project import Project

    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    client_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
    )
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )
    project = Project(
        id=project_id,
        client_id=client_id,
    )

    db = MagicMock()
    db.get.side_effect = [
        data_field,
        source_object,
        data_source,
        project,
    ]
    db.scalar.side_effect = [
        uuid.uuid4(),  # Authorized project access.
        None,  # No existing field governance record.
        None,  # No assignment for the field's client.
    ]

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.put(
            f"/api/v1/field-governance/{data_field_id}",
            json={"steward_assignment_id": str(assignment_id)},
        )

        assert response.status_code == 422
        assert "not available for this client" in (
            response.json()["detail"]
        )

        db.commit.assert_not_called()

        # Ensure the assignment lookup includes the client's ID.
        assignment_query = db.scalar.call_args_list[2].args[0]
        compiled = assignment_query.compile()
        assert client_id in compiled.params.values()
        assert assignment_id in compiled.params.values()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_rejects_non_steward_governance_assignment():
    from app.models.data_field import DataField
    from app.models.data_source import DataSource
    from app.models.source_object import SourceObject
    from app.models.project import Project
    from app.models.governance_assignment import GovernanceAssignment

    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    client_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
    )
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )
    project = Project(
        id=project_id,
        client_id=client_id,
    )
    assignment = GovernanceAssignment(
        id=assignment_id,
        client_id=client_id,
        person_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        role="department_data_owner",
        is_active=True,
    )

    db = MagicMock()
    db.get.side_effect = [
        data_field,
        source_object,
        data_source,
        project,
    ]
    db.scalar.side_effect = [
        uuid.uuid4(),  # Authorized project access.
        None,  # No existing field governance record.
        assignment,
    ]

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.put(
            f"/api/v1/field-governance/{data_field_id}",
            json={"steward_assignment_id": str(assignment_id)},
        )

        assert response.status_code == 422
        assert "not currently valid" in response.json()["detail"]
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_rejects_inactive_steward_assignment():
    from app.models.data_field import DataField
    from app.models.data_source import DataSource
    from app.models.source_object import SourceObject
    from app.models.project import Project
    from app.models.governance_assignment import GovernanceAssignment

    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    client_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
    )
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )
    project = Project(
        id=project_id,
        client_id=client_id,
    )
    assignment = GovernanceAssignment(
        id=assignment_id,
        client_id=client_id,
        person_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        role="data_steward",
        is_active=False,
    )

    db = MagicMock()
    db.get.side_effect = [
        data_field,
        source_object,
        data_source,
        project,
    ]
    db.scalar.side_effect = [
        uuid.uuid4(),  # Authorized project access.
        None,  # No existing governance record.
        assignment,
    ]

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.put(
            f"/api/v1/field-governance/{data_field_id}",
            json={"steward_assignment_id": str(assignment_id)},
        )

        assert response.status_code == 422
        assert "not currently valid" in response.json()["detail"]
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize("date_scenario", ["future", "expired"])
def test_rejects_steward_assignment_outside_effective_dates(date_scenario):
    from datetime import date, timedelta

    from app.models.data_field import DataField
    from app.models.data_source import DataSource
    from app.models.source_object import SourceObject
    from app.models.project import Project
    from app.models.governance_assignment import GovernanceAssignment

    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    client_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    today = date.today()

    if date_scenario == "future":
        effective_start = today + timedelta(days=1)
        effective_end = None
    else:
        effective_start = None
        effective_end = today - timedelta(days=1)

    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
    )
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )
    project = Project(
        id=project_id,
        client_id=client_id,
    )
    assignment = GovernanceAssignment(
        id=assignment_id,
        client_id=client_id,
        person_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        role="data_steward",
        is_active=True,
        effective_start=effective_start,
        effective_end=effective_end,
    )

    db = MagicMock()
    db.get.side_effect = [
        data_field,
        source_object,
        data_source,
        project,
    ]
    db.scalar.side_effect = [
        uuid.uuid4(),
        None,
        assignment,
    ]

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.put(
            f"/api/v1/field-governance/{data_field_id}",
            json={"steward_assignment_id": str(assignment_id)},
        )

        assert response.status_code == 422
        assert "not currently valid" in response.json()["detail"]
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_valid_steward_assignment_preserves_existing_metadata():
    from app.models.data_field import DataField
    from app.models.data_source import DataSource
    from app.models.source_object import SourceObject
    from app.models.project import Project
    from app.models.governance_assignment import GovernanceAssignment
    from app.models.governance_person import GovernancePerson
    from app.models.governance_department import GovernanceDepartment
    from app.models.field_governance_metadata import FieldGovernanceMetadata

    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    client_id = uuid.uuid4()
    assignment_id = uuid.uuid4()
    person_id = uuid.uuid4()
    department_id = uuid.uuid4()

    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
    )
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )
    project = Project(
        id=project_id,
        client_id=client_id,
    )

    governance = FieldGovernanceMetadata(
        id=uuid.uuid4(),
        data_field_id=data_field_id,
        business_name="Customer Identifier",
        business_definition="Unique identifier for a customer.",
        department="Customer Operations",
        data_owner="Existing Data Owner",
        data_steward="Existing Data Steward",
        is_cde=True,
        approval_status="draft",
    )

    assignment = GovernanceAssignment(
        id=assignment_id,
        client_id=client_id,
        person_id=person_id,
        department_id=department_id,
        role="data_steward",
        is_active=True,
    )

    person = GovernancePerson(
        id=person_id,
        client_id=client_id,
        full_name="Approved Test Steward",
        is_active=True,
    )

    department = GovernanceDepartment(
        id=department_id,
        client_id=client_id,
        name="Customer Operations",
        is_active=True,
    )

    db = MagicMock()
    db.get.side_effect = [
        data_field,
        source_object,
        data_source,
        project,
    ]
    db.scalar.side_effect = [
        uuid.uuid4(),
        governance,
        assignment,
        person,
        department,
    ]

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.put(
            f"/api/v1/field-governance/{data_field_id}",
            json={"steward_assignment_id": str(assignment_id)},
        )

        assert response.status_code == 200, response.text
        assert response.json()["steward_assignment_id"] == str(assignment_id)

        assert governance.steward_assignment_id == assignment_id
        assert governance.business_name == "Customer Identifier"
        assert governance.business_definition == (
            "Unique identifier for a customer."
        )
        assert governance.department == "Customer Operations"
        assert governance.data_owner == "Existing Data Owner"
        assert governance.data_steward == "Existing Data Steward"
        assert governance.is_cde is True

        db.commit.assert_called_once()
        db.add.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_clearing_steward_assignment_preserves_existing_metadata():
    from app.models.data_field import DataField
    from app.models.data_source import DataSource
    from app.models.source_object import SourceObject
    from app.models.field_governance_metadata import FieldGovernanceMetadata

    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    old_assignment_id = uuid.uuid4()

    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
    )
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )

    governance = FieldGovernanceMetadata(
        id=uuid.uuid4(),
        data_field_id=data_field_id,
        steward_assignment_id=old_assignment_id,
        business_name="Customer Identifier",
        business_definition="Unique identifier for a customer.",
        department="Customer Operations",
        data_owner="Existing Data Owner",
        data_steward="Existing Data Steward",
        is_cde=True,
        approval_status="draft",
    )

    db = MagicMock()
    db.get.side_effect = [
        data_field,
        source_object,
        data_source,
    ]
    db.scalar.side_effect = [
        uuid.uuid4(),  # Authorized project access.
        governance,
    ]

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.put(
            f"/api/v1/field-governance/{data_field_id}",
            json={"steward_assignment_id": None},
        )

        assert response.status_code == 200, response.text
        assert response.json()["steward_assignment_id"] is None
        assert governance.steward_assignment_id is None

        assert governance.business_name == "Customer Identifier"
        assert governance.business_definition == (
            "Unique identifier for a customer."
        )
        assert governance.department == "Customer Operations"
        assert governance.data_owner == "Existing Data Owner"
        assert governance.data_steward == "Existing Data Steward"
        assert governance.is_cde is True

        db.commit.assert_called_once()
        db.add.assert_not_called()
        assert db.scalar.call_count == 2
    finally:
        app.dependency_overrides.pop(get_db, None)
