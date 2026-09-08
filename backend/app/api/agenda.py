from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.agenda import Appointment, AppointmentType
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


# ---------------------------------------------------------------------------
# Datos de desarrollo/demo.
# NO forman parte de la logica de dominio: solo sirven para probar la API
# y Swagger sin base de datos. Reemplazar cuando exista la agenda real.
# ---------------------------------------------------------------------------
DEV_WORKING_HOURS = {
    "monday": [("15:00", "19:00")],
    "wednesday": [("10:00", "12:00"), ("16:00", "20:00")],
    "friday": [("10:00", "12:00"), ("16:00", "20:00")],
}

# Turnos ya existentes para que las pruebas de disponibilidad tengan sentido.
DEV_NEXT_WEEK_MONDAY = date(2026, 9, 14)
DEV_NEXT_WEEK_WEDNESDAY = date(2026, 9, 16)

DEV_SEED_APPOINTMENTS = [
    Appointment(
        date=DEV_NEXT_WEEK_MONDAY,
        start=time(15, 0),
        patient_id="demo-paciente-1",
        appointment_type=AppointmentType.NORMAL,
    ),
    Appointment(
        date=DEV_NEXT_WEEK_MONDAY,
        start=time(16, 30),
        patient_id="demo-paciente-2",
        appointment_type=AppointmentType.PRIORITY,
    ),
    Appointment(
        date=DEV_NEXT_WEEK_WEDNESDAY,
        start=time(10, 0),
        patient_id="demo-paciente-3",
        appointment_type=AppointmentType.NORMAL,
    ),
]


def create_dev_agenda() -> Agenda:
    agenda = Agenda(working_hours=DEV_WORKING_HOURS)

    for appointment in DEV_SEED_APPOINTMENTS:
        agenda.add_appointment(appointment)

    return agenda


_agenda = create_dev_agenda()


def get_agenda() -> Agenda:
    return _agenda


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
