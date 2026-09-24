"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  createDataSource,
  discoverDatabase,
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
  const [databaseName, setDatabaseName] = useState("");
  const [databaseType, setDatabaseType] = useState<
    "postgresql" | "sql_server"
  >("postgresql");
  const [registeringDatabase, setRegisteringDatabase] = useState(false);
  const [databaseRegistrationMessage, setDatabaseRegistrationMessage] =
    useState("");
  const [discoverySourceId, setDiscoverySourceId] = useState("");
  const [databaseHost, setDatabaseHost] = useState("");
  const [databasePort, setDatabasePort] = useState("");
  const [databaseNameForDiscovery, setDatabaseNameForDiscovery] = useState("");
  const [databaseUsername, setDatabaseUsername] = useState("");
  const [databasePassword, setDatabasePassword] = useState("");
  const [runningDatabaseDiscovery, setRunningDatabaseDiscovery] = useState(false);
  const [databaseDiscoveryMessage, setDatabaseDiscoveryMessage] = useState("");

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

    setDiscoverySourceId("");
    setDatabaseHost("");
    setDatabasePort("");
    setDatabaseNameForDiscovery("");
    setDatabaseUsername("");
    setDatabasePassword("");
    setDatabaseDiscoveryMessage("");
    setDatabaseRegistrationMessage("");

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
          setSources(results);
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

  const fileSources = sources.filter(
    (source) =>
      source.connection_mode === "file" &&
      (source.source_type === "csv" || source.source_type === "excel"),
  );

  const databaseSources = sources.filter(
    (source) =>
      source.connection_mode === "database" &&
      (source.source_type === "postgresql" ||
        source.source_type === "sql_server"),
  );

  async function registerDatabase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const name = databaseName.trim();
    const projectId = selectedProjectId;

    if (!projectId || !name || registeringDatabase) return;

    setRegisteringDatabase(true);
    setDatabaseRegistrationMessage("");

    try {
      await createDataSource({
        project_id: projectId,
        name,
        source_type: databaseType,
      });

      setDatabaseName("");
      setDatabaseRegistrationMessage(`Registered database source: ${name}.`);

      try {
        const updatedSources = await getDataSources(projectId);
        setSources(updatedSources);
      } catch {
        setDatabaseRegistrationMessage(
          `Registered database source: ${name}. Refresh the page to update the list.`,
        );
      }
    } catch {
      setDatabaseRegistrationMessage(
        "Unable to register the database source. Check its name and try again.",
      );
    } finally {
      setRegisteringDatabase(false);
    }
  }

  function selectDiscoverySource(source: DataSource) {
    setDiscoverySourceId(source.id);
    setDatabaseHost("");
    setDatabasePort(source.source_type === "postgresql" ? "5432" : "1433");
    setDatabaseNameForDiscovery("");
    setDatabaseUsername("");
    setDatabasePassword("");
    setDatabaseDiscoveryMessage("");
  }

  async function runDatabaseDiscovery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const source = databaseSources.find(
      (item) => item.id === discoverySourceId,
    );
    const host = databaseHost.trim();
    const database = databaseNameForDiscovery.trim();
    const username = databaseUsername.trim();
    const port = Number(databasePort);

    if (
      !source ||
      !source.is_active ||
      !host ||
      !database ||
      !username ||
      !Number.isInteger(port) ||
      port < 1 ||
      port > 65535 ||
      runningDatabaseDiscovery
    ) {
      return;
    }

    setRunningDatabaseDiscovery(true);
    setDatabaseDiscoveryMessage("");

    try {
      const scan = await discoverDatabase({
        data_source_id: source.id,
        source_type: source.source_type as "postgresql" | "sql_server",
        host,
        port,
        database,
        username,
        ...(databasePassword ? { password: databasePassword } : {}),
      });

      setDatabaseDiscoveryMessage(
        `Discovery for ${source.name}: ${scan.status}. Scan ID: ${scan.id}`,
      );
    } catch {
      setDatabaseDiscoveryMessage(
        `Discovery for ${source.name} could not be completed. Check the connection details and source permissions.`,
      );
    } finally {
      setDatabasePassword("");
      setRunningDatabaseDiscovery(false);
    }
  }

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
            ) : fileSources.length === 0 && !message ? (
              <p>No CSV or Excel data sources are registered for this project.</p>
            ) : (
              fileSources.length > 0 && (
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
                      {fileSources.map((source) => (
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

      <section className="card">
        <h3>Database Sources</h3>
        <p>
          Registered PostgreSQL and SQL Server sources for the selected project.
          Connection details will be supplied when discovery is started.
        </p>

        <form className="form" onSubmit={registerDatabase}>
          <label htmlFor="database-source-name">
            Source name
            <input
              id="database-source-name"
              type="text"
              value={databaseName}
              onChange={(event) => setDatabaseName(event.target.value)}
              maxLength={200}
              required
              disabled={!selectedProjectId || registeringDatabase}
              placeholder="e.g. Reporting database"
            />
          </label>

          <label htmlFor="database-source-type">
            Database type
            <select
              id="database-source-type"
              value={databaseType}
              onChange={(event) =>
                setDatabaseType(
                  event.target.value as "postgresql" | "sql_server",
                )
              }
              disabled={!selectedProjectId || registeringDatabase}
            >
              <option value="postgresql">PostgreSQL</option>
              <option value="sql_server">SQL Server</option>
            </select>
          </label>

          <button
            type="submit"
            disabled={
              !selectedProjectId ||
              !databaseName.trim() ||
              registeringDatabase
            }
          >
            {registeringDatabase ? "Registering..." : "Register Database Source"}
          </button>

          {databaseRegistrationMessage && (
            <p className="notice" role="status">
              {databaseRegistrationMessage}
            </p>
          )}
        </form>

        {!selectedProjectId ? (
          <p>Select a project above to view its database sources.</p>
        ) : loadingSources ? (
          <p>Loading database sources...</p>
        ) : databaseSources.length === 0 ? (
          <p>No PostgreSQL or SQL Server sources are registered for this project.</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Database Type</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {databaseSources.map((source) => (
                  <tr key={source.id}>
                    <td>{source.name}</td>
                    <td>
                      {source.source_type === "postgresql"
                        ? "PostgreSQL"
                        : "SQL Server"}
                    </td>
                    <td>{source.is_active ? "Active" : "Inactive"}</td>
                    <td>
                      <button
                        type="button"
                        className="edit-governance-button"
                        disabled={!source.is_active || runningDatabaseDiscovery}
                        onClick={() => selectDiscoverySource(source)}
                      >
                        Discover
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {discoverySourceId && (
          <form className="form" onSubmit={runDatabaseDiscovery}>
            <h4>
              Discover metadata:{" "}
              {databaseSources.find((item) => item.id === discoverySourceId)?.name}
            </h4>
            <p className="notice">
              Enter connection details for this discovery request. Use an account
              with read-only metadata access. Connection details are not saved
              with the registered source.
            </p>

            <label htmlFor="database-discovery-host">
              Host
              <input
                id="database-discovery-host"
                value={databaseHost}
                onChange={(event) => setDatabaseHost(event.target.value)}
                maxLength={255}
                required
                disabled={runningDatabaseDiscovery}
              />
            </label>

            <label htmlFor="database-discovery-port">
              Port
              <input
                id="database-discovery-port"
                type="number"
                min={1}
                max={65535}
                step={1}
                value={databasePort}
                onChange={(event) => setDatabasePort(event.target.value)}
                required
                disabled={runningDatabaseDiscovery}
              />
            </label>

            <label htmlFor="database-discovery-name">
              Database name
              <input
                id="database-discovery-name"
                value={databaseNameForDiscovery}
                onChange={(event) =>
                  setDatabaseNameForDiscovery(event.target.value)
                }
                maxLength={255}
                required
                disabled={runningDatabaseDiscovery}
              />
            </label>

            <label htmlFor="database-discovery-username">
              Username
              <input
                id="database-discovery-username"
                value={databaseUsername}
                onChange={(event) => setDatabaseUsername(event.target.value)}
                maxLength={255}
                required
                disabled={runningDatabaseDiscovery}
                autoComplete="off"
              />
            </label>

            <label htmlFor="database-discovery-password">
              Password (if required)
              <input
                id="database-discovery-password"
                type="password"
                value={databasePassword}
                onChange={(event) => setDatabasePassword(event.target.value)}
                disabled={runningDatabaseDiscovery}
                autoComplete="off"
              />
            </label>

            <button type="submit" disabled={runningDatabaseDiscovery}>
              {runningDatabaseDiscovery
                ? "Discovering..."
                : "Start Metadata Discovery"}
            </button>

            {databaseDiscoveryMessage && (
              <p className="notice" role="status">
                {databaseDiscoveryMessage}
              </p>
            )}
          </form>
        )}
      </section>
    </>
  );
}
