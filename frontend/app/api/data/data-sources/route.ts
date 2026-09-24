import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "../../../../lib/backend";

export const runtime = "nodejs";

const SESSION_COOKIE = "geovaris_session";

function errorResponse(message: string, status: number) {
  return NextResponse.json(
    { error: message },
    {
      status,
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;

  if (!token) {
    return errorResponse("Authentication required.", 401);
  }

  const projectId = request.nextUrl.searchParams.get("project_id");
  const params = new URLSearchParams();

  if (projectId) {
    params.set("project_id", projectId);
  }

  const query = params.toString();
  const backendPath = `/api/v1/data-sources${query ? `?${query}` : ""}`;

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(backendPath, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    return errorResponse("Data service is unavailable.", 503);
  }

  if (backendResponse.status === 401) {
    return errorResponse("Authentication required.", 401);
  }

  if (backendResponse.status === 403) {
    return errorResponse("Permission denied.", 403);
  }

  if (backendResponse.status === 422) {
    return errorResponse("Invalid project ID.", 400);
  }

  if (!backendResponse.ok) {
    return errorResponse("Data sources could not be retrieved.", 502);
  }

  let dataSources: unknown;

  try {
    dataSources = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  if (!Array.isArray(dataSources)) {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(dataSources, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;

  if (!token) {
    return errorResponse("Authentication required.", 401);
  }

  const origin = request.headers.get("origin");
  const allowedOrigin = process.env.APP_ORIGIN;

  if (!allowedOrigin || origin !== allowedOrigin) {
    return errorResponse("Request origin is not allowed.", 403);
  }

  let body: unknown;

  try {
    body = await request.json();
  } catch {
    return errorResponse("Invalid JSON request body.", 400);
  }

  if (typeof body !== "object" || body === null || Array.isArray(body)) {
    return errorResponse("Invalid data source request.", 400);
  }

  const input = body as Record<string, unknown>;

  if (
    typeof input.project_id !== "string" ||
    !UUID_PATTERN.test(input.project_id) ||
    typeof input.name !== "string" ||
    input.name.trim().length < 1 ||
    input.name.trim().length > 200 ||
    (input.source_type !== "sql_server" &&
      input.source_type !== "postgresql") ||
    input.connection_mode !== "database"
  ) {
    return errorResponse("Invalid database data source request.", 400);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch("/api/v1/data-sources", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        project_id: input.project_id,
        name: input.name.trim(),
        source_type: input.source_type,
        connection_mode: "database",
      }),
    });
  } catch {
    return errorResponse("Data service is unavailable.", 503);
  }

  if (backendResponse.status === 401) {
    return errorResponse("Authentication required.", 401);
  }

  if (backendResponse.status === 403 || backendResponse.status === 404) {
    return errorResponse("Project not found or access denied.", 403);
  }

  if (backendResponse.status === 409) {
    return errorResponse(
      "A data source with this name already exists in the project.",
      409,
    );
  }

  if (backendResponse.status === 400 || backendResponse.status === 422) {
    return errorResponse("Invalid database data source request.", 400);
  }

  if (!backendResponse.ok) {
    return errorResponse("Data source could not be created.", 502);
  }

  let dataSource: unknown;

  try {
    dataSource = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  if (
    typeof dataSource !== "object" ||
    dataSource === null ||
    Array.isArray(dataSource) ||
    typeof (dataSource as Record<string, unknown>).id !== "string" ||
    typeof (dataSource as Record<string, unknown>).project_id !== "string"
  ) {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(dataSource, {
    status: 201,
    headers: { "Cache-Control": "no-store" },
  });
}
