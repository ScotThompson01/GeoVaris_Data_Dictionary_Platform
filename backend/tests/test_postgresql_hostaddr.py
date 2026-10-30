"""Tests for PostgreSQL connection destination IP handling."""

from app.connectors.database.base import DatabaseConnectionConfig
from app.connectors.database.postgresql_connector import PostgreSQLConnector


def test_hostaddr_is_omitted_by_default():
    config = DatabaseConnectionConfig(
        host="database.internal",
        port=5432,
        database="client_data",
    )

    options = PostgreSQLConnector()._connection_options(
        config,
        password=None,
    )

    assert options["host"] == "database.internal"
    assert "hostaddr" not in options


def test_hostaddr_preserves_hostname_for_tls_verification():
    config = DatabaseConnectionConfig(
        host="database.internal",
        port=5432,
        database="client_data",
        ssl_mode="verify-full",
        host_address="192.0.2.10",
    )

    options = PostgreSQLConnector()._connection_options(
        config,
        password=None,
        ssl_root_cert="/test/trusted-ca.pem",
    )

    assert options["host"] == "database.internal"
    assert options["hostaddr"] == "192.0.2.10"
    assert options["sslmode"] == "verify-full"
    assert options["sslrootcert"] == "/test/trusted-ca.pem"


def test_hostaddr_does_not_change_registered_port():
    config = DatabaseConnectionConfig(
        host="database.internal",
        port=5433,
        database="client_data",
        host_address="192.0.2.10",
    )

    options = PostgreSQLConnector()._connection_options(
        config,
        password=None,
    )

    assert options["hostaddr"] == "192.0.2.10"
    assert options["port"] == 5433
