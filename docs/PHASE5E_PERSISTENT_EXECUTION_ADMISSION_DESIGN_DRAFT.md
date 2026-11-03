# GeoVaris Phase 5E — Persistent Execution Admission Design

Status: DRAFT — implementation design not yet approved
Migration: None created or authorized
Scope: Client-hosted Data Quality execution admission

## 1. Approved Requirements

The Phase 5 planning document requires:

- Rule-and-scope duplicate-execution protection.
- Source-specific concurrency limits.
- Organization-wide capacity ceilings.
- Atomic admission and lock acquisition.
- Persistent protection across application restarts.
- Continued capacity reservation for unresolved source workloads.
- No automatic retry or resume after application restart.
- Verification of source termination before releasing uncertain workload protection.
- Persistent controlled queueing when execution capacity is unavailable.

The seven execution statuses are approved. Their transition matrix remains
an implementation design decision.

## 2. Proposed Initial Execution Scope

For the current PostgreSQL numeric range-rule MVP:

- Scope type: full_object
- Rule identity: rule_id
- Registered object identity: source_object_id
- Duplicate-protection key: (rule_id, source_object_id, scope_type)

Rule versions are retained in execution history but excluded from the
duplicate-protection key.

Filtered, sampled, and cross-source scopes require separate future designs.

## 3. Proposed Persistent Admission Model

Separate execution history from workload ownership and capacity policy.

Potential entities:

- Execution admission: owning execution, rule, source object, scope,
  admission status, timestamps, and recovery state.
- Source capacity policy: source identity and approved concurrency limit.
- Capacity reservation: execution identity, capacity scope, reservation
  state, and release verification.
- Installation capacity policy: locally configured hard upper bound.

Final table names, constraints, indexes, and foreign keys require review.

## 4. Atomic Admission

A proposed admission transaction must:

1. Revalidate authorization, rule version, source safety, and scope.
2. Verify the complete required capacity policy.
3. Establish duplicate-execution ownership.
4. Reserve source and installation capacity.
5. Persist the associated execution state.
6. Commit all changes together or roll back all changes.

Concurrent requests must not bypass capacity checks.

A validated configuration alone never authorizes source measurement.

### Admission-to-measurement safety boundary

- Source measurement must not begin until the admission transaction
  successfully commits durable ownership and all required reservations.
- Admission failure or transaction rollback must leave no partial ownership
  or capacity reservations.
- Duplicate protection and source/installation capacity checks must be
  serialized through a documented database concurrency mechanism.
  Reading capacity counts without protecting against concurrent admissions
  is insufficient.
- An unresolved or STATUS_UNCERTAIN source workload retains its duplicate
  protection and relevant capacity reservations until verified termination
  or documented authorized resolution. Heartbeat expiration alone is
  insufficient evidence for release.

These are proposed implementation safeguards supporting the approved
atomic-admission and uncertain-workload requirements.

## 5. Uncertain Workloads

When source termination cannot be confirmed:

- Mark the execution STATUS_UNCERTAIN under the approved recovery policy.
- Preserve duplicate-protection ownership and relevant capacity reservations.
- Block overlapping retry attempts.
- Do not publish partial or uncertain results.
- Require verified source termination or documented administrator resolution.

A heartbeat timeout alone never releases ownership.

## 6. Application Restart

- Reconcile interrupted execution and reservation records.
- Treat unverifiable source workload termination as unresolved.
- Do not automatically resume or retry interrupted work.
- Preserve ownership until safe resolution is documented.

## 7. Open Design Decisions

- Exact interpretation of organization-wide capacity in client-hosted
  deployments: installation, client, or another organizational boundary.
- Configuration source and authorization for source-specific limits.
- Exact workload identity for future filtered and sampled executions.
- Admission locking strategy and capacity accounting under concurrency.
- Worker identity, termination verification, and recovery audit model.
- Persistent queue schema, scheduling fairness, and expiration behavior.
- Administrator resolution permissions and evidence requirements.
- Initial migration and rollout strategy for existing databases.

## 8. Required Validation Before Activation

- Unit tests for duplicate admission and capacity policy failures.
- PostgreSQL concurrency tests for atomic capacity reservations.
- Restart and uncertain-workload reconciliation tests.
- Authorization and project-isolation tests.
- Failure injection for transaction rollback and interrupted workers.
- Explicitly approved isolated migration testing.
- No production migration without separate authorization.

## 9. Current Implementation Boundary

Implemented and tested:

