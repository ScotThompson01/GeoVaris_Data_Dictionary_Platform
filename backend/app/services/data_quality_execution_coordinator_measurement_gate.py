"""Internal Phase 5E protected measurement-start prerequisite.

This function is NOT an authorization decision and is NOT connected
to API routes, runtime admission, workers, or source connectors.

The caller must independently establish that both transaction commits
succeeded. Unknown or ambiguous commit outcomes are not sufficient.

A successful check does not authorize or initiate source measurement.
"""


def require_committed_protected_start(
    *,
    admission_committed: bool,
    running_committed: bool,
) -> None:
    """Require confirmed admission and RUNNING transaction commits.

    Reject False, None, non-Boolean inputs, and ambiguous evidence.
    No database operations, source I/O, or capacity release occur.
    """
    if (
        type(admission_committed) is not bool
        or type(running_committed) is not bool
    ):
        raise ValueError(
            "Protected measurement requires Boolean commit evidence."
        )

    if not admission_committed:
        raise ValueError(
            "Protected admission commit has not been confirmed."
        )

    if not running_committed:
        raise ValueError(
            "Protected RUNNING commit has not been confirmed."
        )
