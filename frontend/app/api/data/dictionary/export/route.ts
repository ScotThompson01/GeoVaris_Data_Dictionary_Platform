import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "../../../../../lib/backend";

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

  const format = request.nextUrl.searchParams.get("format");

  if (format !== "csv" && format !== "xlsx") {
    return errorResponse("Export format must be csv or xlsx.", 400);
  }

  const params = new URLSearchParams({
    project_id: projectId,
    format,
  });

  const search = request.nextUrl.searchParams.get("search")?.trim();
  const dataSourceId = request.nextUrl.searchParams
    .get("data_source_id")
    ?.trim();
  const department = request.nextUrl.searchParams
    .get("department")
    ?.trim();
  const dataOwner = request.nextUrl.searchParams
    .get("data_owner")
    ?.trim();
  const isCde = request.nextUrl.searchParams.get("is_cde");

  if (search) {
    params.set("search", search);
  }

  if (dataSourceId) {
    params.set("data_source_id", dataSourceId);
  }

  if (department) {
    params.set("department", department);
  }

  if (dataOwner) {
    params.set("data_owner", dataOwner);
  }

  if (isCde === "true" || isCde === "false") {
    params.set("is_cde", isCde);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(
      `/api/v1/dictionary/export?${params.toString()}`,
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
    return errorResponse("Project not found.", 404);
  }

  if (!backendResponse.ok) {
    return errorResponse(
      "Dictionary export could not be generated.",
      502,
    );
  }

  const contentType = backendResponse.headers.get("content-type");
  const contentDisposition = backendResponse.headers.get(
    "content-disposition",
  );

  if (!contentType || !contentDisposition) {
    return errorResponse("Invalid data service response.", 502);
  }

  const body = await backendResponse.arrayBuffer();

  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": contentType,
      "Content-Disposition": contentDisposition,
      "Cache-Control": "no-store",
    },
  });
}