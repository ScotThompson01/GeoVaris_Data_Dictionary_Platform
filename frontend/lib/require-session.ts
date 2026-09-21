
import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { backendFetch } from "./backend";

const SESSION_COOKIE = "geovaris_session";

export type CurrentUser = {
  user_id: string;
  username: string;
};

export async function requireSession(): Promise<CurrentUser> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;

  if (!token) {
    redirect("/sign-in");
  }

  const response = await backendFetch("/api/v1/auth/me", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (response.status === 401) {
    redirect("/sign-in");
  }

  if (!response.ok) {
    throw new Error("Session validation could not be completed.");
  }

  const result: unknown = await response.json();

  if (
    typeof result !== "object" ||
    result === null ||
    Array.isArray(result)
  ) {
    throw new Error("Invalid authentication service response.");
  }

  const user = result as Record<string, unknown>;

  if (
    typeof user.user_id !== "string" ||
    typeof user.username !== "string"
  ) {
    throw new Error("Invalid authentication service response.");
  }

  return {
    user_id: user.user_id,
    username: user.username,
  };
}