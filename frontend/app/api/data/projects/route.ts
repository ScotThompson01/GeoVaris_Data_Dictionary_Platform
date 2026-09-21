
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

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch("/api/v1/projects", {
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

  if (!backendResponse.ok) {
    return errorResponse("Project data could not be retrieved.", 502);
  }

  let projects: unknown;

  try {
    projects = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  if (!Array.isArray(projects)) {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(projects, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
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

  if (
    typeof body !== "object" ||
    body === null ||
    Array.isArray(body)
  ) {
    return errorResponse("A client ID and project name are required.", 400);
  }

  const input = body as Record<string, unknown>;

  if (
    typeof input.client_id !== "string" ||
    !input.client_id.trim() ||
    typeof input.name !== "string" ||
    !input.name.trim()
  ) {
    return errorResponse("A client ID and project name are required.", 400);
  }

  if (
    input.description !== undefined &&
    typeof input.description !== "string"
  ) {
    return errorResponse("Project description must be text.", 400);
  }

  if (
    input.status !== undefined &&
    typeof input.status !== "string"
  ) {
    return errorResponse("Project status must be text.", 400);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch("/api/v1/projects", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        client_id: input.client_id.trim(),
        name: input.name.trim(),
        ...(input.description !== undefined
          ? { description: input.description }
          : {}),
        status: input.status ?? "active",
      }),
    });
  } catch {
    return errorResponse("Data service is unavailable.", 503);
  }

  if (backendResponse.status === 401) {
    return errorResponse("Authentication required.", 401);
  }

  if (backendResponse.status === 400 || backendResponse.status === 422) {
    return errorResponse("Invalid project details.", 400);
  }

  if (backendResponse.status === 403) {
    return errorResponse("Permission denied.", 403);
  }

  if (!backendResponse.ok) {
    return errorResponse("Project could not be created.", 502);
  }

  let project: unknown;

  try {
    project = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(project, {
    status: 201,
    headers: {
      "Cache-Control": "no-store",
    },
  });
}