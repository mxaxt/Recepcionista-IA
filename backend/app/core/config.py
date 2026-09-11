"""Configuracion explicita de zona horaria del consultorio.

Los servidores (Render) corren en UTC: usar date.today() o un datetime
naive puede corridas de 3-4 horas el calendario real del consultorio
argentino. Todo lo que necesite "hoy en el consultorio" debe usar
clinic_today().

Se prefiere ZoneInfo con la zona nominal; si la base IANA del sistema
no esta disponible (p. ej. Windows local sin el paquete tzdata), se
cae al offset fijo UTC-3: Argentina no tiene horario de verano desde
2009, por lo que el offset es estable.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

CLINIC_TIMEZONE_NAME = "America/Argentina/Buenos_Aires"

try:
    CLINIC_TIMEZONE = ZoneInfo(CLINIC_TIMEZONE_NAME)
except Exception:
    CLINIC_TIMEZONE = timezone(
        timedelta(hours=-3),
        name=CLINIC_TIMEZONE_NAME,
    )


def clinic_now() -> datetime:
    return datetime.now(CLINIC_TIMEZONE)


def clinic_today() -> date:
    return clinic_now().date()
