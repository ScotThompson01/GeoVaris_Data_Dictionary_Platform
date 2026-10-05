import type { DictionaryField } from "../lib/types";

type Props = {
  fields: DictionaryField[];
  selectedFieldId: string | null;
  onSelectField: (field: DictionaryField) => void;
};

type ObjectGroup = {
  key: string;
  name: string;
  objectType: string;
  fields: DictionaryField[];
};

type SchemaGroup = {
  key: string;
  name: string | null;
  objects: ObjectGroup[];
};

type SourceGroup = {
  key: string;
  name: string;
  sourceType: string;
  schemas: SchemaGroup[];
};

function buildExplorerTree(fields: DictionaryField[]): SourceGroup[] {
  const sources = new Map<
    string,
    {
      name: string;
      sourceType: string;
      schemas: Map<
        string,
        {
          name: string | null;
          objects: Map<string, ObjectGroup>;
        }
      >;
    }
  >();

  for (const field of fields) {
    let source = sources.get(field.data_source_id);

    if (!source) {
      source = {
        name: field.data_source_name,
        sourceType: field.source_type,
        schemas: new Map(),
      };
      sources.set(field.data_source_id, source);
    }

    const schemaKey = field.schema_name ?? "__no_schema__";
    let schema = source.schemas.get(schemaKey);

    if (!schema) {
      schema = {
        name: field.schema_name,
        objects: new Map(),
      };
      source.schemas.set(schemaKey, schema);
    }

    let object = schema.objects.get(field.source_object_id);

    if (!object) {
      object = {
        key: field.source_object_id,
        name: field.object_name,
        objectType: field.object_type,
        fields: [],
      };
      schema.objects.set(field.source_object_id, object);
    }

    object.fields.push(field);
  }

  return Array.from(sources.entries()).map(([sourceId, source]) => ({
    key: sourceId,
    name: source.name,
    sourceType: source.sourceType,
    schemas: Array.from(source.schemas.entries()).map(
      ([schemaKey, schema]) => ({
        key: `${sourceId}:${schemaKey}`,
        name: schema.name,
        objects: Array.from(schema.objects.values()),
      }),
    ),
  }));
}

export default function DictionaryExplorer({
  fields,
  selectedFieldId,
  onSelectField,
}: Props) {
  const sources = buildExplorerTree(fields);

  if (sources.length === 0) {
    return (
      <section className="card dictionary-explorer">
        <h2>Data Explorer</h2>
        <p className="field-subtext">
          Select a project with discovered fields to browse its data.
        </p>
      </section>
    );
  }

  return (
    <section className="card dictionary-explorer">
      <div className="dictionary-explorer-heading">
        <div>
          <h2>Data Explorer</h2>
          <p>Browse sources, objects, and fields.</p>
        </div>
      </div>

      <nav className="dictionary-tree" aria-label="Data Dictionary Explorer">
        {sources.map((source) => (
          <details key={source.key} className="tree-source">
            <summary>
              <span className="tree-node-name">{source.name}</span>
              <span className="tree-node-meta">{source.sourceType}</span>
            </summary>

            <div className="tree-children">
              {source.schemas.map((schema) =>
                schema.name ? (
                  <details key={schema.key} className="tree-schema">
                    <summary>
                      <span className="tree-node-name">{schema.name}</span>
                      <span className="tree-node-meta">Schema</span>
                    </summary>

                    <div className="tree-children">
                      {schema.objects.map((object) => (
                        <ObjectNode
                          key={object.key}
                          object={object}
                          selectedFieldId={selectedFieldId}
                          onSelectField={onSelectField}
                        />
                      ))}
                    </div>
                  </details>
                ) : (
                  <div key={schema.key}>
                    {schema.objects.map((object) => (
                      <ObjectNode
                        key={object.key}
                        object={object}
                        selectedFieldId={selectedFieldId}
                        onSelectField={onSelectField}
                      />
                    ))}
                  </div>
                ),
              )}
            </div>
          </details>
        ))}
      </nav>
    </section>
  );
}

function ObjectNode({
  object,
  selectedFieldId,
  onSelectField,
}: {
  object: ObjectGroup;
  selectedFieldId: string | null;
  onSelectField: (field: DictionaryField) => void;
}) {
  return (
    <details className="tree-object">
      <summary>
        <span className="tree-node-name">{object.name}</span>
        <span className="tree-node-meta">{object.objectType}</span>
      </summary>

      <div className="tree-fields">
        {object.fields
          .slice()
          .sort((a, b) => a.ordinal_position - b.ordinal_position)
          .map((field) => {
            const selected = field.field_id === selectedFieldId;

            return (
              <button
                key={field.field_id}
                type="button"
                className={`tree-field${selected ? " selected" : ""}`}
                onClick={() => onSelectField(field)}
                aria-current={selected ? "true" : undefined}
              >
                <span>{field.field_name}</span>
                <span className="tree-field-type">
                  {field.normalized_data_type ??
                    field.native_data_type ??
                    "Unknown"}
                </span>
              </button>
            );
          })}
      </div>
    </details>
  );
}
