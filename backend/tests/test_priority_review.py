import unittest
from datetime import date, time
from typing import Any

from app.agents.agent import Agent
from app.memory.conversation import ConversationMemory
from app.models.review import PriorityReview, ReviewStatus
from app.providers.fake_provider import FakeProvider
from app.services.agenda import Agenda
from app.services.priority_review import (
    PriorityReviewService,
    ReviewAlreadyResolvedError,
    ReviewNotFoundError,
    ReviewReservationFailedError,
)
from app.tools.agenda_tools import AgendaTools


LUNES = date(2026, 9, 14)
MIERCOLES = date(2026, 9, 16)

WORKING_HOURS = {
    "monday": [("15:00", "19:00")],
    "wednesday": [("10:00", "12:00"), ("16:00", "20:00")],
    "friday": [("10:00", "12:00"), ("16:00", "20:00")],
}

CLASIFICATION_PRIORITY = {
    "status": "PRIORITY",
    "priority": True,
    "urgency": True,
    "root_canal": False,
    "double_check": {"confirmed": True},
}


def crear_servicio() -> tuple[PriorityReviewService, Agenda]:
    agenda = Agenda(working_hours=WORKING_HOURS)
    tools = AgendaTools(agenda=agenda, horizon_days=7)
    service = PriorityReviewService(agenda_tools=tools)
    return service, agenda


def crear_review(service: PriorityReviewService) -> PriorityReview:
    return service.create_review(
        session_id="sesion-1",
        message="tengo la cara hinchada y fiebre",
        classification=CLASIFICATION_PRIORITY,
    )


class CesionDeReviewsTests(unittest.TestCase):

    def setUp(self):
        self.service, self.agenda = crear_servicio()

    def test_creacion_estado_pendiente_y_datos_basicos(self):
        review = crear_review(self.service)

        self.assertEqual(review.status, ReviewStatus.PENDING)
        self.assertEqual(review.session_id, "sesion-1")
        self.assertEqual(review.message, "tengo la cara hinchada y fiebre")
        self.assertEqual(review.classification, CLASIFICATION_PRIORITY)
        self.assertIsNotNone(review.review_id)
        self.assertIsNotNone(review.created_at)
        self.assertIsNone(review.resolved_at)
        self.assertIsNone(review.reservation)
        self.assertFalse(review.is_resolved)

    def test_sugerencias_de_slots_priority_al_crearse(self):
        review = crear_review(self.service)

        self.assertTrue(len(review.suggested_slots) > 0)

        primer_dia = review.suggested_slots[0]

        self.assertGreaterEqual(primer_dia["date"], date.today().isoformat())
        self.assertTrue(len(primer_dia["slots"]) > 0)

    def test_to_dict_serializable(self):
        review = crear_review(self.service)
        data = review.to_dict()

        self.assertEqual(data["status"], "PENDING")
        self.assertEqual(data["review_id"], review.review_id)

    def test_get_review_inexistente(self):
        with self.assertRaises(ReviewNotFoundError):
            self.service.get_review("no-existe")

    def test_list_reviews_y_filtro_por_estado(self):
        review = crear_review(self.service)
        crear_review(self.service)

        self.assertEqual(len(self.service.list_reviews()), 2)
        self.assertEqual(
            len(self.service.list_reviews(status=ReviewStatus.PENDING)),
            2,
        )
        self.assertEqual(
            len(self.service.list_reviews(status=ReviewStatus.APPROVED)),
            0,
        )

        self.service.reject_review(review.review_id)

        self.assertEqual(
            len(self.service.list_reviews(status=ReviewStatus.REJECTED)),
            1,
        )


