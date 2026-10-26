"use client";

import { useEffect, useState } from "react";

import { useInstallationAdmin } from "../../../components/InstallationAdminContext";
import { getProjects } from "../../../lib/api";
import type { Project } from "../../../lib/types";

type ProjectSettings = {
  project_id: string;
  allow_steward_self_approval: boolean;
};

export default function AdministrationPage() {
  const isInstallationAdmin = useInstallationAdmin();

  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [settings, setSettings] = useState<ProjectSettings | null>(null);
  const [draftValue, setDraftValue] = useState(false);
  const [isLoadingProjects, setIsLoadingProjects] = useState(true);
  const [isLoadingSettings, setIsLoadingSettings] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;

    getProjects()
      .then((items) => {
        if (!active) return;
        setProjects(items);
        setSelectedProjectId(items[0]?.id ?? "");
      })
      .catch(() => {
        if (active) {
          setError("Projects could not be loaded. Please try again.");
        }
      })
      .finally(() => {
        if (active) setIsLoadingProjects(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedProjectId) {
      setSettings(null);
      return;
    }

    const controller = new AbortController();

    async function loadSettings() {
      setIsLoadingSettings(true);
      setError("");
      setNotice("");
      setSettings(null);

      try {
        const response = await fetch(
          `/api/data/projects/${encodeURIComponent(selectedProjectId)}/settings`,
          {
            credentials: "same-origin",
            cache: "no-store",
            signal: controller.signal,
          },
        );

        if (!response.ok) {
          if (response.status === 403) {
            throw new Error(
              "You do not have permission to view this project's settings.",
            );
          }
          if (response.status === 404) {
            throw new Error("The project or its settings could not be found.");
          }
          if (response.status === 401) {
            throw new Error("Your session has expired. Please sign in again.");
          }
          throw new Error("Project settings could not be loaded.");
        }

        const result = (await response.json()) as ProjectSettings;

        if (
          result.project_id !== selectedProjectId ||
          typeof result.allow_steward_self_approval !== "boolean"
        ) {
          throw new Error("The settings service returned invalid data.");
        }

        setSettings(result);
        setDraftValue(result.allow_steward_self_approval);
      } catch (cause) {
        if (cause instanceof Error && cause.name === "AbortError") return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Project settings could not be loaded.",
        );
      } finally {
        if (!controller.signal.aborted) setIsLoadingSettings(false);
      }
    }

    void loadSettings();

    return () => {
      controller.abort();
      setIsLoadingSettings(false);
    };
  }, [selectedProjectId]);

  async function saveSettings() {
    if (
      !isInstallationAdmin ||
      !settings ||
      isSaving ||
      draftValue === settings.allow_steward_self_approval
    ) {
      return;
    }

    setIsSaving(true);
    setError("");
    setNotice("");

    try {
      const response = await fetch(
        `/api/data/projects/${encodeURIComponent(selectedProjectId)}/settings`,
        {
          method: "PATCH",
          credentials: "same-origin",
          cache: "no-store",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            allow_steward_self_approval: draftValue,
          }),
        },
      );

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error("Your session has expired. Please sign in again.");
        }
        if (response.status === 403) {
          throw new Error(
            "Permission denied. Only an installation administrator can change this setting.",
          );
        }
        if (response.status === 404) {
          throw new Error("The project could not be found.");
        }
        throw new Error("The setting could not be saved. Please try again.");
      }

      const updated = (await response.json()) as ProjectSettings;

      if (
        updated.project_id !== selectedProjectId ||
        typeof updated.allow_steward_self_approval !== "boolean"
      ) {
        throw new Error("The settings service returned invalid data.");
      }

      setSettings(updated);
      setDraftValue(updated.allow_steward_self_approval);
      setNotice("Project settings saved successfully.");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "The setting could not be saved.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  const hasChanges =
    settings !== null &&
    draftValue !== settings.allow_steward_self_approval;

  return (
    <>
      <header>
        <div>
          <h1>Administration</h1>
          <p>Manage project-level governance settings.</p>
        </div>
      </header>

      <section className="card">
        <h3>Project settings</h3>
        <p>
          Select a project to review its governance controls. Settings apply
          only to the selected project.
        </p>

        {isLoadingProjects ? (
          <p role="status">Loading projects...</p>
        ) : projects.length === 0 ? (
          <p>No accessible projects were found.</p>
        ) : (
          <>
            <label htmlFor="administration-project">Project</label>
            <select
              id="administration-project"
              value={selectedProjectId}
              onChange={(event) => setSelectedProjectId(event.target.value)}
              disabled={isLoadingSettings || isSaving}
            >
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name} ({project.status})
                </option>
              ))}
            </select>

            {isLoadingSettings && (
              <p role="status">Loading project settings...</p>
            )}

            {settings && !isLoadingSettings && (
              <div>
                <h3>Data Steward self-approval</h3>
                <p>
                  When enabled, eligible Data Stewards may approve their own
                  changes only where the approval workflow explicitly permits
                  it. The approval service must enforce those eligibility
                  rules independently.
                </p>

                <label htmlFor="self-approval-setting">
                  <input
                    id="self-approval-setting"
                    type="checkbox"
                    checked={draftValue}
                    disabled={!isInstallationAdmin || isSaving}
                    onChange={(event) => {
                      setDraftValue(event.target.checked);
                      setNotice("");
                      setError("");
                    }}
                  />{" "}
                  Allow Data Stewards to approve their own changes
                </label>

                {!isInstallationAdmin && (
                  <p>
                    Read-only: installation administrator permission is
                    required to change this setting.
                  </p>
                )}

                {isInstallationAdmin && (
                  <div>
                    <button
                      type="button"
                      onClick={() => {
                        if (settings) {
                          setDraftValue(
                            settings.allow_steward_self_approval,
                          );
                          setError("");
                          setNotice("");
                        }
                      }}
                      disabled={!hasChanges || isSaving}
                    >
                      Cancel
                    </button>{" "}
                    <button
                      type="button"
                      onClick={saveSettings}
                      disabled={!hasChanges || isSaving}
                    >
                      {isSaving ? "Saving..." : "Save settings"}
                    </button>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {error && <p role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
      </section>
    </>
  );
}
