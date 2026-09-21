
import "server-only";

import { cookies } from "next/headers";

import { backendFetch } from "./backend";
import type { Client, Project } from "./types";

const SESSION_COOKIE = "geovaris_session";

async function authenticatedGet<T>(path: string): Promise<T> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;

  if (!token) {
    throw new Error("Authentication required.");
  }

  const response = await backendFetch(path, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Data request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function getDashboardClients(): Promise<Client[]> {
  return authenticatedGet<Client[]>("/api/v1/clients");
}

export async function getDashboardProjects(): Promise<Project[]> {
  return authenticatedGet<Project[]>("/api/v1/projects");
}