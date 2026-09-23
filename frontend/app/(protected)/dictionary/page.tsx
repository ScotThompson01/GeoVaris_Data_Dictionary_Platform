"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import FieldGovernancePanel from "../../../components/FieldGovernancePanel";
import FieldProfilingPanel from "../../../components/FieldProfilingPanel";
import { getDictionaryFields, getProjects } from "../../../lib/api";
import type { DictionaryFilters } from "../../../lib/api";
import type { DictionaryField, Project } from "../../../lib/types";

export default function DictionaryPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");

  const [fields, setFields] = useState<DictionaryField[]>([]);
  const [filterOptionsFields, setFilterOptionsFields] = useState<DictionaryField[]>([]);
  const [search, setSearch] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [department, setDepartment] = useState("");
  const [dataOwner, setDataOwner] = useState("");
  const [cdeStatus, setCdeStatus] = useState("");

  const [loadingProjects, setLoadingProjects] = useState(true);
  const [loadingFields, setLoadingFields] = useState(false);
  const [message, setMessage] = useState("");
  const [projectMessage, setProjectMessage] = useState("");

  const [selectedField, setSelectedField] =
    useState<DictionaryField | null>(null);

  // Prevent an older request from replacing results for a newer selection.
  const requestId = useRef(0);

  useEffect(() => {
    let active = true;

    async function loadProjects() {
      try {
        const results = await getProjects();

        if (active) {
          setProjects(results);
        }
      } catch {
        if (active) {
          setProjects([]);
          setProjectMessage("Unable to load projects.");
        }
      } finally {
        if (active) {
          setLoadingProjects(false);
        }
      }
    }

    void loadProjects();

    return () => {
      active = false;
      requestId.current += 1;
    };
  }, []);

  async function loadDictionary(
    projectId: string,
    searchValue = "",
    filters: DictionaryFilters = {
      dataSourceId: sourceId,
      department,
      dataOwner,
      isCde: cdeStatus === "" ? undefined : cdeStatus === "true",
    },
    captureFilterOptions = false,
  ) {
    const currentRequestId = ++requestId.current;

    setLoadingFields(true);
    setMessage("");
    setFields([]);
    setSelectedField(null);

    try {
      const results = await getDictionaryFields(
        projectId,
        searchValue,
        filters,
      );

      if (currentRequestId === requestId.current) {
        setFields(results);
        if (captureFilterOptions) {
          setFilterOptionsFields(results);
        }
      }
    } catch {
      if (currentRequestId === requestId.current) {
        setFields([]);
        setMessage("Unable to load the Data Dictionary.");
      }
    } finally {
      if (currentRequestId === requestId.current) {
        setLoadingFields(false);
      }
    }
  }

  function changeProject(projectId: string) {
    // Invalidate any dictionary request from the previous project.
    requestId.current += 1;

    setSelectedProjectId(projectId);
    setSearch("");
    setSourceId("");
    setDepartment("");
    setDataOwner("");
    setCdeStatus("");
    setFields([]);
    setFilterOptionsFields([]);
    setSelectedField(null);
    setMessage("");
    setLoadingFields(false);

    if (projectId) {
      void loadDictionary(projectId, "", {}, true);
    }
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (selectedProjectId) {
      void loadDictionary(selectedProjectId, search);
    }
  }

  function clearSearch() {
    setSearch("");
    setSourceId("");
    setDepartment("");
    setDataOwner("");
    setCdeStatus("");

    if (selectedProjectId) {
      void loadDictionary(selectedProjectId, "", {});
    }
  }

  const hasSelectedProject = selectedProjectId !== "";

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
        <div>
          <label htmlFor="dictionary-project">
            Project
          </label>

          <select
            id="dictionary-project"
            value={selectedProjectId}
            onChange={(event) =>
              changeProject(event.target.value)
            }
            disabled={loadingProjects}
          >
            <option value="">
              {loadingProjects
                ? "Loading projects..."
                : "Select a project"}
            </option>

            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>

          {projectMessage && (
            <p className="notice">{projectMessage}</p>
          )}
        </div>

        <form
          className="dictionary-search"
          onSubmit={submitSearch}
        >
          <input
            type="search"
            placeholder="Search field names..."
            aria-label="Search field names"
            value={search}
            onChange={(event) =>
              setSearch(event.target.value)
            }
            disabled={!hasSelectedProject || loadingFields}
          />

          <label htmlFor="dictionary-cde">CDE Status</label>
          <select
            id="dictionary-cde"
            value={cdeStatus}
            onChange={(event) => setCdeStatus(event.target.value)}
            disabled={!hasSelectedProject || loadingFields}
          >
            <option value="">All fields</option>
            <option value="true">CDE only</option>
            <option value="false">Non-CDE only</option>
          </select>
          <label htmlFor="dictionary-owner">Data Owner</label>
          <select
            id="dictionary-owner"
            value={dataOwner}
            onChange={(event) => setDataOwner(event.target.value)}
            disabled={!hasSelectedProject || loadingFields}
          >
            <option value="">All data owners</option>
            {Array.from(
              new Set(
                filterOptionsFields
                  .map((field) => field.data_owner)
                  .filter((value): value is string => Boolean(value)),
              ),
            )
              .sort()
              .map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
          </select>
          <label htmlFor="dictionary-department">Department</label>
          <select
            id="dictionary-department"
            value={department}
            onChange={(event) => setDepartment(event.target.value)}
            disabled={!hasSelectedProject || loadingFields}
          >
            <option value="">All departments</option>
            {Array.from(
              new Set(
                filterOptionsFields
                  .map((field) => field.department)
                  .filter((value): value is string => Boolean(value)),
              ),
            )
              .sort()
              .map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
          </select>
          <label htmlFor="dictionary-source">Source</label>
          <select
            id="dictionary-source"
            value={sourceId}
            onChange={(event) => setSourceId(event.target.value)}
            disabled={!hasSelectedProject || loadingFields}
          >
            <option value="">All sources</option>
            {Array.from(
              new Map(
                filterOptionsFields.map((field) => [
                  field.data_source_id,
                  field.data_source_name,
                ]),
              ),
            ).map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={!hasSelectedProject || loadingFields}
          >
            Search
          </button>

          <button
            type="button"
            className="secondary-button"
            onClick={clearSearch}
            disabled={!hasSelectedProject || loadingFields}
          >
            Clear
          </button>
        </form>

        <div className="dictionary-count">
          {loadingFields
            ? "Loading..."
            : `${fields.length} field${
                fields.length === 1 ? "" : "s"
              }`}
        </div>
      </section>

      <div className="dictionary-layout">
        <section className="card dictionary-table-card">
          {!hasSelectedProject && !loadingProjects && (
            <div className="empty-state">
              <h3>Select a project</h3>
              <p>
                Choose a project to view its discovered fields.
              </p>
            </div>
          )}

          {message && (
            <p className="notice">
              {message}
            </p>
          )}

          {hasSelectedProject &&
            !loadingFields &&
            !message &&
            fields.length === 0 && (
              <div className="empty-state">
                <h3>No dictionary fields found</h3>

                <p>
                  Discover a supported data source for this
                  project or adjust your search.
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
                      selectedField?.field_id === field.field_id;

                    return (
                      <tr
                        key={field.field_id}
                        className={
                          selected ? "selected-row" : undefined
                        }
                      >
                        <td>
                          <div className="field-name">
                            {field.field_name}
                          </div>

                          <div className="field-subtext">
                            Position {field.ordinal_position}
                          </div>
                        </td>

                        <td>
                          <span className="type-badge">
                            {field.normalized_data_type ??
                              field.native_data_type ??
                              "Unknown"}
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
                              : "-"}
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
          <div key={selectedField.field_id}>
            <FieldProfilingPanel
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