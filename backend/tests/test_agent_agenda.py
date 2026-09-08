import unittest
from datetime import date, time
from typing import Any

from app.agents.agent import Agent
from app.memory.conversation import ConversationMemory
from app.providers.fake_provider import FakeProvider
from app.services.agenda import Agenda
from app.tools.agenda_tools import AgendaTools


LUNES = date(2026, 9, 14)
MARTES = date(2026, 9, 15)  # dia cerrado
MIERCOLES = date(2026, 9, 16)

WORKING_HOURS = {
    "monday": [("15:00", "19:00")],
    "wednesday": [("10:00", "12:00"), ("16:00", "20:00")],
    "friday": [("10:00", "12:00"), ("16:00", "20:00")],
}


class FakeClassifier:

    async def classify(self, message: str) -> dict[str, Any]:
        return {
            "status": "NORMAL",
            "priority": False,
            "urgency": False,
            "root_canal": False,
            "double_check": {
                "confirmed": True,
                "analysis_1": {"urgency": False, "root_canal": False},
                "analysis_2": {"urgency": False, "root_canal": False},
            },
        }


def crear_agenda() -> Agenda:
    agenda = Agenda(working_hours=WORKING_HOURS)
    agenda.book_appointment(LUNES, "15:00", "paciente-previo")
    return agenda


class AgentSinAgendaTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.agent = Agent(
            provider=FakeProvider(),
            memory=ConversationMemory(),
            system_prompt="PROMPT_BASE",
            classifier=FakeClassifier(),
        )

    async def test_chat_sigue_funcionando_igual_sin_agenda(self):
        respuesta = await self.agent.chat("s1", "Hola")

        self.assertEqual(
            respuesta,
            "Hola 👋 Soy la recepcionista virtual.",
        )

    def test_check_availability_sin_agenda_falla_explicitamente(self):
        with self.assertRaises(RuntimeError):
            self.agent.check_availability()

    def test_book_appointment_sin_agenda_falla_explicitamente(self):
        with self.assertRaises(RuntimeError):
            self.agent.book_appointment(
                date=LUNES,
                start_time="16:00",
                patient_id="paciente-1",
            )


class AgentConAgendaTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.agenda = crear_agenda()
        self.tools = AgendaTools(agenda=self.agenda)
        self.agent = Agent(
            provider=FakeProvider(),
            memory=ConversationMemory(),
            system_prompt="PROMPT_BASE",
            classifier=FakeClassifier(),
            agenda=self.tools,
        )

    def test_check_availability_usa_la_agenda_compartida(self):
        result = self.agent.check_availability(preferred_date=LUNES)

        self.assertTrue(result["ok"])

        dia = result["availability"][0]
        self.assertEqual(dia["date"], "2026-09-14")
        self.assertNotIn("15:00", dia["slots"])
        self.assertIn("15:30", dia["slots"])

    def test_check_availability_priority_muestra_disponibilidad_priority(self):
        result = self.agent.check_availability(priority=True)

        self.assertTrue(result["ok"])
        self.assertEqual(result["appointment_type"], "priority")
        self.assertTrue(len(result["availability"]) > 0)

    def test_book_appointment_reserva_en_la_agenda(self):
        result = self.agent.book_appointment(
            date=LUNES,
            start_time="16:00",
            patient_id="paciente-nuevo",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["appointment"]["patient_id"], "paciente-nuevo")
        self.assertEqual(
            result["appointment"]["appointment_type"],
            "normal",
        )

        horarios = self.agenda.get_available_slots(LUNES)
        self.assertNotIn(time(16, 0), horarios)

    def test_book_appointment_priority_reserva_como_priority(self):
        result = self.agent.book_appointment(
            date=MIERCOLES,
            start_time="11:00",
            patient_id="paciente-prio",
            priority=True,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(
            result["appointment"]["appointment_type"],
            "priority",
        )

    def test_book_appointment_slot_ocupado_devuelve_error_estructurado(self):
        result = self.agent.book_appointment(
            date=LUNES,
            start_time="15:00",
            patient_id="paciente-tardio",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "unavailable")

    def test_book_appointment_dia_cerrado_devuelve_error(self):
        result = self.agent.book_appointment(
            date=MARTES,
            start_time="10:00",
            patient_id="paciente-x",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "invalid_slot")

    def test_reserva_por_agente_se_ve_reflejada_en_chequeo_posterior(self):
        self.agent.book_appointment(
            date=MIERCOLES,
            start_time="10:00",
            patient_id="paciente-a",
        )

        result = self.agent.check_availability(preferred_date=MIERCOLES)

        self.assertNotIn("10:00", result["availability"][0]["slots"])

    async def test_chat_no_se_ve_alterado_por_reservas(self):
        self.agent.book_appointment(
            date=LUNES,
            start_time="17:00",
            patient_id="paciente-1",
        )

        respuesta = await self.agent.chat("s1", "Hola")

        self.assertEqual(
            respuesta,
            "Hola 👋 Soy la recepcionista virtual.",
        )
        self.assertEqual(
            [m["role"] for m in self.agent.memory.get_messages("s1")],
            ["user", "assistant"],
        )

    def test_api_puntual_sin_session_id_no_toca_memoria(self):
        memoria_antes = dict(self.agent.memory.conversations)

        self.agent.book_appointment(
            date=LUNES,
            start_time="18:00",
            patient_id="paciente-1",
        )

        self.assertEqual(self.agent.memory.conversations, memoria_antes)


if __name__ == "__main__":
    unittest.main()
