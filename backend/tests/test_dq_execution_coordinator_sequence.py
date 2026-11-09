"""Offline tests for Phase 5E protected coordinator sequencing.

No API routes, runtime admission, client-source I/O, or capacity release.
"""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.services.data_quality_execution_coordinator_sequence import (
    coordinate_protected_admission_and_start,
)


MODULE = "app.services.data_quality_execution_coordinator_sequence"


def make_context():
    stage_start = Mock()
    stage_start_factory = Mock(return_value=stage_start)

    return {
        "project_id": uuid4(),
        "execution_id": uuid4(),
        "session_factory": Mock(),
        "stage_admission": Mock(),
        "stage_start": stage_start,
        "stage_start_factory": stage_start_factory,
    }


def run_sequence(context):
    return coordinate_protected_admission_and_start(
        session_factory=context["session_factory"],
        project_id=context["project_id"],
        stage_admission=context["stage_admission"],
        stage_start_factory=context["stage_start_factory"],
    )


def test_admission_precedes_start_without_measurement():
    context = make_context()
    events = []

    def admit(**kwargs):
        events.append("admit")
        assert kwargs["session_factory"] is context["session_factory"]
        assert kwargs["project_id"] == context["project_id"]
        assert kwargs["stage_admission"] is context["stage_admission"]
        return context["execution_id"]

    def create_start(execution_id):
        events.append("create_start")
        assert execution_id == context["execution_id"]
        return context["stage_start"]

    context["stage_start_factory"].side_effect = create_start

    def start(**kwargs):
        events.append("start")
        assert kwargs["session_factory"] is context["session_factory"]
        assert kwargs["project_id"] == context["project_id"]
        assert kwargs["execution_id"] == context["execution_id"]
        assert kwargs["stage_start"] is context["stage_start"]
        return context["execution_id"]

    with (
        patch(
            MODULE + ".commit_and_verify_protected_admission",
            side_effect=admit,
        ) as admission,
        patch(
            MODULE + ".commit_and_verify_protected_start",
            side_effect=start,
        ) as running,
    ):
        result = run_sequence(context)

    assert result == context["execution_id"]
    assert events == ["admit", "create_start", "start"]
    admission.assert_called_once()
    running.assert_called_once()


def test_admission_failure_prevents_start_callback_creation():
    context = make_context()

    with (
        patch(
            MODULE + ".commit_and_verify_protected_admission",
            side_effect=ConnectionError("Commit outcome unknown"),
        ) as admission,
        patch(
            MODULE + ".commit_and_verify_protected_start",
        ) as running,
    ):
        with pytest.raises(ConnectionError, match="unknown"):
            run_sequence(context)

    admission.assert_called_once()
    context["stage_start_factory"].assert_not_called()
    running.assert_not_called()


def test_start_failure_propagates_without_retry():
    context = make_context()

    with (
        patch(
            MODULE + ".commit_and_verify_protected_admission",
            return_value=context["execution_id"],
        ) as admission,
        patch(
            MODULE + ".commit_and_verify_protected_start",
            side_effect=ValueError("RUNNING protection missing"),
        ) as running,
    ):
        with pytest.raises(ValueError, match="RUNNING protection missing"):
            run_sequence(context)

    admission.assert_called_once()
    running.assert_called_once()
    context["stage_start_factory"].assert_called_once_with(
        context["execution_id"]
    )


def test_invalid_admission_result_blocks_start():
    context = make_context()

    with (
        patch(
            MODULE + ".commit_and_verify_protected_admission",
            return_value="not-a-uuid",
        ),
        patch(
            MODULE + ".commit_and_verify_protected_start",
        ) as running,
    ):
        with pytest.raises(ValueError):
            run_sequence(context)

    context["stage_start_factory"].assert_not_called()
    running.assert_not_called()


def test_start_callback_factory_must_return_callable():
    context = make_context()
    context["stage_start_factory"].return_value = None

    with (
        patch(
            MODULE + ".commit_and_verify_protected_admission",
            return_value=context["execution_id"],
        ),
        patch(
            MODULE + ".commit_and_verify_protected_start",
        ) as running,
    ):
        with pytest.raises(ValueError):
            run_sequence(context)

    running.assert_not_called()


def test_start_result_identity_mismatch_rejected():
    context = make_context()

    with (
        patch(
            MODULE + ".commit_and_verify_protected_admission",
            return_value=context["execution_id"],
        ),
        patch(
            MODULE + ".commit_and_verify_protected_start",
            return_value=uuid4(),
        ),
    ):
        with pytest.raises(ValueError, match="identity"):
            run_sequence(context)


@pytest.mark.parametrize(
    "invalid",
    [None, "", 1, True],
)
def test_invalid_project_rejected_before_admission(invalid):
    context = make_context()
    context["project_id"] = invalid

    with patch(
        MODULE + ".commit_and_verify_protected_admission"
    ) as admission:
        with pytest.raises(ValueError):
            run_sequence(context)

    admission.assert_not_called()


def test_invalid_session_factory_rejected_before_admission():
    context = make_context()
    context["session_factory"] = None

    with patch(
        MODULE + ".commit_and_verify_protected_admission"
    ) as admission:
        with pytest.raises(ValueError):
            run_sequence(context)

    admission.assert_not_called()


def test_invalid_admission_callback_rejected_before_admission():
    context = make_context()
    context["stage_admission"] = None

    with patch(
        MODULE + ".commit_and_verify_protected_admission"
    ) as admission:
        with pytest.raises(ValueError):
            run_sequence(context)

    admission.assert_not_called()


def test_invalid_start_factory_rejected_before_admission():
    context = make_context()
    context["stage_start_factory"] = None

    with patch(
        MODULE + ".commit_and_verify_protected_admission"
    ) as admission:
        with pytest.raises(ValueError):
            run_sequence(context)

    admission.assert_not_called()
