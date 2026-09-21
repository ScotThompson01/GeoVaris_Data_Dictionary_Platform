
import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "../../../../../lib/backend";

export const runtime = "nodejs";

const SESSION_COOKIE = "geovaris_session";

type RouteContext = {
  params: Promise<{
    dataFieldId: string;
  }>;
};

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

async function getFieldId(context: RouteContext) {
  const { dataFieldId } = await context.params;
  return dataFieldId.trim();
}

export async function GET(
  request: NextRequest,
  context: RouteContext,
) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;

  if (!token) {
    return errorResponse("Authentication required.", 401);
  }

  const dataFieldId = await getFieldId(context);

  if (!dataFieldId) {
    return errorResponse("A field ID is required.", 400);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(
      `/api/v1/field-governance/${encodeURIComponent(dataFieldId)}`,
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
    return errorResponse("Field not found.", 404);
  }

  if (!backendResponse.ok) {
    return errorResponse(
      "Governance metadata could not be retrieved.",
      502,
    );
  }

  let governance: unknown;

  try {
    governance = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(governance, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}

export async function PUT(
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

  const dataFieldId = await getFieldId(context);

  if (!dataFieldId) {
    return errorResponse("A field ID is required.", 400);
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
    Array.isArray(payload)
  ) {
    return errorResponse(
      "Governance metadata must be a JSON object.",
      400,
    );
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(
      `/api/v1/field-governance/${encodeURIComponent(dataFieldId)}`,
      {
        method: "PUT",
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

  if (backendResponse.status === 401) {
    return errorResponse("Authentication required.", 401);
  }

  if (backendResponse.status === 403) {
    return errorResponse("Permission denied.", 403);
  }

  if (backendResponse.status === 404) {
    return errorResponse("Field not found.", 404);
  }

  if (
    backendResponse.status === 400 ||
    backendResponse.status === 422
  ) {
    return errorResponse("Invalid governance metadata.", 400);
  }

  if (!backendResponse.ok) {
    return errorResponse(
      "Governance metadata could not be saved.",
      502,
    );
  }

  let governance: unknown;

  try {
    governance = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(governance, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}