"""Tests for data-source retrieval during Data Quality execution."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.data_quality_rule_execution import get_execution_data_source


def test_missing_execution_data_source_is_rejected():
    source_object = SimpleNamespace(data_source_id=uuid.uuid4())
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc:
        get_execution_data_source(db, source_object=source_object)

    assert exc.value.status_code == 409
    db.scalar.assert_called_once()


def test_referenced_execution_data_source_is_returned():
    source_id = uuid.uuid4()
    source_object = SimpleNamespace(data_source_id=source_id)
    expected_source = SimpleNamespace(
        id=source_id,
        source_type="postgresql",
        connection_mode="database",
        is_active=True,
    )

    db = MagicMock()
    db.scalar.return_value = expected_source

    result = get_execution_data_source(
        db,
        source_object=source_object,
    )

    assert result is expected_source
    db.scalar.assert_called_once()

    query = db.scalar.call_args.args[0]
    compiled = query.compile()
    assert source_id in compiled.params.values()
