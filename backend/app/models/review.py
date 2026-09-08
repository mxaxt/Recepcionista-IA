from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ReviewStatus(str, Enum):
    """Estados explicitos del caso de revision humana.

    PENDING: esperando decision.
    APPROVED: el humano aprueba (con o sin cambio de horario: el cambio
        se registra en los datos, no en el estado).
    REJECTED: el humano rechaza.
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


TERMINAL_STATUSES = {ReviewStatus.APPROVED, ReviewStatus.REJECTED}


@dataclass
class PriorityReview:
    review_id: str
    session_id: str
    message: str
    classification: dict[str, Any]
    status: ReviewStatus = ReviewStatus.PENDING
    suggested_slots: list[dict[str, Any]] = field(default_factory=list)
    approved_slot: dict[str, Any] | None = None
    reservation: dict[str, Any] | None = None
    decision: str | None = None
    decision_reason: str | None = None
    created_at: str | None = None
    resolved_at: str | None = None

    @property
    def is_resolved(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "session_id": self.session_id,
            "message": self.message,
            "classification": self.classification,
            "status": self.status.value,
            "suggested_slots": self.suggested_slots,
            "approved_slot": self.approved_slot,
            "reservation": self.reservation,
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }
