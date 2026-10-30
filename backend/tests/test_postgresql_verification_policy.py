"""Tests for fail-closed PostgreSQL verification configuration."""

from types import SimpleNamespace

import pytest

from app.services.postgresql_verification_policy import (
    PostgreSQLVerificationPolicyError,
    require_postgresql_verification_configuration,
    parse_approved_postgresql_destinations,
    require_approved_postgresql_destination,
    require_postgresql_trusted_ca_file,
    parse_approved_postgresql_ip_networks,
    require_approved_postgresql_ip,
    resolve_approved_postgresql_ip,
)


def make_settings(
    *,
    enabled=False,
    destinations="",
    ca_certificate="",
    ip_networks="",
):
    return SimpleNamespace(
        postgresql_verification_enabled=enabled,
        postgresql_verification_allowed_destinations=destinations,
        postgresql_verification_ssl_root_cert=ca_certificate,
        postgresql_verification_allowed_ip_networks=ip_networks,
    )


def test_verification_disabled_by_default():
    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="disabled",
    ):
        require_postgresql_verification_configuration(make_settings())


def test_missing_approved_destinations_rejected():
    settings = make_settings(
        enabled=True,
        ca_certificate="/etc/geovaris/approved-ca.pem",
    )

    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="destinations",
    ):
        require_postgresql_verification_configuration(settings)


def test_missing_ca_certificate_rejected():
    settings = make_settings(
        enabled=True,
        destinations="database.internal:5432",
    )

    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="CA certificate",
    ):
        require_postgresql_verification_configuration(settings)


def test_whitespace_only_configuration_rejected():
    settings = make_settings(
        enabled=True,
        destinations="   ",
        ca_certificate="   ",
    )

    with pytest.raises(PostgreSQLVerificationPolicyError):
        require_postgresql_verification_configuration(settings)


def test_configured_policy_passes_initial_gate():
    settings = make_settings(
        enabled=True,
        destinations="database.internal:5432",
        ca_certificate="/etc/geovaris/approved-ca.pem",
        ip_networks="10.20.30.0/24",
    )

    require_postgresql_verification_configuration(settings)



def test_approved_destination_parsing():
    result = parse_approved_postgresql_destinations(
        "db1.internal:5432,db2.internal:5433"
    )
    assert result == frozenset({
        ("db1.internal", 5432),
        ("db2.internal", 5433),
    })


def test_approved_destination_case_insensitive():
    require_approved_postgresql_destination(
        host="DB1.INTERNAL",
        port=5432,
        allowed_destinations="db1.internal:5432",
    )


def test_unapproved_destination_rejected():
    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="not approved",
    ):
        require_approved_postgresql_destination(
            host="other.internal",
            port=5432,
            allowed_destinations="db1.internal:5432",
        )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "db.internal",
        "db.internal:",
        ":5432",
        "db.internal:0",
        "db.internal:65536",
        "db.internal:abc",
        "db.internal:5432,",
        "*.internal:5432",
        "https://db.internal:5432",
        "db..internal:5432",
        "-db.internal:5432",
    ],
)
def test_malformed_destinations_rejected(value):
    with pytest.raises(PostgreSQLVerificationPolicyError):
        parse_approved_postgresql_destinations(value)


def test_unapproved_port_rejected():
    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="not approved",
    ):
        require_approved_postgresql_destination(
            host="db1.internal",
            port=5433,
            allowed_destinations="db1.internal:5432",
        )



def test_trusted_ca_file_is_readable(tmp_path):
    certificate = tmp_path / "trusted-ca.pem"
    certificate.write_text(
        "test certificate content",
        encoding="utf-8",
    )

    require_postgresql_trusted_ca_file(str(certificate))


def test_missing_trusted_ca_file_rejected(tmp_path):
    certificate = tmp_path / "missing-ca.pem"

    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="unavailable",
    ):
        require_postgresql_trusted_ca_file(str(certificate))


def test_empty_trusted_ca_file_rejected(tmp_path):
    certificate = tmp_path / "empty-ca.pem"
    certificate.touch()

    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="empty",
    ):
        require_postgresql_trusted_ca_file(str(certificate))


def test_trusted_ca_directory_rejected(tmp_path):
    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="unavailable",
    ):
        require_postgresql_trusted_ca_file(str(tmp_path))


def test_blank_trusted_ca_path_rejected():
    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="not configured",
    ):
        require_postgresql_trusted_ca_file("   ")



def test_approved_ip_network_parsing():
    networks = parse_approved_postgresql_ip_networks(
        "10.20.30.0/24,2001:db8::/32"
    )

    assert len(networks) == 2
    assert str(networks[0]) == "10.20.30.0/24"
    assert str(networks[1]) == "2001:db8::/32"


