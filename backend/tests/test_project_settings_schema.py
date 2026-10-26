"""Tests for project Administration settings API schemas."""

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.project_settings import (
    ProjectSettingsRead,
    ProjectSettingsUpdate,
)


def test_settings_read_schema():
    project_id = uuid.uuid4()

    result = ProjectSettingsRead(
        project_id=project_id,
        allow_steward_self_approval=False,
    )

    assert result.project_id == project_id
    assert result.allow_steward_self_approval is False


def test_settings_update_accepts_boolean():
    result = ProjectSettingsUpdate(
        allow_steward_self_approval=True,
    )

    assert result.allow_steward_self_approval is True


@pytest.mark.parametrize("invalid_value", ["true", "yes", 1, None])
def test_settings_update_rejects_non_boolean_values(invalid_value):
    with pytest.raises(ValidationError):
        ProjectSettingsUpdate(
            allow_steward_self_approval=invalid_value,
        )


def test_settings_update_requires_explicit_value():
    with pytest.raises(ValidationError):
        ProjectSettingsUpdate()


def test_settings_update_rejects_unrelated_fields():
    with pytest.raises(ValidationError):
        ProjectSettingsUpdate(
            allow_steward_self_approval=True,
            name="Unauthorized project rename",
        )
