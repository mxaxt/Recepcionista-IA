"""API minima de Human Review para casos PRIORITY.

Las rutas solo traducen HTTP <-> servicio de dominio; no contienen
reglas de negocio ni de agenda.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import require_admin_token
from app.models.review import ReviewStatus
from app.schemas.review import (
    ApproveRequest,
    RejectRequest,
    ReviewCreate,
    ReviewOut,
)
from app.services.priority_review import (
    PriorityReviewService,
    ReviewAlreadyResolvedError,
    ReviewNotFoundError,
    ReviewReservationFailedError,
)
from app.core.review_container import get_priority_review_service


router = APIRouter(
    prefix="/reviews",
    tags=["reviews"],
    dependencies=[Depends(require_admin_token)],
)


PRIORITY_CLASSIFICATION_STATUS = "PRIORITY"

_BAD_SLOT_CODES = {
    "invalid_date",
    "invalid_time",
    "invalid_slot",
    "priority_not_allowed",
}


@router.post("", response_model=ReviewOut, status_code=201)
def create_review(
    payload: ReviewCreate,
    service: PriorityReviewService = Depends(get_priority_review_service),
):
    if payload.classification.get("status") != PRIORITY_CLASSIFICATION_STATUS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Solo las clasificaciones con status PRIORITY generan "
                "un caso de revision."
            ),
        )

    review = service.create_review(
        session_id=payload.session_id,
        message=payload.message,
        classification=payload.classification,
    )

    return ReviewOut(**review.to_dict())


@router.get("", response_model=list[ReviewOut])
def list_reviews(
    status: ReviewStatus | None = Query(
        None,
        description="Filtrar por estado: PENDING, APPROVED o REJECTED",
    ),
    service: PriorityReviewService = Depends(get_priority_review_service),
):
    reviews = service.list_reviews(status=status)

    return [ReviewOut(**review.to_dict()) for review in reviews]


@router.get("/{review_id}", response_model=ReviewOut)
def get_review(
    review_id: str,
    service: PriorityReviewService = Depends(get_priority_review_service),
):
    try:
        review = service.get_review(review_id)
    except ReviewNotFoundError:
        raise HTTPException(status_code=404, detail="Review no encontrado.")

    return ReviewOut(**review.to_dict())


@router.post("/{review_id}/approve", response_model=ReviewOut)
def approve_review(
    review_id: str,
    payload: ApproveRequest = ApproveRequest(),
    service: PriorityReviewService = Depends(get_priority_review_service),
):
    try:
        review = service.approve_review(
            review_id,
            date=payload.date,
            start_time=payload.start_time,
        )
    except ReviewNotFoundError:
        raise HTTPException(status_code=404, detail="Review no encontrado.")
    except ReviewAlreadyResolvedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ReviewReservationFailedError as exc:
        code = exc.result.get("error_code")
        status_code = 400 if code in _BAD_SLOT_CODES else 409
        raise HTTPException(status_code=status_code, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ReviewOut(**review.to_dict())


@router.post("/{review_id}/reject", response_model=ReviewOut)
def reject_review(
    review_id: str,
    payload: RejectRequest = RejectRequest(),
    service: PriorityReviewService = Depends(get_priority_review_service),
):
    try:
        review = service.reject_review(review_id, reason=payload.reason)
    except ReviewNotFoundError:
        raise HTTPException(status_code=404, detail="Review no encontrado.")
    except ReviewAlreadyResolvedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return ReviewOut(**review.to_dict())
