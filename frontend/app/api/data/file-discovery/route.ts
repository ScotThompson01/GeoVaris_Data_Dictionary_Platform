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
    return errorResponse("Invalid discovery request.", 400);
  }

  const input = body as Record<string, unknown>;

  if (
    typeof input.data_source_id !== "string" ||
    !UUID_PATTERN.test(input.data_source_id) ||
    (input.source_type !== "csv" && input.source_type !== "excel") ||
    typeof input.file_name !== "string"
  ) {
    return errorResponse("Invalid discovery request.", 400);
  }

  const fileName = input.file_name;

  if (
    fileName.length < 1 ||
    fileName.length > 255 ||
    fileName === "." ||
    fileName === ".." ||
    fileName.includes("/") ||
    fileName.includes("\\") ||
    fileName.includes("\0") ||
    !fileName.toLowerCase().endsWith(
      input.source_type === "csv" ? ".csv" : ".xlsx",
    )
  ) {
    return errorResponse("Enter a valid CSV or Excel file name.", 400);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(
      `/api/v1/discovery/${input.source_type}`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          data_source_id: input.data_source_id,
          file_name: fileName,
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
    return errorResponse("File not found in the configured data directory.", 404);
  }

  if (backendResponse.status === 400 || backendResponse.status === 422) {
    return errorResponse("Invalid discovery request or data source.", 400);
  }

  if (!backendResponse.ok) {
    return errorResponse("File discovery failed.", 502);
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

  return NextResponse.json(scan, {
    status: 201,
    headers: { "Cache-Control": "no-store" },
  });
}
