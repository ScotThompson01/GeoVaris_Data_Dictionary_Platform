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

  const projectId = request.nextUrl.searchParams.get("project_id");
  const params = new URLSearchParams();

  if (projectId) {
    params.set("project_id", projectId);
  }

  const query = params.toString();
  const backendPath = `/api/v1/data-sources${query ? `?${query}` : ""}`;

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(backendPath, {
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

  if (backendResponse.status === 403) {
    return errorResponse("Permission denied.", 403);
  }

  if (backendResponse.status === 422) {
    return errorResponse("Invalid project ID.", 400);
  }

  if (!backendResponse.ok) {
    return errorResponse("Data sources could not be retrieved.", 502);
  }

  let dataSources: unknown;

  try {
    dataSources = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  if (!Array.isArray(dataSources)) {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(dataSources, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
