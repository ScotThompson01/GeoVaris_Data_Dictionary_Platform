"""Proposed Phase 5E Data Quality execution lifecycle policy tests.

These tests do not connect to databases or client data sources.
The full transition matrix remains subject to design review.
"""

import pytest

from app.services.data_quality_execution_lifecycle import (
    ExecutionStatus,
    validate_execution_transition,
)


def test_lifecycle_defines_all_seven_approved_statuses():
    assert {status.value for status in ExecutionStatus} == {
        "pending",
        "running",
        "succeeded",
        "failed",
        "incomplete",
        "status_uncertain",
        "cancelled",
    }


@pytest.mark.parametrize(
    ("current", "next_status"),
    [
        (ExecutionStatus.PENDING, ExecutionStatus.RUNNING),
        (ExecutionStatus.PENDING, ExecutionStatus.CANCELLED),
        (ExecutionStatus.RUNNING, ExecutionStatus.SUCCEEDED),
        (ExecutionStatus.RUNNING, ExecutionStatus.FAILED),
        (ExecutionStatus.RUNNING, ExecutionStatus.INCOMPLETE),
        (ExecutionStatus.RUNNING, ExecutionStatus.STATUS_UNCERTAIN),
    ],
)
def test_proposed_basic_transitions_are_allowed(current, next_status):
    validate_execution_transition(current, next_status)


@pytest.mark.parametrize(
    ("current", "next_status"),
    [
        (ExecutionStatus.PENDING, ExecutionStatus.SUCCEEDED),
        (ExecutionStatus.PENDING, ExecutionStatus.FAILED),
        (ExecutionStatus.SUCCEEDED, ExecutionStatus.RUNNING),
        (ExecutionStatus.FAILED, ExecutionStatus.RUNNING),
        (ExecutionStatus.CANCELLED, ExecutionStatus.RUNNING),
        (ExecutionStatus.STATUS_UNCERTAIN, ExecutionStatus.SUCCEEDED),
        (ExecutionStatus.STATUS_UNCERTAIN, ExecutionStatus.CANCELLED),
    ],
)
def test_unsafe_transitions_are_rejected(current, next_status):
    with pytest.raises(ValueError):
        validate_execution_transition(current, next_status)


@pytest.mark.parametrize("status", list((
    "pending", "running", "succeeded", "failed",
    "incomplete", "status_uncertain", "cancelled",
)))
def test_unknown_status_is_not_accepted(status):
    with pytest.raises(ValueError):
        validate_execution_transition(status, "not_a_valid_status")


def test_repeated_transition_is_rejected():
    with pytest.raises(ValueError):
        validate_execution_transition(
            ExecutionStatus.RUNNING,
            ExecutionStatus.RUNNING,
        )
