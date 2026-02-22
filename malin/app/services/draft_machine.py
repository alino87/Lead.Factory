"""
Draft state machine – "Draft is Law".

Valid transitions:
  DRAFT      → APPROVED | REJECTED | NEEDS_REVIEW
  APPROVED   → EXECUTED | NEEDS_REVIEW
  REJECTED   → DRAFT (re-edit creates new version)
  NEEDS_REVIEW → DRAFT | APPROVED | REJECTED

execute_action() MUST raise IllegalStateError unless status == APPROVED.
"""

from malin.app.errors import IllegalStateError
from malin.app.models.tables import DraftStatus

# Allowed transitions: current_status → set of valid next statuses
_TRANSITIONS: dict[DraftStatus, set[DraftStatus]] = {
    DraftStatus.DRAFT:        {DraftStatus.APPROVED, DraftStatus.REJECTED, DraftStatus.NEEDS_REVIEW},
    DraftStatus.APPROVED:     {DraftStatus.EXECUTED, DraftStatus.NEEDS_REVIEW},
    DraftStatus.REJECTED:     {DraftStatus.DRAFT},
    DraftStatus.NEEDS_REVIEW: {DraftStatus.DRAFT, DraftStatus.APPROVED, DraftStatus.REJECTED},
    DraftStatus.EXECUTED:     set(),  # terminal state
}


def validate_transition(current: DraftStatus, target: DraftStatus) -> None:
    """Raise IllegalStateError if the transition is not allowed."""
    allowed = _TRANSITIONS.get(current, set())
    if target not in allowed:
        raise IllegalStateError(
            current_status=current.value,
            attempted_action=f"transition to {target.value}",
        )


def validate_can_execute(status: DraftStatus) -> None:
    """
    Guard for execute_action: MUST be APPROVED.
    This is the core "Draft is Law" enforcement.
    """
    if status != DraftStatus.APPROVED:
        raise IllegalStateError(
            current_status=status.value,
            attempted_action="execute",
        )