def test_approved_ipv4_destination():
    require_approved_postgresql_ip(
        ip_address="10.20.30.15",
        allowed_networks="10.20.30.0/24",
    )


def test_approved_ipv6_destination():
    require_approved_postgresql_ip(
        ip_address="2001:db8::15",
        allowed_networks="2001:db8::/32",
    )


def test_unapproved_ipv4_destination_rejected():
    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="not approved",
    ):
        require_approved_postgresql_ip(
            ip_address="10.20.31.15",
            allowed_networks="10.20.30.0/24",
        )


def test_unapproved_ipv6_destination_rejected():
    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="not approved",
    ):
        require_approved_postgresql_ip(
            ip_address="2001:db9::15",
            allowed_networks="2001:db8::/32",
        )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "10.20.30.15",
        "10.20.30.0/33",
        "10.20.30.15/24",
        "not-an-ip/24",
        "10.20.30.0/24,",
        "10.20.30.0/24,,192.0.2.0/24",
        "2001:db8::1/64",
    ],
)
def test_invalid_ip_network_configuration_rejected(value):
    with pytest.raises(PostgreSQLVerificationPolicyError):
        parse_approved_postgresql_ip_networks(value)


def test_invalid_destination_ip_rejected():
    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="Invalid PostgreSQL destination IP",
    ):
        require_approved_postgresql_ip(
            ip_address="not-an-ip",
            allowed_networks="10.20.30.0/24",
        )


def test_loopback_requires_explicit_authorization():
    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="not approved",
    ):
        require_approved_postgresql_ip(
            ip_address="127.0.0.1",
            allowed_networks="10.20.30.0/24",
        )



def test_dns_all_approved_addresses(monkeypatch):
    import socket

    def fake_getaddrinfo(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "",
             ("10.20.30.20", 5432)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "",
             ("10.20.30.10", 5432)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    result = resolve_approved_postgresql_ip(
        host="database.internal",
        port=5432,
        allowed_networks="10.20.30.0/24",
    )

    assert result == "10.20.30.10"


def test_dns_mixed_authorized_and_unauthorized_rejected(monkeypatch):
    import socket

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "",
             ("10.20.30.10", 5432)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "",
             ("192.0.2.10", 5432)),
        ],
    )

    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="unauthorized",
    ):
        resolve_approved_postgresql_ip(
            host="database.internal",
            port=5432,
            allowed_networks="10.20.30.0/24",
        )


def test_dns_resolution_failure_rejected(monkeypatch):
    import socket

    def fail_resolution(*args, **kwargs):
        raise socket.gaierror("Simulated DNS failure")

    monkeypatch.setattr(socket, "getaddrinfo", fail_resolution)

    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="Unable to resolve",
    ):
        resolve_approved_postgresql_ip(
            host="database.internal",
            port=5432,
            allowed_networks="10.20.30.0/24",
        )


def test_dns_empty_response_rejected(monkeypatch):
    import socket

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [],
    )

    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="no destination IP",
    ):
        resolve_approved_postgresql_ip(
            host="database.internal",
            port=5432,
            allowed_networks="10.20.30.0/24",
        )


def test_dns_invalid_network_policy_blocks_lookup(monkeypatch):
    import socket

    def unexpected_lookup(*args, **kwargs):
        raise AssertionError("DNS must not be called")

    monkeypatch.setattr(socket, "getaddrinfo", unexpected_lookup)

    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="IP networks",
    ):
        resolve_approved_postgresql_ip(
            host="database.internal",
            port=5432,
            allowed_networks="",
        )


def test_dns_ipv6_approved(monkeypatch):
    import socket

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "",
             ("2001:db8::15", 5432, 0, 0)),
        ],
    )

    result = resolve_approved_postgresql_ip(
        host="database.internal",
        port=5432,
        allowed_networks="2001:db8::/32",
    )

    assert result == "2001:db8::15"



def test_missing_ip_network_allowlist_rejected():
    settings = make_settings(
        enabled=True,
        destinations="database.internal:5432",
        ca_certificate="/etc/geovaris/approved-ca.pem",
        ip_networks="",
    )

    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="IP networks",
    ):
        require_postgresql_verification_configuration(settings)


def test_malformed_ip_network_allowlist_rejected_at_initial_gate():
    settings = make_settings(
        enabled=True,
        destinations="database.internal:5432",
        ca_certificate="/etc/geovaris/approved-ca.pem",
        ip_networks="10.20.30.15/24",
    )

    with pytest.raises(
        PostgreSQLVerificationPolicyError,
        match="Invalid approved PostgreSQL IP network",
    ):
        require_postgresql_verification_configuration(settings)
