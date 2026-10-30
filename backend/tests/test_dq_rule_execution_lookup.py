"""Tests for project-scoped Data Quality execution rule retrieval."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.data_quality_rule_execution import get_authorized_execution_rule


def test_rule_outside_authorized_project_is_not_found():
    db = MagicMock()
    db.scalar.return_value = None

    with patch(
        "app.services.project_authorization.require_dq_rule_executor"
    ) as require_executor:
        with pytest.raises(HTTPException) as exc:
            get_authorized_execution_rule(
                db,
                project_id=uuid.uuid4(),
                rule_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
            )

    assert exc.value.status_code == 404
    require_executor.assert_called_once()
    assert db.scalar.call_count == 1


def test_execution_permission_denial_prevents_rule_lookup():
    db = MagicMock()
    project_id = uuid.uuid4()
    rule_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()

    with patch(
        "app.services.project_authorization.require_dq_rule_executor",
        side_effect=HTTPException(
            status_code=403,
            detail="Data Quality rule execution permission required.",
        ),
    ) as require_executor:
        with pytest.raises(HTTPException) as exc:
            get_authorized_execution_rule(
                db,
                project_id=project_id,
                rule_id=rule_id,
                actor_user_id=actor_user_id,
            )

    assert exc.value.status_code == 403
    require_executor.assert_called_once_with(
        db,
        user_id=actor_user_id,
        project_id=project_id,
    )
    db.scalar.assert_not_called()


def test_authorized_project_rule_is_returned():
    db = MagicMock()
    project_id = uuid.uuid4()
    rule_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    expected_rule = MagicMock()
    expected_rule.id = rule_id
    db.scalar.return_value = expected_rule

    with patch(
        "app.services.project_authorization.require_dq_rule_executor"
    ) as require_executor:
        result = get_authorized_execution_rule(
            db,
            project_id=project_id,
            rule_id=rule_id,
            actor_user_id=actor_user_id,
        )

    assert result is expected_rule
    require_executor.assert_called_once_with(
        db,
        user_id=actor_user_id,
        project_id=project_id,
    )
    db.scalar.assert_called_once()
