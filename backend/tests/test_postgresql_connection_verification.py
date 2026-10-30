"""Tests for registered PostgreSQL connection verification."""

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.postgresql_connection_verification import (
    verify_postgresql_connection,
)


@pytest.fixture(autouse=True)
def approved_verification_settings(tmp_path):
    """Provide isolated approved settings and a temporary test CA file."""
    certificate = tmp_path / "trusted-ca.pem"
    certificate.write_text(
        "test certificate content",
        encoding="utf-8",
    )

    with patch(
        "app.services.postgresql_connection_verification.settings"
    ) as mock_settings:
        mock_settings.postgresql_verification_enabled = True
        mock_settings.postgresql_verification_allowed_destinations = (
            "database.internal:5432"
        )
        mock_settings.postgresql_verification_ssl_root_cert = str(certificate)
        mock_settings.postgresql_verification_allowed_ip_networks = (
            "10.20.30.0/24"
        )

        with patch(
            "app.services.postgresql_connection_verification."
            "resolve_approved_postgresql_ip",
            return_value="10.20.30.10",
        ):
            yield


def make_context():
    db = MagicMock()
    identity = MagicMock()
    identity.host = "database.internal"
    identity.port = 5432
    identity.database_name = "client_data"
    identity.connection_revision = 1
    identity.is_verified = False
    identity.verified_at = None
    db.get.return_value = identity
    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.return_value = identity
    return db, identity


def test_verification_requires_tls_hostname_validation():
    db, _ = make_context()

    with patch(
        "app.services.postgresql_connection_verification.PostgreSQLConnector"
    ) as connector:
        verify_postgresql_connection(
            db,
            data_source_id=uuid.uuid4(),
            username="readonly_user",
            password="runtime_secret",
        )

    connector.return_value.validate_connection.assert_called_once()

    args, kwargs = (
        connector.return_value.validate_connection.call_args
    )

    config = args[0]

    assert config.ssl_mode == "verify-full"
    assert config.host == "database.internal"
    assert config.port == 5432
    assert Path(kwargs["ssl_root_cert"]).is_file()


def test_successful_verification_records_status():
    db, identity = make_context()

    with patch(
        "app.services.postgresql_connection_verification.PostgreSQLConnector"
    ) as connector:
        result = verify_postgresql_connection(
            db,
            data_source_id=uuid.uuid4(),
            username="readonly_user",
            password="runtime_secret",
        )

    connector.return_value.validate_connection.assert_called_once()
    assert identity.is_verified is True
    assert identity.verified_at is not None
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(identity)
    assert result is identity


def test_failed_verification_does_not_commit():
    db, identity = make_context()

    with patch(
        "app.services.postgresql_connection_verification.PostgreSQLConnector"
    ) as connector:
        connector.return_value.validate_connection.side_effect = ConnectionError(
            "Unable to validate the PostgreSQL connection."
        )

        with pytest.raises(ConnectionError):
            verify_postgresql_connection(
                db,
                data_source_id=uuid.uuid4(),
                username="readonly_user",
                password="runtime_secret",
            )

    assert identity.is_verified is False
    assert identity.verified_at is None
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_missing_identity_rejected_without_connection():
    db, _ = make_context()
    db.get.return_value = None

    with patch(
        "app.services.postgresql_connection_verification.PostgreSQLConnector"
    ) as connector:
        with pytest.raises(ValueError):
            verify_postgresql_connection(
                db,
                data_source_id=uuid.uuid4(),
                username="readonly_user",
                password=None,
            )

    connector.assert_not_called()
    db.commit.assert_not_called()



def test_destination_change_during_verification_is_rejected():
    db, original_identity = make_context()

    changed_identity = MagicMock()
    changed_identity.host = "different.internal"
    changed_identity.port = 5432
    changed_identity.database_name = "client_data"
    changed_identity.connection_revision = 2
    changed_identity.is_verified = False
    changed_identity.verified_at = None

    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.return_value = changed_identity

    with patch(
        "app.services.postgresql_connection_verification.PostgreSQLConnector"
    ) as connector:
        with pytest.raises(ValueError, match="changed during verification"):
            verify_postgresql_connection(
                db,
                data_source_id=uuid.uuid4(),
                username="readonly_user",
                password="runtime_secret",
            )

    connector.return_value.validate_connection.assert_called_once()
    assert changed_identity.is_verified is False
    assert changed_identity.verified_at is None
    db.commit.assert_not_called()
    assert db.rollback.call_count == 2



