"""Recovery manifest safeguards for disposable Phase 5E tests.

Test-only infrastructure. Never import from production services.
No database connections or runtime admission operations.
"""

import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final
from uuid import UUID, uuid4


MANIFEST_VERSION: Final[int] = 2

RECOVERY_DIRECTORY: Final[Path] = Path("/recovery")
ACTIVE_MANIFEST_NAME: Final[str] = "active-manifest.json"

EXPECTED_DRIVER: Final[str] = "postgresql+psycopg"
EXPECTED_HOST: Final[str] = "migration_test_db"
EXPECTED_PORT: Final[int] = 5432
EXPECTED_DATABASE: Final[str] = "geovaris_phase5e_migration_test"
EXPECTED_USER: Final[str] = "geovaris_migration_test"
EXPECTED_REVISION: Final[str] = "0026"

REQUIRED_FIXTURE_IDS: Final[frozenset[str]] = frozenset(
    {
        "client",
        "project",
        "actor",
        "reviewer",
        "actor_membership",
        "reviewer_membership",
        "reviewer_session",
        "source",
        "object",
        "field",
        "rule",
        "version",
        "execution",
        "ownership",
        "installation_control",
        "source_control",
        "installation_reservation",
        "source_reservation",
        "resolution_grant",
        "release_evidence",
    }
)


def validate_fixture_ids(value: object) -> dict[str, str]:
    """Validate the exact synthetic fixture identifier set.

    Reject malformed, missing, unexpected, or duplicate identifiers.
    Return a new dictionary containing canonical UUID strings.
    """

    if not isinstance(value, dict):
        raise ValueError("Fixture identifiers must be a dictionary.")

    if set(value) != REQUIRED_FIXTURE_IDS:
        raise ValueError("Unexpected synthetic fixture identifier set.")

    validated: dict[str, str] = {}
    seen: set[UUID] = set()

    for key in sorted(REQUIRED_FIXTURE_IDS):
        raw = value[key]

        if not isinstance(raw, str):
            raise ValueError("Fixture identifier must be a UUID string.")

        try:
            identifier = UUID(raw)
        except ValueError:
            raise ValueError("Invalid synthetic fixture UUID.") from None

        if str(identifier) != raw:
            raise ValueError("Fixture UUID must use canonical format.")

        if identifier.int == 0:
            raise ValueError("Zero UUID is not permitted.")

        if identifier in seen:
            raise ValueError("Duplicate synthetic fixture UUID.")

        seen.add(identifier)
        validated[key] = str(identifier)

    return validated


EXPECTED_TEST_NAME: Final[str] = (
    "test_protected_start_release_concurrency"
)

REQUIRED_MANIFEST_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "manifest_version",
        "run_id",
        "test_name",
        "created_at",
        "database_identity",
        "fixture_ids",
        "status",
    }
)


def expected_database_identity() -> dict[str, str | int]:
    """Return the approved credential-free database identity."""

    return {
        "driver": EXPECTED_DRIVER,
        "host": EXPECTED_HOST,
        "port": EXPECTED_PORT,
        "database": EXPECTED_DATABASE,
        "user": EXPECTED_USER,
        "revision": EXPECTED_REVISION,
    }


