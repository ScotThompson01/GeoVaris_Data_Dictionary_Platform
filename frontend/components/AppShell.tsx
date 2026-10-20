import type { ReactNode } from "react";
import Sidebar from "./Sidebar";
import { InstallationAdminProvider } from "./InstallationAdminContext";

export default function AppShell({
  children,
  isInstallationAdmin,
}: {
  children: ReactNode;
  isInstallationAdmin: boolean;
}) {
  return (
    <InstallationAdminProvider isInstallationAdmin={isInstallationAdmin}>
      <div className="shell">
        <Sidebar isInstallationAdmin={isInstallationAdmin} />
        <main>{children}</main>
      </div>
    </InstallationAdminProvider>
  );
}
