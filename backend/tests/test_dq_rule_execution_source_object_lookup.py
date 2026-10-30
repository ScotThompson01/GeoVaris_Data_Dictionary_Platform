"""Tests for source-object retrieval during Data Quality execution."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.data_quality_rule_execution import get_execution_source_object


def test_missing_execution_source_object_is_rejected():
    field = SimpleNamespace(source_object_id=uuid.uuid4())
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc:
        get_execution_source_object(db, field=field)

    assert exc.value.status_code == 409
    db.scalar.assert_called_once()


def test_referenced_execution_source_object_is_returned():
    source_object_id = uuid.uuid4()
    field = SimpleNamespace(source_object_id=source_object_id)
    expected_object = SimpleNamespace(
        id=source_object_id,
        object_type="table",
        schema_name="public",
        object_name="locations",
    )

    db = MagicMock()
    db.scalar.return_value = expected_object

    result = get_execution_source_object(db, field=field)

    assert result is expected_object
    db.scalar.assert_called_once()

    query = db.scalar.call_args.args[0]
    compiled = query.compile()
    assert source_object_id in compiled.params.values()
