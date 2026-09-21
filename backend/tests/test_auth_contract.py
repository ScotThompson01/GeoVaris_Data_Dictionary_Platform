import uuid
from dataclasses import FrozenInstanceError

import pytest

from app.core.auth import AuthenticatedUser


def test_authenticated_user_has_expected_fields():
    user_id = uuid.uuid4()

    user = AuthenticatedUser(
        user_id=user_id,
        username="test-user",
        identity_provider="local",
    )

    assert user.user_id == user_id
    assert user.username == "test-user"
    assert user.identity_provider == "local"


def test_authenticated_user_is_immutable():
    user = AuthenticatedUser(
        user_id=uuid.uuid4(),
        username="test-user",
        identity_provider="local",
    )

    with pytest.raises(FrozenInstanceError):
        user.username = "different-user"