"use client";

import { useEffect, useState } from "react";
import { createGovernanceDepartment, createGovernancePerson, getClients, getGovernanceDepartments, getGovernancePeople } from "../../../lib/api";
import type { Client, GovernanceDepartment, GovernancePerson } from "../../../lib/types";
import { useInstallationAdmin } from "../../../components/InstallationAdminContext";

export default function GovernanceDirectoryPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [departments, setDepartments] = useState<GovernanceDepartment[]>([]);
  const [people, setPeople] = useState<GovernancePerson[]>([]);
  const [loadingPeople, setLoadingPeople] = useState(false);
  const [peopleError, setPeopleError] = useState("");
  const [loadingClients, setLoadingClients] = useState(true);
  const [loadingDepartments, setLoadingDepartments] = useState(false);
  const [error, setError] = useState("");
  const isInstallationAdmin = useInstallationAdmin();
  const [departmentName, setDepartmentName] = useState("");
  const [departmentDescription, setDepartmentDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createSuccess, setCreateSuccess] = useState("");
  const [personName, setPersonName] = useState("");
  const [personJobTitle, setPersonJobTitle] = useState("");
  const [personEmail, setPersonEmail] = useState("");
  const [personPhone, setPersonPhone] = useState("");
  const [personContactUrl, setPersonContactUrl] = useState("");
  const [creatingPerson, setCreatingPerson] = useState(false);
  const [personCreateError, setPersonCreateError] = useState("");
  const [personCreateSuccess, setPersonCreateSuccess] = useState("");

  useEffect(() => {
    let cancelled = false;

    getClients()
      .then((items) => {
        if (cancelled) return;
        setClients(items);
        setClientId(items[0]?.id ?? "");
      })
      .catch(() => {
        if (!cancelled) setError("Unable to load authorized clients.");
      })
      .finally(() => {
        if (!cancelled) setLoadingClients(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!clientId) {
      setDepartments([]);
      return;
    }

    let cancelled = false;
    setLoadingDepartments(true);
    setDepartments([]);
    setError("");

    getGovernanceDepartments(clientId)
      .then((items) => {
        if (!cancelled) setDepartments(items);
      })
      .catch(() => {
        if (!cancelled) setError("Unable to load departments for this client.");
      })
      .finally(() => {
        if (!cancelled) setLoadingDepartments(false);
      });

    return () => {
      cancelled = true;
    };
  }, [clientId]);

  useEffect(() => {
    if (!clientId) {
      setPeople([]);
      setPeopleError("");
      setLoadingPeople(false);
      return;
    }

    let cancelled = false;
    setPeople([]);
    setPeopleError("");
    setLoadingPeople(true);

    getGovernancePeople(clientId)
      .then((items) => {
        if (!cancelled) setPeople(items);
      })
      .catch(() => {
        if (!cancelled) setPeopleError("Unable to load people for this client.");
      })
      .finally(() => {
        if (!cancelled) setLoadingPeople(false);
      });

    return () => {
      cancelled = true;
    };
  }, [clientId]);

  async function handleCreatePerson(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!isInstallationAdmin || !clientId || creatingPerson) return;

    const fullName = personName.trim();
    const email = personEmail.trim();
    const contactUrl = personContactUrl.trim();

    setPersonCreateError("");
    setPersonCreateSuccess("");

    if (!fullName || fullName.length > 255) {
      setPersonCreateError("Full name must contain 1 to 255 characters.");
      return;
    }

    if (email && (
      !email.includes("@") ||
      email.startsWith("@") ||
      email.endsWith("@") ||
      /\\s/.test(email) ||
      email.length > 320
    )) {
      setPersonCreateError("Enter a valid business email address.");
      return;
    }

    if (contactUrl && (!contactUrl.startsWith("https://") || contactUrl.length > 1000)) {
      setPersonCreateError("Contact URL must use HTTPS and be no longer than 1000 characters.");
      return;
    }

    setCreatingPerson(true);

    try {
      await createGovernancePerson(clientId, {
        full_name: fullName,
        job_title: personJobTitle.trim() || null,
        business_email: email || null,
        phone: personPhone.trim() || null,
        contact_url: contactUrl || null,
      });

      const updated = await getGovernancePeople(clientId);
      setPeople(updated);
      setPersonName("");
      setPersonJobTitle("");
      setPersonEmail("");
      setPersonPhone("");
      setPersonContactUrl("");
      setPersonCreateSuccess("Governance contact created successfully.");
    } catch (error) {
      setPersonCreateError(
        error instanceof Error ? error.message : "Unable to create governance contact.",
      );
    } finally {
      setCreatingPerson(false);
    }
  }

  async function handleCreateDepartment(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!isInstallationAdmin || !clientId || creating) return;

    const name = departmentName.trim();
    const description = departmentDescription.trim();

    setCreateError("");
    setCreateSuccess("");

    if (!name || name.length > 200) {
      setCreateError("Department name must contain 1 to 200 characters.");
      return;
    }

    if (description.length > 1000) {
      setCreateError("Description cannot exceed 1000 characters.");
      return;
    }

    setCreating(true);

    try {
      await createGovernanceDepartment(clientId, {
        name,
        description: description || null,
      });

      const updated = await getGovernanceDepartments(clientId);
      setDepartments(updated);
      setDepartmentName("");
      setDepartmentDescription("");
      setCreateSuccess("Department created successfully.");
    } catch (error) {
      setCreateError(
        error instanceof Error ? error.message : "Unable to create department.",
      );
    } finally {
      setCreating(false);
    }
  }

  return (
    <>
      <header>
        <div>
          <h1>Governance Directory</h1>
          <p>Manage the people and departments responsible for your data.</p>
        </div>
      </header>

      <section className="card">
        <h3>Departments</h3>

        <label htmlFor="governance-client">Client</label>
        <select
          id="governance-client"
          value={clientId}
          onChange={(event) => setClientId(event.target.value)}
          disabled={loadingClients || clients.length === 0}
        >
          {clients.length === 0 && <option value="">No clients available</option>}
          {clients.map((client) => (
            <option key={client.id} value={client.id}>
              {client.name}
            </option>
          ))}
        </select>

        {error && <p role="alert">{error}</p>}

        {loadingClients && <p>Loading clients...</p>}
        {!loadingClients && !error && clients.length === 0 && (
          <p>No clients are assigned to your account.</p>
        )}

        {loadingDepartments && <p>Loading departments...</p>}

        {!loadingDepartments && clientId && !error && (
          departments.length === 0 ? (
            <p>No departments have been added for this client yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Department</th>
                  <th>Description</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {departments.map((department) => (
                  <tr key={department.id}>
                    <td>{department.name}</td>
                    <td>{department.description || "?"}</td>
                    <td>{department.is_active ? "Active" : "Inactive"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </section>

      <section className="card">
        <h3>People</h3>
        <p>Governance contacts for the selected client. These are not application login accounts.</p>

        {loadingPeople && <p>Loading people...</p>}
        {peopleError && <p role="alert">{peopleError}</p>}

        {!loadingPeople && !peopleError && clientId && (
          people.length === 0 ? (
            <p>No governance contacts have been added for this client yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Job title</th>
                  <th>Business email</th>
                  <th>Phone</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {people.map((person) => (
                  <tr key={person.id}>
                    <td>{person.full_name}</td>
                    <td>{person.job_title || "?"}</td>
                    <td>{person.business_email || "?"}</td>
                    <td>{person.phone || "?"}</td>
                    <td>{person.is_active ? "Active" : "Inactive"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </section>

      {isInstallationAdmin && clientId && (
        <section className="card">
          <h3>Add Governance Contact</h3>
          <p>Register a person responsible for governance. This does not create a login account.</p>

          <form onSubmit={handleCreatePerson}>
            <div>
              <label htmlFor="person-full-name">Full name</label>
              <input id="person-full-name" value={personName} onChange={(event) => setPersonName(event.target.value)} maxLength={255} required disabled={creatingPerson} />
            </div>
            <div>
              <label htmlFor="person-job-title">Job title (optional)</label>
              <input id="person-job-title" value={personJobTitle} onChange={(event) => setPersonJobTitle(event.target.value)} maxLength={255} disabled={creatingPerson} />
            </div>
            <div>
              <label htmlFor="person-business-email">Business email (optional)</label>
              <input id="person-business-email" type="email" value={personEmail} onChange={(event) => setPersonEmail(event.target.value)} maxLength={320} disabled={creatingPerson} />
            </div>
            <div>
              <label htmlFor="person-phone">Phone (optional)</label>
              <input id="person-phone" type="tel" value={personPhone} onChange={(event) => setPersonPhone(event.target.value)} maxLength={50} disabled={creatingPerson} />
            </div>
            <div>
              <label htmlFor="person-contact-url">Contact URL (HTTPS only, optional)</label>
              <input id="person-contact-url" type="url" value={personContactUrl} onChange={(event) => setPersonContactUrl(event.target.value)} maxLength={1000} placeholder="https://example.com/contact" disabled={creatingPerson} />
            </div>
            <button type="submit" disabled={creatingPerson}>
              {creatingPerson ? "Creating..." : "Add Governance Contact"}
            </button>
            {personCreateError && <p role="alert">{personCreateError}</p>}
            {personCreateSuccess && <p role="status">{personCreateSuccess}</p>}
          </form>
        </section>
      )}

      {isInstallationAdmin && clientId && (
        <section className="card">
          <h3>Create Department</h3>
          <p>Register a department for the selected client.</p>

          <form onSubmit={handleCreateDepartment}>
            <div>
              <label htmlFor="department-name">Department name</label>
              <input
                id="department-name"
                type="text"
                value={departmentName}
                onChange={(event) => setDepartmentName(event.target.value)}
                maxLength={200}
                required
                disabled={creating}
              />
            </div>

            <div>
              <label htmlFor="department-description">Description (optional)</label>
              <textarea
                id="department-description"
                value={departmentDescription}
                onChange={(event) => setDepartmentDescription(event.target.value)}
                maxLength={1000}
                disabled={creating}
              />
            </div>

            <button type="submit" disabled={creating || loadingDepartments}>
              {creating ? "Creating..." : "Create Department"}
            </button>

            {createError && <p role="alert">{createError}</p>}
            {createSuccess && <p role="status">{createSuccess}</p>}
          </form>
        </section>
      )}
    </>
  );
}
