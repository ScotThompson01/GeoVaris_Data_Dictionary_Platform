import type { ReactNode } from "react";
import Sidebar from "./Sidebar";
import { CurrentUserProvider } from "./CurrentUserContext";
import { InstallationAdminProvider } from "./InstallationAdminContext";

export default function AppShell({
  children,
  isInstallationAdmin,
  userId,
}: {
  children: ReactNode;
  isInstallationAdmin: boolean;
  userId: string;
}) {
  return (
    <CurrentUserProvider userId={userId}>
    <InstallationAdminProvider isInstallationAdmin={isInstallationAdmin}>
      <div className="shell">
        <Sidebar isInstallationAdmin={isInstallationAdmin} />
        <main>{children}</main>
      </div>
    </InstallationAdminProvider>
    </CurrentUserProvider>
  );
}
