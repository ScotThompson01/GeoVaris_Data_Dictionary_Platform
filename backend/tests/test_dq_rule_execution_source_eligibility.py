"""Tests for Data Quality execution source eligibility."""

from types import SimpleNamespace

import pytest

from app.services.data_quality_rule_execution import validate_source_eligibility


def make_source(
    source_type="postgresql",
    connection_mode="database",
    is_active=True,
):
    return SimpleNamespace(
        source_type=source_type,
        connection_mode=connection_mode,
        is_active=is_active,
    )


def test_active_postgresql_database_source_is_eligible():
    validate_source_eligibility(make_source())


@pytest.mark.parametrize("source_type", ["csv", "excel", "sql_server"])
def test_unsupported_source_type_is_rejected(source_type):
    with pytest.raises(ValueError, match="PostgreSQL"):
        validate_source_eligibility(make_source(source_type=source_type))


def test_inactive_source_is_rejected():
    with pytest.raises(ValueError, match="active"):
        validate_source_eligibility(make_source(is_active=False))


def test_file_connection_mode_is_rejected():
    with pytest.raises(ValueError, match="database connection"):
        validate_source_eligibility(make_source(connection_mode="file"))
