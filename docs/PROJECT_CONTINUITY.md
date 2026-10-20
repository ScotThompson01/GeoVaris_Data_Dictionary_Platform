# GeoVaris Data Dictionary Platform
## Project Continuity, Milestones, and Development Reference

**Purpose:**
This document is the persistent development reference for the GeoVaris Data Dictionary Platform.

It is intended to be loaded into ChatGPT/GPT development sessions so future work can resume with the correct project context, architecture, security requirements, completed milestones, technical decisions, and known next steps.

**Primary Product Message:**
> Clean data. Confident results.

---

# 1. Product Mission

The GeoVaris Data Dictionary Platform is a secure, client-hosted platform for:

- Data discovery
- Metadata cataloging
- Data dictionaries
- Business metadata
- Data governance
- Data profiling
- Data Quality rules
- Data Quality measurement
- Schema/change detection

The core workflow is:

**Discover → Define → Standardize → Measure → Govern → Improve**

The platform should answer:

- What data do we have?
- Where does it come from?
- What does it mean?
- Who owns it?
- Who stewards it?
- What should valid data look like?
- How good is it?
- Where are the problems?
- What changed?
- Who needs to act?

---

# 2. Security Principles

Security and privacy take priority over convenience.

Default assumptions:

- Client data remains inside the client's firewall.
- No client data is sent to GeoVaris.
- Core operation does not require a cloud dependency.
- Core operation does not require telemetry.
- Source-system access should be read-only whenever possible.
- Discovery and profiling must never modify source data.
- Credentials must never be hard-coded.
- Credentials and other sensitive values must not appear in logs.
- Avoid storing raw source data unless explicitly required.
- Prefer metadata, aggregates, masked values, or approved samples.
- Support restricted and disconnected environments.

Database discovery credentials should be supplied at runtime rather than stored with the registered data source.

---

# 3. Architecture

Preferred application architecture:

**Browser → Next.js → FastAPI → Discovery/Profiling Engine → Connectors → Client Sources**

Technology stack:

### Frontend
- Next.js
- React
- TypeScript

### Backend
- Python
- FastAPI
- Pydantic

### Metadata Database
- PostgreSQL
- SQLite permitted for portable/small deployments

### Deployment
- Docker preferred
- Windows VM support
- Linux VM support

Source-specific behavior should remain inside modular connectors rather than being embedded throughout the core application.

---

# 4. MVP Connectors

Required MVP connectors:

- CSV
- Excel
- PostgreSQL
- SQL Server

Future connectors may include:

- Oracle
- MySQL
- Snowflake
- Databricks
- Parquet
- JSON
- SharePoint
- Azure SQL

Connectors should provide normalized metadata to the core platform.

Expected connector capabilities include:

- Connection validation
- Source discovery
- Schema discovery
- Object discovery
- Field discovery
- Technical metadata extraction
- Optional profiling
- Rescanning
- Change detection

---

# 5. Core Metadata Model

## Technical Metadata

Examples include:

- Source
- Database
- Schema
- Table/view
- Column
- Native data type
- Length
- Precision
- Scale
- Nullability
- Keys
- Constraints
- Defaults
- Source comments
- Row count
- File information
- Worksheet information

## Profiling Metadata

Examples include:

- Null count
- Null percentage
- Distinct count
- Distinct percentage
- Minimum
- Maximum
- Date range
- String length
- Common values
- Patterns
- Invalid values
- Duplicates

## Business/Governance Metadata

Examples include:

- Business term
- Definition
- Department
- Data Owner
- Data Steward
- System Owner
- Business Process
- Critical Data Element status
- System of Record
- Classification
- Retention
- Update frequency
- Downstream use
- Regulatory relevance
- Approval status

**Important:** Machine inference must never be treated as approved business metadata.

---

# 6. Core Entities

Current/planned core entities include:

- client
- project
- data_source
- source_object
- data_field
- department
- data_owner
- data_steward
- business_term
- data_quality_rule
- profiling_result
- rule_execution
- quality_result
- scan
- schema_change
- classification
- approval
- audit_event

---

# 7. Data Quality Model

A field may have multiple structured Data Quality rules.

Supported/planned rule types include:

- Range
- Allowed values
- Regex/format
- Null/completeness
- Uniqueness
- Relational
- Reference/master-data

Examples:

- latitude BETWEEN -90 AND 90
- latitude within an approved client geographic range
- status IN ('ACTIVE', 'INACTIVE', 'PLANNED')
- ZIP matches an approved pattern
- customer_id must be unique
- end_date >= start_date

Universal technical rules must be distinguished from client/business-specific rules.

## Expected vs. Observed

The platform should explicitly compare expected standards with observed source values.

Example:

Expected latitude: 24.3–31.1
Observed latitude: 23.7–32.4

Violations should be clearly visible.

## Data Quality Dimensions

Support:

- Completeness
- Validity
- Uniqueness
- Consistency
- Accuracy
- Timeliness

Accuracy generally requires a trusted reference source and should not be inferred without evidence.

---

# 8. Development Roadmap

The planned development phases are:

