
import type {
  Client,
  DataSource,
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

export type DictionaryFilters = {
  dataSourceId?: string;
  department?: string;
  dataOwner?: string;
  isCde?: boolean;
};
export async function getDictionaryFields(
  projectId: string,
  search?: string,
  filters?: DictionaryFilters,
): Promise<DictionaryField[]> {
  const params = new URLSearchParams({
    project_id: projectId,
  });

  if (search?.trim()) {
    params.set("search", search.trim());
  }

  if (filters?.dataSourceId) {
    params.set("data_source_id", filters.dataSourceId);
  }
  if (filters?.department) {
    params.set("department", filters.department);
  }
  if (filters?.dataOwner) {
    params.set("data_owner", filters.dataOwner);
  }
  if (filters?.isCde !== undefined) {
    params.set("is_cde", String(filters.isCde));
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

export async function getDataSources(
  projectId: string,
): Promise<DataSource[]> {
  const params = new URLSearchParams({
    project_id: projectId,
  });

  return parse<DataSource[]>(
    await fetch(`/api/data/data-sources?${params.toString()}`, {
      credentials: "same-origin",
      cache: "no-store",
    }),
  );
}

export type FileDiscoveryScan = {
  id: string;
  data_source_id: string;
  scan_type: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  connector_version: string | null;
  created_at: string;
};

export async function discoverFile(
  dataSourceId: string,
  sourceType: "csv" | "excel",
  fileName: string,
): Promise<FileDiscoveryScan> {
  return parse<FileDiscoveryScan>(
    await fetch("/api/data/file-discovery", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        data_source_id: dataSourceId,
        source_type: sourceType,
        file_name: fileName,
      }),
    }),
  );
}

export async function createDataSource(
  body: {
    project_id: string;
    name: string;
    source_type: "sql_server" | "postgresql";
  },
): Promise<DataSource> {
  return parse<DataSource>(
    await fetch("/api/data/data-sources", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ...body,
        connection_mode: "database",
      }),
    }),
  );
}

export type DatabaseDiscoveryRequest = {
  data_source_id: string;
  source_type: "postgresql" | "sql_server";
  host: string;
  port: number;
  database: string;
  username: string;
  password?: string;
};

export async function discoverDatabase(
  request: DatabaseDiscoveryRequest,
): Promise<FileDiscoveryScan> {
  return parse<FileDiscoveryScan>(
    await fetch("/api/data/database-discovery", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    }),
  );
}
