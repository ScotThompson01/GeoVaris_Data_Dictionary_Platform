"""Offline authorization tests for basic PostgreSQL profiling requests."""

from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.data_field import DataField
from app.models.data_source import DataSource
from app.models.scan import Scan
from app.models.source_object import SourceObject
from app.services.postgresql_profiling_request_authorization import (
    authorize_postgresql_basic_profiling_request,
)


def make_context(
    *,
    scan_type="basic_profile",
    scan_status="running",
    source_type="postgresql",
    source_active=True,
    scan_source_matches=True,
    object_source_matches=True,
):
    user_id = uuid4()
    source_id = uuid4()
    scan_id = uuid4()
    field_id = uuid4()
    object_id = uuid4()

    other_source_id = uuid4()

    source = SimpleNamespace(
        id=source_id,
        project_id=uuid4(),
        source_type=source_type,
        is_active=source_active,
    )
    scan = SimpleNamespace(
        id=scan_id,
        data_source_id=(
            source_id if scan_source_matches else other_source_id
        ),
        scan_type=scan_type,
        status=scan_status,
    )
    field = SimpleNamespace(
        id=field_id,
        source_object_id=object_id,
        field_name="customer_id",
    )
    source_object = SimpleNamespace(
        id=object_id,
        data_source_id=(
            source_id if object_source_matches else other_source_id
        ),
        schema_name="public",
        object_name="synthetic_customers",
    )

    values = {
        (Scan, scan_id): scan,
        (DataSource, source_id): source,
        (DataField, field_id): field,
        (SourceObject, object_id): source_object,
    }

    db = Mock()
    db.get.side_effect = lambda model, identity: values.get(
        (model, identity)
    )

    return SimpleNamespace(
        db=db,
        user_id=user_id,
        source_id=source_id,
        scan_id=scan_id,
        field_id=field_id,
        source=source,
        scan=scan,
        field=field,
        source_object=source_object,
    )


def authorize(context):
    return authorize_postgresql_basic_profiling_request(
        db=context.db,
        user_id=context.user_id,
        data_source_id=context.source_id,
        scan_id=context.scan_id,
        data_field_id=context.field_id,
    )


def test_disabled_gate_rejects_before_database_reads():
    context = make_context()

    with patch(
        "app.services.postgresql_profiling_request_authorization.settings"
    ) as settings:
        settings.postgresql_profiling_execution_enabled = False

        with pytest.raises(ValueError, match="disabled"):
            authorize(context)

    context.db.get.assert_not_called()


def test_missing_project_access_is_rejected():
    context = make_context()

    with patch(
        "app.services.postgresql_profiling_request_authorization.settings"
    ) as settings, patch(
        "app.services.postgresql_profiling_request_authorization.require_data_source_access",
        side_effect=HTTPException(
            status_code=404,
            detail="Data source not found.",
        ),
    ):
        settings.postgresql_profiling_execution_enabled = True

        with pytest.raises(HTTPException) as error:
            authorize(context)

    assert error.value.status_code == 404


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"source_type": "csv"}, "PostgreSQL"),
        ({"source_active": False}, "inactive"),
        ({"scan_source_matches": False}, "source"),
        ({"scan_type": "metadata"}, "basic"),
        ({"scan_type": "approved_sample"}, "basic"),
        ({"scan_type": "full_profile"}, "basic"),
        ({"scan_status": "pending"}, "running"),
        ({"scan_status": "completed"}, "running"),
        ({"object_source_matches": False}, "source"),
    ],
)
def test_invalid_request_relationships_are_rejected(
    override,
    message,
):
    context = make_context(**override)

    with patch(
        "app.services.postgresql_profiling_request_authorization.settings"
    ) as settings, patch(
        "app.services.postgresql_profiling_request_authorization.require_data_source_access",
        return_value=context.source,
    ):
        settings.postgresql_profiling_execution_enabled = True

        with pytest.raises(ValueError, match=message):
            authorize(context)


def test_valid_metadata_request_passes_without_source_connection():
    context = make_context()

    with patch(
        "app.services.postgresql_profiling_request_authorization.settings"
    ) as settings, patch(
        "app.services.postgresql_profiling_request_authorization.require_data_source_access",
        return_value=context.source,
    ) as require_access:
        settings.postgresql_profiling_execution_enabled = True

        result = authorize(context)

    assert result.source is context.source
    assert result.scan is context.scan
    assert result.field is context.field
    assert result.source_object is context.source_object

    require_access.assert_called_once_with(
        context.db,
        user_id=context.user_id,
        data_source_id=context.source_id,
    )

    context.db.commit.assert_not_called()
    context.db.flush.assert_not_called()
@pytest.mark.parametrize(
    ("missing_model", "message"),
    [
        (Scan, "scan not found"),
        (DataField, "field not found"),
        (SourceObject, "object not found"),
    ],
)
def test_missing_metadata_resource_is_rejected(
    missing_model,
    message,
):
    context = make_context()

    original_get = context.db.get.side_effect
    context.db.get.side_effect = (
        lambda model, identity: (
            None
            if model is missing_model
            else original_get(model, identity)
        )
    )

    with patch(
        "app.services.postgresql_profiling_request_authorization.settings"
    ) as settings, patch(
        "app.services.postgresql_profiling_request_authorization.require_data_source_access",
        return_value=context.source,
    ):
        settings.postgresql_profiling_execution_enabled = True

        with pytest.raises(ValueError, match=message):
            authorize(context)

    context.db.commit.assert_not_called()
    context.db.flush.assert_not_called()


def test_missing_data_source_access_is_rejected_before_metadata_reads():
    context = make_context()

    with patch(
        "app.services.postgresql_profiling_request_authorization.settings"
    ) as settings, patch(
        "app.services.postgresql_profiling_request_authorization.require_data_source_access",
        side_effect=HTTPException(
            status_code=404,
            detail="Data source not found.",
        ),
    ):
        settings.postgresql_profiling_execution_enabled = True

        with pytest.raises(HTTPException) as error:
            authorize(context)

    assert error.value.status_code == 404
    context.db.get.assert_not_called()


def test_authorized_source_identity_must_match_requested_source():
    context = make_context()

    mismatched_source = SimpleNamespace(
        id=uuid4(),
        project_id=context.source.project_id,
        source_type="postgresql",
        is_active=True,
    )

    with patch(
        "app.services.postgresql_profiling_request_authorization.settings"
    ) as settings, patch(
        "app.services.postgresql_profiling_request_authorization.require_data_source_access",
        return_value=mismatched_source,
    ):
        settings.postgresql_profiling_execution_enabled = True

        with pytest.raises(ValueError, match="source identity"):
            authorize(context)

    context.db.commit.assert_not_called()
    context.db.flush.assert_not_called()
