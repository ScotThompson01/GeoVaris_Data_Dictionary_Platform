# GeoVaris Phase 5E
## Disposable PostgreSQL Interrupted-Test Recovery Procedure

Status: Design draft
Date: 2026-11-17

## 1. Purpose

Define a safe recovery procedure for interrupted PostgreSQL
integration tests that require committed synthetic fixtures.

This procedure applies exclusively to the dedicated Phase 5E
disposable migration-test environment.

It does not authorize production or client database operations.

## 2. Mandatory Security Boundaries

- Data Quality runtime admission must remain disabled.
- No Data Quality workers may be launched.
- No client-source connections are permitted.
- Only synthetic test metadata may be used.
- Credentials must never appear in logs or recovery manifests.
- Manual cleanup and database resets require explicit approval.
- Unknown records must never be automatically deleted.

## 3. Approved PostgreSQL Target

Docker Compose file:
docker-compose.migration-test.yml

Expected connection identity:

- Driver: postgresql+psycopg
- Host: migration_test_db
- Port: 5432
- Database: geovaris_phase5e_migration_test
- User: geovaris_migration_test
- Alembic revision: 0026
- Network: geovaris-phase5e-migration-test_migration_test_network

Explicit test opt-in variables:

- PHASE5E_0026_DISPOSABLE_TEST
- PHASE5E_0026_TEST_DATABASE_URL

Verify the actual connected database identity and migration
revision before any test or recovery database operations.

Any mismatch must cause an immediate stop.

## 4. Proposed Recovery Manifest

Before committing synthetic test fixtures, persist a local
recovery manifest containing:

- Unique test-run identifier.
- Manifest format version.
- Test name.
- Creation timestamp in UTC.
- Approved disposable database identity.
- Expected Alembic revision.
- All actual synthetic fixture UUIDs.
- Fixture lifecycle status.

The manifest must not contain:

- Passwords or connection strings.
- Session tokens or authentication secrets.
- Client data or source records.

The manifest must survive test-container termination.
It must be stored outside the container's ephemeral filesystem.

Manifest creation must succeed before fixture commit.

The manifest is not, by itself, authorization to delete records.

## 5. Proposed Fixture Lifecycle

1. Verify explicit test opt-in.
2. Verify disposable database identity and revision.
3. Acquire the required fixture coordination lock.
4. Reject unresolved recovery manifests.
5. Verify that no conflicting installation control exists.
6. Stage synthetic fixtures in one transaction.
7. Capture all actual synthetic fixture identifiers.
8. Persist the recovery manifest.
9. Commit the synthetic fixture transaction.
10. Execute the controlled two-session concurrency test.
11. Roll back and close all test sessions.
12. Delete only verified synthetic fixture records.
13. Verify every recorded synthetic identity is absent.
14. Commit successful cleanup.
15. Mark the manifest as resolved.

Manifest handling and database transactions cannot be made
atomic with one another.

Any uncertain commit or cleanup outcome must cause a safe stop
and require investigation.

## 6. Interrupted-Test Recovery

If a test terminates before verified cleanup:

1. Stop further integration-test execution.
2. Preserve the recovery manifest.
3. Confirm that all relevant test processes have stopped.
4. Verify the approved disposable PostgreSQL target.
5. Inspect recorded fixture identities using read-only queries.
6. Verify that any remaining records belong to the exact
   synthetic fixture, including expected relationships.
7. Obtain explicit authorization for manual recovery.
8. Perform exact-ID cleanup in one controlled transaction.
9. Verify that all recorded synthetic identities are absent.
10. Commit cleanup only after successful verification.
11. Mark the recovery manifest as resolved.

If record ownership, fixture identity, or database identity
cannot be established, stop without deleting anything.

If no records remain, verify the full recorded identity set
before resolving the manifest.

## 7. Cleanup Requirements

Reuse reviewed dependency-ordered cleanup helpers where safe.

- Never delete by a broad name or timestamp filter.
- Never delete all capacity controls.
- Never delete unknown or unrelated records.
- Never use unrestricted table truncation.
- Never use automatic database or Docker volume removal.
- Roll back the cleanup transaction if verification fails.

Serialize recovery against cooperating fixture setup processes.

A conflicting installation control must continue to cause
fixture insertion to fail closed.

## 8. Database Reset Escalation

A database reset is not the default recovery mechanism.

If exact-ID recovery cannot be safely performed, stop and
prepare a separate reset proposal.

The proposal must identify the exact disposable database,
Docker project, container, network, and storage affected.

Explicit authorization is required before executing any
destructive reset.

No production or client resources may be affected.

## 9. Acceptance Criteria

- Missing or invalid manifests fail closed.
- Synthetic identities are recorded before fixture commit.
- Interrupted runs cannot silently permit new fixture creation.
- Unknown records are never automatically removed.
- Cleanup targets only verified synthetic identities.
- Cleanup failures preserve recovery information.
- Successful cleanup is independently verified.
- No credentials or client data appear in recovery artifacts.
- Runtime admission remains disabled.

