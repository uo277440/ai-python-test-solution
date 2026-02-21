"""
State definitions and transition rules for request lifecycle management.

This module centralizes:
- The canonical request status enumeration.
- The allowed state transition graph.
- Validation logic to enforce consistent lifecycle progression.
"""

from enum import Enum


# Enumeration representing the lifecycle states of a request.
# Inherits from `str` to ensure JSON serialization compatibility.
class RequestStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"


# Directed graph describing valid state transitions.
# Each key maps to the set of states it can legally transition to.
ALLOWED_TRANSITIONS = {
    RequestStatus.QUEUED: {RequestStatus.PROCESSING},
    RequestStatus.PROCESSING: {RequestStatus.SENT, RequestStatus.FAILED},
    RequestStatus.SENT: set(),
    RequestStatus.FAILED: set(),
}


# Validate whether a transition between two states is allowed.
# Returns True if the transition is defined in ALLOWED_TRANSITIONS.
def can_transition(from_status: RequestStatus, to_status: RequestStatus) -> bool:
    # Fallback to empty set if the origin state is unknown.
    return to_status in ALLOWED_TRANSITIONS.get(from_status, set())