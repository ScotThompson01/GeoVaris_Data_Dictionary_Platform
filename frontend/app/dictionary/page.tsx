"use client";

import { FormEvent, useEffect, useState } from "react";

import FieldGovernancePanel from "../../components/FieldGovernancePanel";
import { getDictionaryFields } from "../../lib/api";
import type { DictionaryField } from "../../lib/types";
import FieldProfilingPanel from "../../components/FieldProfilingPanel";


export default function DictionaryPage() {
  const [fields, setFields] = useState<DictionaryField[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  const [selectedField, setSelectedField] =
    useState<DictionaryField | null>(null);

  async function loadDictionary(searchValue?: string) {
    setLoading(true);
    setMessage("");

    try {
      const results = await getDictionaryFields(searchValue);
      setFields(results);
    } catch {
      setFields([]);
      setMessage("Unable to load the Data Dictionary.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDictionary();
  }, []);

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    loadDictionary(search);
  }

  function clearSearch() {
    setSearch("");
    loadDictionary();
  }

  return (
    <>
      <header>
        <div>
          <h1>Data Dictionary</h1>

          <p>
            Search discovered technical metadata and maintain
            business governance information.
          </p>
        </div>
      </header>

      <section className="card dictionary-toolbar">
        <form
          className="dictionary-search"
          onSubmit={submitSearch}
        >
          <input
            type="search"
            placeholder="Search field names..."
            value={search}
            onChange={(event) =>
              setSearch(event.target.value)
            }
          />

          <button type="submit">
            Search
          </button>

          <button
            type="button"
            className="secondary-button"
            onClick={clearSearch}
          >
            Clear
          </button>
        </form>

        <div className="dictionary-count">
          {loading
            ? "Loading..."
            : `${fields.length} field${
                fields.length === 1 ? "" : "s"
              }`}
        </div>
      </section>

      <div className="dictionary-layout">
        <section className="card dictionary-table-card">
          {message && (
            <p className="notice">
              {message}
            </p>
          )}

          {!loading &&
            !message &&
            fields.length === 0 && (
              <div className="empty-state">
                <h3>No dictionary fields found</h3>

                <p>
                  Discover a supported data source or
                  adjust your search.
                </p>
              </div>
            )}

          {fields.length > 0 && (
            <div className="table-scroll">
              <table className="dictionary-table">
                <thead>
                  <tr>
                    <th>Field</th>
                    <th>Data Type</th>
                    <th>Source</th>
                    <th>Object</th>
                    <th>Nullable</th>
                    <th>Key</th>
                    <th />
                  </tr>
                </thead>

                <tbody>
                  {fields.map((field) => {
                    const selected =
                      selectedField?.field_id
                      === field.field_id;

                    return (
                      <tr
                        key={field.field_id}
                        className={
                          selected
                            ? "selected-row"
                            : undefined
                        }
                      >
                        <td>
                          <div className="field-name">
                            {field.field_name}
                          </div>

                          <div className="field-subtext">
                            Position{" "}
                            {field.ordinal_position}
                          </div>
                        </td>

                        <td>
                          <span className="type-badge">
                            {field.normalized_data_type
                              ?? field.native_data_type
                              ?? "Unknown"}
                          </span>
                        </td>

                        <td>
                          <div>
                            {field.data_source_name}
                          </div>

                          <div className="field-subtext">
                            {field.source_type}
                          </div>
                        </td>

                        <td>
                          <div>
                            {field.object_name}
                          </div>

                          <div className="field-subtext">
                            {field.object_type}
                          </div>
                        </td>

                        <td>
                          {field.is_nullable === null
                            ? "Unknown"
                            : field.is_nullable
                              ? "Yes"
                              : "No"}
                        </td>

                        <td>
                          {field.is_primary_key
                            ? "Primary Key"
                            : field.is_unique
                              ? "Unique"
                              : "—"}
                        </td>

                        <td>
                          <button
                            type="button"
                            className="edit-governance-button"
                            onClick={() =>
                              setSelectedField(field)
                            }
                          >
                            Governance
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {selectedField && (
          <div>
            <FieldProfilingPanel
              key={selectedField.field_id}
              field={selectedField}
            />

            <FieldGovernancePanel
              field={selectedField}
              onClose={() => setSelectedField(null)}
            />
          </div>
        )}
      </div>
    </>
  );
}