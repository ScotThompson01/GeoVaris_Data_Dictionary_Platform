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
      `/api/v1/clients/${encodeURIComponent(clientId)}/governance/assignments`,
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
      "Governance assignments could not be retrieved.",
      502,
    );
  }

  let assignments: unknown;

  try {
    assignments = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  if (!Array.isArray(assignments)) {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(assignments, {
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
    return errorResponse("Invalid governance assignment request.", 400);
  }

  const input = payload as Record<string, unknown>;

  if (
    typeof input.person_id !== "string" ||
    !uuidPattern.test(input.person_id) ||
    typeof input.department_id !== "string" ||
    !uuidPattern.test(input.department_id)
  ) {
    return errorResponse("Valid person and department IDs are required.", 400);
  }

  const roles = [
    "executive_accountable_owner",
    "department_data_owner",
    "data_steward",
  ];

  if (typeof input.role !== "string" || !roles.includes(input.role)) {
    return errorResponse("A valid governance role is required.", 400);
  }

  const datePattern = /^\d{4}-\d{2}-\d{2}$/;

  for (const field of ["effective_start", "effective_end"]) {
    const value = input[field];

    if (
      value !== undefined &&
      value !== null &&
      (typeof value !== "string" || !datePattern.test(value))
    ) {
      return errorResponse(`${field} must be a date in YYYY-MM-DD format.`, 400);
    }
  }

  const start = input.effective_start as string | null | undefined;
  const end = input.effective_end as string | null | undefined;

  if (start && end && end < start) {
    return errorResponse("Effective end date cannot precede start date.", 400);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(
      `/api/v1/clients/${encodeURIComponent(clientId)}/governance/assignments`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          person_id: input.person_id,
          department_id: input.department_id,
          role: input.role,
          effective_start: start || null,
          effective_end: end || null,
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
    return errorResponse("Administrator permission required.", 403);
  }

  if (backendResponse.status === 404) {
    return errorResponse("Person, department, or client not found.", 404);
  }

  if (backendResponse.status === 409) {
    return errorResponse("Person or department is inactive.", 409);
  }

  if (backendResponse.status === 422) {
    return errorResponse("Governance assignment failed validation.", 422);
  }

  if (backendResponse.status !== 201) {
    return errorResponse("Governance assignment could not be created.", 502);
  }

  let assignment: unknown;

  try {
    assignment = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(assignment, {
    status: 201,
    headers: { "Cache-Control": "no-store" },
  });
}
