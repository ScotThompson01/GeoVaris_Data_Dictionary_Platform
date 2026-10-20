import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "../../../../../../lib/backend";

export const runtime = "nodejs";

const SESSION_COOKIE = "geovaris_session";

type RouteContext = {
  params: Promise<{ clientId: string }>;
};

function errorResponse(message: string, status: number) {
  return NextResponse.json(
    { error: message },
    {
      status,
      headers: { "Cache-Control": "no-store" },
    },
  );
}

export async function GET(
  request: NextRequest,
  context: RouteContext,
) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;

  if (!token) {
    return errorResponse("Authentication required.", 401);
  }

  const { clientId } = await context.params;

  const uuidPattern =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

  if (!uuidPattern.test(clientId)) {
    return errorResponse("A valid client ID is required.", 400);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(
      `/api/v1/clients/${encodeURIComponent(clientId)}/governance/people`,
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
    return errorResponse("Client not found.", 404);
  }

  if (!backendResponse.ok) {
    return errorResponse(
      "Governance people could not be retrieved.",
      502,
    );
  }

  let people: unknown;

  try {
    people = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  if (!Array.isArray(people)) {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(people, {
    headers: { "Cache-Control": "no-store" },
  });
}

export async function POST(
  request: NextRequest,
  context: RouteContext,
) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;

  if (!token) {
    return errorResponse("Authentication required.", 401);
  }

  const { clientId } = await context.params;

  const uuidPattern =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

  if (!uuidPattern.test(clientId)) {
    return errorResponse("A valid client ID is required.", 400);
  }

  let payload: unknown;

  try {
    payload = await request.json();
  } catch {
    return errorResponse("Invalid JSON request body.", 400);
  }

  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return errorResponse("Invalid governance person request.", 400);
  }

  const input = payload as Record<string, unknown>;

  if (typeof input.full_name !== "string") {
    return errorResponse("Full name is required.", 400);
  }

  const fullName = input.full_name.trim();

  if (!fullName || fullName.length > 255) {
    return errorResponse("Full name must contain 1 to 255 characters.", 400);
  }

  const limits: Record<string, number> = {
    job_title: 255,
    business_email: 320,
    phone: 50,
    contact_url: 1000,
  };

  const optionalFields: Record<string, string | null> = {};

  for (const [field, maxLength] of Object.entries(limits)) {
    const value = input[field];

    if (value !== undefined && value !== null && typeof value !== "string") {
      return errorResponse(`${field} must be text.`, 400);
    }

    const normalized = typeof value === "string" ? value.trim() : "";

    if (normalized.length > maxLength) {
      return errorResponse(`${field} cannot exceed ${maxLength} characters.`, 400);
    }

    optionalFields[field] = normalized || null;
  }

  const email = optionalFields.business_email;

  if (
    email &&
    (
      !email.includes("@") ||
      email.startsWith("@") ||
      email.endsWith("@") ||
      /\s/.test(email)
    )
  ) {
    return errorResponse("Enter a valid business email address.", 400);
  }

  const contactUrl = optionalFields.contact_url;

  if (contactUrl && !contactUrl.startsWith("https://")) {
    return errorResponse("Contact URL must use HTTPS.", 400);
  }

  let backendResponse: Response;

  try {
    backendResponse = await backendFetch(
      `/api/v1/clients/${encodeURIComponent(clientId)}/governance/people`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          full_name: fullName,
          ...optionalFields,
        }),
      },
    );
  } catch {
    return errorResponse("Data service is unavailable.", 503);
  }

  if (backendResponse.status === 401) {
    return errorResponse("Authentication required.", 401);
  }

  if (backendResponse.status === 403) {
    return errorResponse("Administrator permission required.", 403);
  }

  if (backendResponse.status === 404) {
    return errorResponse("Client not found or access denied.", 404);
  }

  if (backendResponse.status === 422) {
    return errorResponse("Governance person details failed validation.", 422);
  }

  if (backendResponse.status !== 201) {
    return errorResponse("Governance person could not be created.", 502);
  }

  let person: unknown;

  try {
    person = await backendResponse.json();
  } catch {
    return errorResponse("Invalid data service response.", 502);
  }

  return NextResponse.json(person, {
    status: 201,
    headers: { "Cache-Control": "no-store" },
  });
}
