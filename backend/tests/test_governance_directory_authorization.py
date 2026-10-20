"""Authorization tests for the client-scoped Governance People directory."""

import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.main import app
from app.models.governance_department import GovernanceDepartment
from app.models.governance_person import GovernancePerson
from app.models.user import User


def _request_people(*, client_id: uuid.UUID, grant_access: bool):
    user = User(
        id=uuid.uuid4(),
        username="governance_directory_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )

    db = MagicMock()
    db.scalar.return_value = uuid.uuid4() if grant_access else None
    db.scalars.return_value.all.return_value = []

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-directory-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.get(
                f"/api/v1/clients/{client_id}/governance/people"
            )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

    return response, db, user


def test_authorized_user_can_list_client_people():
    client_id = uuid.uuid4()

    response, db, user = _request_people(
        client_id=client_id,
        grant_access=True,
    )

    assert response.status_code == 200
    assert response.json() == []
    db.scalar.assert_called_once()
    db.scalars.assert_called_once()


def test_user_without_client_access_cannot_list_people():
    response, db, user = _request_people(
        client_id=uuid.uuid4(),
        grant_access=False,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Client not found."}
    db.scalars.assert_not_called()


def test_people_query_is_scoped_to_requested_client():
    client_id = uuid.uuid4()

    response, db, user = _request_people(
        client_id=client_id,
        grant_access=True,
    )

    assert response.status_code == 200

    actual_query = db.scalars.call_args.args[0]
    expected_query = (
        select(GovernancePerson)
        .where(GovernancePerson.client_id == client_id)
        .order_by(GovernancePerson.full_name, GovernancePerson.id)
    )

    assert actual_query.compare(expected_query), (
        "Governance People query must filter by the requested client."
    )


def _request_departments(*, client_id: uuid.UUID, grant_access: bool):
    user = User(
        id=uuid.uuid4(),
        username="governance_departments_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )

    db = MagicMock()
    db.scalar.return_value = uuid.uuid4() if grant_access else None
    db.scalars.return_value.all.return_value = []

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-departments-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.get(
                f"/api/v1/clients/{client_id}/governance/departments"
            )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

    return response, db


def test_authorized_user_can_list_client_departments():
    response, db = _request_departments(
        client_id=uuid.uuid4(),
        grant_access=True,
    )

    assert response.status_code == 200
    assert response.json() == []
    db.scalar.assert_called_once()
    db.scalars.assert_called_once()


def test_user_without_client_access_cannot_list_departments():
    response, db = _request_departments(
        client_id=uuid.uuid4(),
        grant_access=False,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Client not found."}
    db.scalars.assert_not_called()


def test_departments_query_is_scoped_to_requested_client():
    from app.models.governance_department import GovernanceDepartment

    client_id = uuid.uuid4()

    response, db = _request_departments(
        client_id=client_id,
        grant_access=True,
    )

    assert response.status_code == 200

    actual_query = db.scalars.call_args.args[0]
    expected_query = (
        select(GovernanceDepartment)
        .where(GovernanceDepartment.client_id == client_id)
        .order_by(GovernanceDepartment.name, GovernanceDepartment.id)
    )

    assert actual_query.compare(expected_query), (
        "Governance Departments query must filter by the requested client."
    )


def _request_assignments(*, client_id: uuid.UUID, grant_access: bool):
    user = User(
        id=uuid.uuid4(),
        username="governance_assignments_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )

    db = MagicMock()
    db.scalar.return_value = uuid.uuid4() if grant_access else None
    db.scalars.return_value.all.return_value = []

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-assignments-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.get(
                f"/api/v1/clients/{client_id}/governance/assignments"
            )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

    return response, db


def test_authorized_user_can_list_client_assignments():
    response, db = _request_assignments(
        client_id=uuid.uuid4(),
        grant_access=True,
    )

    assert response.status_code == 200
    assert response.json() == []
    db.scalar.assert_called_once()
    db.scalars.assert_called_once()


def test_user_without_client_access_cannot_list_assignments():
    response, db = _request_assignments(
        client_id=uuid.uuid4(),
        grant_access=False,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Client not found."}
    db.scalars.assert_not_called()


def test_assignments_query_is_scoped_to_requested_client():
    from app.models.governance_assignment import GovernanceAssignment

    client_id = uuid.uuid4()

    response, db = _request_assignments(
        client_id=client_id,
        grant_access=True,
    )

    assert response.status_code == 200

    actual_query = db.scalars.call_args.args[0]
    expected_query = (
        select(GovernanceAssignment)
        .where(GovernanceAssignment.client_id == client_id)
        .order_by(
            GovernanceAssignment.department_id,
            GovernanceAssignment.role,
            GovernanceAssignment.id,
        )
    )

    assert actual_query.compare(expected_query), (
        "Governance Assignments query must filter by the requested client."
    )


def test_non_admin_cannot_create_governance_department():
    client_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_non_admin_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )

    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-non-admin-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/departments",
                json={
                    "name": "Finance",
                    "description": "Financial reporting",
                },
            )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Administrator access required."
    }

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_admin_without_client_access_cannot_create_department():
    client_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_ungranted_admin_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    db = MagicMock()
    db.scalar.return_value = None

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-ungranted-admin-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/departments",
                json={
                    "name": "Finance",
                    "description": "Financial reporting",
                },
            )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Client not found."
    }

    db.scalar.assert_called_once()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_authorized_admin_can_create_governance_department():
    client_id = uuid.uuid4()
    department_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_authorized_admin_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    db = MagicMock()
    db.scalar.return_value = uuid.uuid4()

    def refresh_department(department):
        department.id = department_id
        department.is_active = True

    db.refresh.side_effect = refresh_department

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-authorized-admin-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/departments",
                json={
                    "name": "  Finance  ",
                    "description": "Financial reporting",
                },
            )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201
    assert response.json() == {
        "id": str(department_id),
        "client_id": str(client_id),
        "name": "Finance",
        "description": "Financial reporting",
        "is_active": True,
    }

    db.scalar.assert_called_once()
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()

    created_department = db.add.call_args.args[0]
    assert created_department.client_id == client_id
    assert created_department.name == "Finance"
    assert created_department.description == "Financial reporting"


