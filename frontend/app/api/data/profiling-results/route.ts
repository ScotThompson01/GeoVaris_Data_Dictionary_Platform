
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

  const dataFieldId = request.nextUrl.searchParams
    .get("data_field_id")
    ?.trim();

  if (!dataFieldId) {
    return errorResponse("A field ID is required.", 400);
  }

  const params = new URLSearchParams({
    data_field_id: dataFieldId,
  });

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(
      `/api/v1/profiling-results?${params.toString()}`,
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

  if (!backendResponse.ok) {
    return errorResponse(
      "Profiling results could not be retrieved.",
      502,
    );
  }

  let results: unknown;

  try {
    results = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  if (!Array.isArray(results)) {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(results, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}