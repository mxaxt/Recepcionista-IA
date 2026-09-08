from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum


SLOT_MINUTES = 30


class AppointmentType(str, Enum):
    """Tipos de turno soportados por la agenda."""

    NORMAL = "normal"
    PRIORITY = "priority"


@dataclass
class Appointment:
    date: date
    start: time
    patient_id: str
    appointment_type: AppointmentType = AppointmentType.NORMAL
    duration_minutes: int = SLOT_MINUTES

    @property
    def end(self) -> time:
        end_dt = datetime.combine(self.date, self.start) + timedelta(
            minutes=self.duration_minutes
        )
        return end_dt.time()

    def overlaps(self, slot_start: time, slot_end: time) -> bool:
        """Indica si un intervalo [slot_start, slot_end) intersecta al turno."""
        return slot_start < self.end and slot_end > self.start

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "start": self.start.strftime("%H:%M"),
            "end": self.end.strftime("%H:%M"),
            "patient_id": self.patient_id,
            "appointment_type": self.appointment_type.value,
            "duration_minutes": self.duration_minutes,
        }
