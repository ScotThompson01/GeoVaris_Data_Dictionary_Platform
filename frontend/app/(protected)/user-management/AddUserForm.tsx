"use client";

import { FormEvent, useState } from "react";

type AddUserFormProps = {
  onCreated: () => void;
};

export default function AddUserForm({ onCreated }: AddUserFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (!/^[A-Za-z0-9._-]{3,150}$/.test(username)) {
      setError(
        "Username must be 3–150 characters and contain only letters, numbers, periods, underscores, or hyphens.",
      );
      return;
    }

    if (
      password.length < 12 ||
      new TextEncoder().encode(password).length > 1024
    ) {
      setError("Password must be at least 12 characters and no more than 1024 UTF-8 bytes.");
      return;
    }

    if (password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }

    setSubmitting(true);

    try {
      const response = await fetch("/api/data/user-management", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const result: unknown = await response.json().catch(() => null);
        const message =
          typeof result === "object" &&
          result !== null &&
          "error" in result &&
          typeof result.error === "string"
            ? result.error
            : "User account could not be created.";
        throw new Error(message);
      }

      setSuccess(`User "${username}" was created as a standard user.`);
      setUsername("");
      setPassword("");
      setConfirmation("");
      onCreated();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "User account could not be created.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section aria-labelledby="add-user-heading">
      <h2 id="add-user-heading">Add user</h2>
      <p>Installation role: Standard user. New accounts cannot manage users or receive Administrator access through this form.</p>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="new-username">Username</label>
          <input
            id="new-username"
            name="username"
            autoComplete="off"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            minLength={3}
            maxLength={150}
            required
            disabled={submitting}
          />
        </div>
        <div>
          <label htmlFor="new-password">Password</label>
          <input
            id="new-password"
            name="new-password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={12}
            required
            disabled={submitting}
          />
        </div>
        <div>
          <label htmlFor="confirm-password">Confirm password</label>
          <input
            id="confirm-password"
            name="confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            minLength={12}
            required
            disabled={submitting}
          />
        </div>
        {error && <p role="alert">{error}</p>}
        {success && <p role="status">{success}</p>}
        <button type="submit" disabled={submitting}>
          {submitting ? "Creating user..." : "Add user"}
        </button>
      </form>
    </section>
  );
}