def test_department_creation_conflict_rolls_back_transaction():
    from sqlalchemy.exc import IntegrityError

    client_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_conflict_admin_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    db = MagicMock()
    db.scalar.return_value = uuid.uuid4()
    database_error = Exception("Simulated duplicate department name")
    database_error.diag = MagicMock()
    database_error.diag.constraint_name = (
        "uq_governance_departments_client_name"
    )

    db.commit.side_effect = IntegrityError(
        statement="INSERT INTO governance_departments",
        params={},
        orig=database_error,
    )

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-conflict-admin-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/departments",
                json={
                    "name": "Finance",
                    "description": "Financial reporting",
                },
            )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Department name already exists for this client."
    }

    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()



def test_unrelated_department_integrity_error_is_not_reported_as_duplicate():
    from sqlalchemy.exc import IntegrityError

    client_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_other_integrity_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    db = MagicMock()
    db.scalar.return_value = uuid.uuid4()

    database_error = Exception("Simulated unrelated database constraint")
    database_error.diag = MagicMock()
    database_error.diag.constraint_name = (
        "some_other_database_constraint"
    )

    db.commit.side_effect = IntegrityError(
        statement="INSERT INTO governance_departments",
        params={},
        orig=database_error,
    )

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-other-integrity-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/departments",
                json={
                    "name": "Finance",
                    "description": "Financial reporting",
                },
            )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500

    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()


def test_invalid_department_creation_payload_is_rejected():
    user = User(
        id=uuid.uuid4(),
        username="governance_validation_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    db = MagicMock()
    db.scalar.return_value = uuid.uuid4()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-validation-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    invalid_payloads = [
        {"name": ""},
        {"name": "   "},
        {"name": "A" * 201},
        {"name": "Finance", "description": "A" * 1001},
    ]

    try:
        with TestClient(app) as test_client:
            for payload in invalid_payloads:
                response = test_client.post(
                    f"/api/v1/clients/{uuid.uuid4()}/governance/departments",
                    json=payload,
                )

                assert response.status_code == 422, (
                    f"Expected HTTP 422 for payload: {payload!r}"
                )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_non_admin_cannot_create_governance_person():
    client_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_person_regular_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )

    db = MagicMock()
    db.scalar.return_value = uuid.uuid4()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-person-non-admin-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/people",
                json={
                    "full_name": "Jane Smith",
                    "job_title": "Data Steward",
                    "business_email": "jane@example.com",
                },
            )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Administrator access required."
    }

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_admin_without_client_access_cannot_create_governance_person():
    client_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_person_ungranted_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    db = MagicMock()
    db.scalar.return_value = None

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-person-ungranted-admin-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/people",
                json={
                    "full_name": "Jane Smith",
                    "job_title": "Data Steward",
                    "business_email": "jane@example.com",
                },
            )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Client not found."
    }

    db.scalar.assert_called_once()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_authorized_admin_can_create_governance_person():
    client_id = uuid.uuid4()
    person_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_person_authorized_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    db = MagicMock()
    db.scalar.return_value = uuid.uuid4()

    def refresh_person(person):
        person.id = person_id
        person.is_active = True

    db.refresh.side_effect = refresh_person

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-person-authorized-admin-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/people",
                json={
                    "full_name": "  Jane Smith  ",
                    "job_title": "  Data Steward  ",
                    "business_email": " jane@example.com ",
                    "phone": "  ",
                    "contact_url": "https://teams.microsoft.com/example",
                },
            )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201
    assert response.json() == {
        "id": str(person_id),
        "client_id": str(client_id),
        "full_name": "Jane Smith",
        "job_title": "Data Steward",
        "business_email": "jane@example.com",
        "phone": None,
        "contact_url": "https://teams.microsoft.com/example",
        "is_active": True,
    }

    db.scalar.assert_called_once()
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()

    created_person = db.add.call_args.args[0]
    assert created_person.client_id == client_id
    assert created_person.full_name == "Jane Smith"
    assert created_person.job_title == "Data Steward"
    assert created_person.business_email == "jane@example.com"
    assert created_person.phone is None
    assert created_person.contact_url == "https://teams.microsoft.com/example"


