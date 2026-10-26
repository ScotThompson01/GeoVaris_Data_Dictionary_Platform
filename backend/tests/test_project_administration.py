"""Tests for project administration permissions."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.project_administration import require_project_administrator


def test_active_installation_administrator_is_allowed():
    user = SimpleNamespace(is_active=True, is_installation_admin=True)

    require_project_administrator(user)


@pytest.mark.parametrize(
    ("is_active", "is_installation_admin"),
    [
        (True, False),
        (False, True),
        (False, False),
    ],
)
def test_other_users_cannot_administer_project(
    is_active: bool,
    is_installation_admin: bool,
):
    user = SimpleNamespace(
        is_active=is_active,
        is_installation_admin=is_installation_admin,
    )

    with pytest.raises(HTTPException) as error:
        require_project_administrator(user)

    assert error.value.status_code == 403
