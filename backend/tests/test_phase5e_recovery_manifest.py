"""Offline regression tests for Phase 5E recovery safeguards."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest

import phase5e_recovery_manifest as recovery


# Synthetic identifiers for offline tests only.
SYNTHETIC_INSTANCE_IDENTITY = {
    "system_identifier": "7523456789012345678",
    "database_oid": 16384,
}


@pytest.fixture
def fixture_ids():
    return {
        key: str(uuid4())
        for key in recovery.REQUIRED_FIXTURE_IDS
    }


@pytest.fixture
def manifest(fixture_ids):
    return recovery.build_manifest(fixture_ids, instance_identity=SYNTHETIC_INSTANCE_IDENTITY)


def test_fixture_identifier_count(fixture_ids):
    assert len(fixture_ids) == 20
    assert len(set(fixture_ids.values())) == 20


def test_valid_fixture_identifiers(fixture_ids):
    validated = recovery.validate_fixture_ids(fixture_ids)

    assert validated == fixture_ids
    assert validated is not fixture_ids


@pytest.mark.parametrize(
    "invalid_case",
    [
        "missing",
        "unexpected",
        "malformed",
        "duplicate",
        "uppercase",
        "zero",
        "non_string",
    ],
)
def test_invalid_fixture_identifiers(fixture_ids, invalid_case):
    keys = sorted(fixture_ids)

    if invalid_case == "missing":
        fixture_ids.pop(keys[0])
    elif invalid_case == "unexpected":
        fixture_ids["unexpected"] = str(uuid4())
    elif invalid_case == "malformed":
        fixture_ids[keys[0]] = "invalid-uuid"
    elif invalid_case == "duplicate":
        fixture_ids[keys[0]] = fixture_ids[keys[1]]
    elif invalid_case == "uppercase":
        fixture_ids[keys[0]] = (
            "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"
        )
    elif invalid_case == "zero":
        fixture_ids[keys[0]] = (
            "00000000-0000-0000-0000-000000000000"
        )
    elif invalid_case == "non_string":
        fixture_ids[keys[0]] = 123

    with pytest.raises(ValueError):
        recovery.validate_fixture_ids(fixture_ids)


def test_valid_manifest(manifest):
    assert recovery.validate_manifest(manifest) == manifest


def test_manifest_builder_generates_unique_runs(fixture_ids):
    first = recovery.build_manifest(fixture_ids, instance_identity=SYNTHETIC_INSTANCE_IDENTITY)
    second = recovery.build_manifest(fixture_ids, instance_identity=SYNTHETIC_INSTANCE_IDENTITY)

    assert first["run_id"] != second["run_id"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("manifest_version", 999),
        ("manifest_version", True),
        ("run_id", "invalid"),
        ("test_name", "unexpected_test"),
        ("created_at", "invalid"),
        ("created_at", "2026-11-17T12:00:00"),
        ("created_at", "2026-11-17T12:00:00-05:00"),
        ("status", "resolved"),
    ],
)
def test_invalid_manifest_fields(manifest, field, value):
    invalid = deepcopy(manifest)
    invalid[field] = value

    with pytest.raises(ValueError):
        recovery.validate_manifest(invalid)


@pytest.mark.parametrize(
    "field,value",
    [
        ("driver", "sqlite"),
        ("host", "production_db"),
        ("port", 5433),
        ("port", "5432"),
        ("database", "production"),
        ("user", "postgres"),
        ("revision", "0025"),
    ],
)
def test_invalid_database_identity(manifest, field, value):
    manifest["database_identity"][field] = value

    with pytest.raises(ValueError):
        recovery.validate_manifest(manifest)


def test_unexpected_secret_field_rejected(manifest):
    manifest["password"] = "synthetic-placeholder"

    with pytest.raises(ValueError):
        recovery.validate_manifest(manifest)


def test_missing_manifest_field_rejected(manifest):
    manifest.pop("fixture_ids")

    with pytest.raises(ValueError):
        recovery.validate_manifest(manifest)


def test_persist_manifest(manifest, tmp_path, monkeypatch):
    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", tmp_path
    )

    path = recovery.persist_manifest(manifest)

    assert path == tmp_path / recovery.ACTIVE_MANIFEST_NAME

    loaded = json.loads(path.read_bytes())

    assert recovery.validate_manifest(loaded) == manifest


def test_existing_manifest_preserved(
    manifest, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", tmp_path
    )

    path = recovery.persist_manifest(manifest)
    original = path.read_bytes()

    with pytest.raises((RuntimeError, FileExistsError)):
        recovery.persist_manifest(manifest)

    assert path.read_bytes() == original


def test_unexpected_directory_entry_blocks_persistence(
    manifest, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", tmp_path
    )

    unknown = tmp_path / "unknown.txt"
    unknown.write_text("synthetic", encoding="utf-8")

    with pytest.raises(RuntimeError):
        recovery.persist_manifest(manifest)

    assert unknown.read_text(encoding="utf-8") == "synthetic"
    assert not (
        tmp_path / recovery.ACTIVE_MANIFEST_NAME
    ).exists()


def test_invalid_manifest_not_persisted(
    manifest, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", tmp_path
    )

    manifest["status"] = "invalid"

    with pytest.raises(ValueError):
        recovery.persist_manifest(manifest)

    assert list(tmp_path.iterdir()) == []


def test_concurrent_manifest_creation(
    fixture_ids, tmp_path, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", tmp_path
    )

    manifests = [
        recovery.build_manifest(fixture_ids, instance_identity=SYNTHETIC_INSTANCE_IDENTITY),
        recovery.build_manifest(fixture_ids, instance_identity=SYNTHETIC_INSTANCE_IDENTITY),
    ]

    barrier = Barrier(2, timeout=5)

    def attempt(manifest):
        barrier.wait()

        try:
            recovery.persist_manifest(manifest)
        except (RuntimeError, FileExistsError):
            return None

        return manifest

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, manifests))

    winners = [
        result for result in results
        if result is not None
    ]

    assert len(winners) == 1

    path = tmp_path / recovery.ACTIVE_MANIFEST_NAME

    assert recovery.validate_manifest(
        json.loads(path.read_bytes())
    ) == winners[0]


def test_interrupted_write_preserves_recovery_marker(
    manifest, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", tmp_path
    )

    original_write = recovery.os.write

    def interrupted_write(fd, payload):
        original_write(fd, payload[:16])
        raise OSError("Synthetic interrupted write.")

    with monkeypatch.context() as patch:
        patch.setattr(
            recovery.os, "write", interrupted_write
        )

        with pytest.raises(OSError):
            recovery.persist_manifest(manifest)

    path = tmp_path / recovery.ACTIVE_MANIFEST_NAME

    assert path.is_file()

    original = path.read_bytes()

    assert len(original) == 16

    with pytest.raises((RuntimeError, FileExistsError)):
        recovery.persist_manifest(manifest)

    assert path.read_bytes() == original


def test_sync_failure_preserves_recovery_marker(
    manifest, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", tmp_path
    )

    def failed_sync(fd):
        raise OSError("Synthetic synchronization failure.")

    with monkeypatch.context() as patch:
        patch.setattr(recovery.os, "fsync", failed_sync)

        with pytest.raises(OSError):
            recovery.persist_manifest(manifest)

    path = tmp_path / recovery.ACTIVE_MANIFEST_NAME

    assert path.is_file()

    original = path.read_bytes()

    with pytest.raises((RuntimeError, FileExistsError)):
        recovery.persist_manifest(manifest)

    assert path.read_bytes() == original


def test_symbolic_link_recovery_directory_rejected(
    manifest, tmp_path, monkeypatch
):
    actual = tmp_path / "actual"
    actual.mkdir()

    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)

    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", linked
    )

    with pytest.raises(OSError):
        recovery.persist_manifest(manifest)

    assert list(actual.iterdir()) == []


def test_missing_recovery_directory_rejected(
    manifest, tmp_path, monkeypatch
):
    missing = tmp_path / "missing"

    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", missing
    )

    with pytest.raises(FileNotFoundError):
        recovery.persist_manifest(manifest)

    assert not missing.exists()


def test_load_valid_manifest(
    manifest, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", tmp_path
    )

    recovery.persist_manifest(manifest)

    assert recovery.load_active_manifest() == manifest


def test_load_empty_recovery_directory(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", tmp_path
    )

    with pytest.raises(RuntimeError):
        recovery.load_active_manifest()

    assert list(tmp_path.iterdir()) == []


def test_load_unexpected_directory_contents(
    manifest, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", tmp_path
    )

    path = recovery.persist_manifest(manifest)
    original = path.read_bytes()

    unknown = tmp_path / "unknown.txt"
    unknown.write_text("synthetic", encoding="utf-8")

    with pytest.raises(RuntimeError):
        recovery.load_active_manifest()

    assert path.read_bytes() == original
    assert unknown.read_text(encoding="utf-8") == "synthetic"


@pytest.mark.parametrize(
    "payload",
    [
        b"{invalid",
        b'{"status":"pending_cleanup","status":"resolved"}',
        b"\xff\xfe\xff",
        b"",
        b"x" * (recovery.MAX_MANIFEST_BYTES + 1),
    ],
    ids=[
        "malformed_json",
        "duplicate_keys",
        "invalid_utf8",
        "empty_manifest",
        "oversized_manifest",
    ],
)
def test_load_invalid_manifest_content(
    payload, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", tmp_path
    )

    path = tmp_path / recovery.ACTIVE_MANIFEST_NAME
    path.write_bytes(payload)

    with pytest.raises(ValueError):
        recovery.load_active_manifest()

    assert path.read_bytes() == payload


def test_load_symbolic_link_manifest(
    manifest, tmp_path, monkeypatch
):
    recovery_dir = tmp_path / "recovery"
    recovery_dir.mkdir()

    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", recovery_dir
    )

    target = tmp_path / "target.json"
    target.write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    original = target.read_bytes()

    path = recovery_dir / recovery.ACTIVE_MANIFEST_NAME
    path.symlink_to(target)

    with pytest.raises(OSError):
        recovery.load_active_manifest()

    assert path.is_symlink()
    assert target.read_bytes() == original


def test_load_nonregular_manifest(
    tmp_path, monkeypatch
):
    import os
    import stat

    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", tmp_path
    )

    path = tmp_path / recovery.ACTIVE_MANIFEST_NAME
    os.mkfifo(path)

    with pytest.raises(ValueError):
        recovery.load_active_manifest()

    assert stat.S_ISFIFO(path.lstat().st_mode)


def test_load_invalid_database_identity(
    manifest, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", tmp_path
    )

    manifest["database_identity"]["database"] = "unexpected"

    path = tmp_path / recovery.ACTIVE_MANIFEST_NAME
    path.write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    original = path.read_bytes()

    with pytest.raises(ValueError):
        recovery.load_active_manifest()

    assert path.read_bytes() == original


def test_load_preserves_manifest_content(
    manifest, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        recovery, "RECOVERY_DIRECTORY", tmp_path
    )

    path = recovery.persist_manifest(manifest)

    original = path.read_bytes()
    original_mtime = path.stat().st_mtime_ns

    first = recovery.load_active_manifest()
    second = recovery.load_active_manifest()

    assert first == second == manifest
    assert first is not second
    assert path.read_bytes() == original
    assert path.stat().st_mtime_ns == original_mtime


class _SyntheticVerificationConnection:
    """Offline database substitute for absence verification tests."""

    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def execute(self, statement, parameters):
        self.calls.append(
            (str(statement), dict(parameters))
        )

        result = next(self.results)

        if isinstance(result, Exception):
            raise result

        return _SyntheticVerificationResult(result)


class _SyntheticVerificationResult:

    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


def test_verify_all_fixture_records_absent(fixture_ids):
    connection = _SyntheticVerificationConnection([0] * 20)

    assert recovery.verify_fixture_absence(
        connection, fixture_ids
    ) == 20

    assert len(connection.calls) == 20

    expected = [
        (
            f"SELECT count(*) FROM {table} WHERE id = :id",
            {"id": fixture_ids[identity]},
        )
        for table, identity
        in recovery.FIXTURE_VERIFICATION_TARGETS
    ]

    assert connection.calls == expected

    assert {
        parameters["id"]
        for _, parameters in connection.calls
    } == set(fixture_ids.values())


@pytest.mark.parametrize("position", [0, 10, 19])
def test_verify_remaining_fixture_record(
    fixture_ids, position
):
    results = [0] * 20
    results[position] = 1

    connection = _SyntheticVerificationConnection(results)

    with pytest.raises(
        RuntimeError,
        match="Fixture absence not established",
    ):
        recovery.verify_fixture_absence(
            connection, fixture_ids
        )

    assert len(connection.calls) == position + 1


def test_verify_invalid_fixture_identifiers(fixture_ids):
    fixture_ids.pop("client")

    connection = _SyntheticVerificationConnection([])

    with pytest.raises(ValueError):
        recovery.verify_fixture_absence(
            connection, fixture_ids
        )

    assert connection.calls == []


def test_verify_database_query_failure(fixture_ids):
    failure = RuntimeError("Synthetic database query failure.")

    connection = _SyntheticVerificationConnection(
        [0, 0, failure]
    )

    with pytest.raises(RuntimeError) as captured:
        recovery.verify_fixture_absence(
            connection, fixture_ids
        )

    assert captured.value is failure
    assert len(connection.calls) == 3


def test_verify_invalid_query_result(fixture_ids):
    connection = _SyntheticVerificationConnection([False])

    with pytest.raises(RuntimeError):
        recovery.verify_fixture_absence(
            connection, fixture_ids
        )

    assert len(connection.calls) == 1


def test_verify_incomplete_target_configuration(
    fixture_ids, monkeypatch
):
    monkeypatch.setattr(
        recovery,
        "FIXTURE_VERIFICATION_TARGETS",
        recovery.FIXTURE_VERIFICATION_TARGETS[:-1],
    )

    connection = _SyntheticVerificationConnection([])

    with pytest.raises(
        RuntimeError,
        match="Incomplete fixture verification configuration",
    ):
        recovery.verify_fixture_absence(
            connection, fixture_ids
        )

    assert connection.calls == []


@pytest.mark.parametrize(
    "system_identifier,database_oid",
    [
        ("1", 1),
        ("7523456789012345678", 16384),
        ("18446744073709551615", 4294967295),
    ],
)
def test_valid_database_instance_identity(
    system_identifier, database_oid
):
    identity = {
        "system_identifier": system_identifier,
        "database_oid": database_oid,
    }

    validated = recovery.validate_database_instance_identity(
        identity
    )

    assert validated == identity
    assert validated is not identity


@pytest.mark.parametrize(
    "invalid_identifier",
    [
        "",
        "0",
        "01",
        "-1",
        "+1",
        " 123",
        "123 ",
        "1.5",
        "abc",
        "\u0661\u0662\u0663",
        "18446744073709551616",
        "9" * 21,
        123,
        True,
    ],
)
def test_invalid_database_system_identifier(
    invalid_identifier
):
    identity = {
        "system_identifier": invalid_identifier,
        "database_oid": 16384,
    }

    with pytest.raises(ValueError):
        recovery.validate_database_instance_identity(
            identity
        )


@pytest.mark.parametrize(
    "invalid_oid",
    [
        0,
        -1,
        4294967296,
        "16384",
        16384.0,
        True,
    ],
)
def test_invalid_database_oid(invalid_oid):
    identity = {
        "system_identifier": "7523456789012345678",
        "database_oid": invalid_oid,
    }

    with pytest.raises(ValueError):
        recovery.validate_database_instance_identity(
            identity
        )


@pytest.mark.parametrize(
    "invalid_identity",
    [
        None,
        {"system_identifier": "123"},
        {
            "system_identifier": "123",
            "database_oid": 16384,
            "unexpected": "synthetic",
        },
    ],
)
def test_invalid_database_instance_identity_fields(
    invalid_identity
):
    with pytest.raises(ValueError):
        recovery.validate_database_instance_identity(
            invalid_identity
        )


def test_manifest_version_two(manifest):
    assert recovery.MANIFEST_VERSION == 2
    assert manifest["manifest_version"] == 2


def test_manifest_preserves_instance_identity(manifest):
    identity = manifest["database_identity"]

    assert identity == {
        **recovery.expected_database_identity(),
        **SYNTHETIC_INSTANCE_IDENTITY,
    }

    assert len(identity) == 8


def test_legacy_manifest_version_rejected(manifest):
    manifest["manifest_version"] = 1
    manifest["database_identity"].pop("system_identifier")
    manifest["database_identity"].pop("database_oid")

    with pytest.raises(
        ValueError,
        match="Unsupported recovery manifest version",
    ):
        recovery.validate_manifest(manifest)


@pytest.mark.parametrize(
    "missing_field",
    ["system_identifier", "database_oid"],
)
def test_manifest_missing_instance_identifier(
    manifest, missing_field
):
    manifest["database_identity"].pop(missing_field)

    with pytest.raises(ValueError):
        recovery.validate_manifest(manifest)


@pytest.mark.parametrize(
    "field,value",
    [
        ("system_identifier", "0"),
        ("system_identifier", 123),
        ("database_oid", 0),
        ("database_oid", True),
    ],
)
def test_manifest_invalid_instance_identifier(
    manifest, field, value
):
    manifest["database_identity"][field] = value

    with pytest.raises(ValueError):
        recovery.validate_manifest(manifest)


def test_manifest_unexpected_instance_identity_field(manifest):
    manifest["database_identity"]["unexpected"] = "synthetic"

    with pytest.raises(ValueError):
        recovery.validate_manifest(manifest)


def test_manifest_builder_requires_instance_identity(fixture_ids):
    with pytest.raises(TypeError):
        recovery.build_manifest(fixture_ids)


def test_manifest_builder_rejects_invalid_instance_identity(
    fixture_ids
):
    with pytest.raises(ValueError):
        recovery.build_manifest(
            fixture_ids,
            instance_identity={
                "system_identifier": "0",
                "database_oid": 16384,
            },
        )


class _SyntheticIdentityConnection:
    """Simulated connection for offline identity retrieval tests."""

    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def execute(self, statement):
        self.calls.append(str(statement))
        result = next(self.results)

        if isinstance(result, Exception):
            raise result

        return _SyntheticIdentityResult(result)


class _SyntheticIdentityResult:
    def __init__(self, value):
        self.value = value

    def one(self):
        return self.value


def test_read_database_instance_identity(monkeypatch):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    connection = _SyntheticIdentityConnection(
        [
            (recovery.EXPECTED_DATABASE, recovery.EXPECTED_USER),
            ("7523456789012345678", 16384),
        ]
    )

    identity = recovery.read_database_instance_identity(
        connection
    )

    assert identity == SYNTHETIC_INSTANCE_IDENTITY
    assert len(connection.calls) == 2

    assert connection.calls[0] == (
        "SELECT pg_catalog.current_database(), current_user"
    )

    assert connection.calls[1] == (
        "SELECT CAST(control.system_identifier AS text), "
        "CAST(database.oid AS bigint) "
        "FROM pg_catalog.pg_control_system() AS control "
        "CROSS JOIN pg_catalog.pg_database AS database "
        "WHERE database.datname = pg_catalog.current_database()"
    )


@pytest.mark.parametrize(
    "opt_in",
    [None, "", "NO", "yes"],
)
def test_read_database_identity_requires_opt_in(
    monkeypatch, opt_in
):
    if opt_in is None:
        monkeypatch.delenv(
            "PHASE5E_0026_DISPOSABLE_TEST",
            raising=False,
        )
    else:
        monkeypatch.setenv(
            "PHASE5E_0026_DISPOSABLE_TEST", opt_in
        )

    connection = _SyntheticIdentityConnection([])

    with pytest.raises(
        RuntimeError,
        match="Explicit disposable PostgreSQL opt-in required",
    ):
        recovery.read_database_instance_identity(connection)

    assert connection.calls == []


@pytest.mark.parametrize(
    "database,username",
    [
        ("unexpected_database", recovery.EXPECTED_USER),
        (recovery.EXPECTED_DATABASE, "unexpected_user"),
    ],
)
def test_read_database_identity_rejects_wrong_target(
    monkeypatch, database, username
):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    connection = _SyntheticIdentityConnection(
        [(database, username)]
    )

    with pytest.raises(
        RuntimeError,
        match="Connected PostgreSQL identity mismatch",
    ):
        recovery.read_database_instance_identity(connection)

    assert len(connection.calls) == 1


@pytest.mark.parametrize(
    "identifier,oid",
    [
        ("0", 16384),
        ("7523456789012345678", 0),
        (123, 16384),
    ],
)
def test_read_database_identity_rejects_invalid_results(
    monkeypatch, identifier, oid
):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    connection = _SyntheticIdentityConnection(
        [
            (recovery.EXPECTED_DATABASE, recovery.EXPECTED_USER),
            (identifier, oid),
        ]
    )

    with pytest.raises(ValueError):
        recovery.read_database_instance_identity(connection)

    assert len(connection.calls) == 2


@pytest.mark.parametrize("failure_position", [0, 1])
def test_read_database_identity_query_failure(
    monkeypatch, failure_position
):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    failure = RuntimeError("Synthetic database query failure.")

    results = [
        (recovery.EXPECTED_DATABASE, recovery.EXPECTED_USER),
        ("7523456789012345678", 16384),
    ]

    results[failure_position] = failure

    connection = _SyntheticIdentityConnection(results)

    with pytest.raises(RuntimeError) as captured:
        recovery.read_database_instance_identity(connection)

    assert captured.value is failure
    assert len(connection.calls) == failure_position + 1


def test_verify_matching_manifest_database_identity(
    manifest, monkeypatch
):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    connection = _SyntheticIdentityConnection(
        [
            (recovery.EXPECTED_DATABASE, recovery.EXPECTED_USER),
            ("7523456789012345678", 16384),
        ]
    )

    original = deepcopy(manifest)

    result = recovery.verify_manifest_database_identity(
        connection, manifest
    )

    assert result is None
    assert len(connection.calls) == 2
    assert manifest == original


@pytest.mark.parametrize(
    "identifier,oid",
    [
        ("7523456789012345679", 16384),
        ("7523456789012345678", 16385),
        ("7523456789012345679", 16385),
    ],
)
def test_verify_mismatched_manifest_database_identity(
    manifest, monkeypatch, identifier, oid
):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    connection = _SyntheticIdentityConnection(
        [
            (recovery.EXPECTED_DATABASE, recovery.EXPECTED_USER),
            (identifier, oid),
        ]
    )

    original = deepcopy(manifest)

    with pytest.raises(
        RuntimeError,
        match="Recovery database instance identity mismatch",
    ):
        recovery.verify_manifest_database_identity(
            connection, manifest
        )

    assert len(connection.calls) == 2
    assert manifest == original


def test_verify_manifest_identity_rejects_invalid_manifest(
    manifest, monkeypatch
):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    manifest["database_identity"].pop("database_oid")

    connection = _SyntheticIdentityConnection([])

    with pytest.raises(ValueError):
        recovery.verify_manifest_database_identity(
            connection, manifest
        )

    assert connection.calls == []


def test_verify_manifest_identity_requires_opt_in(
    manifest, monkeypatch
):
    monkeypatch.delenv(
        "PHASE5E_0026_DISPOSABLE_TEST",
        raising=False,
    )

    connection = _SyntheticIdentityConnection([])

    with pytest.raises(
        RuntimeError,
        match="Explicit disposable PostgreSQL opt-in required",
    ):
        recovery.verify_manifest_database_identity(
            connection, manifest
        )

    assert connection.calls == []


def test_verify_manifest_identity_rejects_wrong_database(
    manifest, monkeypatch
):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    connection = _SyntheticIdentityConnection(
        [
            ("unexpected_database", recovery.EXPECTED_USER),
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="Connected PostgreSQL identity mismatch",
    ):
        recovery.verify_manifest_database_identity(
            connection, manifest
        )

    assert len(connection.calls) == 1


def test_verify_manifest_identity_propagates_query_failure(
    manifest, monkeypatch
):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    failure = RuntimeError("Synthetic identity query failure.")

    connection = _SyntheticIdentityConnection(
        [
            (recovery.EXPECTED_DATABASE, recovery.EXPECTED_USER),
            failure,
        ]
    )

    original = deepcopy(manifest)

    with pytest.raises(RuntimeError) as captured:
        recovery.verify_manifest_database_identity(
            connection, manifest
        )

    assert captured.value is failure
    assert len(connection.calls) == 2
    assert manifest == original


class _SyntheticLifecycleLockResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class _SyntheticLifecycleLockConnection:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def execute(self, statement, parameters):
        self.calls.append(
            (str(statement), dict(parameters))
        )

        result = next(self.results)

        if isinstance(result, Exception):
            raise result

        return _SyntheticLifecycleLockResult(result)


def test_acquire_lifecycle_lock(monkeypatch):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    connection = _SyntheticLifecycleLockConnection([True])

    assert recovery.acquire_lifecycle_lock(connection) is None

    assert connection.calls == [
        (
            "SELECT pg_catalog.pg_try_advisory_lock("
            ":namespace, :identifier)",
            {"namespace": 481516, "identifier": 1497},
        )
    ]


@pytest.mark.parametrize(
    "authorization", [None, "", "NO", "yes"]
)
def test_acquire_lifecycle_lock_requires_opt_in(
    monkeypatch, authorization
):
    if authorization is None:
        monkeypatch.delenv(
            "PHASE5E_0026_DISPOSABLE_TEST",
            raising=False,
        )
    else:
        monkeypatch.setenv(
            "PHASE5E_0026_DISPOSABLE_TEST",
            authorization,
        )

    connection = _SyntheticLifecycleLockConnection([])

    with pytest.raises(
        RuntimeError,
        match="Explicit disposable PostgreSQL opt-in required",
    ):
        recovery.acquire_lifecycle_lock(connection)

    assert connection.calls == []


@pytest.mark.parametrize(
    "result", [False, None, 0, 1, "true"]
)
def test_acquire_lifecycle_lock_rejects_unconfirmed_result(
    monkeypatch, result
):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    connection = _SyntheticLifecycleLockConnection([result])

    with pytest.raises(
        RuntimeError,
        match="Lifecycle coordination lock not acquired",
    ):
        recovery.acquire_lifecycle_lock(connection)

    assert len(connection.calls) == 1


def test_acquire_lifecycle_lock_propagates_query_failure(
    monkeypatch
):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    failure = RuntimeError("Synthetic lock acquisition failure.")

    connection = _SyntheticLifecycleLockConnection([failure])

    with pytest.raises(RuntimeError) as captured:
        recovery.acquire_lifecycle_lock(connection)

    assert captured.value is failure
    assert len(connection.calls) == 1


def test_release_lifecycle_lock(monkeypatch):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    connection = _SyntheticLifecycleLockConnection([True])

    assert recovery.release_lifecycle_lock(connection) is None

    assert connection.calls == [
        (
            "SELECT pg_catalog.pg_advisory_unlock("
            ":namespace, :identifier)",
            {"namespace": 481516, "identifier": 1497},
        )
    ]


@pytest.mark.parametrize(
    "result", [False, None, 0, 1, "true"]
)
def test_release_lifecycle_lock_rejects_unconfirmed_result(
    result
):
    connection = _SyntheticLifecycleLockConnection([result])

    with pytest.raises(
        RuntimeError,
        match="Lifecycle coordination lock release not confirmed",
    ):
        recovery.release_lifecycle_lock(connection)

    assert len(connection.calls) == 1


def test_release_lifecycle_lock_after_authorization_withdrawal(
    monkeypatch
):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    connection = _SyntheticLifecycleLockConnection(
        [True, True]
    )

    recovery.acquire_lifecycle_lock(connection)

    monkeypatch.delenv(
        "PHASE5E_0026_DISPOSABLE_TEST",
        raising=False,
    )

    recovery.release_lifecycle_lock(connection)

    assert len(connection.calls) == 2


def test_release_lifecycle_lock_propagates_query_failure():
    failure = RuntimeError("Synthetic lock release failure.")

    connection = _SyntheticLifecycleLockConnection([failure])

    with pytest.raises(RuntimeError) as captured:
        recovery.release_lifecycle_lock(connection)

    assert captured.value is failure
    assert len(connection.calls) == 1


SYNTHETIC_DISPOSABLE_DATABASE_URL = (
    "postgresql+psycopg://"
    "geovaris_migration_test:synthetic-placeholder"
    "@migration_test_db:5432/"
    "geovaris_phase5e_migration_test"
)


def test_validate_disposable_database_url(monkeypatch):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    monkeypatch.setenv(
        "PHASE5E_0026_TEST_DATABASE_URL",
        SYNTHETIC_DISPOSABLE_DATABASE_URL,
    )

    url = recovery.validate_disposable_database_url()

    assert url.drivername == recovery.EXPECTED_DRIVER
    assert url.host == recovery.EXPECTED_HOST
    assert url.port == recovery.EXPECTED_PORT
    assert url.database == recovery.EXPECTED_DATABASE
    assert url.username == recovery.EXPECTED_USER
    assert url.password == "synthetic-placeholder"
    assert not url.query


@pytest.mark.parametrize(
    "authorization", [None, "", "NO", "yes"]
)
def test_disposable_database_url_requires_opt_in(
    monkeypatch, authorization
):
    if authorization is None:
        monkeypatch.delenv(
            "PHASE5E_0026_DISPOSABLE_TEST",
            raising=False,
        )
    else:
        monkeypatch.setenv(
            "PHASE5E_0026_DISPOSABLE_TEST",
            authorization,
        )

    monkeypatch.setenv(
        "PHASE5E_0026_TEST_DATABASE_URL",
        SYNTHETIC_DISPOSABLE_DATABASE_URL,
    )

    with pytest.raises(
        RuntimeError,
        match="Explicit disposable PostgreSQL opt-in required",
    ):
        recovery.validate_disposable_database_url()


@pytest.mark.parametrize("raw_url", [None, ""])
def test_disposable_database_url_requires_settings(
    monkeypatch, raw_url
):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    if raw_url is None:
        monkeypatch.delenv(
            "PHASE5E_0026_TEST_DATABASE_URL",
            raising=False,
        )
    else:
        monkeypatch.setenv(
            "PHASE5E_0026_TEST_DATABASE_URL",
            raw_url,
        )

    with pytest.raises(
        RuntimeError,
        match="Disposable PostgreSQL connection settings required",
    ):
        recovery.validate_disposable_database_url()


@pytest.mark.parametrize(
    "original_value,replacement",
    [
        ("postgresql+psycopg", "postgresql"),
        ("postgresql+psycopg", "postgresql+psycopg2"),
        ("@migration_test_db", "@unexpected_host"),
        (":5432/", ":5433/"),
        (":5432/", "/"),
        ("/geovaris_phase5e_migration_test", "/unexpected_database"),
        ("//geovaris_migration_test:", "//unexpected_user:"),
        (":synthetic-placeholder@", "@"),
        (":synthetic-placeholder@", ":@"),
        (
            "/geovaris_phase5e_migration_test",
            "/geovaris_phase5e_migration_test?sslmode=disable",
        ),
    ],
)
def test_disposable_database_url_rejects_unapproved_settings(
    monkeypatch, original_value, replacement
):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    raw_url = SYNTHETIC_DISPOSABLE_DATABASE_URL.replace(
        original_value, replacement
    )

    assert raw_url != SYNTHETIC_DISPOSABLE_DATABASE_URL

    monkeypatch.setenv(
        "PHASE5E_0026_TEST_DATABASE_URL",
        raw_url,
    )

    with pytest.raises(
        RuntimeError,
        match="Unapproved disposable PostgreSQL connection settings",
    ) as captured:
        recovery.validate_disposable_database_url()

    assert "synthetic-placeholder" not in str(captured.value)
    assert raw_url not in str(captured.value)


@pytest.mark.parametrize(
    "raw_url",
    [
        "malformed-synthetic-placeholder",
        SYNTHETIC_DISPOSABLE_DATABASE_URL.replace(
            ":5432/", ":invalid-port/"
        ),
    ],
)
def test_disposable_database_url_rejects_malformed_settings(
    monkeypatch, raw_url
):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    monkeypatch.setenv(
        "PHASE5E_0026_TEST_DATABASE_URL",
        raw_url,
    )

    with pytest.raises(
        RuntimeError,
        match="Invalid disposable PostgreSQL connection settings",
    ) as captured:
        recovery.validate_disposable_database_url()

    assert "synthetic-placeholder" not in str(captured.value)
    assert raw_url not in str(captured.value)
    assert captured.value.__suppress_context__ is True


class _SyntheticRevisionResult:
    def __init__(self, value):
        self.value = value

    def one(self):
        return self.value

    def scalar_one(self):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class _SyntheticRevisionConnection:
    def __init__(self, url, results):
        from types import SimpleNamespace

        self.engine = SimpleNamespace(url=url)
        self.results = iter(results)
        self.calls = []

    def execute(self, statement):
        self.calls.append(str(statement))

        result = next(self.results)

        if isinstance(result, Exception):
            raise result

        return _SyntheticRevisionResult(result)


SYNTHETIC_CONNECTED_DATABASE_IDENTITY = (
    "geovaris_phase5e_migration_test",
    "geovaris_migration_test",
    "geovaris_migration_test",
    False,
)


@pytest.fixture
def approved_revision_url(monkeypatch):
    monkeypatch.setenv(
        "PHASE5E_0026_DISPOSABLE_TEST", "YES"
    )

    monkeypatch.setenv(
        "PHASE5E_0026_TEST_DATABASE_URL",
        SYNTHETIC_DISPOSABLE_DATABASE_URL,
    )

    return recovery.validate_disposable_database_url()


def test_verify_connected_database_revision(
    approved_revision_url
):
    connection = _SyntheticRevisionConnection(
        approved_revision_url,
        [SYNTHETIC_CONNECTED_DATABASE_IDENTITY, "0026"],
    )

    assert recovery.verify_connected_database_revision(
        connection
    ) is None

    assert connection.calls == [
        "SELECT pg_catalog.current_database(), "
        "current_user, session_user, "
        "pg_catalog.pg_is_in_recovery()",
        "SELECT version_num FROM public.alembic_version",
    ]


def test_verify_connected_revision_requires_opt_in(
    monkeypatch, approved_revision_url
):
    monkeypatch.delenv(
        "PHASE5E_0026_DISPOSABLE_TEST",
        raising=False,
    )

    connection = _SyntheticRevisionConnection(
        approved_revision_url, []
    )

    with pytest.raises(
        RuntimeError,
        match="Explicit disposable PostgreSQL opt-in required",
    ):
        recovery.verify_connected_database_revision(connection)

    assert connection.calls == []


def test_verify_connected_revision_requires_matching_url(
    approved_revision_url
):
    mismatched_url = approved_revision_url.set(
        host="unexpected_host"
    )

    connection = _SyntheticRevisionConnection(
        mismatched_url, []
    )

    with pytest.raises(
        RuntimeError,
        match="Connected PostgreSQL settings mismatch",
    ):
        recovery.verify_connected_database_revision(connection)

    assert connection.calls == []


@pytest.mark.parametrize("position", [0, 1, 2])
def test_verify_connected_revision_rejects_wrong_identity(
    approved_revision_url, position
):
    identity = list(SYNTHETIC_CONNECTED_DATABASE_IDENTITY)
    identity[position] = "unexpected_identity"

    connection = _SyntheticRevisionConnection(
        approved_revision_url, [tuple(identity)]
    )

    with pytest.raises(
        RuntimeError,
        match="Connected PostgreSQL identity mismatch",
    ):
        recovery.verify_connected_database_revision(connection)

    assert len(connection.calls) == 1


@pytest.mark.parametrize(
    "recovery_status", [True, None, 0, 1, "false"]
)
def test_verify_connected_revision_rejects_unconfirmed_primary(
    approved_revision_url, recovery_status
):
    identity = (
        *SYNTHETIC_CONNECTED_DATABASE_IDENTITY[:3],
        recovery_status,
    )

    connection = _SyntheticRevisionConnection(
        approved_revision_url, [identity]
    )

    with pytest.raises(
        RuntimeError,
        match="Writable disposable PostgreSQL target not confirmed",
    ):
        recovery.verify_connected_database_revision(connection)

    assert len(connection.calls) == 1


@pytest.mark.parametrize(
    "revision", ["0025", "0027", "", None, 26]
)
def test_verify_connected_revision_rejects_wrong_revision(
    approved_revision_url, revision
):
    connection = _SyntheticRevisionConnection(
        approved_revision_url,
        [SYNTHETIC_CONNECTED_DATABASE_IDENTITY, revision],
    )

    with pytest.raises(
        RuntimeError,
        match="Connected PostgreSQL migration revision mismatch",
    ):
        recovery.verify_connected_database_revision(connection)

    assert len(connection.calls) == 2


@pytest.mark.parametrize("failure_position", [0, 1])
def test_verify_connected_revision_propagates_query_failure(
    approved_revision_url, failure_position
):
    failure = RuntimeError("Synthetic revision query failure.")

    results = [
        SYNTHETIC_CONNECTED_DATABASE_IDENTITY,
        "0026",
    ]
    results[failure_position] = failure

    connection = _SyntheticRevisionConnection(
        approved_revision_url, results
    )

    with pytest.raises(RuntimeError) as captured:
        recovery.verify_connected_database_revision(connection)

    assert captured.value is failure
    assert len(connection.calls) == failure_position + 1


@pytest.mark.parametrize(
    "exception_name",
    ["NoResultFound", "MultipleResultsFound"],
)
def test_verify_connected_revision_requires_exactly_one_row(
    approved_revision_url, exception_name
):
    from sqlalchemy import exc

    failure = getattr(exc, exception_name)()

    connection = _SyntheticRevisionConnection(
        approved_revision_url,
        [SYNTHETIC_CONNECTED_DATABASE_IDENTITY, [failure]],
    )

    # Model scalar_one() rejecting missing or multiple rows.
    connection.results = iter(
        [SYNTHETIC_CONNECTED_DATABASE_IDENTITY, None]
    )

    original_execute = connection.execute

    def execute(statement):
        result = original_execute(statement)

        if len(connection.calls) == 2:
            result.value = failure

        return result

    connection.execute = execute

    with pytest.raises(type(failure)):
        recovery.verify_connected_database_revision(connection)

    assert len(connection.calls) == 2


def test_create_lifecycle_coordination_engine(
    monkeypatch, approved_revision_url
):
    import sqlalchemy
    from sqlalchemy.pool import NullPool

    calls = []
    synthetic_engine = object()

    def create_engine(url, **kwargs):
        calls.append((url, kwargs))
        return synthetic_engine

    monkeypatch.setattr(
        sqlalchemy, "create_engine", create_engine
    )

    engine = recovery.create_lifecycle_coordination_engine()

    assert engine is synthetic_engine

    assert calls == [
        (
            approved_revision_url,
            {
                "poolclass": NullPool,
                "pool_pre_ping": False,
                "echo": False,
                "echo_pool": False,
                "hide_parameters": True,
                "connect_args": {"connect_timeout": 5},
            },
        )
    ]


@pytest.mark.parametrize(
    "opt_in", [None, "", "NO", "yes"]
)
def test_lifecycle_engine_requires_explicit_authorization(
    monkeypatch, approved_revision_url, opt_in
):
    import sqlalchemy

    if opt_in is None:
        monkeypatch.delenv(
            "PHASE5E_0026_DISPOSABLE_TEST", raising=False
        )
    else:
        monkeypatch.setenv(
            "PHASE5E_0026_DISPOSABLE_TEST", opt_in
        )

    def unexpected_engine_creation(*args, **kwargs):
        pytest.fail("Unauthorized engine creation attempted.")

    monkeypatch.setattr(
        sqlalchemy,
        "create_engine",
        unexpected_engine_creation,
    )

    with pytest.raises(
        RuntimeError,
        match="Explicit disposable PostgreSQL opt-in required",
    ):
        recovery.create_lifecycle_coordination_engine()


@pytest.mark.parametrize("raw_url", [None, ""])
def test_lifecycle_engine_requires_connection_settings(
    monkeypatch, approved_revision_url, raw_url
):
    import sqlalchemy

    if raw_url is None:
        monkeypatch.delenv(
            "PHASE5E_0026_TEST_DATABASE_URL", raising=False
        )
    else:
        monkeypatch.setenv(
            "PHASE5E_0026_TEST_DATABASE_URL", raw_url
        )

    def unexpected_engine_creation(*args, **kwargs):
        pytest.fail("Engine creation attempted without settings.")

    monkeypatch.setattr(
        sqlalchemy,
        "create_engine",
        unexpected_engine_creation,
    )

    with pytest.raises(
        RuntimeError,
        match="Disposable PostgreSQL connection settings required",
    ):
        recovery.create_lifecycle_coordination_engine()


def test_lifecycle_engine_rejects_unapproved_settings(
    monkeypatch, approved_revision_url
):
    import sqlalchemy

    monkeypatch.setenv(
        "PHASE5E_0026_TEST_DATABASE_URL",
        SYNTHETIC_DISPOSABLE_DATABASE_URL.replace(
            "@migration_test_db", "@unexpected_host"
        ),
    )

    def unexpected_engine_creation(*args, **kwargs):
        pytest.fail("Unapproved engine creation attempted.")

    monkeypatch.setattr(
        sqlalchemy,
        "create_engine",
        unexpected_engine_creation,
    )

    with pytest.raises(
        RuntimeError,
        match="Unapproved disposable PostgreSQL connection settings",
    ):
        recovery.create_lifecycle_coordination_engine()


def test_lifecycle_engine_creation_failure_is_sanitized(
    monkeypatch, approved_revision_url
):
    import sqlalchemy

    def failing_engine_creation(*args, **kwargs):
        raise RuntimeError(SYNTHETIC_DISPOSABLE_DATABASE_URL)

    monkeypatch.setattr(
        sqlalchemy,
        "create_engine",
        failing_engine_creation,
    )

    with pytest.raises(
        RuntimeError,
        match="Disposable PostgreSQL engine creation failed",
    ) as captured:
        recovery.create_lifecycle_coordination_engine()

    assert "synthetic-placeholder" not in str(captured.value)
    assert SYNTHETIC_DISPOSABLE_DATABASE_URL not in str(
        captured.value
    )
    assert captured.value.__suppress_context__ is True


def test_lifecycle_engine_uses_actual_null_pool(
    monkeypatch, approved_revision_url
):
    import psycopg
    from sqlalchemy.pool import NullPool

    def unexpected_connection(*args, **kwargs):
        pytest.fail("Physical PostgreSQL connection attempted.")

    monkeypatch.setattr(
        psycopg, "connect", unexpected_connection
    )

    engine = recovery.create_lifecycle_coordination_engine()

    try:
        assert isinstance(engine.pool, NullPool)
        assert engine.url == approved_revision_url
        assert engine.echo is False
        assert engine.hide_parameters is True
        assert engine.pool.echo is False
    finally:
        engine.dispose()


@pytest.fixture
def clean_postgresql_environment(monkeypatch):
    import os

    for name in tuple(os.environ):
        if name.upper().startswith("PG"):
            monkeypatch.delenv(name, raising=False)


def test_postgresql_environment_without_overrides(
    clean_postgresql_environment
):
    assert recovery.reject_postgresql_environment_overrides() is None


@pytest.mark.parametrize(
    "name",
    [
        "PGHOST",
        "PGHOSTADDR",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
        "PGPASSFILE",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGOPTIONS",
        "PGSSLMODE",
        "PGSSLROOTCERT",
        "PGCONNECT_TIMEOUT",
        "PGAPPNAME",
        "PGTARGETSESSIONATTRS",
        "PGFUTURESETTING",
        "pghostaddr",
    ],
)
def test_postgresql_environment_rejects_overrides(
    monkeypatch, clean_postgresql_environment, name
):
    import os

    synthetic_value = "synthetic-environment-placeholder"

    monkeypatch.setenv(name, synthetic_value)

    with pytest.raises(
        RuntimeError,
        match="PostgreSQL environment overrides are not permitted",
    ) as captured:
        recovery.reject_postgresql_environment_overrides()

    assert name not in str(captured.value)
    assert synthetic_value not in str(captured.value)
    assert os.environ[name] == synthetic_value


def test_postgresql_environment_rejects_empty_override(
    monkeypatch, clean_postgresql_environment
):
    monkeypatch.setenv("PGOPTIONS", "")

    with pytest.raises(
        RuntimeError,
        match="PostgreSQL environment overrides are not permitted",
    ):
        recovery.reject_postgresql_environment_overrides()


def test_postgresql_environment_allows_unrelated_variables(
    monkeypatch, clean_postgresql_environment
):
    monkeypatch.setenv(
        "GEOVARIS_SYNTHETIC_SETTING", "synthetic-value"
    )

    assert recovery.reject_postgresql_environment_overrides() is None


@pytest.mark.parametrize(
    "name", ["PGHOSTADDR", "PGSERVICE", "PGOPTIONS"]
)
def test_lifecycle_engine_rejects_environment_overrides(
    monkeypatch,
    approved_revision_url,
    clean_postgresql_environment,
    name,
):
    import sqlalchemy

    monkeypatch.setenv(name, "synthetic-override")

    def unexpected_engine_creation(*args, **kwargs):
        pytest.fail(
            "Engine creation attempted with environment overrides."
        )

    monkeypatch.setattr(
        sqlalchemy,
        "create_engine",
        unexpected_engine_creation,
    )

    with pytest.raises(
        RuntimeError,
        match="PostgreSQL environment overrides are not permitted",
    ):
        recovery.create_lifecycle_coordination_engine()
