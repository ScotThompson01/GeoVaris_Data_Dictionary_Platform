"""Tests for retrieving the active Data Quality rule version."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.data_quality_rule_execution import get_active_execution_version


def test_missing_active_version_is_rejected():
    rule_id = uuid.uuid4()
    version_id = uuid.uuid4()
    rule = SimpleNamespace(
        id=rule_id,
        active_version_id=version_id,
    )

    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc:
        get_active_execution_version(db, rule=rule)

    assert exc.value.status_code == 409
    db.scalar.assert_called_once()


def test_active_version_is_returned():
    rule_id = uuid.uuid4()
    version_id = uuid.uuid4()
    rule = SimpleNamespace(
        id=rule_id,
        active_version_id=version_id,
    )
    expected_version = SimpleNamespace(
        id=version_id,
        rule_id=rule_id,
        status="approved",
    )

    db = MagicMock()
    db.scalar.return_value = expected_version

    result = get_active_execution_version(db, rule=rule)

    assert result is expected_version
    db.scalar.assert_called_once()

    query = db.scalar.call_args.args[0]
    compiled = query.compile()
    assert rule_id in compiled.params.values()
    assert version_id in compiled.params.values()
