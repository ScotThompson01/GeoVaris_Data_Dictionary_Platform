"use client";

import {
  createContext,
  useContext,
  type ReactNode,
} from "react";

const CurrentUserContext = createContext<string | undefined>(
  undefined,
);

export function CurrentUserProvider({
  userId,
  children,
}: {
  userId: string;
  children: ReactNode;
}) {
  return (
    <CurrentUserContext.Provider value={userId}>
      {children}
    </CurrentUserContext.Provider>
  );
}

export function useCurrentUserId(): string {
  const userId = useContext(CurrentUserContext);

  if (!userId) {
    throw new Error(
      "useCurrentUserId must be used within CurrentUserProvider.",
    );
  }

  return userId;
}
