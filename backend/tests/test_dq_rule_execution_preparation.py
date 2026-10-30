"""Tests for Data Quality execution preparation."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.data_quality_rule_execution import prepare_rule_execution


def test_inactive_rule_is_rejected_during_preparation():
    db = MagicMock()
    project_id = uuid.uuid4()
    rule = SimpleNamespace(
        id=uuid.uuid4(),
        status="draft",
        active_version_id=uuid.uuid4(),
        data_field_id=uuid.uuid4(),
    )

    with patch(
        "app.services.data_quality_rule_execution.get_authorized_execution_rule",
        return_value=rule,
    ), patch(
        "app.services.data_quality_rule_execution.get_active_execution_version"
    ) as get_version:
        with pytest.raises(ValueError, match="active"):
            prepare_rule_execution(
                db,
                project_id=project_id,
                rule_id=rule.id,
                actor_user_id=uuid.uuid4(),
            )

    get_version.assert_not_called()


def test_valid_execution_metadata_is_prepared_without_measurement():
    db = MagicMock()
    project_id = uuid.uuid4()
    rule_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()

    rule = SimpleNamespace(
        id=rule_id,
        status="active",
        active_version_id=uuid.uuid4(),
        data_field_id=uuid.uuid4(),
    )
    version = SimpleNamespace(
        id=rule.active_version_id,
        rule_id=rule_id,
        status="approved",
        rule_type="range",
        quality_dimension="validity",
    )
    field = SimpleNamespace(
        id=rule.data_field_id,
        normalized_data_type="decimal",
    )
    source_object = SimpleNamespace(
        id=uuid.uuid4(),
        object_type="table",
        schema_name="public",
        object_name="locations",
    )
    source = SimpleNamespace(
        id=uuid.uuid4(),
        project_id=project_id,
        is_active=True,
        source_type="postgresql",
        connection_mode="database",
    )

    with patch(
        "app.services.data_quality_rule_execution.get_authorized_execution_rule",
        return_value=rule,
    ), patch(
        "app.services.data_quality_rule_execution.get_active_execution_version",
        return_value=version,
    ), patch(
        "app.services.data_quality_rule_execution.get_execution_field",
        return_value=field,
    ), patch(
        "app.services.data_quality_rule_execution.get_execution_source_object",
        return_value=source_object,
    ), patch(
        "app.services.data_quality_rule_execution.get_execution_data_source",
        return_value=source,
    ), patch(
        "app.services.data_quality_rule_execution.validate_execution_eligibility",
    ) as validate_rule, patch(
        "app.services.data_quality_rule_execution.validate_source_eligibility",
    ) as validate_source, patch(
        "app.services.data_quality_rule_execution.validate_source_object_eligibility",
    ) as validate_object:
        result = prepare_rule_execution(
            db,
            project_id=project_id,
            rule_id=rule_id,
            actor_user_id=actor_user_id,
        )

    assert result == {
        "rule": rule,
        "version": version,
        "field": field,
        "source_object": source_object,
        "source": source,
    }
    validate_rule.assert_called_once_with(rule, version, field)
    validate_source.assert_called_once_with(source)
    validate_object.assert_called_once_with(source_object)
    db.scalar.assert_not_called()


def test_ineligible_source_prevents_execution_preparation():
    db = MagicMock()
    rule = SimpleNamespace(
        id=uuid.uuid4(),
        status="active",
        active_version_id=uuid.uuid4(),
        data_field_id=uuid.uuid4(),
    )
    version = SimpleNamespace(
        id=rule.active_version_id,
        rule_id=rule.id,
        status="approved",
        rule_type="range",
        quality_dimension="validity",
    )
    field = SimpleNamespace(
        id=rule.data_field_id,
        normalized_data_type="decimal",
    )
    source_object = SimpleNamespace(
        id=uuid.uuid4(),
        object_type="table",
        schema_name="public",
        object_name="locations",
    )
    project_id = uuid.uuid4()
    source = SimpleNamespace(
        id=uuid.uuid4(),
        project_id=project_id,
        is_active=True,
        source_type="csv",
        connection_mode="file",
    )

    with patch(
        "app.services.data_quality_rule_execution.get_authorized_execution_rule",
        return_value=rule,
    ), patch(
        "app.services.data_quality_rule_execution.get_active_execution_version",
        return_value=version,
    ), patch(
        "app.services.data_quality_rule_execution.get_execution_field",
        return_value=field,
    ), patch(
        "app.services.data_quality_rule_execution.get_execution_source_object",
        return_value=source_object,
    ), patch(
        "app.services.data_quality_rule_execution.get_execution_data_source",
        return_value=source,
    ), patch(
        "app.services.data_quality_rule_execution.validate_execution_eligibility",
    ), patch(
        "app.services.data_quality_rule_execution.validate_source_object_eligibility",
    ):
        with pytest.raises(ValueError, match="PostgreSQL"):
            prepare_rule_execution(
                db,
                project_id=project_id,
                rule_id=rule.id,
                actor_user_id=uuid.uuid4(),
            )


def test_cross_project_source_is_rejected_during_preparation():
    db = MagicMock()
    project_id = uuid.uuid4()
    other_project_id = uuid.uuid4()

    rule = SimpleNamespace(
        id=uuid.uuid4(),
        status="active",
        active_version_id=uuid.uuid4(),
        data_field_id=uuid.uuid4(),
    )
    version = SimpleNamespace(
        id=rule.active_version_id,
        rule_id=rule.id,
        status="approved",
        rule_type="range",
        quality_dimension="validity",
    )
    field = SimpleNamespace(
        id=rule.data_field_id,
        normalized_data_type="decimal",
    )
    source_object = SimpleNamespace(
        id=uuid.uuid4(),
        object_type="table",
        schema_name="public",
        object_name="locations",
    )
    source = SimpleNamespace(
        id=uuid.uuid4(),
        project_id=other_project_id,
        is_active=True,
        source_type="postgresql",
        connection_mode="database",
    )

    with patch(
        "app.services.data_quality_rule_execution.get_authorized_execution_rule",
        return_value=rule,
    ), patch(
        "app.services.data_quality_rule_execution.get_active_execution_version",
        return_value=version,
    ), patch(
        "app.services.data_quality_rule_execution.get_execution_field",
        return_value=field,
    ), patch(
        "app.services.data_quality_rule_execution.get_execution_source_object",
        return_value=source_object,
    ), patch(
        "app.services.data_quality_rule_execution.get_execution_data_source",
        return_value=source,
    ), patch(
        "app.services.data_quality_rule_execution.validate_execution_eligibility",
    ), patch(
        "app.services.data_quality_rule_execution.validate_source_eligibility",
    ), patch(
        "app.services.data_quality_rule_execution.validate_source_object_eligibility",
    ):
        with pytest.raises(ValueError, match="project"):
            prepare_rule_execution(
                db,
                project_id=project_id,
                rule_id=rule.id,
                actor_user_id=uuid.uuid4(),
            )



