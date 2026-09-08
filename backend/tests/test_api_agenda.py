import unittest
from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.agenda import create_dev_agenda, get_agenda, router
from app.models.agenda import AppointmentType


LUNES_DEMO = "2026-09-14"
MIERCOLES_DEMO = "2026-09-16"
MARTES = "2026-09-15"


class ApiAgendaTests(unittest.TestCase):

    def setUp(self):
        self.agenda = create_dev_agenda()

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_agenda] = lambda: self.agenda

        self.client = TestClient(app)

    # ---------- GET /agenda/slots ----------

    def test_get_slots_devuelve_disponibilidad_del_dia(self):
        response = self.client.get(
            "/agenda/slots",
            params={"date": LUNES_DEMO},
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(body["date"], LUNES_DEMO)
        self.assertEqual(body["appointment_type"], "normal")
        self.assertNotIn("15:00", body["slots"])
        self.assertIn("15:30", body["slots"])
        self.assertNotIn("16:30", body["slots"])
        self.assertIn("17:00", body["slots"])

    def test_get_slots_con_tipo_priority(self):
        response = self.client.get(
            "/agenda/slots",
            params={"date": MIERCOLES_DEMO, "appointment_type": "priority"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("10:00", response.json()["slots"])

    def test_get_slots_dia_cerrado_devuelve_lista_vacia(self):
        response = self.client.get(
            "/agenda/slots",
            params={"date": MARTES},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slots"], [])

    def test_get_slots_fecha_invalida(self):
        response = self.client.get(
            "/agenda/slots",
            params={"date": "no-es-fecha"},
        )

        self.assertEqual(response.status_code, 422)

    def test_get_slots_tipo_invalido(self):
        response = self.client.get(
            "/agenda/slots",
            params={"date": LUNES_DEMO, "appointment_type": "urgente"},
        )

        self.assertEqual(response.status_code, 422)

    # ---------- POST /agenda/appointments ----------

    def test_book_appointment_exitoso(self):
        response = self.client.post(
            "/agenda/appointments",
            json={
                "date": LUNES_DEMO,
                "start": "18:00",
                "patient_id": "paciente-test",
                "appointment_type": "normal",
            },
        )

        self.assertEqual(response.status_code, 201)

        body = response.json()

        self.assertEqual(body["start"], "18:00")
        self.assertEqual(body["end"], "18:30")
        self.assertEqual(body["patient_id"], "paciente-test")
        self.assertEqual(body["appointment_type"], "normal")

        booked = self.agenda.find_appointment(
            date.fromisoformat(LUNES_DEMO),
            body["start"],
        )
        self.assertIsNotNone(booked)

    def test_book_sin_tipo_usa_normal_por_defecto(self):
        response = self.client.post(
            "/agenda/appointments",
            json={
                "date": MIERCOLES_DEMO,
                "start": "19:30",
                "patient_id": "paciente-default",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["appointment_type"], "normal")

    def test_book_priority_exitoso(self):
        response = self.client.post(
            "/agenda/appointments",
            json={
                "date": MIERCOLES_DEMO,
                "start": "10:30",
                "patient_id": "paciente-prio",
                "appointment_type": "priority",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["appointment_type"], "priority")

    def test_book_doble_reserva_devuelve_409(self):
        payload = {
            "date": LUNES_DEMO,
            "start": "17:30",
            "patient_id": "paciente-a",
        }

        first = self.client.post("/agenda/appointments", json=payload)
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            "/agenda/appointments",
            json={**payload, "patient_id": "paciente-b"},
        )

        self.assertEqual(second.status_code, 409)
        self.assertIn("no esta disponible", second.json()["detail"])

    def test_book_turno_demo_ya_ocupado_devuelve_409(self):
        response = self.client.post(
            "/agenda/appointments",
            json={
                "date": LUNES_DEMO,
                "start": "15:00",
                "patient_id": "paciente-tardio",
            },
        )

        self.assertEqual(response.status_code, 409)

    def test_book_fuera_del_horario_devuelve_400(self):
        response = self.client.post(
            "/agenda/appointments",
            json={
                "date": LUNES_DEMO,
                "start": "20:00",
                "patient_id": "paciente-nocturno",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("no es un slot valido", response.json()["detail"])

    def test_book_en_dia_cerrado_devuelve_400(self):
        response = self.client.post(
            "/agenda/appointments",
            json={
                "date": MARTES,
                "start": "10:00",
                "patient_id": "paciente-fantasma",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_book_hora_invalida_devuelve_422(self):
        response = self.client.post(
            "/agenda/appointments",
            json={
                "date": LUNES_DEMO,
                "start": "las-ocho",
                "patient_id": "paciente-test",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_book_tipo_invalido_devuelve_422(self):
        response = self.client.post(
            "/agenda/appointments",
            json={
                "date": LUNES_DEMO,
                "start": "17:00",
                "patient_id": "paciente-test",
                "appointment_type": "urgente",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_book_sin_patient_id_devuelve_422(self):
        response = self.client.post(
            "/agenda/appointments",
            json={
                "date": LUNES_DEMO,
                "start": "17:00",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_book_refleja_en_disponibilidad(self):
        self.client.post(
            "/agenda/appointments",
            json={
                "date": MIERCOLES_DEMO,
                "start": "16:00",
                "patient_id": "paciente-reservo",
                "appointment_type": AppointmentType.NORMAL.value,
            },
        )

        slots = self.client.get(
            "/agenda/slots",
            params={"date": MIERCOLES_DEMO},
        ).json()["slots"]

        self.assertNotIn("16:00", slots)
        self.assertIn("16:30", slots)


class AgendaMontadaEnAppMainTests(unittest.TestCase):

    def test_rutas_agenda_registradas_en_app_main(self):
        import os

        os.environ.setdefault("GEMINI_API_KEY", "clave-de-test")

        from app.main import app

        paths = set(app.openapi()["paths"])

        self.assertIn("/agenda/slots", paths)
        self.assertIn("/agenda/appointments", paths)


if __name__ == "__main__":
    unittest.main()
