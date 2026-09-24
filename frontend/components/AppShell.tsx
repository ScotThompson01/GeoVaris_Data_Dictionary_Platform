import type { ReactNode } from "react";
import Sidebar from "./Sidebar";

export default function AppShell({
  children,
  isInstallationAdmin,
}: {
  children: ReactNode;
  isInstallationAdmin: boolean;
}) {
  return (
    <div className="shell">
      <Sidebar isInstallationAdmin={isInstallationAdmin} />
      <main>{children}</main>
    </div>
  );
}