1. Foundation
2. File Discovery
3. Database Discovery
4. Data Dictionary UI
5. Rule Engine
6. Data Quality Dashboards
7. Change Detection
8. Governance Workflow
9. Classification
10. Lineage

**Important:** The repository may contain functionality ahead of this documented roadmap. Always inspect the current code before assuming a phase has not been implemented.

---

# 9. Major Development Milestones

## Foundation

Foundation work established the application structure using the GeoVaris preferred architecture.

The application uses:

- Next.js/React/TypeScript frontend
- FastAPI/Python backend
- PostgreSQL metadata database
- Docker-based local development

---

## File Discovery

File discovery work was implemented before database discovery.

Relevant repository history includes:

`7ae5c57`
**Merge pull request #29 from feature/0.4m-file-discovery-page**

This represents the previous file-discovery development checkpoint before database discovery.

Future sessions should inspect the repository for the exact current implementation rather than relying solely on this summary.

---

## Database Discovery

Database discovery has been implemented for the two MVP database connectors:

- PostgreSQL
- SQL Server

Database source registration and secure discovery UI were implemented in:

`10ccbce`
**Add database source registration and secure discovery UI**

This work was merged into `main` through PR #30.

Main checkpoint following that merge:

`6b5d35c`
**Merge pull request #30 from feature/0.4n-database-discovery**

### Database Discovery Security Improvements

The database discovery implementation includes protections such as:

- Runtime credentials rather than persisted database passwords.
- Generic connector/service errors to reduce accidental secret exposure.
- Regression tests for secret leakage.
- SQL Server ODBC credential escaping/handling.
- Source-specific connector logic.
- Read-only discovery expectations.
- Same-origin frontend/API handling.
- Password fields cleared after requests.

---

# 10. Live Database Validation Milestone

Branch:

`feature/0.4o-live-database-validation`

This branch was completed, merged through a pull request, and subsequently deleted.

It contained two major commits.

## PostgreSQL Live Validation

Commit:

`299e09c`
**Add PostgreSQL live discovery validation fixture**

A real PostgreSQL container was used to validate the PostgreSQL connector.

Synthetic database:

`geovaris_discovery_test`

Synthetic discovery role:

`geovaris_discovery_reader`

The reader was configured for read-only transactions.

The fixture contained representative objects under the `operations` schema:

- facilities
- work_orders
- active_facilities

The live PostgreSQL connector successfully discovered:

- 3 objects
- 22 fields

The validation included representative metadata such as:

- Tables
- Views
- Data types
- Lengths
- Precision
- Scale
- Nullability
- Keys
- Constraints
- Defaults
- Comments

PostgreSQL browser end-to-end discovery also succeeded.

Validated flow:

**Browser → Next.js → FastAPI → PostgreSQL Connector → Metadata Persistence**

---

## SQL Server Live Validation

Commit:

`5984117`
**Add SQL Server live discovery validation**

A real SQL Server 2022 container was used to validate the SQL Server connector.

Image:

`mcr.microsoft.com/mssql/server:2022-latest`

Synthetic database:

`geovaris_discovery_test`

Synthetic discovery account:

`geovaris_discovery_reader`

The SQL Server reader was intentionally restricted to metadata discovery.

It received:

- CONNECT
- VIEW DEFINITION

It was not intentionally granted source-row SELECT, write, or DDL privileges for this discovery validation.

The fixture contained:

- operations.facilities
- operations.work_orders
- operations.active_facilities

The SQL Server connector successfully discovered:

- 3 objects
- 22 fields

Representative metadata successfully discovered included:

- Tables
- Views
- Data types
- Lengths
- Precision
- Scale
- Nullability
- Primary key information
- Unique metadata
- Defaults
- Source comments

SQL Server browser end-to-end discovery also succeeded.

Validated flow:

**Browser → Next.js → FastAPI → SQL Server Connector → Metadata Persistence**

---

# 11. Important SQL Server Decisions

## Canonical Source Type

The public/persisted source type is:

`sql_server`

Do not accidentally change persisted/public source-type checks back to:

`sqlserver`

The connector's internal connector name may still use:

`sqlserver`

These are intentionally different concepts.

---

## SQL Server Encryption

Encryption should remain enabled by default.

A local/test-only option was added to explicitly disable SQL Server connection encryption when required by the test environment.

The frontend option:

- Appears only for SQL Server.
- Defaults to encryption enabled.
- Requires explicit user selection to disable encryption.
- Is reset when switching projects or discovery sources.

PostgreSQL must not receive this SQL Server-specific encryption exception.

---

## SQL Server Read-Only Security

`ApplicationIntent=ReadOnly` should not be treated as the primary authorization control.

The actual security boundary is the restricted database account and its database permissions.

For metadata-only discovery, the validation account uses metadata permissions without general source-row access.

If future profiling requires SELECT access, that should be handled as a separate, explicitly approved capability.

---

# 12. Validation Results at Database Discovery Checkpoint

The following automated validation was completed during the live database validation milestone:

### SQL Server discovery service tests
**5 passed**

### SQL Server connector tests
**7 passed**

