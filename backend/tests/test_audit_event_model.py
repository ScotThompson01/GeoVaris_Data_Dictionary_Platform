"""Tests for project administration audit-event metadata."""

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint

from app.models.audit_event import AuditEvent


def test_project_setting_audit_event_structure():
    table = AuditEvent.__table__

    assert table.name == "audit_events"
    assert table.c.id.primary_key
    assert table.c.project_id.nullable is False
    assert table.c.actor_user_id.nullable is False
    assert table.c.event_type.nullable is False

    assert isinstance(table.c.old_value.type, Boolean)
    assert isinstance(table.c.new_value.type, Boolean)
    assert table.c.old_value.nullable is False
    assert table.c.new_value.nullable is False

    assert isinstance(table.c.created_at.type, DateTime)
    assert table.c.created_at.server_default is not None

    user_foreign_keys = [
        constraint
        for constraint in table.foreign_key_constraints
        if any(element.column.table.name == "users" for element in constraint.elements)
    ]
    assert len(user_foreign_keys) == 1
    assert user_foreign_keys[0].ondelete != "CASCADE"
