
import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "../../../../lib/backend";

export const runtime = "nodejs";

const SESSION_COOKIE = "geovaris_session";

function isSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  const allowedOrigin = process.env.APP_ORIGIN;

  // Deny requests if the origin or server configuration is missing.
  if (!origin || !allowedOrigin) {
    return false;
  }

  try {
    return new URL(origin).origin === allowedOrigin;
  } catch {
    return false;
  }
}

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

export async function POST(request: NextRequest) {
  // Reject requests from unapproved origins before reading credentials.
  if (!isSameOrigin(request)) {
    return errorResponse("Request origin is not allowed.", 403);
  }

  let payload: unknown;

  try {
    payload = await request.json();
  } catch {
    return errorResponse("Invalid JSON request.", 400);
  }

  if (
    typeof payload !== "object" ||
    payload === null ||
    Array.isArray(payload)
  ) {
    return errorResponse("Username and password are required.", 400);
  }

  const credentials = payload as Record<string, unknown>;

  if (
    typeof credentials.username !== "string" ||
    typeof credentials.password !== "string" ||
    credentials.username.trim().length === 0 ||
    credentials.username.length > 150 ||
    credentials.password.length === 0
  ) {
    return errorResponse("Username and password are required.", 400);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch("/api/v1/auth/sign-in", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username: credentials.username,
        password: credentials.password,
      }),
    });
  } catch {
    return errorResponse("Authentication service is unavailable.", 503);
  }

  if (backendResponse.status === 401) {
    return errorResponse("Invalid username or password.", 401);
  }

  if (!backendResponse.ok) {
    return errorResponse("Sign-in could not be completed.", 502);
  }

  let result: unknown;

  try {
    result = await backendResponse.json();
  } catch {
    return errorResponse("Invalid authentication service response.", 502);
  }

  if (
    typeof result !== "object" ||
    result === null ||
    Array.isArray(result)
  ) {
    return errorResponse("Invalid authentication service response.", 502);
  }

  const signIn = result as Record<string, unknown>;

  if (
    typeof signIn.session_token !== "string" ||
    signIn.session_token.length === 0 ||
    typeof signIn.username !== "string" ||
    typeof signIn.user_id !== "string"
  ) {
    return errorResponse("Invalid authentication service response.", 502);
  }

  // Never return the session token in the JSON response.
  const response = NextResponse.json({
    user_id: signIn.user_id,
    username: signIn.username,
  });

  response.cookies.set(SESSION_COOKIE, signIn.session_token, {
    httpOnly: true,
    secure: request.nextUrl.protocol === "https:",
    sameSite: "strict",
    path: "/",
  });

  response.headers.set("Cache-Control", "no-store");

  return response;
}