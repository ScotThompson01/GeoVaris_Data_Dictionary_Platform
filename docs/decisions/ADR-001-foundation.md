# ADR-001: Initial platform foundation

## Status
Accepted

## Decision
Use:
- FastAPI for the backend API
- PostgreSQL as the primary metadata repository
- SQLAlchemy 2.x ORM
- Alembic for schema migrations
- Docker Compose for local/on-prem development packaging
- UUID primary keys for core entities

## Security rationale
The application is designed to run inside a client-controlled environment with no required cloud dependency or telemetry. Credentials are provided through environment variables and are not committed to source control.

## Scope control
Build 0.1 includes Client and Project only. Data sources, connectors, profiling, DQ rules, and dashboards are intentionally deferred.
