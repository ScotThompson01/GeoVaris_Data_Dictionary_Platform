import pytest

from app.connectors.database.base import (
    BaseDatabaseConnector,
    DatabaseConnectionConfig,
)


def test_database_connection_config():
    config = DatabaseConnectionConfig(
        host="localhost",
        port=5432,
        database="geovaris_test",
        username="readonly_user",
    )

    assert config.host == "localhost"
    assert config.port == 5432
    assert config.database == "geovaris_test"
    assert config.username == "readonly_user"
    assert config.connect_timeout_seconds == 10


def test_base_database_connector_is_abstract():
    with pytest.raises(TypeError):
        BaseDatabaseConnector()