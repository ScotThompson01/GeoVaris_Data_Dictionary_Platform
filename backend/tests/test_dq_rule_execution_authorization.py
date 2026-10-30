"""Tests for explicit Data Quality rule execution authorization."""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.project_authorization import require_dq_rule_executor


def test_dq_execution_requires_project_membership():
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc:
        require_dq_rule_executor(
            db,
            user_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Project not found."
    assert db.scalar.call_count == 1


def test_project_member_without_dq_execution_permission_is_denied():
    db = MagicMock()
    db.scalar.side_effect = [uuid.uuid4(), None]

    with pytest.raises(HTTPException) as exc:
        require_dq_rule_executor(
            db,
            user_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == (
        "Data Quality rule execution permission required."
    )
    assert db.scalar.call_count == 2


def test_project_member_with_dq_execution_permission_is_allowed():
    db = MagicMock()
    db.scalar.side_effect = [uuid.uuid4(), uuid.uuid4()]

    result = require_dq_rule_executor(
        db,
        user_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
    )

    assert result is None
    assert db.scalar.call_count == 2