- Execution persistence and authorized row-locked start operations.
- Fail-closed installation capacity configuration validation.

Not implemented:

- Persistent admission records or capacity reservations.
- Source-level or installation-level enforcement.
- Worker reconciliation and persistent queueing.
- Production lifecycle integration or source workload ownership.

This document authorizes no database migration or runtime execution changes.


## 10. Proposed Database Integrity Invariants

Status: DRAFT — requires design approval before implementation.

### Workload identity and ownership

- Persist an immutable rule-and-scope identity at admission.
- Exclude rule version from duplicate-protection identity.
- Prevent two unresolved executions from owning the same identity.
- Preserve ownership through worker crashes and application restarts.
- Never treat heartbeat expiration alone as permission to release ownership.

### Capacity accounting

- Source and installation reservations must be acquired atomically.
- Concurrent admission transactions must be serialized against the
  relevant capacity-control records.
- Capacity consumption includes unresolved and STATUS_UNCERTAIN workloads.
- Capacity limits must be positive integers and explicitly configured.
- Missing or invalid capacity policy must block new admission.
- A failed transaction must leave no partial reservations.

### Reservation release

- Normal release requires a verified workload completion or termination.
- Uncertain workload release requires documented authorized resolution
  or verified source termination.
- Record the actor, timestamp, reason, and evidence reference for release.
- Preserve historical execution and release information for audit.
- Never automatically release a reservation solely because it is old.

### Database enforcement

- Use database constraints for stable identity and reservation integrity.
- Use a transaction-safe strategy for numerical capacity limits.
- Ensure all cooperating workers follow the same admission protocol.
- Protect against duplicate admission under concurrent PostgreSQL sessions.
- Use explicit foreign keys, indexes, and constrained status values.
- Do not enable source measurement until admission commits successfully.

### Pending decisions

- Final table structure and uniqueness strategy.
- Source and installation capacity serialization mechanism.
- Reservation release authorization and evidence schema.
- Recovery handling when source termination cannot be verified.
- Migration compatibility with existing execution history.

No migration or runtime implementation is authorized by this section.

## 11. Proposed Persistent Workload Ownership States

Status: DRAFT — requires design approval.

Ownership state is independent of execution lifecycle status.

### RESERVED

- Duplicate-protection ownership and capacity reservations are held.
- Prevents conflicting execution admission.
- Persists across application and worker restarts.

### UNRESOLVED

- Source workload termination cannot be verified.
- Duplicate-protection ownership and capacity reservations remain held.
- Prevents overlapping retries and conflicting execution admission.
- No automatic expiration or heartbeat-based release is permitted.

### RELEASED

- Ownership is no longer active.
- Requires verified source completion or termination, or documented
  authorized administrator resolution.
- Release actor, timestamp, reason, and evidence must be auditable.
- Historical ownership records must remain available.

### Proposed Database Invariants

- RESERVED and UNRESOLVED both count toward capacity.
- Only one RESERVED or UNRESOLVED owner may exist for a given
  rule-and-scope identity.
- RELEASED records do not block future admission.
- An execution lifecycle status change does not automatically release
  ownership.
- Release decisions must be explicit, validated, and auditable.
- No source measurement begins before durable admission commits.

No database migration or runtime implementation is authorized by this section.

## 12. Proposed PostgreSQL Duplicate-Ownership Enforcement

Status: DRAFT — no migration authorized.

### Partial Unique Index

Proposed ownership identity:

- rule_id
- source_object_id
- scope_type

A PostgreSQL partial unique index should reject two records with the
same ownership identity when ownership_state is RESERVED or UNRESOLVED.

Conceptual SQL, not executable migration code:

CREATE UNIQUE INDEX uq_dq_active_workload_identity
ON data_quality_workload_ownership (
    rule_id,
    source_object_id,
    scope_type
)
WHERE ownership_state IN ('reserved', 'unresolved');

### Safety Requirements

- Ownership identity columns must be non-null and validated.
- Admission must not begin source measurement before commit.
- Unique-constraint conflicts must reject or safely queue admission.
- A conflict must not trigger automatic retry against the source.
- RESERVED to UNRESOLVED retains duplicate protection.
- RELEASED ownership remains available as historical evidence.
- An ownership record must never be deleted to bypass an unresolved lock.
- Future filtered or sampled scope types require canonical scope identity.
- Rule or source-object reassignment must not silently change active
  ownership identity.

### Limitations

