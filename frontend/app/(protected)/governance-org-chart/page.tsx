"use client";

import { useEffect, useState } from "react";
import { getClients, getGovernanceDepartments, getGovernancePeople, getGovernanceAssignments } from "../../../lib/api";
import type { Client, GovernanceDepartment, GovernancePerson, GovernanceAssignment } from "../../../lib/types";

export default function GovernanceOrgChartPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [departments, setDepartments] = useState<GovernanceDepartment[]>([]);
  const [people, setPeople] = useState<GovernancePerson[]>([]);
  const [assignments, setAssignments] = useState<GovernanceAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedContact, setSelectedContact] = useState<{ person: GovernancePerson; role: string; department: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    getClients()
      .then((items) => {
        if (cancelled) return;
        setClients(items);
        setClientId(items[0]?.id ?? "");
      })
      .catch(() => {
        if (!cancelled) { setError("Unable to load clients."); setLoading(false); }
      });

  return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    let cancelled = false;
    setDepartments([]); setPeople([]); setAssignments([]);
    if (!clientId) { setLoading(false); return; }
    setLoading(true); setError("");
    Promise.all([getGovernanceDepartments(clientId), getGovernancePeople(clientId), getGovernanceAssignments(clientId)])
      .then(([d, p, a]) => {
        if (!cancelled) { setDepartments(d); setPeople(p); setAssignments(a); }
      })
      .catch(() => {
        if (!cancelled) setError("Unable to load governance information for this client.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [clientId]);
  const corporateDepartment = departments.find((department) => department.is_active && department.name.trim().toLowerCase() === "corporate");
  const businessDepartments = departments.filter((department) => department.is_active && department.id !== corporateDepartment?.id);
  const today = new Date().toISOString().slice(0, 10);
  const corporateOwners = assignments.filter((assignment) => assignment.department_id === corporateDepartment?.id && assignment.role === "executive_accountable_owner" && assignment.is_active && (!assignment.effective_start || assignment.effective_start.slice(0, 10) <= today) && (!assignment.effective_end || assignment.effective_end.slice(0, 10) >= today)).map((assignment) => ({ assignment, person: people.find((person) => person.id === assignment.person_id && person.is_active) })).filter((entry) => entry.person !== undefined);
  return (
    <div className="governance-org-chart">
      <h1>Governance Org Chart</h1>
      <p>Explore governance responsibilities by department, role, and assigned person.</p>
      <div className="card">
        <label htmlFor="org-chart-client">Client</label>
        <select id="org-chart-client" value={clientId} onChange={(event) => setClientId(event.target.value)} disabled={clients.length === 0}>
          {clients.length === 0 && <option value="">No clients available</option>}
          {clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
        </select>
        {loading && <p role="status">Loading governance information...</p>}
        {error && <p role="alert">{error}</p>}
      </div>
      {selectedContact && (
        <section className="card org-chart-contact-panel" aria-label="Team member contact information">
          <button type="button" className="org-chart-contact-close" onClick={() => setSelectedContact(null)}>Close</button>
          <h2>{selectedContact.person.full_name}</h2>
          <p><strong>Governance Role:</strong> {selectedContact.role}</p>
          <p><strong>Department:</strong> {selectedContact.department}</p>
          <p><strong>Job Title:</strong> {selectedContact.person.job_title || "Not provided"}</p>
          <p><strong>Email:</strong> {selectedContact.person.business_email ? <a href={`mailto:${selectedContact.person.business_email}`}>{selectedContact.person.business_email}</a> : "Not provided"}</p>
          <p><strong>Phone:</strong> {selectedContact.person.phone || "Not provided"}</p>
          <p><strong>Contact URL:</strong> {selectedContact.person.contact_url || "Not provided"}</p>
        </section>
      )}
      {!loading && !error && clientId && (
        <>
        <div className="org-chart-corporate">
          <article className="card org-chart-department">
            <h2>Corporate</h2>
            <div className="org-chart-team">
              {corporateOwners.length === 0 && <p>Corporate Data Owner — Unassigned</p>}
              {corporateOwners.map(({ assignment, person }) => (
                <div className="org-chart-member" key={assignment.id}>
                  <button type="button" className="org-chart-contact-link" onClick={() => person && setSelectedContact({ person, role: "Corporate Data Owner", department: "Corporate" })}>{person?.full_name}</button>
                  <span>Corporate Data Owner</span>
                  {person?.job_title && <small>{person.job_title}</small>}
                </div>
              ))}
            </div>
          </article>
        </div>
        <section className="org-chart-departments" aria-label="Governance departments">
          {businessDepartments.length === 0 && <p>No active governance departments have been identified for this client.</p>}
          {businessDepartments.map((department) => (
            <article className="card org-chart-department" key={department.id}>
              <h2>{department.name}</h2>
              {department.description && <p>{department.description}</p>}
              <div className="org-chart-team">
                {!assignments.some((a) => a.department_id === department.id && a.role === "department_data_owner" && a.is_active && (!a.effective_start || a.effective_start.slice(0, 10) <= today) && (!a.effective_end || a.effective_end.slice(0, 10) >= today) && people.some((p) => p.id === a.person_id && p.is_active)) && <div className="org-chart-member"><strong>Unassigned</strong><span>Department Data Owner</span></div>}
                {assignments.filter((assignment) => assignment.department_id === department.id && assignment.is_active && (!assignment.effective_start || assignment.effective_start.slice(0, 10) <= new Date().toISOString().slice(0, 10)) && (!assignment.effective_end || assignment.effective_end.slice(0, 10) >= new Date().toISOString().slice(0, 10))).sort((a, b) => (a.role === "department_data_owner" ? 0 : a.role === "data_steward" ? 1 : 2) - (b.role === "department_data_owner" ? 0 : b.role === "data_steward" ? 1 : 2)).map((assignment) => {
                  const person = people.find((item) => item.id === assignment.person_id && item.is_active);
                  if (!person) return null;
                  return (
                    <div className="org-chart-member" key={assignment.id}>
                      <button type="button" className="org-chart-contact-link" onClick={() => setSelectedContact({ person, role: assignment.role === "department_data_owner" ? "Department Data Owner" : assignment.role === "data_steward" ? "Data Steward" : assignment.role.replaceAll("_", " "), department: department.name })}>{person.full_name}</button>
                      <span>{assignment.role === "department_data_owner" ? "Department Data Owner" : assignment.role === "data_steward" ? "Data Steward" : assignment.role === "executive_accountable_owner" ? "Corporate Data Owner" : assignment.role.replaceAll("_", " ")}</span>
                      {person.job_title && <small>{person.job_title}</small>}
                    </div>
                  );
                })}
                {!assignments.some((a) => a.department_id === department.id && a.role === "data_steward" && a.is_active && (!a.effective_start || a.effective_start.slice(0, 10) <= today) && (!a.effective_end || a.effective_end.slice(0, 10) >= today) && people.some((p) => p.id === a.person_id && p.is_active)) && <div className="org-chart-member"><strong>Unassigned</strong><span>Data Steward</span></div>}
              </div>
            </article>
          ))}
        </section>
        </>
      )}
    </div>
  );
}














