import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "../../../../../../lib/backend";

export const runtime = "nodejs";

const SESSION_COOKIE = "geovaris_session";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type RouteContext = {
  params: Promise<{ projectId: string }>;
};

function errorResponse(message: string, status: number) {
  return NextResponse.json(
    { error: message },
    {
      status,
      headers: { "Cache-Control": "no-store" },
    },
  );
}

async function getProjectId(context: RouteContext) {
  const { projectId } = await context.params;
  return projectId.trim();
}

function mapBackendError(status: number) {
  if (status === 401) {
    return errorResponse("Authentication required.", 401);
  }
  if (status === 403) {
    return errorResponse("Permission denied.", 403);
  }
  if (status === 404) {
    return errorResponse("Project not found.", 404);
  }
  if (status === 400 || status === 422) {
    return errorResponse("Invalid project settings.", 400);
  }
  return errorResponse("Project settings service failed.", 502);
}

export async function GET(
  request: NextRequest,
  context: RouteContext,
) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) {
    return errorResponse("Authentication required.", 401);
  }

  const projectId = await getProjectId(context);
  if (!UUID_PATTERN.test(projectId)) {
    return errorResponse("A valid project ID is required.", 400);
  }

  let response: Response;
  try {
    response = await backendFetch(
      `/api/v1/projects/${encodeURIComponent(projectId)}/settings`,
      {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
      },
    );
  } catch {
    return errorResponse("Data service is unavailable.", 503);
  }

  if (!response.ok) {
    return mapBackendError(response.status);
  }

  try {
    return NextResponse.json(await response.json(), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }
}

export async function PATCH(
  request: NextRequest,
  context: RouteContext,
) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) {
    return errorResponse("Authentication required.", 401);
  }

  const origin = request.headers.get("origin");
  const allowedOrigin = process.env.APP_ORIGIN;
  if (!allowedOrigin || origin !== allowedOrigin) {
    return errorResponse("Request origin is not allowed.", 403);
  }

  const projectId = await getProjectId(context);
  if (!UUID_PATTERN.test(projectId)) {
    return errorResponse("A valid project ID is required.", 400);
  }

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return errorResponse("Invalid JSON request body.", 400);
  }

  if (
    typeof payload !== "object" ||
    payload === null ||
    Array.isArray(payload) ||
    typeof (payload as Record<string, unknown>)
      .allow_steward_self_approval !== "boolean" ||
    Object.keys(payload).length !== 1 ||
    !Object.hasOwn(payload, "allow_steward_self_approval")
  ) {
    return errorResponse(
      "A boolean allow_steward_self_approval setting is required.",
      400,
    );
  }

  let response: Response;
  try {
    response = await backendFetch(
      `/api/v1/projects/${encodeURIComponent(projectId)}/settings`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      },
    );
  } catch {
    return errorResponse("Data service is unavailable.", 503);
  }

  if (!response.ok) {
    return mapBackendError(response.status);
  }

  try {
    return NextResponse.json(await response.json(), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }
}
