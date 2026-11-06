"""Security tests for internal session-authenticated capacity release."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import (
    data_quality_session_authenticated_release as service,
)


def release_case():
    return dict(
        session_token="valid-test-session",
        project_id=uuid4(),
        ownership_id=uuid4(),
        data_source_id=uuid4(),
        evidence_id=uuid4(),
        reason="Approved administrator resolution",
        evidence_reference="resolution-evidence-001",
    )


def test_valid_session_supplies_actor_identity(monkeypatch):
    """The authenticated user, not the caller, identifies the actor."""
    db = object()
    actor_id = uuid4()
    kwargs = release_case()
    sessions = []
    staged = []

    def authenticated_user(session, token):
        sessions.append((session, token))
        return SimpleNamespace(id=actor_id, is_active=True)

    def stage_release(session, **details):
        staged.append((session, details))

    monkeypatch.setattr(service, "get_session_user", authenticated_user)
    monkeypatch.setattr(
        service, "stage_persisted_admin_resolution", stage_release
    )

    service.stage_session_authenticated_admin_resolution(db, **kwargs)

    assert sessions == [(db, kwargs["session_token"])]
    assert len(staged) == 1
    assert staged[0][0] is db
    assert staged[0][1] == {
        **{
            key: value
            for key, value in kwargs.items()
            if key != "session_token"
        },
        "trusted_actor_user_id": actor_id,
        # Preserve the original token for mandatory revalidation
        # inside the locked release transaction.
        "session_token": kwargs["session_token"],
    }


@pytest.mark.parametrize(
    "invalid_token",
    [None, "", " ", " leading", "trailing ", "two tokens", "tab\tvalue"],
)
def test_invalid_tokens_rejected_before_session_lookup(
    monkeypatch, invalid_token
):
    db = object()
    kwargs = release_case()
    kwargs["session_token"] = invalid_token
    calls = []

    monkeypatch.setattr(
        service,
        "get_session_user",
        lambda *args: calls.append("lookup"),
    )
    monkeypatch.setattr(
        service,
        "stage_persisted_admin_resolution",
        lambda *args, **details: calls.append("release"),
    )

    with pytest.raises(PermissionError, match="authenticated session"):
        service.stage_session_authenticated_admin_resolution(db, **kwargs)

    assert calls == []


@pytest.mark.parametrize(
    "session_status",
    ["unknown", "revoked", "expired"],
)
def test_unusable_sessions_cannot_stage_release(
    monkeypatch, session_status
):
    """Existing session lookup rejects unknown, revoked and expired tokens."""
    db = object()
    kwargs = release_case()
    calls = []

    # None represents the result of get_session_user() for each case.
    monkeypatch.setattr(
        service,
        "get_session_user",
        lambda session, token: None,
    )
    monkeypatch.setattr(
        service,
        "stage_persisted_admin_resolution",
        lambda *args, **details: calls.append("release"),
    )

    with pytest.raises(PermissionError, match="authenticated session"):
        service.stage_session_authenticated_admin_resolution(db, **kwargs)

    assert calls == []


@pytest.mark.parametrize(
    "user",
    [
        SimpleNamespace(id=uuid4(), is_active=False),
        SimpleNamespace(id=uuid4(), is_active=None),
        SimpleNamespace(id="claimed-user-id", is_active=True),
        SimpleNamespace(is_active=True),
    ],
)
def test_invalid_authenticated_user_cannot_stage_release(
    monkeypatch, user
):
    db = object()
    calls = []

    monkeypatch.setattr(
        service,
        "get_session_user",
        lambda session, token: user,
    )
    monkeypatch.setattr(
        service,
        "stage_persisted_admin_resolution",
        lambda *args, **details: calls.append("release"),
    )

    with pytest.raises(PermissionError, match="authenticated session"):
        service.stage_session_authenticated_admin_resolution(
            db, **release_case()
        )

    assert calls == []


def test_caller_cannot_override_authenticated_actor(monkeypatch):
    db = object()
    calls = []

    monkeypatch.setattr(
        service,
        "get_session_user",
        lambda *args: calls.append("lookup"),
    )
    monkeypatch.setattr(
        service,
        "stage_persisted_admin_resolution",
        lambda *args, **details: calls.append("release"),
    )

    kwargs = release_case()
    kwargs["trusted_actor_user_id"] = uuid4()

    with pytest.raises(TypeError, match="unexpected keyword"):
        service.stage_session_authenticated_admin_resolution(db, **kwargs)

    assert calls == []


def test_persisted_authorization_rejection_propagates(monkeypatch):
    """The adapter must not suppress downstream authorization failures."""
    db = object()
    monkeypatch.setattr(
        service,
        "get_session_user",
        lambda session, token: SimpleNamespace(
            id=uuid4(), is_active=True
        ),
    )

    def reject_authorization(*args, **details):
        raise ValueError("Persisted release authorization rejected.")

    monkeypatch.setattr(
        service,
        "stage_persisted_admin_resolution",
        reject_authorization,
    )

    with pytest.raises(ValueError, match="authorization rejected"):
        service.stage_session_authenticated_admin_resolution(
            db, **release_case()
        )
