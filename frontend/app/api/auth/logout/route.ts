
import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "../../../../lib/backend";

export const runtime = "nodejs";

const SESSION_COOKIE = "geovaris_session";

function isSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  const allowedOrigin = process.env.APP_ORIGIN;

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
  if (!isSameOrigin(request)) {
    return errorResponse("Request origin is not allowed.", 403);
  }

  const token = request.cookies.get(SESSION_COOKIE)?.value;

  if (!token) {
    return errorResponse("Authentication required.", 401);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch("/api/v1/auth/logout", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    return errorResponse("Authentication service is unavailable.", 503);
  }

  if (backendResponse.status === 401) {
    const response = errorResponse("Authentication required.", 401);
    response.cookies.delete(SESSION_COOKIE);
    return response;
  }

  if (backendResponse.status !== 204) {
    return errorResponse("Sign-out could not be completed.", 502);
  }

  const response = new NextResponse(null, {
    status: 204,
    headers: {
      "Cache-Control": "no-store",
    },
  });

  response.cookies.delete(SESSION_COOKIE);

  return response;
}