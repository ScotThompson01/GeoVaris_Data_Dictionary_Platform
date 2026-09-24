import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "../../../../../../lib/backend";

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

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ userId: string }> },
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

  let body: unknown;

  try {
    body = await request.json();
  } catch {
    return errorResponse("Invalid JSON request body.", 400);
  }

  if (
    typeof body !== "object" ||
    body === null ||
    Array.isArray(body) ||
    typeof (body as Record<string, unknown>).is_installation_admin !==
      "boolean"
  ) {
    return errorResponse("A valid user role is required.", 400);
  }

  const { userId } = await context.params;

  if (!/^[0-9a-fA-F-]{36}$/.test(userId)) {
    return errorResponse("Invalid user identifier.", 400);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(
      `/api/v1/user-management/${userId}/role`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          is_installation_admin: (
            body as { is_installation_admin: boolean }
          ).is_installation_admin,
        }),
      },
    );
  } catch {
    return errorResponse("User management service is unavailable.", 503);
  }

  if (backendResponse.status === 401) {
    return errorResponse("Authentication required.", 401);
  }

  if (backendResponse.status === 403) {
    return errorResponse("Administrator access required.", 403);
  }

  if (backendResponse.status === 404) {
    return errorResponse("User not found.", 404);
  }

  if (backendResponse.status === 409) {
    return errorResponse(
      "You cannot remove your own Administrator role.",
      409,
    );
  }

  if (!backendResponse.ok) {
    return errorResponse("User role could not be updated.", 502);
  }

  let user: unknown;

  try {
    user = await backendResponse.json();
  } catch {
    return errorResponse("Invalid user management response.", 502);
  }

  return NextResponse.json(user, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}

