"""Unit tests for explicit data source connection-management authorization."""

from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.project_authorization import (
    require_data_source_connection_manager,
)


def test_connection_manager_requires_project_membership():
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc:
        require_data_source_connection_manager(
            db,
            user_id=uuid4(),
            project_id=uuid4(),
        )

    assert exc.value.status_code == 404
    assert db.scalar.call_count == 1


def test_project_member_without_management_permission_is_denied():
    db = MagicMock()
    db.scalar.side_effect = [uuid4(), None]

    with pytest.raises(HTTPException) as exc:
        require_data_source_connection_manager(
            db,
            user_id=uuid4(),
            project_id=uuid4(),
        )

    assert exc.value.status_code == 403
    assert db.scalar.call_count == 2


def test_explicit_connection_manager_is_authorized():
    db = MagicMock()
    db.scalar.side_effect = [uuid4(), uuid4()]

    result = require_data_source_connection_manager(
        db,
        user_id=uuid4(),
        project_id=uuid4(),
    )

    assert result is None
    assert db.scalar.call_count == 2
