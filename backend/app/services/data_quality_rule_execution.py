"""Eligibility checks for Data Quality rule execution.

These checks do not connect to client data sources.
Project authorization and source validation are separate requirements.
"""

from app.models.data_field import DataField
from app.models.data_quality_rule import DataQualityRule
from app.models.data_quality_rule_version import DataQualityRuleVersion


def validate_execution_eligibility(
    rule: DataQualityRule,
    version: DataQualityRuleVersion,
    field: DataField,
) -> None:
    """Reject rules that are not eligible for numeric range execution."""
    if rule.status != "active":
        raise ValueError("Rule must be active before execution.")

    if version.rule_id != rule.id:
        raise ValueError("Rule version must belong to its parent rule.")

    if rule.active_version_id != version.id:
        raise ValueError("Rule must reference its active version.")

    if version.status != "approved":
        raise ValueError("Rule version must be approved before execution.")

    if version.rule_type != "range":
        raise ValueError("Only range rules are supported for execution.")

    if version.quality_dimension != "validity":
        raise ValueError("Range execution requires the validity dimension.")

    if field.normalized_data_type not in {"integer", "decimal"}:
        raise ValueError("Range execution requires a numeric field.")


def validate_source_eligibility(source) -> None:
    """Require an active PostgreSQL database source for rule execution."""
    if not source.is_active:
        raise ValueError("Data source must be active before execution.")
    if source.source_type != "postgresql":
        raise ValueError("Only PostgreSQL sources support rule execution.")
    if source.connection_mode != "database":
        raise ValueError("Rule execution requires a database connection.")


def validate_source_object_eligibility(source_object) -> None:
    """Require a PostgreSQL table or view with complete identifying metadata."""
    if source_object.object_type not in {"table", "view"}:
        raise ValueError("Rule execution requires a table or view.")

    if not isinstance(source_object.schema_name, str) or not source_object.schema_name.strip():
        raise ValueError("Rule execution requires a schema name.")

    if not isinstance(source_object.object_name, str) or not source_object.object_name.strip():
        raise ValueError("Rule execution requires an object name.")


def get_authorized_execution_rule(
    db,
    *,
    project_id,
    rule_id,
    actor_user_id,
):
    """Retrieve a rule only after authorization and project-scoped lookup."""
    from fastapi import HTTPException
    from sqlalchemy import select

    from app.models.data_source import DataSource
    from app.models.source_object import SourceObject
    from app.services.project_authorization import require_dq_rule_executor

    require_dq_rule_executor(
        db,
        user_id=actor_user_id,
        project_id=project_id,
    )

    rule = db.scalar(
        select(DataQualityRule)
        .join(DataField, DataQualityRule.data_field_id == DataField.id)
        .join(SourceObject, DataField.source_object_id == SourceObject.id)
        .join(DataSource, SourceObject.data_source_id == DataSource.id)
        .where(
            DataQualityRule.id == rule_id,
            DataSource.project_id == project_id,
        )
    )

    if rule is None:
        raise HTTPException(
            status_code=404,
            detail="Data Quality rule not found.",
        )

    return rule


def get_active_execution_version(db, *, rule: DataQualityRule) -> DataQualityRuleVersion:
    """Retrieve only the active version belonging to the authorized parent rule."""
    from fastapi import HTTPException
    from sqlalchemy import select

    if rule.active_version_id is None:
        raise HTTPException(
            status_code=409,
            detail="Data Quality rule has no active version.",
        )

    version = db.scalar(
        select(DataQualityRuleVersion).where(
            DataQualityRuleVersion.id == rule.active_version_id,
            DataQualityRuleVersion.rule_id == rule.id,
        )
    )

    if version is None:
        raise HTTPException(
            status_code=409,
            detail="Active Data Quality rule version not found.",
        )

    return version


def get_execution_field(db, *, rule: DataQualityRule) -> DataField:
    """Retrieve the exact field referenced by a Data Quality rule."""
    from fastapi import HTTPException
    from sqlalchemy import select

    field = db.scalar(
        select(DataField).where(
            DataField.id == rule.data_field_id,
        )
    )

    if field is None:
        raise HTTPException(
            status_code=409,
            detail="Data Quality rule field not found.",
        )

    return field


def get_execution_source_object(db, *, field: DataField):
    """Retrieve the exact source object referenced by the execution field."""
    from fastapi import HTTPException
    from sqlalchemy import select

    from app.models.source_object import SourceObject

    source_object = db.scalar(
        select(SourceObject).where(
            SourceObject.id == field.source_object_id,
        )
    )

    if source_object is None:
        raise HTTPException(
            status_code=409,
            detail="Data Quality rule source object not found.",
        )

    return source_object


