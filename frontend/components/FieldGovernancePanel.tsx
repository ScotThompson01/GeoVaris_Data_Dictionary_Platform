"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  getFieldGovernance,
  saveFieldGovernance,
} from "../lib/api";

import type {
  DictionaryField,
  FieldGovernanceMetadata,
} from "../lib/types";


type Props = {
  field: DictionaryField;
  onClose: () => void;
};


export default function FieldGovernancePanel({
  field,
  onClose,
}: Props) {
  const [form, setForm] = useState<FieldGovernanceMetadata | null>(
    null,
  );

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    async function load() {
      setLoading(true);
      setMessage("");

      try {
        const result = await getFieldGovernance(
          field.field_id,
        );

        setForm(result);
      } catch {
        setMessage(
          "Unable to load governance metadata.",
        );
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [field.field_id]);

  function update(
    key: keyof FieldGovernanceMetadata,
    value: string | boolean,
  ) {
    setForm((current) => {
      if (!current) {
        return current;
      }

      return {
        ...current,
        [key]: value,
      };
    });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();

    if (!form) {
      return;
    }

    setSaving(true);
    setMessage("");

    try {
      const result = await saveFieldGovernance(
        field.field_id,
        {
          business_name: form.business_name,
          business_definition: form.business_definition,
          department: form.department,
          data_owner: form.data_owner,
          data_steward: form.data_steward,
          business_process: form.business_process,
          system_of_record: form.system_of_record,
          is_cde: form.is_cde,
          classification: form.classification,
          approval_status: form.approval_status,
          notes: form.notes,
        },
      );

      setForm(result);
      setMessage("Governance metadata saved.");
    } catch {
      setMessage(
        "Unable to save governance metadata.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <aside className="governance-panel">
      <div className="governance-panel-header">
        <div>
          <p className="eyebrow">
            GOVERNANCE METADATA
          </p>

          <h2>{field.field_name}</h2>

          <p>
            {field.data_source_name}
            {" · "}
            {field.object_name}
          </p>
        </div>

        <button
          type="button"
          className="secondary-button"
          onClick={onClose}
        >
          Close
        </button>
      </div>

      {loading && (
        <p>Loading governance metadata...</p>
      )}

      {message && (
        <p className="notice">
          {message}
        </p>
      )}

      {!loading && form && (
        <form
          className="governance-form"
          onSubmit={submit}
        >
          <label>
            Business Name
            <input
              value={form.business_name ?? ""}
              onChange={(event) =>
                update(
                  "business_name",
                  event.target.value,
                )
              }
            />
          </label>

          <label>
            Business Definition
            <textarea
              rows={4}
              value={form.business_definition ?? ""}
              onChange={(event) =>
                update(
                  "business_definition",
                  event.target.value,
                )
              }
            />
          </label>

          <div className="form-grid">
            <label>
              Department
              <input
                value={form.department ?? ""}
                onChange={(event) =>
                  update(
                    "department",
                    event.target.value,
                  )
                }
              />
            </label>

            <label>
              Classification
              <input
                value={form.classification ?? ""}
                onChange={(event) =>
                  update(
                    "classification",
                    event.target.value,
                  )
                }
              />
            </label>

            <label>
              Data Owner
              <input
                value={form.data_owner ?? ""}
                onChange={(event) =>
                  update(
                    "data_owner",
                    event.target.value,
                  )
                }
              />
            </label>

            <label>
              Data Steward
              <input
                value={form.data_steward ?? ""}
                onChange={(event) =>
                  update(
                    "data_steward",
                    event.target.value,
                  )
                }
              />
            </label>

            <label>
              Business Process
              <input
                value={form.business_process ?? ""}
                onChange={(event) =>
                  update(
                    "business_process",
                    event.target.value,
                  )
                }
              />
            </label>

            <label>
              System of Record
              <input
                value={form.system_of_record ?? ""}
                onChange={(event) =>
                  update(
                    "system_of_record",
                    event.target.value,
                  )
                }
              />
            </label>
          </div>

          <label>
            Approval Status
            <select
              value={form.approval_status}
              onChange={(event) =>
                update(
                  "approval_status",
                  event.target.value,
                )
              }
            >
              <option value="draft">
                Draft
              </option>
              <option value="steward_review">
                Steward Review
              </option>
              <option value="owner_approval">
                Owner Approval
              </option>
              <option value="published">
                Published
              </option>
            </select>
          </label>

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={form.is_cde}
              onChange={(event) =>
                update(
                  "is_cde",
                  event.target.checked,
                )
              }
            />

            Critical Data Element
          </label>

          <label>
            Notes
            <textarea
              rows={3}
              value={form.notes ?? ""}
              onChange={(event) =>
                update(
                  "notes",
                  event.target.value,
                )
              }
            />
          </label>

          <button
            type="submit"
            disabled={saving}
          >
            {saving
              ? "Saving..."
              : "Save Governance Metadata"}
          </button>
        </form>
      )}
    </aside>
  );
}