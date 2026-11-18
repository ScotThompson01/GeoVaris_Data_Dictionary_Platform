const DEFAULT_PROJECT_PREFIX = "geovaris:default-project:";

function preferenceKey(userId: string): string {
  return `${DEFAULT_PROJECT_PREFIX}${userId}`;
}

export function getDefaultProject(
  userId: string,
): string | null {
  if (!userId || typeof window === "undefined") {
    return null;
  }

  try {
    return window.localStorage.getItem(preferenceKey(userId));
  } catch {
    return null;
  }
}

export function setDefaultProject(
  userId: string,
  projectId: string,
): boolean {
  if (!userId || !projectId || typeof window === "undefined") {
    return false;
  }

  try {
    window.localStorage.setItem(
      preferenceKey(userId),
      projectId,
    );

    return true;
  } catch {
    return false;
  }
}

export function clearDefaultProject(
  userId: string,
): boolean {
  if (!userId || typeof window === "undefined") {
    return false;
  }

  try {
    window.localStorage.removeItem(preferenceKey(userId));

    return true;
  } catch {
    return false;
  }
}
