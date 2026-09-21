"""Authentication contract for GeoVaris.

This module defines the identity returned by a future validated
authentication mechanism. It does not authenticate requests yet.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuthenticatedUser:
    """Internal identity shared by supported sign-in methods."""

    user_id: UUID
    username: str
    identity_provider: str