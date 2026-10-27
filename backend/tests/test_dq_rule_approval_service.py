"""Unit tests for controlled Data Quality rule approval."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.data_quality_rule_approval import approve_dq_rule_version


@pytest.fixture
def approval_context():
    db = MagicMock()
    identifiers = {
        "project_id": uuid.uuid4(),
        "rule_id": uuid.uuid4(),
        "version_id": uuid.uuid4(),
        "actor_user_id": uuid.uuid4(),
    }
    return db, identifiers


@patch("app.services.data_quality_rule_approval.require_dq_rule_approver")
def test_rejects_rule_outside_project(mock_authorize, approval_context):
    db, identifiers = approval_context
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as error:
        approve_dq_rule_version(db, **identifiers)

    assert error.value.status_code == 404
    assert db.scalar.call_count == 1
    db.commit.assert_not_called()
    db.add.assert_not_called()


@patch("app.services.data_quality_rule_approval.require_dq_rule_approver")
def test_rejects_missing_version(mock_authorize, approval_context):
    db, identifiers = approval_context
    db.scalar.side_effect = [
        identifiers["rule_id"],
        SimpleNamespace(status="draft"),
        None,
    ]

    with pytest.raises(HTTPException) as error:
        approve_dq_rule_version(db, **identifiers)

    assert error.value.status_code == 404
    assert db.scalar.call_count == 3
    db.commit.assert_not_called()
    db.add.assert_not_called()


@patch("app.services.data_quality_rule_approval.require_dq_rule_approver")
def test_rejects_retired_parent_rule(mock_authorize, approval_context):
    db, identifiers = approval_context
    db.scalar.side_effect = [
        identifiers["rule_id"],
        SimpleNamespace(status="retired"),
        SimpleNamespace(
            status="draft",
            created_by_user_id=uuid.uuid4(),
        ),
    ]

    with pytest.raises(HTTPException) as error:
        approve_dq_rule_version(db, **identifiers)

    assert error.value.status_code == 409
    assert db.scalar.call_count == 3
    db.commit.assert_not_called()
    db.add.assert_not_called()


@patch("app.services.data_quality_rule_approval.require_dq_rule_approver")
def test_rejects_unknown_creator(mock_authorize, approval_context):
    db, identifiers = approval_context
    db.scalar.side_effect = [
        identifiers["rule_id"],
        SimpleNamespace(status="draft"),
        SimpleNamespace(status="draft", created_by_user_id=None),
    ]

    with pytest.raises(HTTPException) as error:
        approve_dq_rule_version(db, **identifiers)

    assert error.value.status_code == 409
    db.commit.assert_not_called()
    db.add.assert_not_called()


@patch("app.services.data_quality_rule_approval.require_dq_rule_approver")
def test_rejects_creator_self_approval(mock_authorize, approval_context):
    db, identifiers = approval_context
    db.scalar.side_effect = [
        identifiers["rule_id"],
        SimpleNamespace(status="draft"),
        SimpleNamespace(
            status="draft",
            created_by_user_id=identifiers["actor_user_id"],
        ),
    ]

    with pytest.raises(HTTPException) as error:
        approve_dq_rule_version(db, **identifiers)

    assert error.value.status_code == 403
    db.commit.assert_not_called()
    db.add.assert_not_called()


@patch("app.services.data_quality_rule_approval.require_dq_rule_approver")
def test_successful_approval_creates_audit_event(
    mock_authorize, approval_context
):
    db, identifiers = approval_context

    parent_rule = SimpleNamespace(
        status="draft",
        active_version_id=None,
    )
    version = SimpleNamespace(
        status="draft",
        created_by_user_id=uuid.uuid4(),
    )

    db.scalar.side_effect = [
        identifiers["rule_id"],
        parent_rule,
        version,
    ]

    result = approve_dq_rule_version(db, **identifiers)

    assert result is version
    assert version.status == "approved"
    assert parent_rule.status == "draft"
    assert parent_rule.active_version_id is None

    db.add.assert_called_once()
    event = db.add.call_args.args[0]

    assert event.project_id == identifiers["project_id"]
    assert event.actor_user_id == identifiers["actor_user_id"]
    assert event.rule_id == identifiers["rule_id"]
    assert event.version_id == identifiers["version_id"]
    assert event.event_type == "version.approved"
    assert event.old_status == "draft"
    assert event.new_status == "approved"

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


@patch("app.services.data_quality_rule_approval.require_dq_rule_approver")
def test_commit_failure_rolls_back(mock_authorize, approval_context):
    db, identifiers = approval_context

    version = SimpleNamespace(
        status="draft",
        created_by_user_id=uuid.uuid4(),
    )

    db.scalar.side_effect = [
        identifiers["rule_id"],
        SimpleNamespace(status="draft", active_version_id=None),
        version,
    ]
    db.commit.side_effect = RuntimeError("Simulated commit failure")

    with pytest.raises(RuntimeError, match="Simulated commit failure"):
        approve_dq_rule_version(db, **identifiers)

    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.rollback.assert_called_once()
