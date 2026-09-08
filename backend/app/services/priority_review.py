"""Casos de revision humana para clasificaciones PRIORITY.

El MVP no permite que la IA reserve un sobreturno por si sola: cuando el
classifier dictamina PRIORITY se abre un caso PENDING y un humano decide
aprobar (con el horario sugerido u otro), o rechazar.

La reserva real SIEMPRE pasa por AgendaTools -> Agenda. Este modulo no
vuelve a implementar ninguna regla de disponibilidad: solo administra el
estado de la aprobacion humana y registra cada decision para poder
aprender del uso real.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from app.models.review import PriorityReview, ReviewStatus
from app.tools.agenda_tools import AgendaTools


SUGGESTION_LIMIT = 5


class ReviewNotFoundError(KeyError):
    """No existe un review con ese id."""


class ReviewAlreadyResolvedError(RuntimeError):
    """El review ya fue aprobado o rechazado y no se puede resolver dos veces."""


class ReviewReservationFailedError(RuntimeError):
    """La agenda rechazo la reserva pedida por el revisor."""

    def __init__(self, result: dict[str, Any]):
        super().__init__(result.get("detail", "La reserva fallo."))
        self.result = result


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt_time(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")

    return str(value)[:5]


class PriorityReviewService:

    def __init__(
        self,
        agenda_tools: AgendaTools | None = None,
    ):
        self.agenda_tools = agenda_tools
        self._reviews: dict[str, PriorityReview] = {}
        self.decision_log: list[dict[str, Any]] = []

    # ---------- lectura ----------

    def list_reviews(
        self,
        status: ReviewStatus | None = None,
    ) -> list[PriorityReview]:
        reviews = list(self._reviews.values())

        if status is not None:
            reviews = [r for r in reviews if r.status == status]

        return reviews

    def get_review(self, review_id: str) -> PriorityReview:
        review = self._reviews.get(review_id)

        if review is None:
            raise ReviewNotFoundError(review_id)

        return review

    # ---------- creacion ----------

    def create_review(
        self,
        session_id: str,
        message: str,
        classification: dict[str, Any],
    ) -> PriorityReview:
        review = PriorityReview(
            review_id=uuid.uuid4().hex,
            session_id=session_id,
            message=message,
            classification=classification,
            suggested_slots=self._suggest_slots(),
            created_at=_utc_now_iso(),
        )

        self._reviews[review.review_id] = review

        return review

    def _suggest_slots(self) -> list[dict[str, Any]]:
        if self.agenda_tools is None:
            return []

        availability = self.agenda_tools.check_availability(
            priority=True,
        )

        if not availability["ok"]:
            return []

        return availability["availability"][:SUGGESTION_LIMIT]

    # ---------- resolucion ----------

    def approve_review(
        self,
        review_id: str,
        date: Any = None,
        start_time: Any = None,
    ) -> PriorityReview:
        review = self._get_pending(review_id)

        if self.agenda_tools is None:
            raise ReviewReservationFailedError(
                {
                    "ok": False,
                    "error_code": "no_agenda",
                    "detail": "El servicio de revision no tiene agenda asociada.",
                }
            )

        if (date is None) != (start_time is None):
            raise ValueError(
                "Para elegir un horario se deben indicar date y start_time."
            )

        suggested = self._first_suggested_slot(review)

        if date is not None and start_time is not None:
            slot: dict[str, Any] | None = {
                "date": date,
                "start_time": start_time,
            }
        else:
            slot = suggested

        if slot is None:
            raise ReviewReservationFailedError(
                {
                    "ok": False,
                    "error_code": "no_slots_available",
                    "detail": "No hay slots priority disponibles para aprobar.",
                }
            )

        appointment = self._reserve(review, slot)

        review.status = ReviewStatus.APPROVED
        review.decision = "approved"
        review.approved_slot = {
            "date": str(slot["date"])[:10],
            "start_time": _fmt_time(slot["start_time"]),
        }
        review.reservation = appointment
        review.resolved_at = _utc_now_iso()

        self._record_decision(review, suggested=suggested)

        return review

    def reject_review(
        self,
        review_id: str,
        reason: str | None = None,
    ) -> PriorityReview:
        review = self._get_pending(review_id)

        review.status = ReviewStatus.REJECTED
        review.decision = "rejected"
        review.decision_reason = reason
        review.resolved_at = _utc_now_iso()

        self._record_decision(
            review,
            suggested=self._first_suggested_slot(review),
        )

        return review

    # ---------- internos ----------

    def _get_pending(self, review_id: str) -> PriorityReview:
        review = self.get_review(review_id)

        if review.is_resolved:
            raise ReviewAlreadyResolvedError(
                f"El review {review_id} ya esta {review.status.value}."
            )

        return review

    @staticmethod
    def _first_suggested_slot(
        review: PriorityReview,
    ) -> dict[str, Any] | None:
        for day in review.suggested_slots:
            if day["slots"]:
                return {"date": day["date"], "start_time": day["slots"][0]}

        return None

    def _reserve(
        self,
        review: PriorityReview,
        slot: dict[str, Any],
    ) -> dict[str, Any]:
        if self.agenda_tools is None:
            raise ReviewReservationFailedError(
                {
                    "ok": False,
                    "error_code": "no_agenda",
                    "detail": "El servicio de revision no tiene agenda asociada.",
                }
            )

        result = self.agenda_tools.reserve(
            date=slot["date"],
            start_time=slot["start_time"],
            patient_id=review.session_id,
            priority=True,
        )

        if not result["ok"]:
            raise ReviewReservationFailedError(result)

        return result["appointment"]

    def _record_decision(
        self,
        review: PriorityReview,
        suggested: dict[str, Any] | None,
    ) -> None:
        changed_slot = (
            review.approved_slot is not None
            and suggested is not None
            and review.approved_slot != suggested
        )

        self.decision_log.append(
            {
                "review_id": review.review_id,
                "session_id": review.session_id,
                "ai_classification": review.classification,
                "human_decision": review.decision,
                "decision_reason": review.decision_reason,
                "suggested_slot": suggested,
                "approved_slot": review.approved_slot,
                "changed_slot": changed_slot,
                "resolved_at": review.resolved_at,
            }
        )