### PostgreSQL discovery regression tests
**5 passed**

### Frontend production build
**Passed**

### Discovery Docker Compose configuration
**Passed**

### Git whitespace validation
**Passed**

Windows LF/CRLF conversion warnings were observed but were not whitespace errors.

Both PostgreSQL and SQL Server were also validated against live containerized databases.

---

# 13. Docker Safety Notes

The primary application Docker services are:

- geovaris-data-platform-db-1
- geovaris-data-platform-api-1
- geovaris-data-platform-frontend-1

Isolated authentication/browser test services have included:

- auth_test_db
- auth_test_api
- auth_test_frontend

The isolated browser test frontend has used:

`http://localhost:3001`

### Important Development Rule

Do not use:

`--remove-orphans`

when working with the isolated Compose environments.

The main development services should not be unintentionally stopped or removed while running isolated validation environments.

---

# 14. Test Fixtures

Live database discovery fixtures are stored under:

`test_fixtures/`

Known database discovery fixtures include:

- PostgreSQL discovery fixture
- SQL Server discovery fixture

SQL Server fixture:

`test_fixtures/sqlserver_discovery/init.sql`

These fixtures use synthetic test-only credentials.

Never replace them with client or production credentials.

---

# 15. Current Development Checkpoint

At the end of the live database validation milestone:

- PostgreSQL discovery is implemented and live validated.
- SQL Server discovery is implemented and live validated.
- Both database connectors successfully normalize discovered metadata.
- Browser-to-database discovery has been exercised end-to-end.
- Metadata persistence has been verified.
- Security controls were retained during validation.
- The validation feature branch was merged through a pull request.
- The feature branch was deleted after the PR was completed.

This represents a strong checkpoint for **Phase 3 – Database Discovery**.

---

# 16. Important Next-Step Instruction

Do **not** immediately begin building a new Data Dictionary implementation based solely on the roadmap.

The repository appears to already contain Data Dictionary and governance-related functionality, including routes associated with:

- dictionary
- field governance
- profiling results

The documentation may be behind the actual codebase.

Therefore, the first task when development resumes should be:

**Inspect the current `main` branch and inventory the existing Data Dictionary implementation.**

Determine:

1. What Data Dictionary backend functionality already exists?
2. What Data Dictionary frontend functionality already exists?
3. What governance metadata is already editable?
4. What search/filter capabilities already exist?
5. What profiling information is already exposed?
6. What is complete, partial, or missing relative to Phase 4?
7. What is the smallest logical next unit of work?

Only after this inventory should the next feature branch be planned.

---

# 17. Development Method

When deciding what to build next:

1. Update and inspect `main`.
2. Review the current development phase.
3. Inspect actual implementation before trusting older documentation.
4. Identify dependencies.
5. Choose the smallest logical unit of work.
6. Create a focused feature branch.
7. Implement securely.
8. Add automated tests.
9. Validate the user workflow.
10. Review the diff.
11. Commit.
12. Push.
13. Create a pull request.
14. Merge only after validation.
15. Delete completed feature branches when appropriate.
16. Update this continuity document at significant milestones.

---

# 18. Working Style for GPT-Assisted Development

The primary developer may be learning software development.

GPT development assistance should:

- Work in small, manageable steps.
- Prefer one command/action at a time during interactive debugging.
- Wait for command output before proceeding when the result affects the next step.
- Clearly distinguish PowerShell commands from expected output.
- Explain what each important command does.
- Distinguish Windows, Linux, and Docker instructions when relevant.
- Avoid large uncontrolled changes.
- Review diffs before commits.
- Prefer secure, maintainable solutions over shortcuts.
- Avoid unnecessary vendor lock-in.
- Never sacrifice GeoVaris security principles for development convenience.

---

# 19. Definition of Done for Discovery Work

Discovery functionality should not be considered complete merely because unit tests pass.

Where practical, validation should include:

- Automated tests
- Connector-level validation
- Real source/container validation
- API validation
- Browser workflow validation
- Metadata persistence validation
- Security review
- Secret-leak review
- Production frontend build
- Git diff review

This validation approach was used successfully for the PostgreSQL and SQL Server discovery milestone.

---

# 20. Future Continuity Updates

Update this document whenever one of the following occurs:

- A development phase is completed.
- A major feature is merged.
- An architectural decision is made.
- A security decision is made.
- A new connector is implemented.
- Database/schema design changes materially.
- A significant test environment is introduced.
- A major bug reveals an important design lesson.
- A roadmap priority changes.
- A new deployment requirement is established.

For each milestone, record:

- Feature/phase
- Branch
- PR if known
- Important commit(s)
- What was implemented
- Security decisions
- Tests completed
- Live validation performed
- Known limitations
- Remaining work
- Recommended next step

---

# 21. Guiding Principle

The GeoVaris platform should remain:

**Secure, client-hosted, explainable, modular, maintainable, and useful to both technical and business governance users.**

The goal is not simply to collect metadata.

The goal is to help organizations move from:

**Discover → Define → Standardize → Measure → Govern → Improve**

while keeping client data under client control.
