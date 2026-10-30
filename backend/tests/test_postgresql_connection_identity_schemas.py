import pytest
from pydantic import ValidationError

from app.schemas.postgresql_connection_identity import PostgreSQLConnectionIdentityCreate


def test_valid_postgresql_connection_identity():
    identity = PostgreSQLConnectionIdentityCreate(
        host="database.internal",
        port=5432,
        database_name="client_data",
    )

    assert identity.host == "database.internal"
    assert identity.port == 5432
    assert identity.database_name == "client_data"


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {"host": " ", "port": 5432, "database_name": "client_data"},
        {"host": "database.internal", "port": 0, "database_name": "client_data"},
        {"host": "database.internal", "port": 65536, "database_name": "client_data"},
        {"host": "database.internal", "port": "5432", "database_name": "client_data"},
        {"host": "database.internal", "port": 5432, "database_name": " "},
        {"host": "database.internal", "port": 5432, "database_name": "client_data", "password": "not_allowed"},
        {"host": "database.internal", "port": 5432, "database_name": "client_data", "is_verified": True},
        {"host": "database.internal", "port": 5432, "database_name": "client_data", "verified_at": "2026-10-29T12:00:00Z"},
    ],
)
def test_invalid_postgresql_connection_identity(invalid_payload):
    with pytest.raises(ValidationError):
        PostgreSQLConnectionIdentityCreate(**invalid_payload)
