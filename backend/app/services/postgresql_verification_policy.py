"""Fail-closed security policy for PostgreSQL connection verification."""

from app.core.config import Settings


class PostgreSQLVerificationPolicyError(ValueError):
    """Raised when PostgreSQL verification security requirements are unmet."""


def require_postgresql_verification_configuration(
    settings: Settings,
) -> None:
    """Reject verification when required deployment controls are absent."""

    if not settings.postgresql_verification_enabled:
        raise PostgreSQLVerificationPolicyError(
            "PostgreSQL connection verification is disabled."
        )

    if not settings.postgresql_verification_allowed_destinations.strip():
        raise PostgreSQLVerificationPolicyError(
            "Approved PostgreSQL destinations are not configured."
        )

    if not settings.postgresql_verification_ssl_root_cert.strip():
        raise PostgreSQLVerificationPolicyError(
            "A trusted PostgreSQL CA certificate is not configured."
        )

    # Validate approved IP networks before any DNS or connection activity.
    parse_approved_postgresql_ip_networks(
        settings.postgresql_verification_allowed_ip_networks
    )



def parse_approved_postgresql_destinations(
    value: str,
) -> frozenset[tuple[str, int]]:
    """Parse exact approved DNS hostname and TCP port pairs."""

    import re

    if not value.strip():
        raise PostgreSQLVerificationPolicyError(
            "Approved PostgreSQL destinations are not configured."
        )

    destinations: set[tuple[str, int]] = set()

    for entry in value.split(","):
        entry = entry.strip()

        if entry.count(":") != 1:
            raise PostgreSQLVerificationPolicyError(
                "Invalid approved PostgreSQL destination format."
            )

        hostname, port_text = entry.split(":", 1)

        if (
            not hostname
            or len(hostname) > 253
            or not re.fullmatch(
                r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?",
                hostname,
            )
            or ".." in hostname
            or any(
                len(label) > 63 or label.startswith("-") or label.endswith("-")
                for label in hostname.split(".")
            )
            or not re.fullmatch(r"[0-9]+", port_text)
        ):
            raise PostgreSQLVerificationPolicyError(
                "Invalid approved PostgreSQL destination format."
            )

        port = int(port_text)

        if not 1 <= port <= 65535:
            raise PostgreSQLVerificationPolicyError(
                "Approved PostgreSQL destination port is invalid."
            )

        destinations.add((hostname.lower(), port))

    return frozenset(destinations)


def require_approved_postgresql_destination(
    *,
    host: str,
    port: int,
    allowed_destinations: str,
) -> None:
    """Require an exact match with a configured approved destination."""

    approved = parse_approved_postgresql_destinations(
        allowed_destinations
    )

    if (host.lower(), port) not in approved:
        raise PostgreSQLVerificationPolicyError(
            "PostgreSQL destination is not approved for verification."
        )



def require_postgresql_trusted_ca_file(certificate_path: str) -> None:
    """Require a readable, nonempty regular CA certificate file."""

    from pathlib import Path

    if not certificate_path.strip():
        raise PostgreSQLVerificationPolicyError(
            "A trusted PostgreSQL CA certificate is not configured."
        )

    path = Path(certificate_path)

    try:
        if not path.is_file():
            raise PostgreSQLVerificationPolicyError(
                "The trusted PostgreSQL CA certificate file is unavailable."
            )

        with path.open("rb") as certificate:
            if not certificate.read(1):
                raise PostgreSQLVerificationPolicyError(
                    "The trusted PostgreSQL CA certificate file is empty."
                )

    except OSError:
        raise PostgreSQLVerificationPolicyError(
            "The trusted PostgreSQL CA certificate file cannot be read."
        ) from None



def parse_approved_postgresql_ip_networks(
    value: str,
) -> tuple:
    """Parse explicitly approved IPv4/IPv6 CIDR networks."""

    import ipaddress

    if not value.strip():
        raise PostgreSQLVerificationPolicyError(
            "Approved PostgreSQL IP networks are not configured."
        )

    networks = []

    for entry in value.split(","):
        entry = entry.strip()

        if not entry or "/" not in entry:
            raise PostgreSQLVerificationPolicyError(
                "Invalid approved PostgreSQL IP network."
            )

        try:
            network = ipaddress.ip_network(
                entry,
                strict=True,
            )
        except ValueError:
            raise PostgreSQLVerificationPolicyError(
                "Invalid approved PostgreSQL IP network."
            ) from None

        networks.append(network)

    return tuple(networks)


def require_approved_postgresql_ip(
    *,
    ip_address: str,
    allowed_networks: str,
) -> None:
    """Reject destination IPs outside client-approved networks."""

    import ipaddress

    networks = parse_approved_postgresql_ip_networks(
        allowed_networks
    )

    try:
        address = ipaddress.ip_address(ip_address)
    except ValueError:
        raise PostgreSQLVerificationPolicyError(
            "Invalid PostgreSQL destination IP address."
        ) from None

    if not any(address in network for network in networks):
        raise PostgreSQLVerificationPolicyError(
            "PostgreSQL destination IP is not approved."
        )



def resolve_approved_postgresql_ip(
    *,
    host: str,
    port: int,
    allowed_networks: str,
) -> str:
    """Resolve a hostname and require every returned IP to be authorized."""

    import ipaddress
    import socket

    # Reject missing or malformed network policy before DNS access.
    networks = parse_approved_postgresql_ip_networks(
        allowed_networks
    )

    try:
        results = socket.getaddrinfo(
            host,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except (OSError, UnicodeError):
        raise PostgreSQLVerificationPolicyError(
            "Unable to resolve the approved PostgreSQL hostname."
        ) from None

    addresses = set()

    for result in results:
        try:
            address = ipaddress.ip_address(result[4][0])
        except (ValueError, IndexError, TypeError):
            raise PostgreSQLVerificationPolicyError(
                "PostgreSQL DNS returned an invalid destination IP."
            ) from None

        addresses.add(address)

    if not addresses:
        raise PostgreSQLVerificationPolicyError(
            "PostgreSQL DNS returned no destination IP addresses."
        )

    if any(
        not any(address in network for network in networks)
        for address in addresses
    ):
        raise PostgreSQLVerificationPolicyError(
            "PostgreSQL DNS returned an unauthorized destination IP."
        )

    # Choose deterministically. The caller must pass this IP via hostaddr
    # while retaining the original hostname for TLS verify-full.
    return str(sorted(addresses, key=lambda address: (
        address.version,
        int(address),
    ))[0])