def test_governance_person_creation_integrity_error_rolls_back():
    from sqlalchemy.exc import IntegrityError

    client_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_person_integrity_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    db = MagicMock()
    db.scalar.return_value = uuid.uuid4()
    db.commit.side_effect = IntegrityError(
        statement="INSERT INTO governance_people",
        params={},
        orig=Exception("Simulated database integrity error"),
    )

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-person-integrity-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/people",
                json={
                    "full_name": "Jane Smith",
                    "business_email": "jane@example.com",
                },
            )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()

def test_invalid_governance_person_creation_payload_is_rejected():
    user = User(
        id=uuid.uuid4(),
        username="governance_person_validation_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-person-validation-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    invalid_payloads = [
        {"full_name": ""},
        {"full_name": "   "},
        {"full_name": "X" * 256},
        {
            "full_name": "Jane Smith",
            "business_email": "invalid-email",
        },
        {
            "full_name": "Jane Smith",
            "contact_url": "http://example.com",
        },
        {
            "full_name": "Jane Smith",
            "contact_url": "https://" + "a" * 1000,
        },
    ]

    try:
        with TestClient(app) as test_client:
            for payload in invalid_payloads:
                response = test_client.post(
                    f"/api/v1/clients/{uuid.uuid4()}/governance/people",
                    json=payload,
                )

                assert response.status_code == 422, (
                    f"Expected HTTP 422 for payload: {payload!r}"
                )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_non_admin_cannot_create_governance_assignment():
    client_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_assignment_non_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )

    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-assignment-non-admin-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/assignments",
                json={
                    "person_id": str(uuid.uuid4()),
                    "department_id": str(uuid.uuid4()),
                    "role": "data_steward",
                },
            )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Administrator access required."
    }

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_admin_without_client_access_cannot_create_governance_assignment():
    client_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_assignment_ungranted_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    db = MagicMock()
    db.scalar.return_value = None

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-assignment-ungranted-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/assignments",
                json={
                    "person_id": str(uuid.uuid4()),
                    "department_id": str(uuid.uuid4()),
                    "role": "data_steward",
                },
            )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert response.json() == {"detail": "Client not found."}

    db.scalar.assert_called_once()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_cannot_assign_person_outside_authorized_client():
    client_id = uuid.uuid4()
    person_id = uuid.uuid4()
    department_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_assignment_cross_client_person",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    db = MagicMock()
    # First lookup authorizes the client; second cannot find
    # the requested person within that client's directory.
    db.scalar.side_effect = [uuid.uuid4(), None]

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-assignment-cross-client-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/assignments",
                json={
                    "person_id": str(person_id),
                    "department_id": str(department_id),
                    "role": "data_steward",
                },
            )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Person not found for this client."
    }

    assert db.scalar.call_count == 2

    actual_query = db.scalar.call_args_list[1].args[0]
    expected_query = (
        select(GovernancePerson)
        .where(
            GovernancePerson.id == person_id,
            GovernancePerson.client_id == client_id,
        )
    )
    assert actual_query.compare(expected_query), (
        "Person lookup must require both person ID and client ID."
    )

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_cannot_assign_department_outside_authorized_client():
    client_id = uuid.uuid4()
    person_id = uuid.uuid4()
    department_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_assignment_cross_client_department",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    db = MagicMock()
    person = MagicMock()
    person.is_active = True

    # Client authorization succeeds, person exists,
    # but department is absent from this client's directory.
    db.scalar.side_effect = [uuid.uuid4(), person, None]

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-assignment-cross-department-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/assignments",
                json={
                    "person_id": str(person_id),
                    "department_id": str(department_id),
                    "role": "data_steward",
                },
            )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Department not found for this client."
    }

    assert db.scalar.call_count == 3

    actual_query = db.scalar.call_args_list[2].args[0]
    expected_query = (
        select(GovernanceDepartment)
        .where(
            GovernanceDepartment.id == department_id,
            GovernanceDepartment.client_id == client_id,
        )
    )
    assert actual_query.compare(expected_query), (
        "Department lookup must require both department ID and client ID."
    )

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_admin_can_create_governance_steward_assignment():
    client_id = uuid.uuid4()
    person_id = uuid.uuid4()
    department_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_assignment_create_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    person = MagicMock()
    person.is_active = True

    department = MagicMock()
    department.is_active = True

    db = MagicMock()
    db.scalar.side_effect = [uuid.uuid4(), person, department]

    def refresh_assignment(assignment):
        assignment.id = uuid.uuid4()
        assignment.is_active = True

    db.refresh.side_effect = refresh_assignment

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-assignment-create-admin-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/assignments",
                json={
                    "person_id": str(person_id),
                    "department_id": str(department_id),
                    "role": "data_steward",
                    "effective_start": "2026-10-01",
                },
            )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201, response.text

    result = response.json()
    assert result["client_id"] == str(client_id)
    assert result["person_id"] == str(person_id)
    assert result["department_id"] == str(department_id)
    assert result["role"] == "data_steward"
    assert result["effective_start"] == "2026-10-01"
    assert result["is_active"] is True

    db.add.assert_called_once()
    assignment = db.add.call_args.args[0]

    assert assignment.client_id == client_id
    assert assignment.person_id == person_id
    assert assignment.department_id == department_id
    assert assignment.role == "data_steward"

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(assignment)
    db.rollback.assert_not_called()


