"""Unit tests for controlled Data Quality rule activation."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.data_quality_rule_activation import activate_dq_rule_version


@patch("app.services.data_quality_rule_activation.require_dq_rule_approver")
def test_approved_version_can_be_activated(mock_authorize):
    db = MagicMock()

    identifiers = {
        "project_id": uuid.uuid4(),
        "rule_id": uuid.uuid4(),
        "version_id": uuid.uuid4(),
        "actor_user_id": uuid.uuid4(),
    }

    parent_rule = SimpleNamespace(
        status="draft",
        active_version_id=None,
    )
    version = SimpleNamespace(status="approved")

    db.scalar.side_effect = [
        identifiers["rule_id"],
        parent_rule,
        version,
    ]

    result = activate_dq_rule_version(db, **identifiers)

    assert result is parent_rule
    assert parent_rule.status == "active"
    assert parent_rule.active_version_id == identifiers["version_id"]
    assert version.status == "approved"

    mock_authorize.assert_called_once_with(
        db,
        user_id=identifiers["actor_user_id"],
        project_id=identifiers["project_id"],
    )

    db.add.assert_called_once()
    event = db.add.call_args.args[0]

    assert event.project_id == identifiers["project_id"]
    assert event.actor_user_id == identifiers["actor_user_id"]
    assert event.rule_id == identifiers["rule_id"]
    assert event.version_id == identifiers["version_id"]
    assert event.event_type == "version.activated"
    assert event.old_status == "draft"
    assert event.new_status == "active"

    db.commit.assert_called_once()
    db.rollback.assert_not_called()

from fastapi import HTTPException
import pytest


@pytest.fixture
def activation_context():
    db = MagicMock()
    identifiers = {
        "project_id": uuid.uuid4(),
        "rule_id": uuid.uuid4(),
        "version_id": uuid.uuid4(),
        "actor_user_id": uuid.uuid4(),
    }
    return db, identifiers


@patch("app.services.data_quality_rule_activation.require_dq_rule_approver")
def test_rejects_rule_outside_project(mock_authorize, activation_context):
    db, identifiers = activation_context
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as error:
        activate_dq_rule_version(db, **identifiers)

    assert error.value.status_code == 404
    db.commit.assert_not_called()
    db.add.assert_not_called()


@patch("app.services.data_quality_rule_activation.require_dq_rule_approver")
def test_rejects_missing_version(mock_authorize, activation_context):
    db, identifiers = activation_context
    db.scalar.side_effect = [
        identifiers["rule_id"],
        SimpleNamespace(status="draft", active_version_id=None),
        None,
    ]

    with pytest.raises(HTTPException) as error:
        activate_dq_rule_version(db, **identifiers)

    assert error.value.status_code == 404
    db.commit.assert_not_called()
    db.add.assert_not_called()


@patch("app.services.data_quality_rule_activation.require_dq_rule_approver")
def test_rejects_unapproved_version(mock_authorize, activation_context):
    db, identifiers = activation_context
    db.scalar.side_effect = [
        identifiers["rule_id"],
        SimpleNamespace(status="draft", active_version_id=None),
        SimpleNamespace(status="draft"),
    ]

    with pytest.raises(HTTPException) as error:
        activate_dq_rule_version(db, **identifiers)

    assert error.value.status_code == 409
    db.commit.assert_not_called()
    db.add.assert_not_called()


@patch("app.services.data_quality_rule_activation.require_dq_rule_approver")
def test_rejects_retired_parent_rule(mock_authorize, activation_context):
    db, identifiers = activation_context
    db.scalar.side_effect = [
        identifiers["rule_id"],
        SimpleNamespace(status="retired", active_version_id=None),
        SimpleNamespace(status="approved"),
    ]

    with pytest.raises(HTTPException) as error:
        activate_dq_rule_version(db, **identifiers)

    assert error.value.status_code == 409
    db.commit.assert_not_called()
    db.add.assert_not_called()


@patch("app.services.data_quality_rule_activation.require_dq_rule_approver")
def test_rejects_already_active_version(mock_authorize, activation_context):
    db, identifiers = activation_context
    db.scalar.side_effect = [
        identifiers["rule_id"],
        SimpleNamespace(
            status="active",
            active_version_id=identifiers["version_id"],
        ),
        SimpleNamespace(status="approved"),
    ]

    with pytest.raises(HTTPException) as error:
        activate_dq_rule_version(db, **identifiers)

    assert error.value.status_code == 409
    db.commit.assert_not_called()
    db.add.assert_not_called()


@patch("app.services.data_quality_rule_activation.require_dq_rule_approver")
def test_commit_failure_rolls_back_activation(mock_authorize, activation_context):
    db, identifiers = activation_context
    parent_rule = SimpleNamespace(status="draft", active_version_id=None)

    db.scalar.side_effect = [
        identifiers["rule_id"],
        parent_rule,
        SimpleNamespace(status="approved"),
    ]
    db.commit.side_effect = RuntimeError("Simulated commit failure")

    with pytest.raises(RuntimeError, match="Simulated commit failure"):
        activate_dq_rule_version(db, **identifiers)

    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.rollback.assert_called_once()
