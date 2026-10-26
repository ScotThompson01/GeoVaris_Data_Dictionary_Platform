"""Authorization helpers for project administration."""

from fastapi import HTTPException, status

from app.models.user import User


def require_project_administrator(user: User) -> None:
    """Require an active installation administrator."""
    if not user.is_active or not user.is_installation_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project administration permission required.",
        )

def update_steward_self_approval(
    db: "Session",
    *,
    project: "Project",
    actor_user_id: "uuid.UUID",
    enabled: bool,
) -> bool:
    """Update the project setting and audit it in one transaction.

    Authorization must be completed by the calling API endpoint.
    Returns True if the setting changed.
    """
    from app.models.audit_event import AuditEvent

    previous_value = project.allow_steward_self_approval

    if previous_value == enabled:
        return False

    try:
        project.allow_steward_self_approval = enabled

        db.add(
            AuditEvent(
                project_id=project.id,
                actor_user_id=actor_user_id,
                event_type="project.steward_self_approval.changed",
                old_value=previous_value,
                new_value=enabled,
            )
        )

        db.commit()
    except Exception:
        db.rollback()
        project.allow_steward_self_approval = previous_value
        raise

    return True
