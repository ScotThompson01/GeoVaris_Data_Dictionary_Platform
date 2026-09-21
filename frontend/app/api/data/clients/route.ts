
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
    backendResponse = await backendFetch("/api/v1/clients", {
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
    return errorResponse("Client data could not be retrieved.", 502);
  }

  let clients: unknown;

  try {
    clients = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  if (!Array.isArray(clients)) {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(clients, {
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
    return errorResponse("A client name is required.", 400);
  }

  const input = body as Record<string, unknown>;

  if (
    typeof input.name !== "string" ||
    !input.name.trim()
  ) {
    return errorResponse("A client name is required.", 400);
  }

  if (
    input.description !== undefined &&
    typeof input.description !== "string"
  ) {
    return errorResponse("Client description must be text.", 400);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch("/api/v1/clients", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: input.name.trim(),
        ...(input.description !== undefined
          ? { description: input.description }
          : {}),
      }),
    });
  } catch {
    return errorResponse("Data service is unavailable.", 503);
  }

  if (backendResponse.status === 401) {
    return errorResponse("Authentication required.", 401);
  }

  if (!backendResponse.ok) {
    return errorResponse("Client could not be created.", 502);
  }

  let client: unknown;

  try {
    client = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(client, {
    status: 201,
    headers: {
      "Cache-Control": "no-store",
    },
  });
}