class AprobacionTests(unittest.TestCase):

    def setUp(self):
        self.service, self.agenda = crear_servicio()
        self.review = crear_review(self.service)

    def test_aprobar_sin_horario_usa_la_primera_sugerencia(self):
        sugerido = self.review.suggested_slots[0]

        aprobado = self.service.approve_review(self.review.review_id)

        self.assertEqual(aprobado.status, ReviewStatus.APPROVED)
        self.assertEqual(
            aprobado.approved_slot,
            {"date": sugerido["date"], "start_time": sugerido["slots"][0]},
        )
        self.assertIsNotNone(aprobado.resolved_at)
        self.assertTrue(aprobado.is_resolved)

    def test_aprobar_reserva_en_la_agenda_como_priority(self):
        aprobado = self.service.approve_review(self.review.review_id)

        self.assertEqual(aprobado.reservation["appointment_type"], "priority")
        self.assertEqual(aprobado.reservation["patient_id"], "sesion-1")

        fecha = date.fromisoformat(aprobado.approved_slot["date"])
        hora = time.fromisoformat(aprobado.approved_slot["start_time"])

        self.assertIsNotNone(self.agenda.find_appointment(fecha, hora))

    def test_aprobar_con_horario_elegido_por_el_humano(self):
        aprobado = self.service.approve_review(
            self.review.review_id,
            date="2026-09-14",
            start_time="17:30",
        )

        self.assertEqual(
            aprobado.approved_slot,
            {"date": "2026-09-14", "start_time": "17:30"},
        )
        self.assertEqual(aprobado.reservation["start"], "17:30")

        slot_elegido = self.agenda.find_appointment(LUNES, time(17, 30))
        self.assertIsNotNone(slot_elegido)

    def test_aprobar_horario_ocupado_deja_el_review_pendiente(self):
        self.service.approve_review(
            self.review.review_id,
            date="2026-09-14",
            start_time="17:30",
        )

        segunda = crear_review(self.service)

        with self.assertRaises(ReviewReservationFailedError) as ctx:
            self.service.approve_review(
                segunda.review_id,
                date="2026-09-14",
                start_time="17:30",
            )

        self.assertEqual(ctx.exception.result["error_code"], "unavailable")
        self.assertEqual(
            self.service.get_review(segunda.review_id).status,
            ReviewStatus.PENDING,
        )

    def test_aprobar_con_date_sin_start_time_es_error(self):
        with self.assertRaises(ValueError):
            self.service.approve_review(
                self.review.review_id,
                date="2026-09-14",
            )

    def test_aprobar_inexistente(self):
        with self.assertRaises(ReviewNotFoundError):
            self.service.approve_review("fantasma")

    def test_aprobar_dos_veces_es_error(self):
        self.service.approve_review(self.review.review_id)

        with self.assertRaises(ReviewAlreadyResolvedError):
            self.service.approve_review(self.review.review_id)

    def test_sin_slots_disponibles_no_se_puede_aprobar(self):
        agenda = Agenda(working_hours={"monday": [("15:00", "15:30")]})
        tools = AgendaTools(agenda=agenda, horizon_days=1)
        service = PriorityReviewService(agenda_tools=tools)

        agenda.book_appointment(LUNES, "15:00", "otro", "priority")

        review = service.create_review(
            session_id="s2",
            message="urgencia",
            classification=CLASIFICATION_PRIORITY,
        )

        self.assertEqual(review.suggested_slots, [])

        with self.assertRaises(ReviewReservationFailedError) as ctx:
            service.approve_review(review.review_id)

        self.assertEqual(
            ctx.exception.result["error_code"],
            "no_slots_available",
        )

    def test_service_sin_agenda_no_puede_aprobar(self):
        service = PriorityReviewService()

        review = service.create_review(
            session_id="s3",
            message="urgencia",
            classification=CLASIFICATION_PRIORITY,
        )

        self.assertEqual(review.suggested_slots, [])

        with self.assertRaises(ReviewReservationFailedError) as ctx:
            service.approve_review(review.review_id)

        self.assertEqual(ctx.exception.result["error_code"], "no_agenda")


class RechazoTests(unittest.TestCase):

    def setUp(self):
        self.service, self.agenda = crear_servicio()
        self.review = crear_review(self.service)

    def test_rechazo_no_reserva_nada(self):
        rechazado = self.service.reject_review(
            self.review.review_id,
            reason="el dolor no parece urgente",
        )

        self.assertEqual(rechazado.status, ReviewStatus.REJECTED)
        self.assertEqual(rechazado.decision, "rejected")
        self.assertEqual(
            rechazado.decision_reason,
            "el dolor no parece urgente",
        )
        self.assertIsNone(rechazado.reservation)
        self.assertEqual(self.agenda.appointments, [])

    def test_rechazar_despues_de_aprobar_es_error(self):
        self.service.approve_review(self.review.review_id)

        with self.assertRaises(ReviewAlreadyResolvedError):
            self.service.reject_review(self.review.review_id)

    def test_rechazar_dos_veces_es_error(self):
        self.service.reject_review(self.review.review_id)

        with self.assertRaises(ReviewAlreadyResolvedError):
            self.service.reject_review(self.review.review_id)

    def test_rechazar_inexistente(self):
        with self.assertRaises(ReviewNotFoundError):
            self.service.reject_review("fantasma")


