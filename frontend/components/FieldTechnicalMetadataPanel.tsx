import type { DictionaryField } from "../lib/types";

type Props = {
  field: DictionaryField;
};

function displayValue(value: string | number | null): string {
  return value === null || value === "" ? "Not available" : String(value);
}

function displayBoolean(value: boolean | null): string {
  return value === null ? "Unknown" : value ? "Yes" : "No";
}

export default function FieldTechnicalMetadataPanel({ field }: Props) {
  return (
    <section className="card">
      <h2>Technical Metadata</h2>

      <p>
        Discovered technical details for <strong>{field.field_name}</strong>.
        These values come from source discovery and are separate from
        business governance metadata.
      </p>

      <dl>
        <dt>Source</dt>
        <dd>{field.data_source_name}</dd>

        <dt>Source type</dt>
        <dd>{field.source_type}</dd>

        <dt>Schema</dt>
        <dd>{displayValue(field.schema_name)}</dd>

        <dt>Object</dt>
        <dd>{field.object_name}</dd>

        <dt>Object type</dt>
        <dd>{field.object_type}</dd>

        <dt>Native object name</dt>
        <dd>{displayValue(field.native_name)}</dd>

        <dt>Object description</dt>
        <dd>{displayValue(field.object_description)}</dd>

        <dt>Object row count</dt>
        <dd>{displayValue(field.object_row_count)}</dd>

        <dt>Field position</dt>
        <dd>{field.ordinal_position}</dd>

        <dt>Native data type</dt>
        <dd>{displayValue(field.native_data_type)}</dd>

        <dt>Normalized data type</dt>
        <dd>{displayValue(field.normalized_data_type)}</dd>

        <dt>Maximum length</dt>
        <dd>{displayValue(field.max_length)}</dd>

        <dt>Numeric precision</dt>
        <dd>{displayValue(field.numeric_precision)}</dd>

        <dt>Numeric scale</dt>
        <dd>{displayValue(field.numeric_scale)}</dd>

        <dt>Nullable</dt>
        <dd>{displayBoolean(field.is_nullable)}</dd>

        <dt>Primary key</dt>
        <dd>{field.is_primary_key ? "Yes" : "No"}</dd>

        <dt>Unique</dt>
        <dd>{field.is_unique ? "Yes" : "No"}</dd>

        <dt>Default value</dt>
        <dd>{displayValue(field.default_value)}</dd>

        <dt>Source comment</dt>
        <dd>{displayValue(field.source_comment)}</dd>
      </dl>
    </section>
  );
}
