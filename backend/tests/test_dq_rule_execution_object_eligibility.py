"""Tests for Data Quality execution source-object eligibility."""

from types import SimpleNamespace

import pytest

from app.services.data_quality_rule_execution import validate_source_object_eligibility


def make_object(
    object_type="table",
    schema_name="public",
    object_name="customers",
):
    return SimpleNamespace(
        object_type=object_type,
        schema_name=schema_name,
        object_name=object_name,
    )


@pytest.mark.parametrize("object_type", ["table", "view"])
def test_postgresql_table_and_view_are_eligible(object_type):
    validate_source_object_eligibility(make_object(object_type=object_type))


@pytest.mark.parametrize("object_type", ["file", "worksheet"])
def test_unsupported_object_type_is_rejected(object_type):
    with pytest.raises(ValueError, match="table or view"):
        validate_source_object_eligibility(make_object(object_type=object_type))


@pytest.mark.parametrize("schema_name", [None, "", "   "])
def test_missing_schema_name_is_rejected(schema_name):
    with pytest.raises(ValueError, match="schema name"):
        validate_source_object_eligibility(make_object(schema_name=schema_name))


@pytest.mark.parametrize("object_name", [None, "", "   "])
def test_missing_object_name_is_rejected(object_name):
    with pytest.raises(ValueError, match="object name"):
        validate_source_object_eligibility(make_object(object_name=object_name))
