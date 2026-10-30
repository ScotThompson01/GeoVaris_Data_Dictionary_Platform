"""Tests for retrieving field metadata during Data Quality execution."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.data_quality_rule_execution import get_execution_field


def test_missing_execution_field_is_rejected():
    rule = SimpleNamespace(
        data_field_id=uuid.uuid4(),
    )
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc:
        get_execution_field(db, rule=rule)

    assert exc.value.status_code == 409
    db.scalar.assert_called_once()


def test_referenced_execution_field_is_returned():
    field_id = uuid.uuid4()
    rule = SimpleNamespace(data_field_id=field_id)
    expected_field = SimpleNamespace(id=field_id, field_name="latitude")

    db = MagicMock()
    db.scalar.return_value = expected_field

    result = get_execution_field(db, rule=rule)

    assert result is expected_field
    db.scalar.assert_called_once()

    query = db.scalar.call_args.args[0]
    compiled = query.compile()
    assert field_id in compiled.params.values()