def test_revision_change_during_verification_is_rejected():
    db, original_identity = make_context()
    original_identity.connection_revision = 1

    changed_identity = MagicMock()
    changed_identity.host = original_identity.host
    changed_identity.port = original_identity.port
    changed_identity.database_name = original_identity.database_name
    changed_identity.connection_revision = 3
    changed_identity.is_verified = False
    changed_identity.verified_at = None

    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.return_value = changed_identity

    with patch(
        "app.services.postgresql_connection_verification.PostgreSQLConnector"
    ) as connector:
        with pytest.raises(ValueError, match="changed during verification"):
            verify_postgresql_connection(
                db,
                data_source_id=uuid.uuid4(),
                username="readonly_user",
                password="runtime_secret",
            )

    connector.return_value.validate_connection.assert_called_once()
    assert changed_identity.is_verified is False
    assert changed_identity.verified_at is None
    db.commit.assert_not_called()
    assert db.rollback.call_count == 2



def test_verification_disabled_blocks_connection():
    db, identity = make_context()

    with (
        patch(
            "app.services.postgresql_connection_verification.settings"
        ) as mock_settings,
        patch(
            "app.services.postgresql_connection_verification.PostgreSQLConnector"
        ) as connector,
    ):
        mock_settings.postgresql_verification_enabled = False

        with pytest.raises(ValueError, match="disabled"):
            verify_postgresql_connection(
                db,
                data_source_id=uuid.uuid4(),
                username="readonly_user",
                password="runtime_secret",
            )

    connector.assert_not_called()
    db.commit.assert_not_called()
    assert identity.is_verified is False


def test_unapproved_hostname_blocks_connection():
    db, identity = make_context()
    identity.host = "unapproved.internal"

    with patch(
        "app.services.postgresql_connection_verification.PostgreSQLConnector"
    ) as connector:
        with pytest.raises(ValueError, match="not approved"):
            verify_postgresql_connection(
                db,
                data_source_id=uuid.uuid4(),
                username="readonly_user",
                password="runtime_secret",
            )

    connector.assert_not_called()
    db.commit.assert_not_called()
    assert identity.is_verified is False


def test_unapproved_port_blocks_connection():
    db, identity = make_context()
    identity.port = 5433

    with patch(
        "app.services.postgresql_connection_verification.PostgreSQLConnector"
    ) as connector:
        with pytest.raises(ValueError, match="not approved"):
            verify_postgresql_connection(
                db,
                data_source_id=uuid.uuid4(),
                username="readonly_user",
                password="runtime_secret",
            )

    connector.assert_not_called()
    db.commit.assert_not_called()
    assert identity.is_verified is False



def test_missing_ca_file_blocks_connection(tmp_path):
    """A missing trusted CA file must prevent network access."""
    db, identity = make_context()
    missing_certificate = tmp_path / "missing-ca.pem"

    with (
        patch(
            "app.services.postgresql_connection_verification.settings"
        ) as mock_settings,
        patch(
            "app.services.postgresql_connection_verification.PostgreSQLConnector"
        ) as connector,
    ):
        mock_settings.postgresql_verification_enabled = True
        mock_settings.postgresql_verification_allowed_destinations = (
            "database.internal:5432"
        )
        mock_settings.postgresql_verification_ssl_root_cert = str(
            missing_certificate
        )

        with pytest.raises(ValueError, match="unavailable"):
            verify_postgresql_connection(
                db,
                data_source_id=uuid.uuid4(),
                username="readonly_user",
                password="runtime_secret",
            )

    connector.assert_not_called()
    db.commit.assert_not_called()
    assert identity.is_verified is False
    assert identity.verified_at is None



def test_verification_pins_approved_destination_ip():
    """The connector must receive the authorized IP and original hostname."""
    db, _ = make_context()

    with patch(
        "app.services.postgresql_connection_verification.PostgreSQLConnector"
    ) as connector:
        verify_postgresql_connection(
            db,
            data_source_id=uuid.uuid4(),
            username="readonly_user",
            password="runtime_secret",
        )

    connector.return_value.validate_connection.assert_called_once()

    args, kwargs = connector.return_value.validate_connection.call_args
    config = args[0]

    assert config.host == "database.internal"
    assert config.host_address == "10.20.30.10"
    assert config.port == 5432
    assert config.ssl_mode == "verify-full"
    assert Path(kwargs["ssl_root_cert"]).is_file()


def test_dns_authorization_failure_blocks_connection():
    """A rejected DNS destination must never reach the connector."""
    db, identity = make_context()

    with (
        patch(
            "app.services.postgresql_connection_verification."
            "resolve_approved_postgresql_ip",
            side_effect=ValueError(
                "PostgreSQL DNS returned an unauthorized destination IP."
            ),
        ),
        patch(
            "app.services.postgresql_connection_verification.PostgreSQLConnector"
        ) as connector,
    ):
        with pytest.raises(ValueError, match="unauthorized destination IP"):
            verify_postgresql_connection(
                db,
                data_source_id=uuid.uuid4(),
                username="readonly_user",
                password="runtime_secret",
            )

    connector.assert_not_called()
    db.commit.assert_not_called()
    assert identity.is_verified is False
    assert identity.verified_at is None