The partial unique index prevents duplicate ownership for one defined
rule-and-scope identity.

It does not enforce source-level or installation-wide numeric capacity.
Those requirements need separate transaction-safe capacity accounting.

The proposed table and index require design review and isolated migration
testing before implementation.

## 13. Proposed Atomic Capacity Enforcement

Status: DRAFT — no implementation or migration authorized.

### Persistent Capacity Controls

Proposed capacity-control records:

- Installation capacity: one deployment-wide concurrency ceiling.
- Source capacity: one approved concurrency ceiling per data source.

Capacity limits must be positive integers. Missing or invalid required
capacity configuration blocks admission.

### Transactional Admission Strategy

A proposed admission transaction should:

1. Validate execution authorization, source safety, and rule eligibility.
2. Acquire the installation capacity-control row lock.
3. Acquire the relevant source capacity-control row lock.
4. Verify capacity, counting all RESERVED and UNRESOLVED workloads.
5. Establish rule-and-scope duplicate ownership.
6. Persist execution and capacity reservations.
7. Commit all changes atomically.

Lock acquisition order must be consistent across workers.

If any check fails, roll back the entire transaction without beginning
source measurement.

### Capacity Reservation Rules

- Every admitted source workload consumes one source-capacity slot.
- Every admitted workload consumes one installation-capacity slot.
- RESERVED and UNRESOLVED workloads continue consuming capacity.
- RELEASED reservations no longer consume capacity.
- A worker restart or missed heartbeat does not release capacity.
- Capacity decreases must not silently evict existing reservations.
- All workers must use the same database-enforced admission protocol.

### Concurrency Validation

Required PostgreSQL integration tests:

- Simultaneous requests for the same rule and scope.
- Simultaneous requests for different rules sharing one source limit.
- Simultaneous requests across sources sharing the installation limit.
- Atomic rollback when any required capacity is unavailable.
- Preservation of capacity after an execution becomes UNRESOLVED.
- No automatic release after interrupted worker activity.
- Deadlock avoidance through consistent lock acquisition order.

### Remaining Design Decisions

- Exact schema for capacity-control records and reservations.
- Whether capacity usage is derived from reservations or maintained
  through transactionally updated counters.
- Policy management permissions and change auditing.
- Reconciliation after crashes during source execution.
- Persistent queue integration and admission fairness.

These proposals require review before migration 0025 is created.

## 14. Proposed Capacity Accounting Decision

Status: PROPOSED — pending architecture approval.

### Recommended initial strategy

Derive capacity usage from persistent workload reservations rather than
maintaining separate mutable usage counters.

Count reservations in RESERVED and UNRESOLVED states.
Exclude RELEASED reservations from current capacity consumption.

### Concurrency requirements

- Lock the installation capacity-control record before reading usage.
- Lock the relevant source capacity-control record next.
- Count reservations while holding both locks.
- Create ownership and reservations within the same transaction.
- Commit before starting source measurement.
- Apply the same locking discipline when releasing reservations.
- Reject admission when either capacity limit would be exceeded.
- Preserve reservations after worker crashes or uncertain termination.

### Important limitations

Row locking capacity-control records protects accounting only when all
workers and release operations follow the prescribed transaction protocol.

Reservation counts must use a database transaction isolation strategy
that observes previously committed admissions after acquiring the locks.
A stale transaction snapshot must not determine available capacity.

Use PostgreSQL concurrency integration tests to validate this behavior
before enabling execution admission.

### Decision status

This recommendation has not been approved for implementation.

No migration, source execution, or capacity-enforcement activation is
authorized by this section.

## 15. PostgreSQL Transaction Isolation Requirements

Status: DRAFT — implementation not yet authorized.

### Verified Test Environment

The isolated Phase 5E PostgreSQL database reports:

- default_transaction_isolation = read committed

This was verified through a read-only query.
It does not establish the isolation level of every future application
transaction or authorize changes to other databases.

### Proposed Admission Requirement

The initial reservation-counting implementation should use
PostgreSQL READ COMMITTED isolation with explicit capacity-control
row locks.

Required transaction sequence:

1. Begin the admission transaction.
2. Acquire the installation capacity-control row lock.
3. Acquire the relevant source capacity-control row lock.
4. Query active reservation counts after acquiring both locks.
5. Validate duplicate ownership and available capacity.
6. Persist execution ownership and capacity reservations.
7. Commit all admission changes together.
8. Begin source measurement only after successful commit.

All participating admission and release operations must follow a
consistent locking protocol.