def get_execution_data_source(db, *, source_object):
    """Retrieve the exact data source referenced by the source object."""
    from fastapi import HTTPException
    from sqlalchemy import select

    from app.models.data_source import DataSource

    source = db.scalar(
        select(DataSource).where(
            DataSource.id == source_object.data_source_id,
        )
    )

    if source is None:
        raise HTTPException(
            status_code=409,
            detail="Data Quality rule data source not found.",
        )

    return source


def prepare_rule_execution(
    db,
    *,
    project_id,
    rule_id,
    actor_user_id,
):
    """Validate execution metadata without querying client data."""
    from app.models.data_quality_rule import DataQualityRule

    rule = get_authorized_execution_rule(
        db,
        project_id=project_id,
        rule_id=rule_id,
        actor_user_id=actor_user_id,
    )

    if rule.status != "active":
        raise ValueError("Rule must be active before execution.")

    version = get_active_execution_version(db, rule=rule)
    field = get_execution_field(db, rule=rule)
    source_object = get_execution_source_object(db, field=field)
    source = get_execution_data_source(db, source_object=source_object)

    if source.project_id != project_id:
        raise ValueError("Data Quality rule source must belong to the authorized project.")

    validate_execution_eligibility(rule, version, field)
    validate_source_eligibility(source)
    validate_source_object_eligibility(source_object)

    return {
        "rule": rule,
        "version": version,
        "field": field,
        "source_object": source_object,
        "source": source,
    }


def measure_prepared_range_rule(
    prepared,
    *,
    config,
    password=None,
    connector=None,
    statement_timeout_ms=30000,
):
    """Measure an already-authorized and validated numeric range rule.

    Callers must obtain prepared metadata through prepare_rule_execution().
    This function does not perform authorization or persist results.
    """
    from app.connectors.database.postgresql_connector import PostgreSQLConnector

    if not 1 <= statement_timeout_ms <= 300000:
        raise ValueError("Statement timeout must be between 1 and 300000 ms.")

    if connector is None:
        connector = PostgreSQLConnector()

    version = prepared["version"]
    field = prepared["field"]
    source_object = prepared["source_object"]

    return connector.measure_range(
        config=config,
        schema_name=source_object.schema_name,
        object_name=source_object.object_name,
        field_name=field.field_name,
        min_value=version.min_value,
        max_value=version.max_value,
        null_allowed=version.null_allowed,
        password=password,
        statement_timeout_ms=statement_timeout_ms,
    )


def record_successful_execution(
    db,
    *,
    prepared,
    project_id,
    actor_user_id,
    measurement,
    started_at,
    completed_at,
):
    """Stage a successful aggregate execution record without committing."""
    from app.models.data_quality_rule_execution import DataQualityRuleExecution

    rule = prepared["rule"]
    version = prepared["version"]

    if version.rule_id != rule.id:
        raise ValueError("Execution version does not belong to the rule.")

    total = measurement.total_count
    passing = measurement.passing_count
    violations = measurement.violation_count

    if any(type(value) is not int or value < 0 for value in (total, passing, violations)):
        raise ValueError("Execution counts must be nonnegative integers.")

    if total != passing + violations:
        raise ValueError("Execution counts must balance.")

    if started_at.tzinfo is None or completed_at.tzinfo is None:
        raise ValueError("Execution timestamps must include a timezone.")

    if completed_at < started_at:
        raise ValueError("Execution completion cannot precede its start.")

    execution = DataQualityRuleExecution(
        project_id=project_id,
        actor_user_id=actor_user_id,
        rule_id=rule.id,
        version_id=version.id,
        status="succeeded",
        total_count=total,
        passing_count=passing,
        violation_count=violations,
        error_code=None,
        started_at=started_at,
        completed_at=completed_at,
    )

    db.add(execution)
    db.flush()
    return execution


def execute_range_rule(
    db,
    *,
    project_id,
    rule_id,
    actor_user_id,
    config,
    password=None,
    connector=None,
    statement_timeout_ms=30000,
):
    """Execute an authorized range rule and stage aggregate history.

    The caller owns the database transaction and must commit or roll back.
    Source credentials are used at runtime and are never persisted.
    """
    from datetime import datetime, timezone

    prepared = prepare_rule_execution(
        db,
        project_id=project_id,
        rule_id=rule_id,
        actor_user_id=actor_user_id,
    )

    started_at = datetime.now(timezone.utc)

    measurement = measure_prepared_range_rule(
        prepared,
        config=config,
        password=password,
        connector=connector,
        statement_timeout_ms=statement_timeout_ms,
    )

    completed_at = datetime.now(timezone.utc)

    return record_successful_execution(
        db,
        prepared=prepared,
        project_id=project_id,
        actor_user_id=actor_user_id,
        measurement=measurement,
        started_at=started_at,
        completed_at=completed_at,
    )
