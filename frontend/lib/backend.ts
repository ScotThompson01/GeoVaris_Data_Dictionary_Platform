import "server-only";

const BACKEND_URL =
  process.env.INTERNAL_API_URL ?? "http://api:8000";

export async function backendFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  if (!path.startsWith("/") || path.startsWith("//")) {
    throw new Error("Backend path must start with a single slash.");
  }

  return fetch(`${BACKEND_URL}${path}`, {
    ...options,
    cache: "no-store",
    redirect: "manual",
  });
}