### Safety Conditions

- Do not use stale reservation counts obtained before lock acquisition.
- Do not assume database defaults establish session-level isolation.
- Reject unsupported isolation configurations until validated.
- Do not use unprotected count queries for admission decisions.
- Preserve RESERVED and UNRESOLVED capacity after application restarts.
- Fail closed if required locks, policies, or database checks fail.

### Required PostgreSQL Validation

- Two transactions competing for the final installation capacity slot.
- Two transactions competing for the final source capacity slot.
- Concurrent duplicate rule-and-scope admission attempts.
- Visibility of previously committed reservations after acquiring locks.
- Atomic rollback when admission cannot acquire all reservations.
- Preservation of uncertain workload capacity.

These requirements must be tested before enabling execution admission.

No migration or source-execution activation is authorized by this section.

## 16. Consolidated Architecture Decision Register

Status: DRAFT — no schema or implementation approval implied.

### A. Resolve before drafting migration 0025

1. Capacity scope: proposed installation-wide hard ceiling plus
   separately configured source-specific limits.
2. Duplicate identity: proposed (rule_id, source_object_id, full_object).
3. Capacity accounting: proposed counts of RESERVED and UNRESOLVED
   persistent reservations.
4. Concurrency enforcement: proposed capacity-control row locks,
   consistent acquisition order, and partial unique ownership index.
5. Relational integrity: define exact foreign keys, uniqueness,
   release history, and reservation relationships.
6. Migration compatibility: preserve existing execution records and
   ensure safe upgrade and downgrade conditions.

All six decisions require explicit design approval.

### B. Resolve before runtime execution admission

- Worker identity and durable workload association.
- Source workload termination verification.
- Authorization and audit requirements for manual resolution.
- Recovery and reconciliation after worker or application failure.
- Verified release of ownership and capacity reservations.
- Admission authorization, source safety, and committed ownership.
- PostgreSQL concurrency and failure-injection integration tests.

No source measurement may use the new admission path until these
requirements are implemented and validated.

### C. Later implementation increments

- Canonical identity for filtered and sampled execution scopes.
- Persistent controlled queue and admission scheduling.
- Priority fairness, request expiration, and execution windows.
- Additional organizational capacity policies where approved.

Deferred implementation does not waive approved Phase 5 requirements.
A runtime feature depending on deferred safeguards must remain disabled.

### Current Approval Boundary

This register organizes proposed decisions only.
It does not authorize migration 0025, database writes, source
measurements, commits, or pushes.

## 17. Existing Execution Integration Boundary

Status: DRAFT — no runtime implementation authorized.

### Existing Components

- prepare_rule_execution(): authorizes the requester and validates
  rule, version, field, source object, and data source metadata.
- stage_pending_execution(): stages a PENDING execution without
  performing source measurement.
- get_authorized_locked_execution(): obtains a project-scoped
  execution row lock using SELECT FOR UPDATE.
- stage_running_execution(): validates and stages PENDING -> RUNNING.
- measure_prepared_range_rule(): performs source-side aggregate
  measurement against the approved PostgreSQL connection.
- execute_range_rule(): legacy orchestration that measures before
  staging a successful execution record.

### Required Future Admission Boundary

A protected admission service must:

1. Revalidate authorization, metadata eligibility, source identity,
   and execution status inside the admission transaction.
2. Acquire capacity-control locks in the documented order.
3. Enforce duplicate workload identity and capacity ceilings.
4. Persist workload ownership and reservations atomically.
5. Stage the authorized execution transition.
6. Commit the admission transaction before source measurement.
7. Permit measurement only through the admitted workload context.
8. Preserve ownership and capacity until source completion or
   termination is verified and safely recorded.

### Bypass Prevention

- Execution-row locking alone is insufficient.
- stage_authorized_running_execution() must not independently
  authorize source measurement.
- execute_range_rule() must not remain a production-accessible
  measurement path that bypasses persistent admission.
- Capacity-check-only implementations are insufficient without
  atomic durable reservation.
- Failure or application restart must not automatically release
  capacity when source termination remains unverified.

### Compatibility and Validation

Preserve historical execution records and current authorized
metadata-validation logic. Before runtime activation, test
concurrent admissions, lifecycle transitions, crash recovery,
source-identity changes, and all callable measurement paths.

No migration, source execution, or runtime activation is
authorized by this section.

## 18. Proposed Persistent Ownership Relational Integrity

Status: DRAFT — requires architecture approval before migration.

