"""Schema contract for execution-bound PostgreSQL authorization.

These tests are intentionally red until the new model is implemented.
They do not connect to a database or initiate source measurement.
"""

import importlib

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    UniqueConstraint,
)


def _tables():
    import app.db.base
    from app.db.session import Base

    importlib.import_module(
        "app.models.data_quality_execution_connection_authorization"
    )

    name = "data_quality_execution_connection_authorizations"
    assert name in Base.metadata.tables
    return (
        Base.metadata.tables[name],
        Base.metadata.tables["data_quality_workload_ownership"],
    )


def test_authorization_evidence_has_required_nonsecret_columns():
    table, _ = _tables()

    expected = {
        "execution_id",
        "project_id",
        "data_source_id",
        "connection_revision",
        "authorized_host",
        "authorized_port",
        "authorized_database",
        "authorized_ip",
        "authorized_at",
    }

    assert set(table.columns.keys()) == expected

    for name in expected:
        assert table.c[name].nullable is False

    assert [column.name for column in table.primary_key.columns] == [
        "execution_id"
    ]

    assert table.c.authorized_at.type.timezone is True

    assert not any(
        word in name.lower()
        for name in table.columns.keys()
        for word in (
            "password",
            "secret",
            "credential",
            "private_key",
        )
    )


def test_authorization_evidence_is_bound_to_workload_and_source():
    table, ownership = _tables()

    foreign_keys = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]

    assert any(
        tuple(element.parent.name for element in constraint.elements)
        == ("execution_id", "project_id", "data_source_id")
        and tuple(
            element.target_fullname
            for element in constraint.elements
        )
        == (
            "data_quality_workload_ownership.execution_id",
            "data_quality_workload_ownership.project_id",
            "data_quality_workload_ownership.data_source_id",
        )
        and constraint.ondelete == "RESTRICT"
        for constraint in foreign_keys
    )

    assert any(
        tuple(element.parent.name for element in constraint.elements)
        == ("data_source_id",)
        and tuple(
            element.target_fullname
            for element in constraint.elements
        )
        == ("postgresql_connection_identities.data_source_id",)
        and constraint.ondelete == "RESTRICT"
        for constraint in foreign_keys
    )

    assert any(
        isinstance(constraint, UniqueConstraint)
        and {
            column.name for column in constraint.columns
        } == {"execution_id", "project_id", "data_source_id"}
        for constraint in ownership.constraints
    )


def test_authorization_evidence_has_revision_and_port_guards():
    table, _ = _tables()

    checks = [
        str(constraint.sqltext).lower()
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    ]

    assert any(
        "connection_revision" in expression
        and ">= 1" in expression
        for expression in checks
    )

    assert any(
        "authorized_port" in expression
        and "between 1 and 65535" in expression
        for expression in checks
    )