class DecisionLogTests(unittest.TestCase):

    def setUp(self):
        self.service, self.agenda = crear_servicio()

    def test_registra_que_clasifico_la_ia_y_que_decidio_el_humano(self):
        aprobado = self.service.approve_review(
            crear_review(self.service).review_id
        )

        entrada = self.service.decision_log[0]

        self.assertEqual(entrada["ai_classification"], CLASIFICATION_PRIORITY)
        self.assertEqual(entrada["human_decision"], "approved")
        self.assertIsNotNone(entrada["suggested_slot"])
        self.assertEqual(entrada["approved_slot"], aprobado.approved_slot)
        self.assertFalse(entrada["changed_slot"])
        self.assertEqual(entrada["resolved_at"], aprobado.resolved_at)

    def test_change_slot_queda_registrado_como_cambio(self):
        review = crear_review(self.service)
        sugerido = review.suggested_slots[0]

        self.service.approve_review(
            review.review_id,
            date="2026-09-16",
            start_time="16:30",
        )

        entrada = self.service.decision_log[-1]

        self.assertEqual(
            entrada["suggested_slot"],
            {"date": sugerido["date"], "start_time": sugerido["slots"][0]},
        )
        self.assertEqual(
            entrada["approved_slot"],
            {"date": "2026-09-16", "start_time": "16:30"},
        )
        self.assertTrue(entrada["changed_slot"])

    def test_reject_registra_decision_sin_aprobacion(self):
        review = crear_review(self.service)
        self.service.reject_review(review.review_id, reason="no aplica")

        entrada = self.service.decision_log[-1]

        self.assertEqual(entrada["human_decision"], "rejected")
        self.assertIsNone(entrada["approved_slot"])
        self.assertFalse(entrada["changed_slot"])


class FakeClassifier:

    def __init__(self, status: str):
        self.status = status

    async def classify(self, message: str) -> dict[str, Any]:
        base = dict(CLASIFICATION_PRIORITY)
        base["status"] = self.status
        base["priority"] = self.status == "PRIORITY"
        return base


class AgentPriorityReviewHookTests(unittest.IsolatedAsyncioTestCase):

    async def test_chat_priority_crea_un_review_pendiente(self):
        service, agenda = crear_servicio()
        agent = Agent(
            provider=FakeProvider(),
            memory=ConversationMemory(),
            system_prompt="PROMPT_BASE",
            classifier=FakeClassifier("PRIORITY"),
            agenda=AgendaTools(agenda=agenda, horizon_days=7),
            reviews=service,
        )

        respuesta = await agent.chat("s1", "me duele y estoy hinchado")

        self.assertEqual(len(service.list_reviews()), 1)
        review = service.list_reviews()[0]
        self.assertEqual(review.session_id, "s1")
        self.assertEqual(review.message, "me duele y estoy hinchado")
        self.assertEqual(review.status, ReviewStatus.PENDING)
        self.assertEqual(
            respuesta,
            "Hola 👋 Soy la recepcionista virtual.",
        )
        self.assertEqual(
            [m["role"] for m in agent.memory.get_messages("s1")],
            ["user", "assistant"],
        )

    async def test_chat_normal_no_crea_review(self):
        service, agenda = crear_servicio()
        agent = Agent(
            provider=FakeProvider(),
            memory=ConversationMemory(),
            system_prompt="PROMPT_BASE",
            classifier=FakeClassifier("NORMAL"),
            reviews=service,
        )

        await agent.chat("s1", "quiero un turno de limpieza")

        self.assertEqual(service.list_reviews(), [])

    async def test_chat_review_status_no_crea_review(self):
        service, agenda = crear_servicio()
        agent = Agent(
            provider=FakeProvider(),
            memory=ConversationMemory(),
            system_prompt="PROMPT_BASE",
            classifier=FakeClassifier("REVIEW"),
            reviews=service,
        )

        await agent.chat("s1", "me duele una muela")

        self.assertEqual(service.list_reviews(), [])


if __name__ == "__main__":
    unittest.main()
