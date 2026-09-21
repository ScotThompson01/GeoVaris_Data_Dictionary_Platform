
import type { ReactNode } from "react";

import AppShell from "../../components/AppShell";
import { requireSession } from "../../lib/require-session";

export default async function ProtectedLayout({
  children,
}: {
  children: ReactNode;
}) {
  await requireSession();

  return <AppShell>{children}</AppShell>;
}