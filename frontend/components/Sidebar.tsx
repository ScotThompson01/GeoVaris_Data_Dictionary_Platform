
"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function Sidebar({ isInstallationAdmin }: { isInstallationAdmin: boolean }) {
  const router = useRouter();
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState("");

  async function handleSignOut() {
    if (isSigningOut) {
      return;
    }

    setIsSigningOut(true);
    setSignOutError("");

    try {
      const response = await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
      });

      if (response.status !== 204) {
        throw new Error("Sign-out could not be completed. Please try again.");
      }

      router.replace("/sign-in");
      router.refresh();
    } catch {
      setSignOutError("Sign-out could not be completed. Please try again.");
      setIsSigningOut(false);
    }
  }

  return (
    <aside className="sidebar">
      <div className="brand">
        <Image
          src="/branding/geovaris-logo.svg"
          alt="GeoVaris"
          width={82}
          height={82}
          className="logo"
          priority
        />
        <div>
          <strong>GeoVaris</strong>
          <span>Data Dictionary Platform</span>
        </div>
      </div>

      <nav>
        <Link href="/">Dashboard</Link>
        <Link href="/clients">Clients</Link>
        <Link href="/projects">Projects</Link>
        <Link href="/data-sources">Data Sources</Link>
        <Link href="/dictionary">Data Dictionary</Link>
        {isInstallationAdmin && (
          <Link href="/user-management">User Management</Link>
        )}
        <div className="disabled">
          Data Quality <small>Soon</small>
        </div>

        <button
          type="button"
          onClick={handleSignOut}
          disabled={isSigningOut}
        >
          {isSigningOut ? "Signing out..." : "Sign out"}
        </button>

        {signOutError && <p role="alert">{signOutError}</p>}
      </nav>
    </aside>
  );
}