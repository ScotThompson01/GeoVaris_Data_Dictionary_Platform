"""Phase 5E tests for authorized, project-scoped execution row locking."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.data_quality_execution_persistence import (
    get_authorized_locked_execution,
)


def test_permission_denial_prevents_execution_lookup():
    db = MagicMock()
    project_id = uuid4()
    actor_user_id = uuid4()

    with patch(
        "app.services.project_authorization.require_dq_rule_executor",
        side_effect=HTTPException(
            status_code=403,
            detail="Execution permission required.",
        ),
    ) as require_executor:
        with pytest.raises(HTTPException) as exc:
            get_authorized_locked_execution(
                db,
                project_id=project_id,
                execution_id=uuid4(),
                actor_user_id=actor_user_id,
            )

    assert exc.value.status_code == 403
    require_executor.assert_called_once_with(
        db,
        user_id=actor_user_id,
        project_id=project_id,
    )
    db.scalar.assert_not_called()


def test_execution_outside_project_is_not_found():
    db = MagicMock()
    db.scalar.return_value = None

    with patch(
        "app.services.project_authorization.require_dq_rule_executor"
    ):
        with pytest.raises(HTTPException) as exc:
            get_authorized_locked_execution(
                db,
                project_id=uuid4(),
                execution_id=uuid4(),
                actor_user_id=uuid4(),
            )

    assert exc.value.status_code == 404
    db.scalar.assert_called_once()


def test_authorized_execution_is_retrieved_with_row_lock():
    db = MagicMock()
    project_id = uuid4()
    execution_id = uuid4()
    actor_user_id = uuid4()

    execution = MagicMock()
    execution.id = execution_id
    execution.project_id = project_id
    db.scalar.return_value = execution

    with patch(
        "app.services.project_authorization.require_dq_rule_executor"
    ) as require_executor:
        result = get_authorized_locked_execution(
            db,
            project_id=project_id,
            execution_id=execution_id,
            actor_user_id=actor_user_id,
        )

    assert result is execution
    require_executor.assert_called_once_with(
        db,
        user_id=actor_user_id,
        project_id=project_id,
    )

    statement = db.scalar.call_args.args[0]
    compiled = str(statement.compile()).upper()

    assert "FOR UPDATE" in compiled
    assert statement.get_execution_options().get("populate_existing") is True
    assert "PROJECT_ID" in compiled
    assert "ID" in compiled

    db.commit.assert_not_called()
