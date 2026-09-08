from datetime import date, time

from pydantic import BaseModel, Field

from app.models.agenda import AppointmentType


class AppointmentCreate(BaseModel):
    date: date
    start: time
    patient_id: str = Field(min_length=1)
    appointment_type: AppointmentType = AppointmentType.NORMAL


class SlotsResponse(BaseModel):
    date: date
    appointment_type: AppointmentType
    slots: list[str]


class AppointmentOut(BaseModel):
    date: date
    start: str
    end: str
    patient_id: str
    appointment_type: AppointmentType
    duration_minutes: int
