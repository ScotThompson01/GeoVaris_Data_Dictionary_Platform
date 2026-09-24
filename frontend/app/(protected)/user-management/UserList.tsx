"use client";

import { useEffect, useState } from "react";
import AddUserForm from "./AddUserForm";

type ManagedUser = {
  user_id: string;
  username: string;
  is_active: boolean;
  is_installation_admin: boolean;
  created_at: string;
  updated_at: string;
};

export default function UserList({ currentUserId }: { currentUserId: string }) {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [roleError, setRoleError] = useState<string | null>(null);
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadUsers() {
      try {
        const response = await fetch("/api/data/user-management", {
          credentials: "same-origin",
          cache: "no-store",
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(
            response.status === 403
              ? "Administrator access is required."
              : "User accounts could not be loaded.",
          );
        }

        const data: unknown = await response.json();

        if (!Array.isArray(data)) {
          throw new Error("Invalid user management response.");
        }

        if (!controller.signal.aborted) {
          setUsers(data as ManagedUser[]);
        }
      } catch (caught) {
        if (!controller.signal.aborted) {
          setError(
            caught instanceof Error
              ? caught.message
              : "User accounts could not be loaded.",
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadUsers();

    return () => controller.abort();
  }, [refreshKey]);

  async function changeRole(user: ManagedUser, isAdministrator: boolean) {
    if (user.user_id === currentUserId || updatingUserId !== null) {
      return;
    }

    setRoleError(null);
    setUpdatingUserId(user.user_id);

    try {
      const response = await fetch(
        `/api/data/user-management/${user.user_id}/role`,
        {
          method: "PATCH",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            is_installation_admin: isAdministrator,
          }),
        },
      );

      if (!response.ok) {
        const result: unknown = await response.json().catch(() => null);
        const message =
          typeof result === "object" &&
          result !== null &&
          "error" in result &&
          typeof result.error === "string"
            ? result.error
            : "User role could not be updated.";

        throw new Error(message);
      }

      setRefreshKey((key) => key + 1);
    } catch (caught) {
      setRoleError(
        caught instanceof Error
          ? caught.message
          : "User role could not be updated.",
      );
    } finally {
      setUpdatingUserId(null);
    }
  }
  if (loading) {
    return <p>Loading user accounts...</p>;
  }

  if (error) {
    return <p role="alert">{error}</p>;
  }

  if (users.length === 0) {
    return <><AddUserForm onCreated={() => setRefreshKey((key) => key + 1)} /><p>No user accounts found.</p></>;
  }

  return (
    <div>
      <AddUserForm onCreated={() => setRefreshKey((key) => key + 1)} />
      {roleError && <p role="alert">{roleError}</p>}
      <div style={{ overflowX: "auto" }}>
      <table>
        <thead>
          <tr>
            <th scope="col">Username</th>
            <th scope="col">Status</th>
            <th scope="col">Installation role</th>
            <th scope="col">Created</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.user_id}>
              <td>{user.username}</td>
              <td>{user.is_active ? "Active" : "Inactive"}</td>
              <td>
                <select
                  aria-label={`Installation role for ${user.username}`}
                  value={user.is_installation_admin ? "administrator" : "standard"}
                  disabled={user.user_id === currentUserId || updatingUserId !== null}
                  onChange={(event) =>
                    void changeRole(user, event.target.value === "administrator")
                  }
                >
                  <option value="standard">Standard user</option>
                  <option value="administrator">Administrator</option>
                </select>
              </td>
              <td>{new Date(user.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}
