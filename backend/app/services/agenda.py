from datetime import date as date_type, datetime, time, timedelta
from typing import Any

from app.models.agenda import Appointment, AppointmentType, SLOT_MINUTES


WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


class SlotInvalidError(ValueError):
    """El horario pedido no es un slot valido dentro del horario de atencion."""


class SlotUnavailableError(ValueError):
    """El slot existe pero ya esta ocupado por otro turno."""


class PriorityNotAllowedError(ValueError):
    """El slot no admite turnos priority segun la configuracion vigente."""


def _parse_time(value: Any) -> time:
    if isinstance(value, time):
        return value
    try:
        return datetime.strptime(str(value), "%H:%M").time()
    except ValueError:
        raise ValueError(f"Horario inválido: {value!r} (esperado HH:MM)")


def _parse_intervals(config: dict, field_name: str) -> dict[int, list[tuple[time, time]]]:
    intervals: dict[int, list[tuple[time, time]]] = {}

    for day_name, day_intervals in config.items():
        weekday = WEEKDAYS.get(str(day_name).lower())

        if weekday is None:
            raise ValueError(f"Día inválido en {field_name}: {day_name!r}")

        parsed = []

        for interval in day_intervals:
            start = _parse_time(interval[0])
            end = _parse_time(interval[1])

            if start >= end:
                raise ValueError(
                    f"Intervalo inválido en {field_name} para {day_name}: "
                    f"{start:%H:%M}-{end:%H:%M}"
                )

            parsed.append((start, end))

        intervals[weekday] = sorted(parsed)

    return intervals


class Agenda:
    """Agenda en memoria para el MVP.

    working_hours: dias y horarios de atencion.
    priority_hours: subconjunto de horarios donde se permiten turnos
        priority. Si no se configura, priority puede reservarse en
        cualquier horario disponible.
    """

    SLOT_MINUTES = SLOT_MINUTES

    def __init__(
        self,
        working_hours: dict,
        priority_hours: dict | None = None,
    ):
        self._working_hours = _parse_intervals(
            working_hours, "working_hours"
        )
        self._priority_hours = (
            _parse_intervals(priority_hours, "priority_hours")
            if priority_hours is not None
            else None
        )
        self._appointments: list[Appointment] = []

    @property
    def appointments(self) -> list[Appointment]:
        return list(self._appointments)

    def generate_day_slots(self, day: date_type) -> list[time]:
        """Genera los slots de 30 minutos dentro del horario del dia."""
        intervals = self._working_hours.get(day.weekday(), [])
        slots: list[time] = []

        for start, end in intervals:
            current = datetime.combine(day, start)
            close = datetime.combine(day, end)

            while current + timedelta(minutes=self.SLOT_MINUTES) <= close:
                slots.append(current.time())
                current += timedelta(minutes=self.SLOT_MINUTES)

        return sorted(slots)

    def _is_within_priority_hours(self, day: date_type, slot: time) -> bool:
        if self._priority_hours is None:
            return True

        intervals = self._priority_hours.get(day.weekday(), [])
        slot_start = slot.hour * 60 + slot.minute
        slot_end = slot_start + self.SLOT_MINUTES

        return any(
            start.hour * 60 + start.minute <= slot_start
            and slot_end <= end.hour * 60 + end.minute
            for start, end in intervals
        )

    def appointments_on(self, day: date_type) -> list[Appointment]:
        return [a for a in self._appointments if a.date == day]

    def is_slot_available(
        self,
        day: date_type,
        slot: time,
        duration_minutes: int = SLOT_MINUTES,
    ) -> bool:
        if slot not in self.generate_day_slots(day):
            return False

        slot_start = datetime.combine(day, slot)
        slot_end = slot_start + timedelta(minutes=duration_minutes)

        for appointment in self.appointments_on(day):
            start = datetime.combine(day, appointment.start)
            end = start + timedelta(minutes=appointment.duration_minutes)

            if slot_start < end and slot_end > start:
                return False

        return True

    def get_available_slots(
        self,
        day: date_type,
        appointment_type: AppointmentType = AppointmentType.NORMAL,
    ) -> list[time]:
        appointment_type = AppointmentType(appointment_type)
        available = []

        for slot in self.generate_day_slots(day):
            if not self.is_slot_available(day, slot):
                continue

            if (
                appointment_type == AppointmentType.PRIORITY
                and not self._is_within_priority_hours(day, slot)
            ):
                continue

            available.append(slot)

        return available

    def add_appointment(self, appointment: Appointment) -> Appointment:
        """Agrega un turno existente validando horario y disponibilidad."""
        start = _parse_time(appointment.start)

        if start not in self.generate_day_slots(appointment.date):
            raise SlotInvalidError(
                f"El horario {start:%H:%M} no es un slot valido del "
                f"{appointment.date:%Y-%m-%d}."
            )

        if not self.is_slot_available(
            appointment.date,
            start,
            duration_minutes=appointment.duration_minutes,
        ):
            raise SlotUnavailableError(
                f"El slot {start:%H:%M} del {appointment.date:%Y-%m-%d} "
                f"no esta disponible."
            )

        appointment.start = start
        self._appointments.append(appointment)

        return appointment

    def book_appointment(
        self,
        day: date_type,
        slot: time,
        patient_id: str,
        appointment_type: AppointmentType = AppointmentType.NORMAL,
    ) -> Appointment:
        slot = _parse_time(slot)
        appointment_type = AppointmentType(appointment_type)

        if not patient_id:
            raise ValueError("Se requiere un identificador de paciente.")

        if (
            appointment_type == AppointmentType.PRIORITY
            and not self._is_within_priority_hours(day, slot)
        ):
            raise PriorityNotAllowedError(
                f"El slot {slot:%H:%M} del {day:%Y-%m-%d} no admite "
                f"turnos priority."
            )

        return self.add_appointment(
            Appointment(
                date=day,
                start=slot,
                patient_id=patient_id,
                appointment_type=appointment_type,
                duration_minutes=self.SLOT_MINUTES,
            )
        )

    def find_appointment(
        self,
        day: date_type,
        slot: time,
    ) -> Appointment | None:
        slot = _parse_time(slot)

        for appointment in self.appointments_on(day):
            if appointment.start == slot:
                return appointment

        return None
