import { notFound } from "next/navigation";

import { requireSession } from "../../../lib/require-session";
import UserList from "./UserList";

export default async function UserManagementPage() {
  const user = await requireSession();

  if (!user.is_installation_admin) {
    notFound();
  }

  return (
    <>
      <header>
        <div>
          <h1>User Management</h1>
          <p>View local user accounts and their installation roles.</p>
        </div>
      </header>

      <section className="card">
        <h3>User accounts</h3>
        <UserList currentUserId={user.user_id} />
      </section>
    </>
  );
}
