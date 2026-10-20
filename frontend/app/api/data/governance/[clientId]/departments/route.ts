import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "../../../../../../lib/backend";

export const runtime = "nodejs";

const SESSION_COOKIE = "geovaris_session";

type RouteContext = {
  params: Promise<{ clientId: string }>;
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

export async function GET(
  request: NextRequest,
  context: RouteContext,
) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;

  if (!token) {
    return errorResponse("Authentication required.", 401);
  }

  const { clientId } = await context.params;

  const uuidPattern =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

  if (!uuidPattern.test(clientId)) {
    return errorResponse("A valid client ID is required.", 400);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(
      `/api/v1/clients/${encodeURIComponent(clientId)}/governance/departments`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
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
    return errorResponse("Client not found.", 404);
  }

  if (!backendResponse.ok) {
    return errorResponse(
      "Governance departments could not be retrieved.",
      502,
    );
  }

  let departments: unknown;

  try {
    departments = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  if (!Array.isArray(departments)) {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(departments, {
    headers: { "Cache-Control": "no-store" },
  });
}

export async function POST(
  request: NextRequest,
  context: RouteContext,
) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;

  if (!token) {
    return errorResponse("Authentication required.", 401);
  }

  const { clientId } = await context.params;

  const uuidPattern =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

  if (!uuidPattern.test(clientId)) {
    return errorResponse("A valid client ID is required.", 400);
  }

  let payload: unknown;

  try {
    payload = await request.json();
  } catch {
    return errorResponse("Invalid JSON request body.", 400);
  }

  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return errorResponse("Invalid department request.", 400);
  }

  const input = payload as Record<string, unknown>;

  if (typeof input.name !== "string") {
    return errorResponse("Department name is required.", 400);
  }

  const name = input.name.trim();

  if (!name || name.length > 200) {
    return errorResponse("Department name must contain 1 to 200 characters.", 400);
  }

  if (
    input.description !== undefined &&
    input.description !== null &&
    typeof input.description !== "string"
  ) {
    return errorResponse("Department description must be text.", 400);
  }

  const description = input.description ?? null;

  if (typeof description === "string" && description.length > 1000) {
    return errorResponse("Department description cannot exceed 1000 characters.", 400);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(
      `/api/v1/clients/${encodeURIComponent(clientId)}/governance/departments`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name, description }),
      },
    );
  } catch {
    return errorResponse("Data service is unavailable.", 503);
  }

  if (backendResponse.status === 401) {
    return errorResponse("Authentication required.", 401);
  }

  if (backendResponse.status === 403) {
    return errorResponse("Administrator permission required.", 403);
  }

  if (backendResponse.status === 404) {
    return errorResponse("Client not found or access denied.", 404);
  }

  if (backendResponse.status === 409) {
    return errorResponse("Department name already exists for this client.", 409);
  }

  if (backendResponse.status === 422) {
    return errorResponse("Department details failed validation.", 422);
  }

  if (backendResponse.status !== 201) {
    return errorResponse("Department could not be created.", 502);
  }

  let department: unknown;

  try {
    department = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(department, {
    status: 201,
    headers: { "Cache-Control": "no-store" },
  });
}
