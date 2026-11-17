"""Offline fail-closed tests for the connection authorization prerequisite gate."""

from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest

import app.services.data_quality_execution_connection_authorization_gate as gate


def make_context(monkeypatch):
    execution_id = uuid4()
    project_id = uuid4()
    data_source_id = uuid4()
    revision = 3
    session_factory = Mock()

    verifier = Mock(return_value=execution_id)
    monkeypatch.setattr(
        gate,
        "verify_committed_connection_authorization",
        verifier,
    )

    return {
        "execution_id": execution_id,
        "project_id": project_id,
        "data_source_id": data_source_id,
        "revision": revision,
        "session_factory": session_factory,
        "verifier": verifier,
    }


def invoke(context, **overrides):
    arguments = {
        "session_factory": context["session_factory"],
        "execution_id": context["execution_id"],
        "project_id": context["project_id"],
        "data_source_id": context["data_source_id"],
        "expected_connection_revision": context["revision"],
    }
    arguments.update(overrides)

    return gate.require_committed_connection_authorization(**arguments)


def test_verified_exact_identity_returns_execution_uuid(monkeypatch):
    context = make_context(monkeypatch)

    result = invoke(context)

    assert isinstance(result, UUID)
    assert result == context["execution_id"]
    context["verifier"].assert_called_once_with(
        session_factory=context["session_factory"],
        execution_id=context["execution_id"],
        project_id=context["project_id"],
        data_source_id=context["data_source_id"],
        expected_connection_revision=context["revision"],
    )
    context["session_factory"].assert_not_called()


def test_verifier_called_only_once(monkeypatch):
    context = make_context(monkeypatch)

    assert invoke(context) == context["execution_id"]

    assert context["verifier"].call_count == 1
    context["session_factory"].assert_not_called()


@pytest.mark.parametrize("invalid_factory", [None, object(), "not_callable", 7])
def test_invalid_session_factory_rejected_before_verification(
    monkeypatch, invalid_factory
):
    context = make_context(monkeypatch)

    with pytest.raises(ValueError, match="session factory"):
        invoke(context, session_factory=invalid_factory)

    context["verifier"].assert_not_called()
    context["session_factory"].assert_not_called()


@pytest.mark.parametrize(
    "identity_name",
    ["execution_id", "project_id", "data_source_id"],
)
@pytest.mark.parametrize("invalid_value", [None, "not-a-uuid", 7, True])
def test_invalid_uuid_identity_rejected_before_verification(
    monkeypatch, identity_name, invalid_value
):
    context = make_context(monkeypatch)

    with pytest.raises(ValueError, match="UUID identities"):
        invoke(context, **{identity_name: invalid_value})

    context["verifier"].assert_not_called()
    context["session_factory"].assert_not_called()


@pytest.mark.parametrize(
    "invalid_revision",
    [None, 0, -1, -100, True, False, 1.0, "1"],
)
def test_invalid_connection_revision_rejected_before_verification(
    monkeypatch, invalid_revision
):
    context = make_context(monkeypatch)

    with pytest.raises(ValueError, match="positive connection revision"):
        invoke(
            context,
            expected_connection_revision=invalid_revision,
        )

    context["verifier"].assert_not_called()
    context["session_factory"].assert_not_called()


@pytest.mark.parametrize(
    "exception_type",
    [RuntimeError, ValueError, LookupError],
)
def test_verification_failure_propagates_without_retry(
    monkeypatch, exception_type
):
    context = make_context(monkeypatch)
    context["verifier"].side_effect = exception_type(
        "Synthetic offline verification failure."
    )

    with pytest.raises(exception_type):
        invoke(context)

    assert context["verifier"].call_count == 1
    context["session_factory"].assert_not_called()


@pytest.mark.parametrize(
    "invalid_verified_value",
    [None, True, False, 0, 1, "not-a-uuid", object()],
)
def test_invalid_verified_identity_rejected(
    monkeypatch, invalid_verified_value
):
    context = make_context(monkeypatch)
    context["verifier"].return_value = invalid_verified_value

    with pytest.raises(
        ValueError,
        match="Committed connection authorization identity mismatch",
    ):
        invoke(context)

    context["verifier"].assert_called_once()
    context["session_factory"].assert_not_called()


def test_different_verified_execution_uuid_rejected(monkeypatch):
    context = make_context(monkeypatch)
    context["verifier"].return_value = uuid4()

    with pytest.raises(
        ValueError,
        match="Committed connection authorization identity mismatch",
    ):
        invoke(context)

    context["verifier"].assert_called_once()
    context["session_factory"].assert_not_called()


@pytest.mark.parametrize(
    "identity_name",
    ["execution_id", "project_id", "data_source_id"],
)
def test_verifier_receives_exact_requested_identity(
    monkeypatch, identity_name
):
    context = make_context(monkeypatch)
    replacement_id = uuid4()

    if identity_name == "execution_id":
        context["verifier"].return_value = replacement_id

    result = invoke(context, **{identity_name: replacement_id})

    expected = {
        "session_factory": context["session_factory"],
        "execution_id": context["execution_id"],
        "project_id": context["project_id"],
        "data_source_id": context["data_source_id"],
        "expected_connection_revision": context["revision"],
    }
    expected[identity_name] = replacement_id

    context["verifier"].assert_called_once_with(**expected)
    assert result == expected["execution_id"]
    context["session_factory"].assert_not_called()


def test_verifier_receives_exact_requested_revision(monkeypatch):
    context = make_context(monkeypatch)

    result = invoke(context, expected_connection_revision=17)

    assert result == context["execution_id"]
    assert (
        context["verifier"].call_args.kwargs[
            "expected_connection_revision"
        ] == 17
    )
    context["verifier"].assert_called_once()
    context["session_factory"].assert_not_called()


def test_no_verification_without_valid_arguments(monkeypatch):
    context = make_context(monkeypatch)

    invalid_inputs = [
        {"session_factory": None},
        {"execution_id": None},
        {"project_id": None},
        {"data_source_id": None},
        {"expected_connection_revision": 0},
    ]

    for changes in invalid_inputs:
        with pytest.raises(ValueError):
            invoke(context, **changes)

    context["verifier"].assert_not_called()
    context["session_factory"].assert_not_called()


def test_success_does_not_call_session_factory_directly(monkeypatch):
    context = make_context(monkeypatch)

    assert invoke(context) == context["execution_id"]

    context["session_factory"].assert_not_called()
    context["verifier"].assert_called_once()


def test_verification_exception_does_not_become_success(monkeypatch):
    context = make_context(monkeypatch)
    context["verifier"].side_effect = RuntimeError(
        "Synthetic uncertain committed evidence."
    )

    with pytest.raises(RuntimeError):
        invoke(context)

    context["verifier"].assert_called_once()
    context["session_factory"].assert_not_called()