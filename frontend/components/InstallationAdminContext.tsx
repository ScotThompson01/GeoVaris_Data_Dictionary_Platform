"use client";

import {
  createContext,
  useContext,
  type ReactNode,
} from "react";

const InstallationAdminContext = createContext<boolean | undefined>(undefined);

export function InstallationAdminProvider({
  isInstallationAdmin,
  children,
}: {
  isInstallationAdmin: boolean;
  children: ReactNode;
}) {
  return (
    <InstallationAdminContext.Provider value={isInstallationAdmin}>
      {children}
    </InstallationAdminContext.Provider>
  );
}

export function useInstallationAdmin(): boolean {
  const value = useContext(InstallationAdminContext);

  if (value === undefined) {
    throw new Error(
      "useInstallationAdmin must be used within InstallationAdminProvider.",
    );
  }

  return value;
}
