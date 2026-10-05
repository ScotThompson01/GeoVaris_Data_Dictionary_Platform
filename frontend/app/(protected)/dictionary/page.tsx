"use client";

import Link from "next/link";

import { useEffect, useRef, useState } from "react";

import DictionaryExplorer from "../../../components/DictionaryExplorer";
import FieldGovernancePanel from "../../../components/FieldGovernancePanel";
import FieldProfilingPanel from "../../../components/FieldProfilingPanel";
import FieldTechnicalMetadataPanel from "../../../components/FieldTechnicalMetadataPanel";
import { getDictionaryFields, getProjects } from "../../../lib/api";
import type { DictionaryField, Project } from "../../../lib/types";

export default function DictionaryPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");

  const [fields, setFields] = useState<DictionaryField[]>([]);

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

  async function loadDictionary(projectId: string) {
    const currentRequestId = ++requestId.current;

    setLoadingFields(true);
    setMessage("");
    setFields([]);
    setSelectedField(null);

    try {
      const results = await getDictionaryFields(projectId, "", {});

      if (currentRequestId === requestId.current) {
        setFields(results);
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
    setFields([]);
    setSelectedField(null);
    setMessage("");
    setLoadingFields(false);

    if (projectId) {
      void loadDictionary(projectId);
    }
  }
  const hasSelectedProject = selectedProjectId !== "";

  return (
    <>
      <header>
        <div>
          <h1>Data Dictionary</h1>

          <p>
            Browse discovered data sources, objects, and fields, then
            review technical metadata and governance information.
          </p>
          <nav className="dictionary-view-nav" aria-label="Data Dictionary views">
            <Link className="dictionary-view-link active" href="/dictionary">
              Explorer
            </Link>
            <Link className="dictionary-view-link" href="/dictionary/all-fields">
              All Fields
            </Link>
          </nav>
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


      </section>

      <div className="dictionary-explorer-layout">
        <div className="dictionary-explorer-status">
          {!hasSelectedProject && !loadingProjects && (
            <div className="empty-state">
              <h3>Select a project</h3>
              <p>Choose a project to browse its discovered data.</p>
            </div>
          )}

          {loadingFields && (
            <p className="notice">Loading Data Dictionary...</p>
          )}

          {message && <p className="notice">{message}</p>}

          {hasSelectedProject &&
            !loadingFields &&
            !message &&
            fields.length === 0 && (
              <div className="empty-state">
                <h3>No dictionary fields found</h3>
                <p>
                  Discover a supported data source for this project to
                  populate the Data Dictionary.
                </p>
              </div>
            )}
        </div>

        <DictionaryExplorer
          fields={fields}
          selectedFieldId={selectedField?.field_id ?? null}
          onSelectField={setSelectedField}
        />
        {selectedField && (
          <div key={selectedField.field_id}>
            <FieldTechnicalMetadataPanel field={selectedField} />

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
