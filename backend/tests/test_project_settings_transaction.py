"""Tests for transactional project administration setting updates."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.audit_event import AuditEvent
from app.services.project_administration import update_steward_self_approval


def test_setting_change_creates_audit_event_and_commits():
    db = MagicMock()
    project = SimpleNamespace(
        id=uuid.uuid4(),
        allow_steward_self_approval=False,
    )
    actor_id = uuid.uuid4()

    changed = update_steward_self_approval(
        db,
        project=project,
        actor_user_id=actor_id,
        enabled=True,
    )

    assert changed is True
    assert project.allow_steward_self_approval is True

    audit_event = db.add.call_args.args[0]
    assert isinstance(audit_event, AuditEvent)
    assert audit_event.project_id == project.id
    assert audit_event.actor_user_id == actor_id
    assert audit_event.old_value is False
    assert audit_event.new_value is True
    assert audit_event.event_type == "project.steward_self_approval.changed"

    db.commit.assert_called_once()


def test_unchanged_setting_does_not_create_audit_event():
    db = MagicMock()
    project = SimpleNamespace(
        id=uuid.uuid4(),
        allow_steward_self_approval=False,
    )

    changed = update_steward_self_approval(
        db,
        project=project,
        actor_user_id=uuid.uuid4(),
        enabled=False,
    )

    assert changed is False
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_failed_commit_rolls_back_setting_change():
    db = MagicMock()
    db.commit.side_effect = RuntimeError("Synthetic database failure")

    project = SimpleNamespace(
        id=uuid.uuid4(),
        allow_steward_self_approval=False,
    )

    with pytest.raises(RuntimeError, match="Synthetic database failure"):
        update_steward_self_approval(
            db,
            project=project,
            actor_user_id=uuid.uuid4(),
            enabled=True,
        )

    db.rollback.assert_called_once()
    assert project.allow_steward_self_approval is False
