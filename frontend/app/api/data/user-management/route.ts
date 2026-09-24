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
    backendResponse = await backendFetch("/api/v1/user-management", {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    return errorResponse("User management service is unavailable.", 503);
  }

  if (backendResponse.status === 401) {
    return errorResponse("Authentication required.", 401);
  }

  if (backendResponse.status === 403) {
    return errorResponse("Administrator access required.", 403);
  }

  if (!backendResponse.ok) {
    return errorResponse("Users could not be retrieved.", 502);
  }

  let users: unknown;

  try {
    users = await backendResponse.json();
  } catch {
    return errorResponse("Invalid user management response.", 502);
  }

  if (!Array.isArray(users)) {
    return errorResponse("Invalid user management response.", 502);
  }

  return NextResponse.json(users, {
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
    return errorResponse("Username and password are required.", 400);
  }

  const input = body as Record<string, unknown>;

  if (
    typeof input.username !== "string" ||
    typeof input.password !== "string"
  ) {
    return errorResponse("Username and password are required.", 400);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch("/api/v1/user-management", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username: input.username,
        password: input.password,
      }),
    });
  } catch {
    return errorResponse("User management service is unavailable.", 503);
  }

  if (backendResponse.status === 401) {
    return errorResponse("Authentication required.", 401);
  }

  if (backendResponse.status === 403) {
    return errorResponse("Administrator access required.", 403);
  }

  if (backendResponse.status === 409) {
    return errorResponse("Username is already in use.", 409);
  }

  if (backendResponse.status === 422) {
    return errorResponse("Username or password is invalid.", 422);
  }

  if (!backendResponse.ok) {
    return errorResponse("User account could not be created.", 502);
  }

  let user: unknown;

  try {
    user = await backendResponse.json();
  } catch {
    return errorResponse("Invalid user management response.", 502);
  }

  return NextResponse.json(user, {
    status: 201,
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
