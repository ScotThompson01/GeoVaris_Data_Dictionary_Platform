import type {
  Client,
  DictionaryField,
  FieldGovernanceMetadata,
  FieldGovernanceUpdate,
  ProfilingResult,
  Project,
} from "./types";

const API_URL =
  typeof window === "undefined"
    ? process.env.INTERNAL_API_URL ?? "http://api:8000"
    : process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
    await fetch(`${API_URL}/api/v1/clients`, {
      cache: "no-store",
    }),
  );
}

export async function getProjects(): Promise<Project[]> {
  return parse<Project[]>(
    await fetch(`${API_URL}/api/v1/projects`, {
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
    await fetch(`${API_URL}/api/v1/clients`, {
      method: "POST",
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
    await fetch(`${API_URL}/api/v1/projects`, {
      method: "POST",
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
    await fetch(
      `${API_URL}/api/v1/dictionary?${params.toString()}`,
      {
        cache: "no-store",
      },
    ),
  );
}

export async function getFieldGovernance(
  dataFieldId: string,
): Promise<FieldGovernanceMetadata> {
  return parse<FieldGovernanceMetadata>(
    await fetch(
      `${API_URL}/api/v1/field-governance/${dataFieldId}`,
      {
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
      `${API_URL}/api/v1/field-governance/${dataFieldId}`,
      {
        method: "PUT",
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
      `${API_URL}/api/v1/profiling-results?${params.toString()}`,
      {
        cache: "no-store",
      },
    ),
  );
}