### Ownership Identity

Proposed ownership records identify:

- execution_id
- project_id
- rule_id
- source_object_id
- data_source_id
- scope_type (initially full_object)
- ownership_state (reserved, unresolved, released)

Execution identity and source identity must be immutable after admission.

### Database Integrity Requirements

1. An ownership record must reference an existing execution.
2. Its project_id and rule_id must match that execution.
3. Its source_object_id must belong to its data_source_id.
4. Its data_source_id must belong to its project_id.
5. Its rule must identify a field belonging to the recorded source object.
6. Each execution may have at most one ownership record.
7. At most one RESERVED or UNRESOLVED ownership record may exist
   for the same rule, source object, and full-object scope.
8. Ownership and reservation history must not be cascade-deleted
   while source termination remains unresolved.

### Proposed Constraint Strategy

Use composite foreign keys and supporting unique constraints where
they can enforce relationships directly.

The rule-to-field-to-source relationship spans multiple existing
tables and cannot be fully guaranteed by independent foreign keys.
It requires an explicitly reviewed database enforcement strategy,
such as additional composite identity constraints or controlled
immutable association records.

Validate the complete identity chain again inside the locked
admission transaction.

Application validation alone must not be represented as full
database-enforced relational integrity.

### Historical Compatibility

Existing execution records must remain unchanged.
Do not fabricate ownership records or active capacity reservations
for historical executions.

New ownership constraints must be validated against the existing
schema before migration 0025 is drafted.

### Deletion Safety

Review existing CASCADE relationships before implementation.
A deleted source or field must never silently release ownership
or capacity while the associated source workload is unresolved.

No database migration or runtime change is authorized here.

## 19. Connection Identity and Admission Lock Coordination

Status: DRAFT — locking protocol requires design approval.

### Existing Behavior

PostgreSQL connection registration locks the DataSource row before
checking and updating connection identity.

Changing the registered destination increments connection_revision,
clears is_verified, and removes verified_at.

Connection verification locks PostgreSQLConnectionIdentity before
marking a destination verified.

Execution connection revalidation also locks
PostgreSQLConnectionIdentity and compares the recorded revision.

### Proposed Admission Requirements

1. Establish a globally consistent lock acquisition protocol for
   installation capacity, source capacity, source metadata,
   connection identity, and execution state.
2. Coordinate with connection registration's existing DataSource
   row lock so destination changes cannot race with admission.
3. Revalidate registered source identity and verified connection
   revision before committing workload ownership.
4. Persist the admitted connection revision and non-secret source
   identity snapshot for later reconciliation.
5. Reject admission if verification or source authorization changes
   before the admission transaction commits.
6. Commit ownership and capacity reservations before source access.
7. Never perform source network operations while capacity-control
   locks are held.
8. Preserve reserved capacity if source termination is uncertain.

### Lock Ordering Review

The final ordering must be checked against every existing writer,
including connection registration, connection verification, rule
activation, execution transitions, and reservation release.

Do not assume an ordering is safe solely because individual
operations use SELECT FOR UPDATE.

Concurrent tests must cover admission versus connection updates,
connection verification, source deactivation, and capacity release.

### Implementation Boundary

This section does not authorize changing connection registration,
performing source measurements, or creating migration 0025.

## 20. Source Lifecycle and Workload Retention

Status: DRAFT — implementation requires separate authorization.

### Existing Platform Behavior

Projects have a status field.
Data sources have an is_active field.

Execution eligibility checks reject inactive data sources.

No application service or API endpoint for changing
DataSource.is_active was identified during the Phase 5E review.

### Proposed Admission Policy

- Require the registered data source to be active.
- Revalidate active status inside the protected admission transaction.
- Coordinate source-status updates with admission locking.
- Do not admit new workloads after source deactivation.
- Preserve existing workload ownership and capacity reservations.

### Unresolved Workload Protection

Source deactivation, project status changes, connection revocation,
and application restarts must not automatically release capacity.

A workload with unverified source termination must remain
UNRESOLVED until verified termination or documented administrator
resolution.

### Deletion and History Retention

Persistent ownership relationships must prevent cascading deletion
from silently removing unresolved workload evidence.

Retained execution history and source retirement requirements must
be considered before permitting permanent metadata deletion.

The final retention and deletion policy requires architecture review.

### Implementation Scope

This section does not authorize source deactivation endpoints,
schema migrations, database writes, source measurements, or changes
to existing metadata deletion behavior.
