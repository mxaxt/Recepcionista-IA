from typing import Any

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    classification: dict[str, Any]


class ApproveRequest(BaseModel):
    date: str | None = Field(
        default=None,
        description="YYYY-MM-DD elegido por el humano (opcional). "
        "Si se omite, se usa el primer slot sugerido.",
    )
    start_time: str | None = Field(
        default=None,
        description="HH:MM elegido por el humano (opcional). "
        "Si se omite, se usa el primer slot sugerido.",
    )


class RejectRequest(BaseModel):
    reason: str | None = None


class ReviewOut(BaseModel):
    review_id: str
    session_id: str
    message: str
    classification: dict[str, Any]
    status: str
    suggested_slots: list[dict[str, Any]]
    approved_slot: dict[str, Any] | None
    reservation: dict[str, Any] | None
    decision: str | None
    decision_reason: str | None
    created_at: str | None
    resolved_at: str | None
