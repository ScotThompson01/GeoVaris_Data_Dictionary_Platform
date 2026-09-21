
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

  const projectId = request.nextUrl.searchParams
    .get("project_id")
    ?.trim();

  if (!projectId) {
    return errorResponse("A project ID is required.", 400);
  }

  const search = request.nextUrl.searchParams
    .get("search")
    ?.trim();

  const params = new URLSearchParams({
    project_id: projectId,
  });

  if (search) {
    params.set("search", search);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(
      `/api/v1/dictionary?${params.toString()}`,
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
      "Dictionary data could not be retrieved.",
      502,
    );
  }

  let fields: unknown;

  try {
    fields = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  if (!Array.isArray(fields)) {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(fields, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}