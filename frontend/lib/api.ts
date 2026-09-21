
import type {
  Client,
  DictionaryField,
  FieldGovernanceMetadata,
  FieldGovernanceUpdate,
  ProfilingResult,
  Project,
} from "./types";

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(
      (await response.text()) ||
        `Request failed: ${response.status}`,
    );
  }

  return response.json() as Promise<T>;
}

export async function getClients(): Promise<Client[]> {
  return parse<Client[]>(
    await fetch("/api/data/clients", {
      credentials: "same-origin",
      cache: "no-store",
    }),
  );
}

export async function getProjects(): Promise<Project[]> {
  return parse<Project[]>(
    await fetch("/api/data/projects", {
      credentials: "same-origin",
      cache: "no-store",
    }),
  );
}

export async function createClient(
  body: {
    name: string;
    description?: string;
  },
): Promise<Client> {
  return parse<Client>(
    await fetch("/api/data/clients", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }),
  );
}

export async function createProject(
  body: {
    client_id: string;
    name: string;
    description?: string;
    status?: string;
  },
): Promise<Project> {
  return parse<Project>(
    await fetch("/api/data/projects", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ...body,
        status: body.status ?? "active",
      }),
    }),
  );
}

export async function getDictionaryFields(
  projectId: string,
  search?: string,
): Promise<DictionaryField[]> {
  const params = new URLSearchParams({
    project_id: projectId,
  });

  if (search?.trim()) {
    params.set("search", search.trim());
  }

  return parse<DictionaryField[]>(
    await fetch(`/api/data/dictionary?${params.toString()}`, {
      credentials: "same-origin",
      cache: "no-store",
    }),
  );
}

export async function getFieldGovernance(
  dataFieldId: string,
): Promise<FieldGovernanceMetadata> {
  return parse<FieldGovernanceMetadata>(
    await fetch(
      `/api/data/field-governance/${encodeURIComponent(dataFieldId)}`,
      {
        credentials: "same-origin",
        cache: "no-store",
      },
    ),
  );
}

export async function saveFieldGovernance(
  dataFieldId: string,
  payload: FieldGovernanceUpdate,
): Promise<FieldGovernanceMetadata> {
  return parse<FieldGovernanceMetadata>(
    await fetch(
      `/api/data/field-governance/${encodeURIComponent(dataFieldId)}`,
      {
        method: "PUT",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      },
    ),
  );
}

export async function getFieldProfilingResults(
  dataFieldId: string,
): Promise<ProfilingResult[]> {
  const params = new URLSearchParams({
    data_field_id: dataFieldId,
  });

  return parse<ProfilingResult[]>(
    await fetch(
      `/api/data/profiling-results?${params.toString()}`,
      {
        credentials: "same-origin",
        cache: "no-store",
      },
    ),
  );
}