"""Offline fail-closed tests for committed connection authorization.

Tests use synthetic values and fake sessions. No PostgreSQL connection,
client-source access, runtime admission, or measurement is performed.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services.data_quality_execution_committed_connection_authorization import (
    CommittedConnectionAuthorizationUnavailableError,
    verify_committed_connection_authorization,
)


def make_context():
    execution_id = uuid4()
    project_id = uuid4()
    data_source_id = uuid4()

    evidence = SimpleNamespace(
        execution_id=execution_id,
        project_id=project_id,
        data_source_id=data_source_id,
        connection_revision=3,
        authorized_host="approved.example.invalid",
        authorized_port=5432,
        authorized_database="synthetic_test",
        authorized_ip="192.0.2.10",
        authorized_at=datetime.now(timezone.utc),
    )

    session = Mock()
    session.scalar.return_value = evidence
    session_factory = Mock(return_value=session)

    arguments = {
        "session_factory": session_factory,
        "execution_id": execution_id,
        "project_id": project_id,
        "data_source_id": data_source_id,
        "expected_connection_revision": 3,
    }

    return evidence, session, session_factory, arguments


def test_matching_persisted_authorization_returns_immutable_identifier():
    evidence, session, factory, arguments = make_context()

    result = verify_committed_connection_authorization(**arguments)

    assert result == evidence.execution_id
    assert result is arguments["execution_id"]
    factory.assert_called_once_with()
    session.scalar.assert_called_once()
    session.close.assert_called_once_with()

    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    session.flush.assert_not_called()
    session.add.assert_not_called()
    session.delete.assert_not_called()


def test_missing_authorization_rejected_and_session_closed():
    _, session, _, arguments = make_context()
    session.scalar.return_value = None

    with pytest.raises(CommittedConnectionAuthorizationUnavailableError):
        verify_committed_connection_authorization(**arguments)

    session.close.assert_called_once_with()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "field",
    [
        "execution_id",
        "project_id",
        "data_source_id",
    ],
)
def test_mismatched_persisted_uuid_rejected(field):
    evidence, session, _, arguments = make_context()
    setattr(evidence, field, uuid4())

    with pytest.raises(CommittedConnectionAuthorizationUnavailableError):
        verify_committed_connection_authorization(**arguments)

    session.close.assert_called_once_with()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "revision",
    [0, -1, True, False, 3.0, "3", None],
)
def test_invalid_expected_revision_rejected_before_session_creation(revision):
    _, _, factory, arguments = make_context()
    arguments["expected_connection_revision"] = revision

    with pytest.raises(ValueError):
        verify_committed_connection_authorization(**arguments)

    factory.assert_not_called()


@pytest.mark.parametrize(
    "field",
    [
        "execution_id",
        "project_id",
        "data_source_id",
    ],
)
@pytest.mark.parametrize(
    "invalid_value",
    [None, "not-a-uuid", 123],
)
def test_invalid_expected_identity_rejected_before_session(
    field, invalid_value
):
    _, _, factory, arguments = make_context()
    arguments[field] = invalid_value

    with pytest.raises(ValueError):
        verify_committed_connection_authorization(**arguments)

    factory.assert_not_called()


@pytest.mark.parametrize("invalid_factory", [None, False, "session", 42])
def test_invalid_session_factory_rejected(invalid_factory):
    _, _, _, arguments = make_context()
    arguments["session_factory"] = invalid_factory

    with pytest.raises(ValueError):
        verify_committed_connection_authorization(**arguments)


@pytest.mark.parametrize(
    "invalid_revision",
    [0, -1, True, 3.0, "3", None, 4],
)
def test_mismatched_or_invalid_persisted_revision_rejected(
    invalid_revision,
):
    evidence, session, _, arguments = make_context()
    evidence.connection_revision = invalid_revision

    with pytest.raises(CommittedConnectionAuthorizationUnavailableError):
        verify_committed_connection_authorization(**arguments)

    session.close.assert_called_once_with()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "field,invalid_value",
    [
        ("authorized_host", None),
        ("authorized_host", ""),
        ("authorized_host", "   "),
        ("authorized_port", None),
        ("authorized_port", True),
        ("authorized_port", 0),
        ("authorized_port", 65536),
        ("authorized_port", "5432"),
        ("authorized_database", None),
        ("authorized_database", ""),
        ("authorized_database", "   "),
        ("authorized_ip", None),
        ("authorized_ip", ""),
        ("authorized_ip", "not-an-ip"),
        ("authorized_ip", "999.999.999.999"),
        ("authorized_at", None),
        ("authorized_at", "2026-01-01"),
        ("authorized_at", datetime(2026, 1, 1)),
    ],
)
def test_invalid_persisted_destination_or_timestamp_rejected(
    field, invalid_value
):
    evidence, session, _, arguments = make_context()
    setattr(evidence, field, invalid_value)

    with pytest.raises(CommittedConnectionAuthorizationUnavailableError):
        verify_committed_connection_authorization(**arguments)

    session.close.assert_called_once_with()
    session.commit.assert_not_called()


def test_valid_ipv6_destination_accepted():
    evidence, session, _, arguments = make_context()
    evidence.authorized_ip = "2001:db8::10"

    assert verify_committed_connection_authorization(**arguments) == (
        evidence.execution_id
    )
    session.close.assert_called_once_with()


def test_timezone_aware_timestamp_accepted():
    evidence, session, _, arguments = make_context()
    evidence.authorized_at = datetime(
        2026, 1, 1, tzinfo=timezone(timedelta(hours=-5))
    )

    assert verify_committed_connection_authorization(**arguments) == (
        evidence.execution_id
    )
    session.close.assert_called_once_with()


def test_database_read_failure_propagates_and_closes_session():
    _, session, _, arguments = make_context()
    session.scalar.side_effect = RuntimeError("synthetic read failure")

    with pytest.raises(RuntimeError, match="synthetic read failure"):
        verify_committed_connection_authorization(**arguments)

    session.close.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_session_creation_failure_prevents_database_read():
    _, session, factory, arguments = make_context()
    factory.side_effect = RuntimeError("synthetic session failure")

    with pytest.raises(RuntimeError, match="synthetic session failure"):
        verify_committed_connection_authorization(**arguments)

    factory.assert_called_once_with()
    session.scalar.assert_not_called()
    session.close.assert_not_called()


def test_fresh_session_created_for_each_verification():
    evidence, first, _, arguments = make_context()
    second = Mock()
    second.scalar.return_value = evidence

    factory = Mock(side_effect=[first, second])
    arguments["session_factory"] = factory

    first_result = verify_committed_connection_authorization(**arguments)
    second_result = verify_committed_connection_authorization(**arguments)

    assert first_result == evidence.execution_id
    assert second_result == evidence.execution_id
    assert factory.call_count == 2

    first.close.assert_called_once_with()
    second.close.assert_called_once_with()

    first.commit.assert_not_called()
    second.commit.assert_not_called()
