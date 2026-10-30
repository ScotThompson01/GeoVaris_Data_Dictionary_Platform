"""Validation tests for Phase 5D execution API schemas."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.data_quality_execution import (
    RangeRuleExecutionRequest,
    RangeRuleExecutionResponse,
)


def valid_request():
    return {
        "project_id": uuid4(),
        "host": "localhost",
        "database": "test_database",
        "username": "readonly_user",
        "password": "synthetic_test_secret",
    }


def test_execution_request_masks_runtime_password():
    request = RangeRuleExecutionRequest(**valid_request())

    assert request.password.get_secret_value() == "synthetic_test_secret"
    assert "synthetic_test_secret" not in repr(request)
    assert "synthetic_test_secret" not in str(request)


def test_execution_request_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        RangeRuleExecutionRequest(
            **valid_request(),
            unexpected_setting="not_allowed",
        )


@pytest.mark.parametrize("port", [0, 65536])
def test_execution_request_rejects_invalid_port(port):
    with pytest.raises(ValidationError):
        RangeRuleExecutionRequest(**{**valid_request(), "port": port})


def test_execution_response_rejects_negative_counts():
    with pytest.raises(ValidationError):
        RangeRuleExecutionResponse(
            execution_id=uuid4(),
            project_id=uuid4(),
            rule_id=uuid4(),
            version_id=uuid4(),
            status="succeeded",
            total_count=10,
            passing_count=9,
            violation_count=-1,
            started_at="2026-10-29T12:00:00Z",
            completed_at="2026-10-29T12:00:01Z",
        )
