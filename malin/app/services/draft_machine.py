"""
Draft state machine — SPEC §5.2 "Draft is Law".

Allowed transitions (exakt nach SPEC §5.2):
  DRAFT        → APPROVED | REJECTED
  NEEDS_REVIEW → APPROVED | REJECTED
  APPROVED     → EXECUTED
  EXECUTED     → ARCHIVED
  REJECTED     → (terminal – edit creates new version)
  ARCHIVED     → (terminal)

Hard rule: execute_action() MUST raise IllegalStateError unless status == APPROVED.
"""

from malin.app.errors import IllegalStateError
from malin.app.models.tables import DraftStatus

_TRANSITIONS: dict[DraftStatus, set[DraftStatus]] = {
    DraftStatus.DRAFT:        {DraftStatus.APPROVED, DraftStatus.REJECTED},
    DraftStatus.NEEDS_REVIEW: {DraftStatus.APPROVED, DraftStatus.REJECTED},
    DraftStatus.APPROVED:     {DraftStatus.EXECUTED},
    DraftStatus.EXECUTED:     {DraftStatus.ARCHIVED},
    DraftStatus.REJECTED:     set(),
    DraftStatus.ARCHIVED:     set(),
}


def validate_transition(current: DraftStatus, target: DraftStatus) -> None:
    """Raise IllegalStateError if the transition is not allowed per SPEC §5.2."""
    allowed = _TRANSITIONS.get(current, set())
    if target not in allowed:
        raise IllegalStateError(
            current_status=current.value,
            attempted_action=f"transition to {target.value}",
        )


def validate_can_execute(status: DraftStatus) -> None:
    """
    SPEC §5.2 Hard rule:
    execute_action() darf nur wenn status == APPROVED, sonst IllegalStateError.
    """
    if status != DraftStatus.APPROVED:
        raise IllegalStateError(
            current_status=status.value,
            attempted_action="execute",
        )