def test_cannot_create_assignment_for_inactive_person():
    client_id = uuid.uuid4()
    person_id = uuid.uuid4()
    department_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_assignment_inactive_person_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    person = MagicMock()
    person.is_active = False

    department = MagicMock()
    department.is_active = True

    db = MagicMock()
    db.scalar.side_effect = [uuid.uuid4(), person, department]

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-assignment-inactive-person-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/assignments",
                json={
                    "person_id": str(person_id),
                    "department_id": str(department_id),
                    "role": "data_steward",
                },
            )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Person and department must both be active."
    }

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_cannot_create_assignment_for_inactive_department():
    client_id = uuid.uuid4()
    person_id = uuid.uuid4()
    department_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_assignment_inactive_department_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    person = MagicMock()
    person.is_active = True

    department = MagicMock()
    department.is_active = False

    db = MagicMock()
    db.scalar.side_effect = [uuid.uuid4(), person, department]

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-assignment-inactive-department-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/assignments",
                json={
                    "person_id": str(person_id),
                    "department_id": str(department_id),
                    "role": "data_steward",
                },
            )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Person and department must both be active."
    }

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_invalid_governance_assignment_payloads_are_rejected():
    client_id = uuid.uuid4()

    invalid_payloads = [
        {
            "person_id": str(uuid.uuid4()),
            "department_id": str(uuid.uuid4()),
            "role": "unapproved_role",
        },
        {
            "person_id": str(uuid.uuid4()),
            "department_id": str(uuid.uuid4()),
            "role": "data_steward",
            "effective_start": "2026-10-20",
            "effective_end": "2026-10-19",
        },
    ]

    user = User(
        id=uuid.uuid4(),
        username="governance_assignment_validation_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-assignment-validation-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            for payload in invalid_payloads:
                response = test_client.post(
                    f"/api/v1/clients/{client_id}/governance/assignments",
                    json=payload,
                )
                assert response.status_code == 422, response.text
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_governance_assignment_integrity_error_rolls_back():
    from sqlalchemy.exc import IntegrityError

    client_id = uuid.uuid4()
    person_id = uuid.uuid4()
    department_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="governance_assignment_rollback_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    person = MagicMock()
    person.is_active = True

    department = MagicMock()
    department.is_active = True

    db = MagicMock()
    db.scalar.side_effect = [uuid.uuid4(), person, department]
    db.commit.side_effect = IntegrityError(
        "INSERT INTO governance_assignments",
        {},
        Exception("Simulated database constraint violation"),
    )

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="governance-assignment-rollback-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.post(
                f"/api/v1/clients/{client_id}/governance/assignments",
                json={
                    "person_id": str(person_id),
                    "department_id": str(department_id),
                    "role": "data_steward",
                },
            )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()
