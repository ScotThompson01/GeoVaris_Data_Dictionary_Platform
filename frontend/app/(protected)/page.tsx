
import Image from "next/image";

import {
  getDashboardClients,
  getDashboardProjects,
} from "../../lib/dashboard-data";

export const dynamic = "force-dynamic";

export default async function Page() {
  const [clients, projects] = await Promise.all([
    getDashboardClients(),
    getDashboardProjects(),
  ]);

  return (
    <>
      <header>
        <div>
          <h1>Dashboard</h1>
          <p>
            Secure metadata discovery and governance inside the client
            environment.
          </p>
        </div>
        <span className="status">Local environment</span>
      </header>

      <section className="hero">
        <div>
          <span className="eyebrow">
            GeoVaris Data Dictionary Platform
          </span>
          <h2>Clean data. Confident results.</h2>
          <p>
            Discover enterprise data, document what it means, assign
            accountability, define standards, and measure quality
            without requiring client data to leave the
            client-controlled environment.
          </p>
        </div>

        <Image
          src="/branding/data-dictionary-icon.png"
          alt="GeoVaris Data Dictionary"
          width={280}
          height={280}
          priority
        />
      </section>

      <section className="metrics">
        <div className="card">
          <span>Clients</span>
          <strong>{clients.length}</strong>
        </div>
        <div className="card">
          <span>Projects</span>
          <strong>{projects.length}</strong>
        </div>
        <div className="card">
          <span>Data Sources</span>
          <strong>0</strong>
        </div>
      </section>

      <section className="card">
        <h3>Recent Projects</h3>
        <table>
          <thead>
            <tr>
              <th>Project</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((project) => (
              <tr key={project.id}>
                <td>{project.name}</td>
                <td>{project.status}</td>
                <td>
                  {new Date(
                    project.created_at,
                  ).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}