## 10. Implementation Status

This document defines proposed safeguards.

Recovery manifest handling and interrupted-test recovery
are not yet implemented or validated.

The two-session PostgreSQL concurrency test must not be
executed until its required recovery safeguards are reviewed
and implemented.

GeoVaris: Clean data. Confident results.


## 11. Coordinated Manifest Resolution

Status: Implementation requirements.

Manifest resolution must remain separate from destructive
database cleanup.

### 11.1 Mandatory Preconditions

- Verify explicit disposable-test authorization.
- Verify the actual connected PostgreSQL database identity.
- Establish durable database instance identification.
- Verify the expected Alembic revision.
- Hold the required fixture lifetime coordination lock.
- Load and validate the active recovery manifest.
- Verify that the manifest matches the intended test run.
- Confirm all test execution sessions have stopped.
- Confirm no source worker was launched.

### 11.2 Independent Cleanup Verification

- Complete exact-ID cleanup in a controlled transaction.
- Verify absence of all twenty recorded fixture identities.
- Successfully commit the cleanup transaction.
- Open a separate verification connection.
- Revalidate the connected database identity.
- Verify all twenty recorded identities are absent again.
- Maintain fixture coordination throughout verification.

An uncommitted cleanup transaction is not sufficient evidence
for manifest resolution.

A caller-supplied success flag or verification count alone
must not authorize manifest resolution.

### 11.3 Manifest Resolution

- Revalidate the active manifest immediately before resolution.
- Require an exact match with the verified manifest.
- Reject unexpected files or directory contents.
- Reject symbolic links and invalid recovery records.
- Serialize resolution against cooperating fixture writers.
- Clear only the verified active recovery record.
- Synchronize the recovery directory after resolution.
- Stop further testing if the resolution outcome is uncertain.

### 11.4 Failure Handling

If any mandatory precondition fails:

- Do not proceed with manifest resolution.
- Preserve available recovery evidence.
- Stop further integration-test execution.
- Require investigation before another test run.

No automatic database reset, broad deletion, or runtime
admission activation is permitted.

### 11.5 Current Implementation Checkpoint

Completed:

- Recovery manifest creation and validation.
- Persistent manifest storage.
- Windows Docker bind-mount synchronization probe.
- Safe manifest retrieval.
- Exact-ID fixture absence verification helper.
- Fifty-seven passing offline regression tests.

Outstanding:

- Durable database instance identification.
- Lifetime fixture coordination.
- Independent post-commit verification integration.
- Safe manifest resolution implementation.
- Resolution regression tests.
- Controlled two-session PostgreSQL concurrency validation.

Data Quality runtime admission must remain disabled.


## 12. Lifecycle Coordination Locking

### Proposed advisory lock identifiers

- Lifecycle coordination: (481516, 1497).
- Existing fixture transaction coordination: (481516, 1496).
- Existing application bootstrap locks remain unchanged.

The lifecycle lock is reserved for disposable PostgreSQL
integration testing and recovery coordination only.

### Lock acquisition requirements

- Require explicit disposable-test authorization.
- Verify approved connection settings and migration revision.
- Verify the connected PostgreSQL database identity.
- Use a dedicated, non-pooled PostgreSQL connection.
- Acquire the session-level lifecycle lock before acquiring
  the existing fixture transaction lock.
- Prefer non-blocking advisory lock acquisition.
- If acquisition fails, stop without staging fixture records.
- Inspect recovery storage while lifecycle coordination is held.
- Reject unresolved or unexpected recovery directory contents
  before starting a new fixture lifecycle.

### Lock lifetime

Hold lifecycle coordination throughout:

1. Recovery storage inspection.
2. Synthetic fixture staging.
3. Durable recovery manifest persistence.
4. Fixture transaction commit.
5. Two-session concurrency testing.
6. Test session rollback and closure.
7. Exact synthetic fixture cleanup.
8. Cleanup transaction commit.
9. Independent post-commit fixture absence verification.
10. Verified recovery manifest resolution.

Release the lifecycle lock only after successful resolution
or controlled termination of the test lifecycle.

### Failure handling

- Never continue after uncertain lock acquisition.
- Never treat a lost database connection as valid coordination.
- Never automatically reacquire a lost lifecycle lock and resume.
- Stop recovery operations when coordination becomes uncertain.
- Preserve any unresolved recovery manifest.
- Roll back outstanding test transactions where possible.
- Close participating database sessions.
- Do not automatically reset the database.
- Do not enable runtime execution admission.

### Implementation constraints

All participating fixture creation and recovery paths must
honor the same lifecycle coordination protocol.

The lifecycle lock must not be used by the second session
whose purpose is to test execution-row lock contention.

The existing transaction lock remains unchanged.

Session-level advisory locks coordinate cooperating database
sessions only. They do not independently protect filesystem
state, prove database authenticity, or exclude non-cooperating
processes.

Actual PostgreSQL behavior, connection-loss handling,
cross-process exclusion, and recovery safeguards require
controlled validation before use.
