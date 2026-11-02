"""Security tests for PostgreSQL Data Quality execution authorization."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services.postgresql_execution_authorization import (
    authorize_postgresql_execution_connection,
)


def test_unverified_connection_is_rejected_before_network_access():
    source_id = uuid4()
    db = Mock()
    db.get.return_value = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        connection_revision=1,
        is_verified=False,
        verified_at=None,
    )

    with pytest.raises(ValueError, match="[Vv]erif"):
        authorize_postgresql_execution_connection(
            db,
            data_source_id=source_id,
            username="readonly_user",
        )

    db.get.assert_called_once()

def test_verified_connection_is_rejected_when_verification_is_disabled():
    """Previous verification must not bypass current deployment policy."""
    from datetime import datetime, timezone
    from unittest.mock import patch

    source_id = uuid4()
    db = Mock()
    db.get.return_value = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        connection_revision=1,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.core.config.settings.postgresql_verification_enabled",
        False,
    ):
        with pytest.raises(ValueError, match="[Dd]isabled"):
            authorize_postgresql_execution_connection(
                db,
                data_source_id=source_id,
                username="readonly_user",
            )

def test_verified_connection_rejects_unapproved_destination():
    """A verified connection must still satisfy the current destination allowlist."""
    from datetime import datetime, timezone
    from unittest.mock import patch

    source_id = uuid4()
    db = Mock()
    db.get.return_value = SimpleNamespace(
        data_source_id=source_id,
        host="unapproved.internal",
        port=5432,
        database_name="client_data",
        connection_revision=1,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.services.postgresql_verification_policy.require_postgresql_verification_configuration"
    ) as require_configuration, patch(
        "app.services.postgresql_verification_policy.require_approved_postgresql_destination"
    ) as require_destination:
        require_destination.side_effect = ValueError(
            "PostgreSQL destination is not approved."
        )

        with pytest.raises(ValueError, match="not approved"):
            authorize_postgresql_execution_connection(
                db,
                data_source_id=source_id,
                username="readonly_user",
            )

    require_configuration.assert_called_once()
    require_destination.assert_called_once()

def test_verified_connection_rejects_unavailable_trusted_ca():
    """Execution must reject a missing or unreadable trusted CA certificate."""
    from datetime import datetime, timezone
    from unittest.mock import patch

    source_id = uuid4()
    db = Mock()
    db.get.return_value = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        connection_revision=1,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.services.postgresql_verification_policy.require_postgresql_verification_configuration"
    ), patch(
        "app.services.postgresql_verification_policy.require_approved_postgresql_destination"
    ), patch(
        "app.services.postgresql_verification_policy.require_postgresql_trusted_ca_file",
        side_effect=ValueError("Trusted PostgreSQL CA certificate is unavailable."),
    ) as require_ca:
        with pytest.raises(ValueError, match="CA certificate is unavailable"):
            authorize_postgresql_execution_connection(
                db,
                data_source_id=source_id,
                username="readonly_user",
            )

    require_ca.assert_called_once()

def test_verified_connection_rejects_unapproved_resolved_ip():
    """Execution must reject DNS results outside approved networks."""
    from datetime import datetime, timezone
    from unittest.mock import patch

    source_id = uuid4()
    db = Mock()
    db.get.return_value = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        connection_revision=1,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.services.postgresql_verification_policy.require_postgresql_verification_configuration"
    ), patch(
        "app.services.postgresql_verification_policy.require_approved_postgresql_destination"
    ), patch(
        "app.services.postgresql_verification_policy.require_postgresql_trusted_ca_file"
    ), patch(
        "app.services.postgresql_verification_policy.resolve_approved_postgresql_ip",
        side_effect=ValueError("Resolved PostgreSQL IP is not approved."),
    ) as resolve_ip:
        with pytest.raises(ValueError, match="IP is not approved"):
            authorize_postgresql_execution_connection(
                db,
                data_source_id=source_id,
                username="readonly_user",
            )

    resolve_ip.assert_called_once()

def test_verified_connection_returns_pinned_tls_configuration():
    """Approved execution must preserve TLS hostname and pin the destination IP."""
    from datetime import datetime, timezone
    from unittest.mock import patch

    source_id = uuid4()
    db = Mock()
    db.get.return_value = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        connection_revision=1,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.services.postgresql_verification_policy.require_postgresql_verification_configuration"
    ), patch(
        "app.services.postgresql_verification_policy.require_approved_postgresql_destination"
    ), patch(
        "app.services.postgresql_verification_policy.require_postgresql_trusted_ca_file"
    ), patch(
        "app.services.postgresql_verification_policy.resolve_approved_postgresql_ip",
        return_value="10.20.30.40",
    ):
        config = authorize_postgresql_execution_connection(
            db,
            data_source_id=source_id,
            username="readonly_user",
        )

    assert config.host == "database.internal"
    assert config.host_address == "10.20.30.40"
    assert config.port == 5432
    assert config.database == "client_data"
    assert config.username == "readonly_user"
    assert config.ssl_mode == "verify-full"

def test_execution_revalidation_rejects_changed_connection_revision():
    """Reject execution results if the registered connection revision changed."""
    from app.services.postgresql_execution_authorization import (
        revalidate_postgresql_execution_connection,
    )

    source_id = uuid4()
    db = Mock()

    current_identity = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        connection_revision=2,
        is_verified=True,
        verified_at=object(),
    )

    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.return_value = (
        current_identity
    )

    with pytest.raises(ValueError, match="[Cc]hang"):
        revalidate_postgresql_execution_connection(
            db,
            data_source_id=source_id,
            expected_host="database.internal",
            expected_port=5432,
            expected_database="client_data",
            expected_revision=1,
        )

def test_execution_revalidation_rejects_revoked_verification():
    """Reject execution results when connection verification was revoked."""
    from app.services.postgresql_execution_authorization import (
        revalidate_postgresql_execution_connection,
    )

    source_id = uuid4()
    db = Mock()

    current_identity = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        connection_revision=1,
        is_verified=False,
        verified_at=None,
    )

    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.return_value = (
        current_identity
    )

    with pytest.raises(ValueError, match="[Rr]evoked"):
        revalidate_postgresql_execution_connection(
            db,
            data_source_id=source_id,
            expected_host="database.internal",
            expected_port=5432,
            expected_database="client_data",
            expected_revision=1,
        )

def test_execution_revalidation_accepts_unchanged_verified_connection():
    """An unchanged, verified connection must pass revalidation."""
    from datetime import datetime, timezone

    from app.services.postgresql_execution_authorization import (
        revalidate_postgresql_execution_connection,
    )

    source_id = uuid4()
    db = Mock()

    current_identity = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        connection_revision=1,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )

    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.return_value = (
        current_identity
    )

    result = revalidate_postgresql_execution_connection(
        db,
        data_source_id=source_id,
        expected_host="database.internal",
        expected_port=5432,
        expected_database="client_data",
        expected_revision=1,
    )

    assert result is current_identity
    db.query.return_value.filter.return_value.with_for_update.assert_called_once()

def test_execution_authorization_returns_connection_revision_snapshot():
    """Authorization must preserve the revision for post-measurement revalidation."""
    from datetime import datetime, timezone
    from unittest.mock import Mock, patch
    from uuid import uuid4

    from app.services.postgresql_execution_authorization import (
        authorize_postgresql_execution_connection,
    )

    source_id = uuid4()
    identity = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        connection_revision=7,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )

    db = Mock()
    db.get.return_value = identity

    with patch(
        "app.services.postgresql_verification_policy.require_postgresql_verification_configuration"
    ), patch(
        "app.services.postgresql_verification_policy.require_approved_postgresql_destination"
    ), patch(
        "app.services.postgresql_verification_policy.require_postgresql_trusted_ca_file"
    ), patch(
        "app.services.postgresql_verification_policy.resolve_approved_postgresql_ip",
        return_value="10.20.30.40",
    ):
        result = authorize_postgresql_execution_connection(
            db,
            data_source_id=source_id,
            username="readonly_user",
        )

    assert result.connection_revision == 7
    assert result.config.host == "database.internal"
    assert result.config.host_address == "10.20.30.40"
    assert result.config.ssl_mode == "verify-full"
