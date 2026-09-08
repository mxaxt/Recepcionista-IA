from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.agenda import AppointmentType
from app.schemas.agenda import (
    AppointmentCreate,
    AppointmentOut,
    SlotsResponse,
)
from app.services.agenda import (
    Agenda,
    PriorityNotAllowedError,
    SlotInvalidError,
    SlotUnavailableError,
)

# La agenda de desarrollo/demo y su factory viven en un unico punto de
# composicion (app.core.agenda_container) para que API y Agent compartan
# la misma instancia en memoria.
from app.core.agenda_container import create_dev_agenda, get_agenda


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/agenda", tags=["agenda"])


@router.get("/slots", response_model=SlotsResponse)
def get_available_slots(
    day: date = Query(alias="date", description="Fecha YYYY-MM-DD"),
    appointment_type: AppointmentType = Query(
        AppointmentType.NORMAL,
        description="Tipo de turno: normal o priority",
    ),
    agenda: Agenda = Depends(get_agenda),
):
    try:
        slots = agenda.get_available_slots(day, appointment_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return SlotsResponse(
        date=day,
        appointment_type=appointment_type,
        slots=[f"{slot:%H:%M}" for slot in slots],
    )


@router.post("/appointments", response_model=AppointmentOut, status_code=201)
def book_appointment(
    payload: AppointmentCreate,
    agenda: Agenda = Depends(get_agenda),
):
    try:
        appointment = agenda.book_appointment(
            payload.date,
            payload.start,
            payload.patient_id,
            payload.appointment_type,
        )
    except SlotUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except PriorityNotAllowedError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except SlotInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return AppointmentOut(**appointment.to_dict())
