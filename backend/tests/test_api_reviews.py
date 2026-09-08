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


CLASIFICATION_PRIORITY = {
    "status": "PRIORITY",
    "priority": True,
    "urgency": True,
    "root_canal": False,
    "double_check": {"confirmed": True},
}

WORKING_HOURS = {
    "monday": [("15:00", "19:00")],
    "wednesday": [("10:00", "12:00"), ("16:00", "20:00")],
    "friday": [("10:00", "12:00"), ("16:00", "20:00")],
}

LUNES = "2026-09-14"


class ApiReviewsTests(unittest.TestCase):

    def setUp(self):
        self.agenda = Agenda(working_hours=WORKING_HOURS)
        self.service = PriorityReviewService(
            agenda_tools=AgendaTools(agenda=self.agenda, horizon_days=7),
        )

        app = FastAPI()
        app.include_router(reviews_router)
        app.include_router(agenda_router)
        app.dependency_overrides[get_priority_review_service] = (
            lambda: self.service
        )
        app.dependency_overrides[get_agenda] = lambda: self.agenda

        self.client = TestClient(app)

    def _crear_review(self) -> str:
        response = self.client.post(
            "/reviews",
            json={
                "session_id": "sesion-swagger",
                "message": "cara hinchada y fiebre",
                "classification": CLASIFICATION_PRIORITY,
            },
        )

        self.assertEqual(response.status_code, 201)

        return response.json()["review_id"]

    # ---------- POST /reviews ----------

    def test_crear_review_priority(self):
        review = self.client.get(
            f"/reviews/{self._crear_review()}"
        ).json()

        self.assertEqual(review["status"], "PENDING")
        self.assertEqual(review["session_id"], "sesion-swagger")
        self.assertEqual(
            review["classification"],
            CLASIFICATION_PRIORITY,
        )
        self.assertTrue(len(review["suggested_slots"]) > 0)

    def test_crear_review_con_clasificacion_no_priority_es_400(self):
        response = self.client.post(
            "/reviews",
            json={
                "session_id": "s1",
                "message": "turno de limpieza",
                "classification": {"status": "NORMAL"},
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_crear_review_sin_campos_es_422(self):
        response = self.client.post("/reviews", json={})

        self.assertEqual(response.status_code, 422)

    # ---------- GET /reviews ----------

    def test_listar_y_filter_por_estado(self):
        self._crear_review()

        todas = self.client.get("/reviews").json()
        pendientes = self.client.get(
            "/reviews",
            params={"status": "PENDING"},
        ).json()
        rechazadas = self.client.get(
            "/reviews",
            params={"status": "REJECTED"},
        ).json()

        self.assertEqual(len(todas), 1)
        self.assertEqual(len(pendientes), 1)
        self.assertEqual(len(rechazadas), 0)

    def test_get_review_inexistente_es_404(self):
        response = self.client.get("/reviews/deadbeef")

        self.assertEqual(response.status_code, 404)

    # ---------- approve ----------

    def test_aprove_acepta_el_primer_slot_sugerido_y_reserva(self):
        review_id = self._crear_review()

        response = self.client.post(f"/reviews/{review_id}/approve", json={})

        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["status"], "APPROVED")
        self.assertEqual(body["decision"], "approved")
        self.assertEqual(
            body["reservation"]["appointment_type"],
            "priority",
        )
        self.assertEqual(
            body["reservation"]["patient_id"],
            "sesion-swagger",
        )

        fecha = date.fromisoformat(body["approved_slot"]["date"])
        self.assertEqual(len(self.agenda.appointments_on(fecha)), 1)

    def test_aprove_con_cambio_de_horario(self):
        review_id = self._crear_review()

        response = self.client.post(
            f"/reviews/{review_id}/approve",
            json={"date": LUNES, "start_time": "18:00"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["approved_slot"],
            {"date": LUNES, "start_time": "18:00"},
        )
        self.assertIsNotNone(
            self.agenda.find_appointment(
                date.fromisoformat(LUNES),
                time(18, 0),
            )
        )

    def test_aprove_de_review_inexistente_es_404(self):
        response = self.client.post("/reviews/fantasma/approve", json={})

        self.assertEqual(response.status_code, 404)

    def test_doble_aprove_es_409(self):
        review_id = self._crear_review()
        self.client.post(f"/reviews/{review_id}/approve", json={})

        response = self.client.post(f"/reviews/{review_id}/approve", json={})

        self.assertEqual(response.status_code, 409)

    def test_aprove_con_slot_ya_reservado_es_409_y_sigue_pendiente(self):
        primera = self._crear_review()
        self.client.post(
            f"/reviews/{primera}/approve",
            json={"date": LUNES, "start_time": "18:00"},
        )

        segunda = self._crear_review()
        response = self.client.post(
            f"/reviews/{segunda}/approve",
            json={"date": LUNES, "start_time": "18:00"},
        )

        self.assertEqual(response.status_code, 409)

        estado = self.client.get(f"/reviews/{segunda}").json()["status"]
        self.assertEqual(estado, "PENDING")

    def test_aprove_con_slot_fuera_de_horario_es_400(self):
        review_id = self._crear_review()

        response = self.client.post(
            f"/reviews/{review_id}/approve",
            json={"date": LUNES, "start_time": "21:00"},
        )

        self.assertEqual(response.status_code, 400)

    # ---------- reject ----------

    def test_reject_registra_motivo(self):
        review_id = self._crear_review()

        response = self.client.post(
            f"/reviews/{review_id}/reject",
            json={"reason": "dolor leve"},
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["status"], "REJECTED")
        self.assertEqual(body["decision_reason"], "dolor leve")
        self.assertEqual(self.agenda.appointments, [])

    def test_reject_despues_de_aprove_es_409(self):
        review_id = self._crear_review()
        self.client.post(f"/reviews/{review_id}/approve", json={})

        response = self.client.post(
            f"/reviews/{review_id}/reject",
            json={},
        )

        self.assertEqual(response.status_code, 409)

    def test_reject_inexistente_es_404(self):
        response = self.client.post("/reviews/nada/reject", json={})

        self.assertEqual(response.status_code, 404)

    # ---------- flujo extremo a extremo ----------

    def test_flujo_completo_aprobado_refleja_en_agenda_slots(self):
        review_id = self._crear_review()

        aprobado = self.client.post(
            f"/reviews/{review_id}/approve",
            json={"date": LUNES, "start_time": "15:00"},
        ).json()

        slots = self.client.get(
            "/agenda/slots",
            params={"date": LUNES, "appointment_type": "priority"},
        ).json()["slots"]

        self.assertNotIn("15:00", slots)
        self.assertEqual(aprobado["status"], "APPROVED")


if __name__ == "__main__":
    unittest.main()