def validate_manifest(value: object) -> dict[str, object]:
    """Validate a recovery manifest without database access."""

    if not isinstance(value, dict):
        raise ValueError("Manifest must be a dictionary.")

    if set(value) != REQUIRED_MANIFEST_FIELDS:
        raise ValueError("Unexpected recovery manifest fields.")

    version = value["manifest_version"]

    if type(version) is not int or version != MANIFEST_VERSION:
        raise ValueError("Unsupported recovery manifest version.")

    run_id = value["run_id"]

    if not isinstance(run_id, str):
        raise ValueError("Invalid recovery run identifier.")

    try:
        identifier = UUID(run_id)
    except ValueError:
        raise ValueError("Invalid recovery run identifier.") from None

    if identifier.int == 0 or str(identifier) != run_id:
        raise ValueError("Invalid recovery run identifier.")

    if value["test_name"] != EXPECTED_TEST_NAME:
        raise ValueError("Unexpected recovery test name.")

    created_at = value["created_at"]

    if not isinstance(created_at, str):
        raise ValueError("Invalid recovery timestamp.")

    try:
        timestamp = datetime.fromisoformat(created_at)
    except ValueError:
        raise ValueError("Invalid recovery timestamp.") from None

    if (
        timestamp.tzinfo is None
        or timestamp.utcoffset() != timedelta(0)
        or timestamp.isoformat() != created_at
    ):
        raise ValueError("Recovery timestamp must be canonical UTC.")

    identity = value["database_identity"]
    expected_identity = expected_database_identity()

    if not isinstance(identity, dict):
        raise ValueError("Invalid recovery database identity.")

    required_identity_fields = (
        set(expected_identity) | REQUIRED_INSTANCE_IDENTITY_FIELDS
    )

    if set(identity) != required_identity_fields:
        raise ValueError("Unexpected recovery database identity fields.")

    for key, expected in expected_identity.items():
        actual = identity[key]

        if type(actual) is not type(expected) or actual != expected:
            raise ValueError("Recovery database identity mismatch.")

    instance_identity = validate_database_instance_identity(
        {
            key: identity[key]
            for key in REQUIRED_INSTANCE_IDENTITY_FIELDS
        }
    )

    if value["status"] != "pending_cleanup":
        raise ValueError("Unexpected recovery manifest status.")

    fixture_ids = validate_fixture_ids(value["fixture_ids"])

    if run_id in fixture_ids.values():
        raise ValueError("Recovery run identifier must be unique.")

    return {
        "manifest_version": MANIFEST_VERSION,
        "run_id": run_id,
        "test_name": EXPECTED_TEST_NAME,
        "created_at": created_at,
        "database_identity": {**expected_identity, **instance_identity},
        "fixture_ids": fixture_ids,
        "status": "pending_cleanup",
    }


def build_manifest(
    fixture_ids: object,
    *,
    instance_identity: object,
) -> dict[str, object]:
    """Build a validated credential-free recovery manifest.

    This function performs no filesystem or database operations.
    """

    validated_ids = validate_fixture_ids(fixture_ids)

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "run_id": str(uuid4()),
        "test_name": EXPECTED_TEST_NAME,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database_identity": {
            **expected_database_identity(),
            **validate_database_instance_identity(instance_identity),
        },
        "fixture_ids": validated_ids,
        "status": "pending_cleanup",
    }

    return validate_manifest(manifest)


