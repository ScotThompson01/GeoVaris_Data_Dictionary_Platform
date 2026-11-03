"""Unit tests for the authorized, transaction-scoped execution start."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.data_quality_execution_persistence import (
    stage_authorized_running_execution,
)


def test_authorized_start_locks_before_staging_running():
    db = MagicMock()
    project_id = uuid4()
    execution_id = uuid4()
    actor_user_id = uuid4()
    started_at = datetime.now(timezone.utc)
    execution = MagicMock()
    updated_execution = MagicMock()
    calls = []

    def lock(*args, **kwargs):
        calls.append("lock")
        assert args == (db,)
        assert kwargs == {
            "project_id": project_id,
            "execution_id": execution_id,
            "actor_user_id": actor_user_id,
        }
        return execution

    def stage(*args, **kwargs):
        calls.append("stage")
        assert args == (db,)
        assert kwargs == {
            "execution": execution,
            "started_at": started_at,
        }
        return updated_execution

    with patch(
        "app.services.data_quality_execution_persistence."
        "get_authorized_locked_execution",
        side_effect=lock,
    ), patch(
        "app.services.data_quality_execution_persistence."
        "stage_running_execution",
        side_effect=stage,
    ):
        result = stage_authorized_running_execution(
            db,
            project_id=project_id,
            execution_id=execution_id,
            actor_user_id=actor_user_id,
            started_at=started_at,
        )

    assert result is updated_execution
    assert calls == ["lock", "stage"]
    db.commit.assert_not_called()


def test_authorized_start_does_not_stage_after_access_denial():
    db = MagicMock()

    with patch(
        "app.services.data_quality_execution_persistence."
        "get_authorized_locked_execution",
        side_effect=HTTPException(status_code=403, detail="Forbidden"),
    ), patch(
        "app.services.data_quality_execution_persistence."
        "stage_running_execution",
    ) as stage:
        with pytest.raises(HTTPException) as exc:
            stage_authorized_running_execution(
                db,
                project_id=uuid4(),
                execution_id=uuid4(),
                actor_user_id=uuid4(),
                started_at=datetime.now(timezone.utc),
            )

    assert exc.value.status_code == 403
    stage.assert_not_called()
    db.commit.assert_not_called()


def test_authorized_start_propagates_invalid_transition():
    db = MagicMock()

    with patch(
        "app.services.data_quality_execution_persistence."
        "get_authorized_locked_execution",
        return_value=MagicMock(status="cancelled"),
    ), patch(
        "app.services.data_quality_execution_persistence."
        "stage_running_execution",
        side_effect=ValueError("Transition not permitted"),
    ):
        with pytest.raises(ValueError, match="not permitted"):
            stage_authorized_running_execution(
                db,
                project_id=uuid4(),
                execution_id=uuid4(),
                actor_user_id=uuid4(),
                started_at=datetime.now(timezone.utc),
            )

    db.commit.assert_not_called()
