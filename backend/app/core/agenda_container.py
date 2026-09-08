"""Composicion de la agenda en memoria para el MVP.

Unico punto donde se construye la Agenda de desarrollo: la API y el
Agent comparten esta misma instancia, de modo que un turno reservado
por via del agente se refleja en /agenda/slots y viceversa.

Los datos de abajo son DEMO/DESARROLLO. No forman parte de la logica
de dominio (app.services.agenda) y deberan reemplazarse cuando exista
la persistencia real.
"""

from datetime import date, time

from app.models.agenda import Appointment, AppointmentType
from app.services.agenda import Agenda


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
