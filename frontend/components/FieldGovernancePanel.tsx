"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  getFieldGovernance,
  getGovernanceAssignments,
  getGovernanceDepartments,
  getGovernancePeople,
  saveFieldGovernance,
} from "../lib/api";

import type {
  DictionaryField,
  FieldGovernanceMetadata,
  GovernanceAssignment,
  GovernanceDepartment,
  GovernancePerson,
} from "../lib/types";


type Props = {
  field: DictionaryField;
  clientId: string;
  onClose: () => void;
};


export default function FieldGovernancePanel({
  field,
  clientId,
  onClose,
}: Props) {
  const [form, setForm] = useState<FieldGovernanceMetadata | null>(
    null,
  );

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [assignments, setAssignments] = useState<GovernanceAssignment[]>([]);
  const [people, setPeople] = useState<GovernancePerson[]>([]);
  const [departments, setDepartments] = useState<GovernanceDepartment[]>([]);
  const [directoryLoading, setDirectoryLoading] = useState(false);
  const [directoryError, setDirectoryError] = useState("");
  const [stewardAssignmentChanged, setStewardAssignmentChanged] =
    useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setMessage("");

      try {
        const result = await getFieldGovernance(
          field.field_id,
        );

        setForm(result);
        setStewardAssignmentChanged(false);
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

  useEffect(() => {
    let active = true;

    setAssignments([]);
    setPeople([]);
    setDepartments([]);
    setDirectoryError("");

    if (!clientId) {
      setDirectoryLoading(false);
      return;
    }

    setDirectoryLoading(true);

    async function loadDirectory() {
      try {
        const [assignmentResults, peopleResults, departmentResults] =
          await Promise.all([
            getGovernanceAssignments(clientId),
            getGovernancePeople(clientId),
            getGovernanceDepartments(clientId),
          ]);

        if (active) {
          setAssignments(assignmentResults);
          setPeople(peopleResults);
          setDepartments(departmentResults);
        }
      } catch {
        if (active) {
          setDirectoryError("Unable to load the Governance Directory.");
        }
      } finally {
        if (active) {
          setDirectoryLoading(false);
        }
      }
    }

    void loadDirectory();

    return () => {
      active = false;
    };
  }, [clientId]);

  const today = new Date().toLocaleDateString("en-CA");

  const eligibleStewards = assignments.filter((assignment) => {
    if (assignment.client_id !== clientId ||
        assignment.role !== "data_steward" ||
        !assignment.is_active ||
        (assignment.effective_start && assignment.effective_start > today) ||
        (assignment.effective_end && assignment.effective_end < today)) {
      return false;
    }

    const person = people.find(
      (item) => item.id === assignment.person_id &&
        item.client_id === clientId && item.is_active,
    );

    const department = departments.find(
      (item) => item.id === assignment.department_id &&
        item.client_id === clientId && item.is_active,
    );

    return Boolean(person && department);
  });

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
          ...(stewardAssignmentChanged
            ? { steward_assignment_id: form.steward_assignment_id }
            : {}),
          business_process: form.business_process,
          system_of_record: form.system_of_record,
          is_cde: form.is_cde,
          classification: form.classification,
          approval_status: form.approval_status,
          notes: form.notes,
        },
      );

      setForm(result);
      setStewardAssignmentChanged(false);
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
              Assigned Data Steward
              <select
                value={form.steward_assignment_id ?? ""}
                onChange={(event) => {
                  setStewardAssignmentChanged(true);
                  setForm((current) =>
                    current
                      ? {
                          ...current,
                          steward_assignment_id:
                            event.target.value || null,
                        }
                      : current,
                  );
                }}
                disabled={saving || directoryLoading || Boolean(directoryError) || !clientId}
              >
                <option value="">No directory assignment</option>
                {form.steward_assignment_id &&
                  !eligibleStewards.some(
                    (item) => item.id === form.steward_assignment_id,
                  ) && (
                    <option value={form.steward_assignment_id} disabled>
                      Current assignment (no longer eligible or unavailable)
                    </option>
                  )}
                {eligibleStewards.map((assignment) => {
                  const person = people.find(
                    (item) => item.id === assignment.person_id,
                  );
                  const department = departments.find(
                    (item) => item.id === assignment.department_id,
                  );

                  return (
                    <option key={assignment.id} value={assignment.id}>
                      {person?.full_name ?? "Unknown person"}
                      {" ? "}
                      {department?.name ?? "Unknown department"}
                    </option>
                  );
                })}
              </select>
              {directoryLoading && (
                <span className="field-subtext">
                  Loading directory assignments...
                </span>
              )}
              {directoryError && (
                <span className="field-subtext">
                  {directoryError}
                </span>
              )}
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