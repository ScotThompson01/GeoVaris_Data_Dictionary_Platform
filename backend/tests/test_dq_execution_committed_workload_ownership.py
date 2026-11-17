"""Offline tests of independent committed workload ownership verification.

All database sessions and ownership records are synthetic mocks.
No live database engine or client connection is created.
"""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services.data_quality_execution_committed_workload_ownership import (
    CommittedWorkloadOwnershipUnavailableError,
    verify_committed_workload_ownership,
)


def make_context():
    execution_id = uuid4()
    project_id = uuid4()
    data_source_id = uuid4()

    ownership = SimpleNamespace(
        execution_id=execution_id,
        project_id=project_id,
        data_source_id=data_source_id,
        ownership_state="reserved",
        released_at=None,
        release_actor=None,
        release_reason=None,
        release_evidence_reference=None,
    )

    session = Mock()
    session.scalar.return_value = ownership

    session_factory = Mock(return_value=session)

    return {
        "execution_id": execution_id,
        "project_id": project_id,
        "data_source_id": data_source_id,
        "ownership": ownership,
        "session": session,
        "session_factory": session_factory,
    }


def invoke(context, **overrides):
    arguments = {
        "session_factory": context["session_factory"],
        "execution_id": context["execution_id"],
        "project_id": context["project_id"],
        "data_source_id": context["data_source_id"],
    }
    arguments.update(overrides)
    return verify_committed_workload_ownership(**arguments)


def assert_one_read_and_close(context):
    context["session_factory"].assert_called_once_with()
    context["session"].scalar.assert_called_once()
    context["session"].close.assert_called_once_with()


def assert_no_writes(context):
    session = context["session"]
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    session.flush.assert_not_called()
    session.execute.assert_not_called()
    session.delete.assert_not_called()


def test_exact_reserved_unreleased_ownership_passes():
    context = make_context()

    result = invoke(context)

    assert result == context["execution_id"]
    assert_one_read_and_close(context)
    assert_no_writes(context)


@pytest.mark.parametrize(
    "invalid_factory",
    [None, object(), 7, "not_callable"],
)
def test_invalid_session_factory_rejected_before_session_creation(
    invalid_factory,
):
    context = make_context()

    with pytest.raises(ValueError, match="session factory"):
        invoke(context, session_factory=invalid_factory)

    context["session_factory"].assert_not_called()
    context["session"].scalar.assert_not_called()
    context["session"].close.assert_not_called()


@pytest.mark.parametrize(
    "identity_name",
    ["execution_id", "project_id", "data_source_id"],
)
@pytest.mark.parametrize(
    "invalid_value",
    [None, True, 7, "not-a-uuid"],
)
def test_invalid_uuid_identity_rejected_before_session_creation(
    identity_name, invalid_value,
):
    context = make_context()

    with pytest.raises(ValueError, match="UUID identities"):
        invoke(context, **{identity_name: invalid_value})

    context["session_factory"].assert_not_called()
    context["session"].scalar.assert_not_called()


def test_missing_committed_ownership_is_rejected():
    context = make_context()
    context["session"].scalar.return_value = None

    with pytest.raises(
        CommittedWorkloadOwnershipUnavailableError,
        match="unavailable",
    ):
        invoke(context)

    assert_one_read_and_close(context)
    assert_no_writes(context)


@pytest.mark.parametrize(
    "identity_name",
    ["execution_id", "project_id", "data_source_id"],
)
def test_committed_ownership_identity_mismatch_is_rejected(identity_name):
    context = make_context()
    setattr(context["ownership"], identity_name, uuid4())

    with pytest.raises(
        CommittedWorkloadOwnershipUnavailableError,
        match="identity mismatch",
    ):
        invoke(context)

    assert_one_read_and_close(context)
    assert_no_writes(context)


@pytest.mark.parametrize(
    "state",
    ["released", "unresolved", "RESERVED", "RELEASED", "PENDING", "ACTIVE", None, ""],
)
def test_non_reserved_ownership_is_rejected(state):
    context = make_context()
    context["ownership"].ownership_state = state

    with pytest.raises(
        CommittedWorkloadOwnershipUnavailableError,
        match="not reserved",
    ):
        invoke(context)

    assert_one_read_and_close(context)
    assert_no_writes(context)


@pytest.mark.parametrize(
    "field",
    [
        "released_at",
        "release_actor",
        "release_reason",
        "release_evidence_reference",
    ],
)
def test_any_release_metadata_rejects_even_reserved_ownership(field):
    context = make_context()
    setattr(context["ownership"], field, "synthetic-release-evidence")

    with pytest.raises(
        CommittedWorkloadOwnershipUnavailableError,
        match="release metadata",
    ):
        invoke(context)

    assert_one_read_and_close(context)
    assert_no_writes(context)


@pytest.mark.parametrize(
    "error_type",
    [RuntimeError, ValueError, LookupError],
)
def test_database_read_failure_propagates_without_retry(error_type):
    context = make_context()
    context["session"].scalar.side_effect = error_type(
        "Synthetic offline read failure."
    )

    with pytest.raises(error_type):
        invoke(context)

    assert_one_read_and_close(context)
    assert_no_writes(context)


def test_session_factory_failure_propagates_without_retry():
    context = make_context()
    context["session_factory"].side_effect = RuntimeError(
        "Synthetic session creation failure."
    )

    with pytest.raises(RuntimeError):
        invoke(context)

    context["session_factory"].assert_called_once_with()
    context["session"].scalar.assert_not_called()
    context["session"].close.assert_not_called()


def test_session_close_failure_propagates():
    context = make_context()
    context["session"].close.side_effect = RuntimeError(
        "Synthetic session close failure."
    )

    with pytest.raises(RuntimeError):
        invoke(context)

    context["session_factory"].assert_called_once_with()
    context["session"].scalar.assert_called_once()
    context["session"].close.assert_called_once()
    assert_no_writes(context)


def test_failed_ownership_verification_still_closes_session():
    context = make_context()
    context["ownership"].ownership_state = "released"

    with pytest.raises(CommittedWorkloadOwnershipUnavailableError):
        invoke(context)

    context["session"].close.assert_called_once_with()
    context["session"].scalar.assert_called_once()


def test_success_never_writes_or_releases_capacity():
    context = make_context()

    assert invoke(context) == context["execution_id"]

    assert_no_writes(context)
    context["session"].close.assert_called_once_with()


def test_exact_execution_identity_is_required():
    context = make_context()
    requested_id = uuid4()

    with pytest.raises(
        CommittedWorkloadOwnershipUnavailableError,
        match="identity mismatch",
    ):
        invoke(context, execution_id=requested_id)

    assert_one_read_and_close(context)
    assert_no_writes(context)