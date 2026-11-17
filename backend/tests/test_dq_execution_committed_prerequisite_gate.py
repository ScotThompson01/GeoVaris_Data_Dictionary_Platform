"""Offline tests of the combined committed execution prerequisite gate.

Both independent verifiers are replaced with mocks. No database sessions,
client connections, or protected execution actions are created.
"""

from unittest.mock import Mock, call
from uuid import uuid4

import pytest

import app.services.data_quality_execution_committed_prerequisite_gate as gate


def make_context(monkeypatch):
    execution_id = uuid4()
    project_id = uuid4()
    data_source_id = uuid4()
    events = []

    def ownership_result(**kwargs):
        events.append("ownership")
        return kwargs["execution_id"]

    def connection_result(**kwargs):
        events.append("connection")
        return kwargs["execution_id"]

    ownership = Mock(side_effect=ownership_result)
    connection = Mock(side_effect=connection_result)

    monkeypatch.setattr(
        gate, "verify_committed_workload_ownership", ownership
    )
    monkeypatch.setattr(
        gate, "require_committed_connection_authorization", connection
    )

    return {
        "session_factory": Mock(),
        "execution_id": execution_id,
        "project_id": project_id,
        "data_source_id": data_source_id,
        "expected_connection_revision": 3,
        "ownership": ownership,
        "connection": connection,
        "events": events,
    }


def invoke(context, **overrides):
    arguments = {
        "session_factory": context["session_factory"],
        "execution_id": context["execution_id"],
        "project_id": context["project_id"],
        "data_source_id": context["data_source_id"],
        "expected_connection_revision":
            context["expected_connection_revision"],
    }
    arguments.update(overrides)
    return gate.require_committed_execution_prerequisites(**arguments)


def assert_no_verifiers_called(context):
    context["ownership"].assert_not_called()
    context["connection"].assert_not_called()
    context["session_factory"].assert_not_called()


def test_success_returns_exact_execution_and_forwards_all_inputs(monkeypatch):
    context = make_context(monkeypatch)

    assert invoke(context) == context["execution_id"]

    context["ownership"].assert_called_once_with(
        session_factory=context["session_factory"],
        execution_id=context["execution_id"],
        project_id=context["project_id"],
        data_source_id=context["data_source_id"],
    )
    context["connection"].assert_called_once_with(
        session_factory=context["session_factory"],
        execution_id=context["execution_id"],
        project_id=context["project_id"],
        data_source_id=context["data_source_id"],
        expected_connection_revision=3,
    )
    assert context["events"] == ["ownership", "connection"]
    context["session_factory"].assert_not_called()


def test_ownership_verification_precedes_connection(monkeypatch):
    context = make_context(monkeypatch)

    invoke(context)

    assert context["events"] == ["ownership", "connection"]


@pytest.mark.parametrize(
    "invalid_factory",
    [None, object(), 17, "not callable"],
)
def test_invalid_factory_rejected_before_verification(
    monkeypatch, invalid_factory,
):
    context = make_context(monkeypatch)

    with pytest.raises(ValueError, match="session factory"):
        invoke(context, session_factory=invalid_factory)

    assert_no_verifiers_called(context)


@pytest.mark.parametrize(
    "identity_name",
    ["execution_id", "project_id", "data_source_id"],
)
@pytest.mark.parametrize(
    "invalid_value",
    [None, True, 17, "not-a-uuid"],
)
def test_invalid_identity_rejected_before_verification(
    monkeypatch, identity_name, invalid_value,
):
    context = make_context(monkeypatch)

    with pytest.raises(ValueError, match="UUID"):
        invoke(context, **{identity_name: invalid_value})

    assert_no_verifiers_called(context)


@pytest.mark.parametrize(
    "invalid_revision",
    [None, 0, -1, True, False, 1.0, "1"],
)
def test_invalid_revision_rejected_before_verification(
    monkeypatch, invalid_revision,
):
    context = make_context(monkeypatch)

    with pytest.raises(ValueError, match="connection revision"):
        invoke(context, expected_connection_revision=invalid_revision)

    assert_no_verifiers_called(context)


@pytest.mark.parametrize(
    "error_type",
    [RuntimeError, ValueError, LookupError],
)
def test_ownership_failure_blocks_connection_verification(
    monkeypatch, error_type,
):
    context = make_context(monkeypatch)
    context["ownership"].side_effect = error_type(
        "Synthetic ownership verification failure."
    )

    with pytest.raises(error_type):
        invoke(context)

    context["ownership"].assert_called_once()
    context["connection"].assert_not_called()
    context["session_factory"].assert_not_called()


@pytest.mark.parametrize(
    "error_type",
    [RuntimeError, ValueError, LookupError],
)
def test_connection_failure_propagates_without_retry(
    monkeypatch, error_type,
):
    context = make_context(monkeypatch)
    context["connection"].side_effect = error_type(
        "Synthetic connection verification failure."
    )

    with pytest.raises(error_type):
        invoke(context)

    context["ownership"].assert_called_once()
    context["connection"].assert_called_once()
    context["session_factory"].assert_not_called()


@pytest.mark.parametrize(
    "bad_result",
    [None, "other-id", True, "different_uuid"],
)
def test_unexpected_ownership_result_blocks_connection(
    monkeypatch, bad_result,
):
    context = make_context(monkeypatch)
    result = uuid4() if bad_result == "different_uuid" else bad_result
    context["ownership"].return_value = result
    context["ownership"].side_effect = None

    with pytest.raises(ValueError, match="ownership identity mismatch"):
        invoke(context)

    context["ownership"].assert_called_once()
    context["connection"].assert_not_called()
    context["session_factory"].assert_not_called()


@pytest.mark.parametrize(
    "bad_result",
    [None, "other-id", True, "different_uuid"],
)
def test_unexpected_connection_result_is_rejected(
    monkeypatch, bad_result,
):
    context = make_context(monkeypatch)
    result = uuid4() if bad_result == "different_uuid" else bad_result
    context["connection"].return_value = result
    context["connection"].side_effect = None

    with pytest.raises(
        ValueError,
        match="connection authorization identity mismatch",
    ):
        invoke(context)

    context["ownership"].assert_called_once()
    context["connection"].assert_called_once()
    context["session_factory"].assert_not_called()


def test_verifier_failure_never_invokes_session_factory(monkeypatch):
    context = make_context(monkeypatch)
    context["connection"].side_effect = RuntimeError(
        "Synthetic fail-closed condition."
    )

    with pytest.raises(RuntimeError):
        invoke(context)

    context["session_factory"].assert_not_called()
    assert context["ownership"].call_count == 1
    assert context["connection"].call_count == 1