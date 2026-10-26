"""Tests for project-level Data Quality administration settings."""

from app.models.project import Project


def test_steward_self_approval_is_disabled_by_default():
    column = Project.__table__.c.allow_steward_self_approval

    assert column.nullable is False
    assert column.default is not None
    assert column.default.arg is False
    assert column.server_default is not None
    assert column.server_default.arg == "false"
