"""Internal transaction boundary for Phase 5E coordination.

NOT connected to API routes, runtime admission, or source measurement.

The session factory must create an independent database session.
The stage callback must not perform source I/O or commit transactions.

A returned value means session.commit() completed normally. It does
not independently establish persistence or authorize measurement.
The coordinator must separately verify durable protection records.

If commit raises an exception, its outcome is uncertain. Attempting
rollback or closing the session does not prove the server rolled back.
"""


def run_coordinator_transaction(
    *,
    session_factory,
    stage,
):
    """Execute one staging operation with caller-independent session ownership.

    The returned result should contain immutable identifiers or values,
    not ORM objects that may expire when the session closes.
    """
    if not callable(session_factory):
        raise ValueError("A callable database session factory is required.")

    if not callable(stage):
        raise ValueError("A callable transaction stage is required.")

    db = session_factory()

    try:
        result = stage(db)
        db.commit()
    except BaseException:
        # Preserve the original staging or commit exception.
        # A rollback attempt after a commit exception does not prove
        # that the server-side transaction failed to commit.
        try:
            db.rollback()
        except Exception:
            pass

        try:
            db.close()
        except Exception:
            # Secondary cleanup failures must not hide the original
            # exception or obscure an uncertain commit outcome.
            pass

        raise

    # A close failure after successful commit must not be reported
    # as an entirely successful transaction operation.
    db.close()
    return result
