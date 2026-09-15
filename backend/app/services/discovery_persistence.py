from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base import DiscoveredObject
from app.models.data_field import DataField
from app.models.data_source import DataSource
from app.models.source_object import SourceObject


def persist_discovered_object(
    db: Session,
    data_source: DataSource,
    discovered: DiscoveredObject,
) -> SourceObject:
    """
    Create or update one discovered source object and its fields.

    Only connector-discovered technical metadata is persisted here.
    Human-maintained governance metadata is intentionally untouched.
    """

    source_object = db.scalar(
        select(SourceObject).where(
            SourceObject.data_source_id == data_source.id,
            SourceObject.object_name == discovered.object_name,
            SourceObject.schema_name == discovered.schema_name,
        )
    )

    if source_object is None:
        source_object = SourceObject(
            data_source_id=data_source.id,
            object_type=discovered.object_type,
            object_name=discovered.object_name,
            schema_name=discovered.schema_name,
            native_name=discovered.native_name,
            row_count=discovered.row_count,
        )

        db.add(source_object)
        db.flush()

    else:
        source_object.object_type = discovered.object_type
        source_object.schema_name = discovered.schema_name
        source_object.native_name = discovered.native_name
        source_object.row_count = discovered.row_count

    existing_fields = {
        field.field_name: field
        for field in db.scalars(
            select(DataField).where(
                DataField.source_object_id == source_object.id
            )
        ).all()
    }

    for discovered_field in discovered.fields:
        data_field = existing_fields.get(
            discovered_field.field_name
        )

        if data_field is None:
            data_field = DataField(
                source_object_id=source_object.id,
                field_name=discovered_field.field_name,
                ordinal_position=discovered_field.ordinal_position,
            )

            db.add(data_field)

        data_field.ordinal_position = (
            discovered_field.ordinal_position
        )

        data_field.native_data_type = (
            discovered_field.native_data_type
        )

        data_field.normalized_data_type = (
            discovered_field.normalized_data_type
        )

        data_field.max_length = (
            discovered_field.max_length
        )

        data_field.numeric_precision = (
            discovered_field.numeric_precision
        )

        data_field.numeric_scale = (
            discovered_field.numeric_scale
        )

        data_field.is_nullable = (
            discovered_field.is_nullable
        )

        data_field.is_primary_key = (
            discovered_field.is_primary_key
        )

        data_field.is_unique = (
            discovered_field.is_unique
        )

        data_field.default_value = (
            discovered_field.default_value
        )

        data_field.source_comment = (
            discovered_field.source_comment
        )

    db.flush()

    return source_object