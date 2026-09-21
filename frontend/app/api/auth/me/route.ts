
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

  // A missing cookie is not an authenticated session.
  if (!token) {
    return errorResponse("Authentication required.", 401);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch("/api/v1/auth/me", {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    return errorResponse("Authentication service is unavailable.", 503);
  }

  if (backendResponse.status === 401) {
    const response = errorResponse("Authentication required.", 401);

    // Discard a cookie whose backend session is no longer valid.
    response.cookies.delete(SESSION_COOKIE);

    return response;
  }

  if (!backendResponse.ok) {
    return errorResponse("Session validation could not be completed.", 502);
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

  const user = result as Record<string, unknown>;

  if (
    typeof user.user_id !== "string" ||
    typeof user.username !== "string"
  ) {
    return errorResponse("Invalid authentication service response.", 502);
  }

  // Return user identity only. Never expose the session token.
  return NextResponse.json(
    {
      user_id: user.user_id,
      username: user.username,
    },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}