def persist_manifest(manifest: object) -> Path:
    """Persist a validated manifest before synthetic fixture commit.

    Exclusively create the active manifest in the recovery directory.
    Never overwrite or automatically remove an existing manifest.

    Any persistence failure must prevent fixture commit.
    """

    validated = validate_manifest(manifest)

    payload = (
        json.dumps(
            validated,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")

    directory_fd = os.open(
        RECOVERY_DIRECTORY,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )

    try:
        if os.listdir(directory_fd):
            raise RuntimeError(
                "Recovery directory is not empty. Review required."
            )

        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
        )

        file_fd = os.open(
            ACTIVE_MANIFEST_NAME,
            flags,
            0o600,
            dir_fd=directory_fd,
        )

        try:
            remaining = memoryview(payload)

            while remaining:
                written = os.write(file_fd, remaining)

                if written <= 0:
                    raise OSError("Recovery manifest write failed.")

                remaining = remaining[written:]

            os.fsync(file_fd)
        finally:
            os.close(file_fd)

        os.fsync(directory_fd)

    finally:
        os.close(directory_fd)

    return RECOVERY_DIRECTORY / ACTIVE_MANIFEST_NAME


MAX_MANIFEST_BYTES: Final[int] = 16384


def _reject_duplicate_json_keys(pairs):
    """Reject ambiguous JSON objects."""

    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate recovery manifest JSON key.")

        result[key] = value

    return result


def load_active_manifest() -> dict[str, object]:
    """Read and validate the active manifest without modifying it.

    Missing, malformed, or unexpected recovery state fails closed.
    This function does not authorize database cleanup.
    """

    directory_fd = os.open(
        RECOVERY_DIRECTORY,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )

    try:
        if set(os.listdir(directory_fd)) != {ACTIVE_MANIFEST_NAME}:
            raise RuntimeError(
                "Unexpected recovery directory state. Review required."
            )

        file_fd = os.open(
            ACTIVE_MANIFEST_NAME,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=directory_fd,
        )

        try:
            metadata = os.fstat(file_fd)

            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("Recovery manifest is not a regular file.")

            if not 0 < metadata.st_size <= MAX_MANIFEST_BYTES:
                raise ValueError("Invalid recovery manifest size.")

            payload = bytearray()

            while True:
                chunk = os.read(file_fd, 4096)

                if not chunk:
                    break

                payload.extend(chunk)

                if len(payload) > MAX_MANIFEST_BYTES:
                    raise ValueError("Recovery manifest exceeds size limit.")

            if len(payload) != metadata.st_size:
                raise ValueError("Recovery manifest size changed during read.")

        finally:
            os.close(file_fd)

    finally:
        os.close(directory_fd)

    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (ValueError, RecursionError):
        raise ValueError("Invalid recovery manifest content.") from None

    return validate_manifest(decoded)


FIXTURE_VERIFICATION_TARGETS: Final[tuple[tuple[str, str], ...]] = (
    ("clients", "client"),
    ("projects", "project"),
    ("users", "actor"),
    ("users", "reviewer"),
    ("project_access", "actor_membership"),
    ("project_access", "reviewer_membership"),
    ("auth_sessions", "reviewer_session"),
    ("data_sources", "source"),
    ("source_objects", "object"),
    ("data_fields", "field"),
    ("data_quality_rules", "rule"),
    ("data_quality_rule_versions", "version"),
    ("data_quality_rule_executions", "execution"),
    ("data_quality_workload_ownership", "ownership"),
    (
        "data_quality_execution_capacity_controls",
        "installation_control",
    ),
    (
        "data_quality_execution_capacity_controls",
        "source_control",
    ),
    (
        "data_quality_execution_capacity_reservations",
        "installation_reservation",
    ),
    (
        "data_quality_execution_capacity_reservations",
        "source_reservation",
    ),
    (
        "data_quality_workload_resolution_grants",
        "resolution_grant",
    ),
    (
        "data_quality_workload_release_evidence",
        "release_evidence",
    ),
)


def verify_fixture_absence(
    connection,
    fixture_ids: object,
) -> int:
    """Verify exact synthetic fixture identities are absent.

    The caller must verify the disposable database identity,
    hold the required coordination lock, and control the
    transaction lifecycle.

    This function performs read-only queries. It does not
    authorize cleanup or manifest resolution.
    """
    from sqlalchemy import text

    validated = validate_fixture_ids(fixture_ids)

    target_keys = [
        identity
        for _, identity in FIXTURE_VERIFICATION_TARGETS
    ]

    if (
        len(target_keys) != len(REQUIRED_FIXTURE_IDS)
        or set(target_keys) != REQUIRED_FIXTURE_IDS
    ):
        raise RuntimeError(
            "Incomplete fixture verification configuration."
        )

    verified_count = 0

    for table, identity in FIXTURE_VERIFICATION_TARGETS:
        remaining = connection.execute(
            text(
                f"SELECT count(*) FROM {table} "
                "WHERE id = :id"
            ),
            {"id": validated[identity]},
        ).scalar_one()

        if type(remaining) is not int or remaining != 0:
            raise RuntimeError(
                f"Fixture absence not established: {table}/{identity}"
            )

        verified_count += 1

    return verified_count


MAX_SYSTEM_IDENTIFIER: Final[int] = (1 << 64) - 1
MAX_DATABASE_OID: Final[int] = (1 << 32) - 1

REQUIRED_INSTANCE_IDENTITY_FIELDS: Final[frozenset[str]] = (
    frozenset({"system_identifier", "database_oid"})
)


def validate_database_instance_identity(
    value: object,
) -> dict[str, str | int]:
    """Validate PostgreSQL instance identifier metadata.

    This function validates structure and numeric bounds only.
    It does not establish the identity of a connected database.
    """
    if not isinstance(value, dict):
        raise ValueError("Invalid database instance identity.")

    if set(value) != REQUIRED_INSTANCE_IDENTITY_FIELDS:
        raise ValueError("Unexpected database instance identity fields.")

    system_identifier = value["system_identifier"]
    database_oid = value["database_oid"]

    if (
        type(system_identifier) is not str
        or not 1 <= len(system_identifier) <= 20
        or not system_identifier.isascii()
        or not system_identifier.isdecimal()
        or system_identifier.startswith("0")
    ):
        raise ValueError("Invalid PostgreSQL system identifier.")

    if not 1 <= int(system_identifier) <= MAX_SYSTEM_IDENTIFIER:
        raise ValueError("PostgreSQL system identifier out of range.")

    if (
        type(database_oid) is not int
        or not 1 <= database_oid <= MAX_DATABASE_OID
    ):
        raise ValueError("Invalid PostgreSQL database OID.")

    return {
        "system_identifier": system_identifier,
        "database_oid": database_oid,
    }


def read_database_instance_identity(
    connection,
) -> dict[str, str | int]:
    """Read PostgreSQL instance identifiers from an existing connection.

    The caller must establish explicit disposable-test authorization
    and verify the approved connection settings before calling.

    This helper does not open a connection, modify records,
    commit transactions, or authorize recovery operations.
    """
    from sqlalchemy import text

    if os.getenv("PHASE5E_0026_DISPOSABLE_TEST") != "YES":
        raise RuntimeError(
            "Explicit disposable PostgreSQL opt-in required."
        )

    database, username = connection.execute(
        text(
            "SELECT pg_catalog.current_database(), current_user"
        )
    ).one()

    if (
        database != EXPECTED_DATABASE
        or username != EXPECTED_USER
    ):
        raise RuntimeError(
            "Connected PostgreSQL identity mismatch."
        )

    system_identifier, database_oid = connection.execute(
        text(
            "SELECT CAST(control.system_identifier AS text), "
            "CAST(database.oid AS bigint) "
            "FROM pg_catalog.pg_control_system() AS control "
            "CROSS JOIN pg_catalog.pg_database AS database "
            "WHERE database.datname = pg_catalog.current_database()"
        )
    ).one()

    return validate_database_instance_identity(
        {
            "system_identifier": system_identifier,
            "database_oid": database_oid,
        }
    )


def verify_manifest_database_identity(
    connection,
    manifest: object,
) -> None:
    """Compare recovery metadata with connected instance identifiers.

    The caller must verify approved connection settings,
    migration revision, and required lifecycle coordination.

    A successful comparison is only one recovery prerequisite.
    It does not authorize cleanup or manifest removal.
    """

    validated_manifest = validate_manifest(manifest)

    recorded_identity = validated_manifest["database_identity"]

    expected_instance = validate_database_instance_identity(
        {
            key: recorded_identity[key]
            for key in REQUIRED_INSTANCE_IDENTITY_FIELDS
        }
    )

    actual_instance = read_database_instance_identity(
        connection
    )

    if actual_instance != expected_instance:
        raise RuntimeError(
            "Recovery database instance identity mismatch."
        )


LIFECYCLE_LOCK_NAMESPACE: Final[int] = 481516
LIFECYCLE_LOCK_IDENTIFIER: Final[int] = 1497


def acquire_lifecycle_lock(connection) -> None:
    """Attempt non-blocking session-level lifecycle coordination.

    The caller must provide a dedicated, verified, non-pooled
    PostgreSQL connection and manage its complete lifetime.

    Call only once per dedicated session. PostgreSQL advisory
    locks permit repeated acquisition by the same session.

    Successful acquisition does not authorize fixture staging,
    database cleanup, or manifest removal.
    """
    from sqlalchemy import text

    if os.getenv("PHASE5E_0026_DISPOSABLE_TEST") != "YES":
        raise RuntimeError(
            "Explicit disposable PostgreSQL opt-in required."
        )

    acquired = connection.execute(
        text(
            "SELECT pg_catalog.pg_try_advisory_lock("
            ":namespace, :identifier)"
        ),
        {
            "namespace": LIFECYCLE_LOCK_NAMESPACE,
            "identifier": LIFECYCLE_LOCK_IDENTIFIER,
        },
    ).scalar_one()

    if acquired is not True:
        raise RuntimeError(
            "Lifecycle coordination lock not acquired."
        )


def release_lifecycle_lock(connection) -> None:
    """Release lifecycle coordination on the acquiring session.

    The caller must establish that the lifecycle has ended
    and preserve any unresolved recovery manifest.

    This function does not commit, roll back, close connections,
    resolve manifests, or authorize runtime execution.
    """
    from sqlalchemy import text

    released = connection.execute(
        text(
            "SELECT pg_catalog.pg_advisory_unlock("
            ":namespace, :identifier)"
        ),
        {
            "namespace": LIFECYCLE_LOCK_NAMESPACE,
            "identifier": LIFECYCLE_LOCK_IDENTIFIER,
        },
    ).scalar_one()

    if released is not True:
        raise RuntimeError(
            "Lifecycle coordination lock release not confirmed."
        )


def validate_disposable_database_url():
    """Validate explicitly authorized disposable connection settings.

    Return a validated SQLAlchemy URL without opening a connection.

    The returned URL contains credentials and must never be
    logged, serialized, or included in recovery manifests.

    Connection settings alone do not establish actual database
    identity or authorize fixture creation or cleanup.
    """
    from sqlalchemy.engine import make_url

    if os.getenv("PHASE5E_0026_DISPOSABLE_TEST") != "YES":
        raise RuntimeError(
            "Explicit disposable PostgreSQL opt-in required."
        )

    raw_url = os.getenv(
        "PHASE5E_0026_TEST_DATABASE_URL"
    )

    if not raw_url:
        raise RuntimeError(
            "Disposable PostgreSQL connection settings required."
        )

    try:
        url = make_url(raw_url)

        approved = (
            url.drivername == EXPECTED_DRIVER
            and url.host == EXPECTED_HOST
            and url.port == EXPECTED_PORT
            and url.database == EXPECTED_DATABASE
            and url.username == EXPECTED_USER
            and bool(url.password)
            and not url.query
        )

    except Exception:
        raise RuntimeError(
            "Invalid disposable PostgreSQL connection settings."
        ) from None

    if not approved:
        raise RuntimeError(
            "Unapproved disposable PostgreSQL connection settings."
        )

    return url


def verify_connected_database_revision(connection) -> None:
    """Verify the connected disposable PostgreSQL migration target.

    This function performs read-only verification on an existing
    connection. It does not acquire locks, modify records, commit
    transactions, or authorize fixture execution or cleanup.
    """
    from sqlalchemy import text

    approved_url = validate_disposable_database_url()

    if connection.engine.url != approved_url:
        raise RuntimeError(
            "Connected PostgreSQL settings mismatch."
        )

    database, username, session_username, in_recovery = (
        connection.execute(
            text(
                "SELECT pg_catalog.current_database(), "
                "current_user, session_user, "
                "pg_catalog.pg_is_in_recovery()"
            )
        ).one()
    )

    if (
        database != EXPECTED_DATABASE
        or username != EXPECTED_USER
        or session_username != EXPECTED_USER
    ):
        raise RuntimeError(
            "Connected PostgreSQL identity mismatch."
        )

    if in_recovery is not False:
        raise RuntimeError(
            "Writable disposable PostgreSQL target not confirmed."
        )

    revision = connection.execute(
        text(
            "SELECT version_num "
            "FROM public.alembic_version"
        )
    ).scalar_one()

    if revision != EXPECTED_REVISION:
        raise RuntimeError(
            "Connected PostgreSQL migration revision mismatch."
        )


def reject_postgresql_environment_overrides() -> None:
    """Reject ambient PostgreSQL environment configuration.

    Dedicated disposable recovery connections must not inherit
    uncontrolled PostgreSQL connection or session settings.

    This intentionally conservative policy rejects all PG-prefixed
    environment variable names, including empty values.

    Environment variable names and values are not included in
    error messages. This function does not modify the environment.
    """
    if any(
        name.upper().startswith("PG")
        for name in os.environ
    ):
        raise RuntimeError(
            "PostgreSQL environment overrides are not permitted."
        )


def create_lifecycle_coordination_engine():
    """Create a dedicated non-pooled disposable PostgreSQL engine.

    Validate explicit authorization and approved connection
    settings before constructing the SQLAlchemy engine.

    Engine creation does not establish a physical connection.
    The caller must verify connected database identity and
    migration revision before acquiring lifecycle coordination.

    The caller owns connection closure and engine disposal.
    This factory does not authorize fixture execution or cleanup.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    approved_url = validate_disposable_database_url()
    reject_postgresql_environment_overrides()

    try:
        engine = create_engine(
            approved_url,
            poolclass=NullPool,
            pool_pre_ping=False,
            echo=False,
            echo_pool=False,
            hide_parameters=True,
            connect_args={"connect_timeout": 5},
        )
    except Exception:
        raise RuntimeError(
            "Disposable PostgreSQL engine creation failed."
        ) from None

    return engine
