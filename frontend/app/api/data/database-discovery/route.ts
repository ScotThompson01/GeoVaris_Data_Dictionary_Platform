import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "../../../../lib/backend";

export const runtime = "nodejs";

const SESSION_COOKIE = "geovaris_session";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function errorResponse(message: string, status: number) {
  return NextResponse.json(
    { error: message },
    {
      status,
      headers: { "Cache-Control": "no-store" },
    },
  );
}

function validText(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.trim().length > 0 &&
    value.length <= 255 &&
    !value.includes("\0")
  );
}

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
    return errorResponse("Invalid database discovery request.", 400);
  }

  const input = body as Record<string, unknown>;

  if (
    typeof input.data_source_id !== "string" ||
    !UUID_PATTERN.test(input.data_source_id) ||
    (input.source_type !== "postgresql" &&
      input.source_type !== "sql_server") ||
    !validText(input.host) ||
    !validText(input.database) ||
    !validText(input.username) ||
    typeof input.port !== "number" ||
    !Number.isInteger(input.port) ||
    input.port < 1 ||
    input.port > 65535 ||
    (input.password !== undefined &&
      (typeof input.password !== "string" ||
        input.password.length > 4096))
  ) {
    return errorResponse("Invalid database discovery request.", 400);
  }

  const endpoint =
    input.source_type === "postgresql" ? "postgresql" : "sqlserver";

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(
      `/api/v1/discovery/${endpoint}`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          data_source_id: input.data_source_id,
          host: input.host,
          port: input.port,
          database: input.database,
          username: input.username,
          ...(input.password === undefined
            ? {}
            : { password: input.password }),
        }),
      },
    );
  } catch {
    return errorResponse("Data service is unavailable.", 503);
  }

  if (backendResponse.status === 401) {
    return errorResponse("Authentication required.", 401);
  }

  if (backendResponse.status === 403) {
    return errorResponse("Permission denied.", 403);
  }

  if (backendResponse.status === 404) {
    return errorResponse("Data source not found.", 404);
  }

  if (backendResponse.status === 400 || backendResponse.status === 422) {
    return errorResponse(
      "Unable to connect or discover metadata. Check the connection details and data source.",
      400,
    );
  }

  if (!backendResponse.ok) {
    return errorResponse("Database discovery failed.", 502);
  }

  let scan: unknown;

  try {
    scan = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  if (
    typeof scan !== "object" ||
    scan === null ||
    Array.isArray(scan) ||
    typeof (scan as Record<string, unknown>).id !== "string" ||
    typeof (scan as Record<string, unknown>).status !== "string"
  ) {
    return errorResponse("Invalid data service response.", 502);
  }

  const result = scan as Record<string, unknown>;

  return NextResponse.json(
    { id: result.id, status: result.status },
    {
      status: 201,
      headers: { "Cache-Control": "no-store" },
    },
  );
}
