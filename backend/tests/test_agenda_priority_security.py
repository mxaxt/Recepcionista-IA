"""Regla de seguridad: una reserva PRIORITY no puede crearse por la via
directa de la API de agenda; solo un PriorityReview aprobado puede
reservar via AgendaTools.
"""

import unittest
from datetime import date, time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.agenda import get_agenda
from app.api.agenda import router as agenda_router
from app.api.reviews import get_priority_review_service
from app.api.reviews import router as reviews_router
from app.services.agenda import Agenda
from app.services.priority_review import PriorityReviewService
from app.tools.agenda_tools import AgendaTools


WORKING_HOURS = {
    "monday": [("15:00", "19:00")],
    "wednesday": [("10:00", "12:00"), ("16:00", "20:00")],
    "friday": [("10:00", "12:00"), ("16:00", "20:00")],
}

LUNES = "2026-09-14"

CLASIFICATION_PRIORITY = {
    "status": "PRIORITY",
    "priority": True,
    "urgency": True,
    "root_canal": False,
    "double_check": {"confirmed": True},
}


class PrioritySecurityTests(unittest.TestCase):

    def setUp(self):
        self.agenda = Agenda(working_hours=WORKING_HOURS)
        self.service = PriorityReviewService(
            agenda_tools=AgendaTools(agenda=self.agenda, horizon_days=7),
        )

        app = FastAPI()
        app.include_router(agenda_router)
        app.include_router(reviews_router)
        app.dependency_overrides[get_agenda] = lambda: self.agenda
        app.dependency_overrides[get_priority_review_service] = (
            lambda: self.service
        )

        self.client = TestClient(app)

    def _post_agenda(self, appointment_type: str):
        return self.client.post(
            "/agenda/appointments",
            json={
                "date": LUNES,
                "start": "16:00",
                "patient_id": "paciente-test",
                "appointment_type": appointment_type,
            },
        )

    def _crear_review(self):
        created = self.client.post(
            "/reviews",
            json={
                "session_id": "sesion-prio",
                "message": "cara hinchada y fiebre",
                "classification": CLASIFICATION_PRIORITY,
            },
        )

        self.assertEqual(created.status_code, 201)

        return created.json()["review_id"]

    # 1. NORMAL directa sigue funcionando

    def test_reserva_normal_directa_sigue_funcionando(self):
        response = self._post_agenda("normal")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json()["appointment_type"],
            "normal",
        )

    def test_reserva_normal_implicita_sigue_funcionando(self):
        response = self.client.post(
            "/agenda/appointments",
            json={
                "date": LUNES,
                "start": "16:00",
                "patient_id": "paciente-test",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json()["appointment_type"],
            "normal",
        )

    # 2. PRIORITY directa rechazada

    def test_reserva_priority_directa_es_rechazada(self):
        response = self._post_agenda("priority")

        self.assertEqual(response.status_code, 403)
        self.assertIn("revision", response.json()["detail"].lower())
        self.assertEqual(self.agenda.appointments, [])

    def test_reserva_priority_rechazada_no_consume_el_slot(self):
        rechazada = self._post_agenda("priority")
        self.assertEqual(rechazada.status_code, 403)

        normal = self._post_agenda("normal")

        self.assertEqual(normal.status_code, 201)

    # 3. Review aprobado sigue reservando PRIORITY

    def test_review_aprobado_reserva_priority(self):
        review_id = self._crear_review()

        approved = self.client.post(
            f"/reviews/{review_id}/approve",
            json={"date": LUNES, "start_time": "16:00"},
        )

        self.assertEqual(approved.status_code, 200)

        body = approved.json()

        self.assertEqual(body["status"], "APPROVED")
        self.assertEqual(
            body["reservation"]["appointment_type"],
            "priority",
        )

        turno = self.agenda.find_appointment(
            date.fromisoformat(LUNES),
            time(16, 0),
        )

        self.assertIsNotNone(turno)
        self.assertEqual(turno.patient_id, "sesion-prio")

    # 4. Review rechazado no crea ninguna reserva

    def test_review_rechazado_no_crea_reserva(self):
        review_id = self._crear_review()

        rejected = self.client.post(
            f"/reviews/{review_id}/reject",
            json={"reason": "sintomas leves"},
        )

        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.json()["status"], "REJECTED")
        self.assertEqual(self.agenda.appointments, [])

    # 5. La reserva aprobada se refleja en GET /agenda/slots

    def test_aprobacion_se_refleja_en_agenda_slots(self):
        antes = self.client.get(
            "/agenda/slots",
            params={"date": LUNES, "appointment_type": "priority"},
        ).json()["slots"]

        self.assertIn("16:00", antes)

        review_id = self._crear_review()
        self.client.post(
            f"/reviews/{review_id}/approve",
            json={"date": LUNES, "start_time": "16:00"},
        )

        despues = self.client.get(
            "/agenda/slots",
            params={"date": LUNES, "appointment_type": "priority"},
        ).json()["slots"]

        self.assertNotIn("16:00", despues)
        self.assertIn("16:30", despues)

    def test_consulta_de_slots_priority_no_se_bloquea(self):
        response = self.client.get(
            "/agenda/slots",
            params={"date": LUNES, "appointment_type": "priority"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.json()["slots"]) > 0)

    # Regla de negocio: el dominio y la fachada NO cambian

    def test_agenda_tools_sigue_reservando_priority_interno(self):
        result = self.service.agenda_tools.reserve(
            date=LUNES,
            start_time="16:00",
            patient_id="flujo-interno",
            priority=True,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(
            result["appointment"]["appointment_type"],
            "priority",
        )


if __name__ == "__main__":
    unittest.main()
