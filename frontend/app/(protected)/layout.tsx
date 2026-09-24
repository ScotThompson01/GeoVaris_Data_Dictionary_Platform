import type { ReactNode } from "react";

import AppShell from "../../components/AppShell";
import { requireSession } from "../../lib/require-session";

export default async function ProtectedLayout({
  children,
}: {
  children: ReactNode;
}) {
  const user = await requireSession();

  return (
    <AppShell isInstallationAdmin={user.is_installation_admin}>
      {children}
    </AppShell>
  );
}
