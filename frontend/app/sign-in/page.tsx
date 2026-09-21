
"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

export default function SignInPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      const response = await fetch("/api/auth/sign-in", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "same-origin",
        cache: "no-store",
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        setError(
          response.status === 401
            ? "Invalid username or password."
            : "Sign-in is unavailable. Please try again."
        );
        return;
      }

      router.replace("/");
      router.refresh();
    } catch {
      setError("Unable to connect. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: "24px",
      }}
    >
      <section
        aria-labelledby="sign-in-title"
        style={{
          width: "100%",
          maxWidth: "420px",
          padding: "32px",
          border: "1px solid #d8dce8",
          borderRadius: "16px",
          background: "#fff",
        }}
      >
        <Image
          src="/branding/geovaris-logo.svg"
          alt="GeoVaris"
          width={82}
          height={82}
          priority
        />

        <h1 id="sign-in-title">Sign in</h1>
        <p>GeoVaris Data Dictionary Platform</p>

        <form onSubmit={handleSubmit}>
          <label
            htmlFor="username"
            style={{ display: "block", marginTop: "24px" }}
          >
            Username
          </label>
          <input
            id="username"
            name="username"
            type="text"
            autoComplete="username"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            disabled={submitting}
            style={{ width: "100%", padding: "10px", marginTop: "6px" }}
          />

          <label
            htmlFor="password"
            style={{ display: "block", marginTop: "16px" }}
          >
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={submitting}
            style={{ width: "100%", padding: "10px", marginTop: "6px" }}
          />

          {error && (
            <p role="alert" style={{ color: "#a11b1b" }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            style={{
              width: "100%",
              marginTop: "24px",
              padding: "12px",
              border: 0,
              borderRadius: "8px",
              background: "#4931a8",
              color: "#fff",
              cursor: submitting ? "wait" : "pointer",
            }}
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p style={{ marginTop: "24px", fontSize: "14px" }}>
          Clean data. Confident results.
        </p>
      </section>
    </main>
  );
}