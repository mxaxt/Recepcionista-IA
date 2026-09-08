"""Composicion del servicio de revision humana para el MVP.

Comparte la Agenda en memoria de app.core.agenda_container a traves de
una fachada AgendaTools, de modo que las aprobaciones de la cola de
revision impactan en la misma agenda que exponen /agenda/* y el Agent.
"""

from app.core.agenda_container import get_agenda
from app.services.priority_review import PriorityReviewService
from app.tools.agenda_tools import AgendaTools


_agenda_tools = AgendaTools(agenda=get_agenda())

_service = PriorityReviewService(agenda_tools=_agenda_tools)


def get_priority_review_service() -> PriorityReviewService:
    return _service
