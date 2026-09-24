"use client";

import { useEffect, useState } from "react";

import {
  discoverFile,
  getDataSources,
  getProjects,
} from "../../../lib/api";
import type { DataSource, Project } from "../../../lib/types";

export default function Page() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [sources, setSources] = useState<DataSource[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [loadingSources, setLoadingSources] = useState(false);
  const [message, setMessage] = useState("");
  const [fileNames, setFileNames] = useState<Record<string, string>>({});
  const [runningSourceId, setRunningSourceId] = useState("");
  const [discoveryMessage, setDiscoveryMessage] = useState("");

  useEffect(() => {
    let active = true;

    async function loadProjects() {
      try {
        const results = await getProjects();
        if (active) setProjects(results);
      } catch {
        if (active) setMessage("Unable to load projects.");
      } finally {
        if (active) setLoadingProjects(false);
      }
    }

    void loadProjects();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    if (!selectedProjectId) {
      setSources([]);
      setLoadingSources(false);
      return;
    }

    setSources([]);
    setMessage("");
    setLoadingSources(true);

    async function loadSources() {
      try {
        const results = await getDataSources(selectedProjectId);
        if (active) {
          setSources(
            results.filter(
              (source) =>
                source.connection_mode === "file" &&
                (source.source_type === "csv" ||
                  source.source_type === "excel"),
            ),
          );
        }
      } catch {
        if (active) setMessage("Unable to load file data sources.");
      } finally {
        if (active) setLoadingSources(false);
      }
    }

    void loadSources();
    return () => {
      active = false;
    };
  }, [selectedProjectId]);

  async function runDiscovery(source: DataSource) {
    const fileName = (fileNames[source.id] ?? "").trim();

    if (!fileName || runningSourceId) return;
    if (source.source_type !== "csv" && source.source_type !== "excel") {
      return;
    }

    setRunningSourceId(source.id);
    setDiscoveryMessage("");

    try {
      const scan = await discoverFile(
        source.id,
        source.source_type,
        fileName,
      );
      setDiscoveryMessage(
        `Discovery for ${source.name}: ${scan.status}. Scan ID: ${scan.id}`,
      );
    } catch {
      setDiscoveryMessage(
        `Discovery for ${source.name} could not be completed. Check the file name and data source.`,
      );
    } finally {
      setRunningSourceId("");
    }
  }

  return (
    <>
      <header>
        <div>
          <h1>Data Sources</h1>
          <p>
            Discover and manage metadata from client-controlled data sources.
          </p>
        </div>
      </header>

      <section className="card">
        <h3>File Discovery</h3>
        <p>
          Select a project to view its registered CSV and Excel data sources.
          Discovery reads files already available in the backend&apos;s
          configured data directory; it does not upload files from your browser.
        </p>

        <label htmlFor="file-discovery-project">Project</label>
        <select
          id="file-discovery-project"
          value={selectedProjectId}
          onChange={(event) => {
            setSelectedProjectId(event.target.value);
            setDiscoveryMessage("");
          }}
          disabled={loadingProjects || Boolean(runningSourceId)}
        >
          <option value="">
            {loadingProjects ? "Loading projects..." : "Select a project"}
          </option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>

        {message && <p className="notice" role="alert">{message}</p>}

        {selectedProjectId && (
          <>
            <h3>Registered File Sources</h3>
            {loadingSources ? (
              <p>Loading file sources...</p>
            ) : sources.length === 0 && !message ? (
              <p>No CSV or Excel data sources are registered for this project.</p>
            ) : (
              sources.length > 0 && (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>File Type</th>
                        <th>Status</th>
                        <th>Discover File</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sources.map((source) => (
                        <tr key={source.id}>
                          <td>{source.name}</td>
                          <td>
                            {source.source_type === "csv" ? "CSV" : "Excel"}
                          </td>
                          <td>{source.is_active ? "Active" : "Inactive"}</td>
                          <td>
                            <label htmlFor={`file-name-${source.id}`}>
                              File name
                            </label>
                            <input
                              id={`file-name-${source.id}`}
                              type="text"
                              placeholder={
                                source.source_type === "csv"
                                  ? "example.csv"
                                  : "example.xlsx"
                              }
                              value={fileNames[source.id] ?? ""}
                              onChange={(event) =>
                                setFileNames((current) => ({
                                  ...current,
                                  [source.id]: event.target.value,
                                }))
                              }
                              disabled={
                                !source.is_active || Boolean(runningSourceId)
                              }
                            />
                            <button
                              type="button"
                              onClick={() => void runDiscovery(source)}
                              disabled={
                                !source.is_active ||
                                !(fileNames[source.id] ?? "").trim() ||
                                Boolean(runningSourceId)
                              }
                            >
                              {runningSourceId === source.id
                                ? "Discovering..."
                                : "Discover"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}
            {discoveryMessage && (
              <p className="notice" role="status">
                {discoveryMessage}
              </p>
            )}
          </>
        )}
      </section>
    </>
  );
}
