"""Capability de agenda para el Agent.

Fachada deliberadamente chica: NO es un framework de tools generico.
Traduce parametros ya estructurados (fecha, hora, priority) a llamadas
contra el servicio de dominio `Agenda` y devuelve SIEMPRE resultados
estructurados, sin que las excepciones de dominio crucen la frontera.

Las reglas de negocio (slots validos, horarios, solapes, disponibilidad
priority) siguen viviendo exclusivamente en app.services.agenda.
"""

from datetime import date, datetime, timedelta
from typing import Any

from app.core.config import clinic_today
from app.models.agenda import AppointmentType
from app.services.agenda import (
    Agenda,
    PriorityNotAllowedError,
    SlotInvalidError,
    SlotUnavailableError,
)


DEFAULT_HORIZON_DAYS = 14


def _to_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return date.fromisoformat(str(value))


def _format_slots(slots: list) -> list[str]:
    return [f"{slot:%H:%M}" for slot in slots]


class AgendaTools:

    def __init__(
        self,
        agenda: Agenda,
        horizon_days: int = DEFAULT_HORIZON_DAYS,
    ):
        self.agenda = agenda
        self.horizon_days = horizon_days

    @staticmethod
    def _appointment_type(priority: bool) -> AppointmentType:
        """Politica: los pacientes normales nunca reservan como priority."""
        if priority:
            return AppointmentType.PRIORITY
        return AppointmentType.NORMAL

    def check_availability(
        self,
        preferred_date: Any = None,
        priority: bool = False,
        reference_date: Any = None,
    ) -> dict[str, Any]:
        appointment_type = self._appointment_type(priority)

        if preferred_date is not None:
            try:
                days = [_to_date(preferred_date)]
            except (ValueError, TypeError):
                return {
                    "ok": False,
                    "error_code": "invalid_date",
                    "detail": (
                        f"Fecha invalida: {preferred_date!r} "
                        f"(esperado YYYY-MM-DD)"
                    ),
                }
        else:
            try:
                start = _to_date(
                    reference_date
                    if reference_date is not None
                    else clinic_today()
                )
            except (ValueError, TypeError):
                return {
                    "ok": False,
                    "error_code": "invalid_date",
                    "detail": (
                        f"Fecha de referencia invalida: {reference_date!r}"
                    ),
                }

            days = [
                start + timedelta(offset)
                for offset in range(self.horizon_days)
            ]

        availability = []

        for day in days:
            slots = self.agenda.get_available_slots(day, appointment_type)

            if preferred_date is None and not slots:
                continue

            availability.append({
                "date": day.isoformat(),
                "slots": _format_slots(slots),
            })

        return {
            "ok": True,
            "appointment_type": appointment_type.value,
            "availability": availability,
        }

    def reserve(
        self,
        date: Any,
        start_time: Any,
        patient_id: str,
        priority: bool = False,
    ) -> dict[str, Any]:
        appointment_type = self._appointment_type(priority)

        if not patient_id or not str(patient_id).strip():
            return {
                "ok": False,
                "error_code": "invalid_patient_id",
                "detail": "Se requiere un identificador de paciente.",
            }

        try:
            day = _to_date(date)
        except (ValueError, TypeError):
            return {
                "ok": False,
                "error_code": "invalid_date",
                "detail": f"Fecha invalida: {date!r} (esperado YYYY-MM-DD)",
            }

        try:
            appointment = self.agenda.book_appointment(
                day,
                start_time,
                str(patient_id).strip(),
                appointment_type,
            )
        except SlotInvalidError as exc:
            return {
                "ok": False,
                "error_code": "invalid_slot",
                "detail": str(exc),
            }
        except SlotUnavailableError as exc:
            return {
                "ok": False,
                "error_code": "unavailable",
                "detail": str(exc),
            }
        except PriorityNotAllowedError as exc:
            return {
                "ok": False,
                "error_code": "priority_not_allowed",
                "detail": str(exc),
            }
        except ValueError as exc:
            return {
                "ok": False,
                "error_code": "invalid_time",
                "detail": str(exc),
            }

        return {
            "ok": True,
            "appointment": appointment.to_dict(),
        }
