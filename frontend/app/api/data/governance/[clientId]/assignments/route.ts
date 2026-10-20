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
