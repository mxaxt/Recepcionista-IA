import unittest
from datetime import date

from app.models.agenda import AppointmentType
from app.services.agenda import Agenda
from app.tools.agenda_tools import AgendaTools


LUNES = date(2026, 9, 14)
MARTES = date(2026, 9, 15)  # dia cerrado
MIERCOLES = date(2026, 9, 16)
VIERNES = date(2026, 9, 18)

WORKING_HOURS = {
    "monday": [("15:00", "19:00")],
    "wednesday": [("10:00", "12:00"), ("16:00", "20:00")],
    "friday": [("10:00", "12:00"), ("16:00", "20:00")],
}

PRIORITY_HOURS = {
    "monday": [("15:00", "16:00")],
}


def crear_agenda(ocupada: bool = True) -> Agenda:
    agenda = Agenda(working_hours=WORKING_HOURS)

    if ocupada:
        agenda.book_appointment(LUNES, "15:00", "paciente-previo")

    return agenda


class CheckAvailabilityTests(unittest.TestCase):

    def setUp(self):
        self.tools = AgendaTools(agenda=crear_agenda())

    def test_fecha_explicita_devuelve_solo_ese_dia_sin_ocupados(self):
        result = self.tools.check_availability(preferred_date=LUNES)

        self.assertTrue(result["ok"])
        self.assertEqual(result["appointment_type"], "normal")
        self.assertEqual(len(result["availability"]), 1)

        dia = result["availability"][0]
        self.assertEqual(dia["date"], "2026-09-14")
        self.assertNotIn("15:00", dia["slots"])
        self.assertIn("15:30", dia["slots"])

    def test_sin_fecha_escanea_ventana_y_omite_dias_cerrados(self):
        result = self.tools.check_availability(
            reference_date=LUNES,
        )

        self.assertTrue(result["ok"])

        fechas = [dia["date"] for dia in result["availability"]]

        self.assertIn("2026-09-14", fechas)
        self.assertNotIn("2026-09-15", fechas)
        self.assertIn("2026-09-16", fechas)

        for dia in result["availability"]:
            self.assertTrue(len(dia["slots"]) > 0)

    def test_horizon_days_limita_la_ventana(self):
        tools = AgendaTools(agenda=crear_agenda(), horizon_days=3)

        result = tools.check_availability(reference_date=LUNES)

        fechas = [dia["date"] for dia in result["availability"]]

        self.assertEqual(fechas, ["2026-09-14", "2026-09-16"])

    def test_dia_cerrado_con_fecha_explicita_devuelve_slots_vacios(self):
        result = self.tools.check_availability(preferred_date=MARTES)

        self.assertTrue(result["ok"])
        self.assertEqual(
            result["availability"],
            [{"date": "2026-09-15", "slots": []}],
        )

    def test_fecha_invalida_no_lanza_excepcion(self):
        result = self.tools.check_availability(preferred_date="14-09-2026")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "invalid_date")

    def test_priority_true_consulta_disponibilidad_priority(self):
        agenda = Agenda(
            working_hours=WORKING_HOURS,
            priority_hours=PRIORITY_HOURS,
        )
        tools = AgendaTools(agenda=agenda)

        result = tools.check_availability(
            preferred_date=LUNES,
            priority=True,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["appointment_type"], "priority")
        self.assertEqual(result["availability"][0]["slots"], [
            "15:00",
            "15:30",
        ])

    def test_normal_consulta_toda_la_jornada_aunque_haya_franja_priority(self):
        agenda = Agenda(
            working_hours=WORKING_HOURS,
            priority_hours=PRIORITY_HOURS,
        )
        tools = AgendaTools(agenda=agenda)

        result = tools.check_availability(
            preferred_date=LUNES,
            priority=False,
        )

        self.assertIn("18:30", result["availability"][0]["slots"])


class ReserveTests(unittest.TestCase):

    def setUp(self):
        self.agenda = crear_agenda()
        self.tools = AgendaTools(agenda=self.agenda)

    def test_reserve_exitoso_normal(self):
        result = self.tools.reserve(
            date=LUNES,
            start_time="16:00",
            patient_id="paciente-1",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(
            result["appointment"],
            {
                "date": "2026-09-14",
                "start": "16:00",
                "end": "16:30",
                "patient_id": "paciente-1",
                "appointment_type": "normal",
                "duration_minutes": 30,
            },
        )
        self.assertEqual(len(self.agenda.appointments), 2)

    def test_reserve_con_priority_mapea_tipo_priority(self):
        result = self.tools.reserve(
            date=LUNES,
            start_time="16:00",
            patient_id="paciente-prio",
            priority=True,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(
            result["appointment"]["appointment_type"],
            "priority",
        )

    def test_reserve_slot_ya_ocupado(self):
        result = self.tools.reserve(
            date=LUNES,
            start_time="15:00",
            patient_id="paciente-2",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "unavailable")

    def test_doble_reserve_sucessivo_devuelve_unavailable(self):
        primero = self.tools.reserve(
            date=LUNES,
            start_time="17:00",
            patient_id="paciente-a",
        )
        segundo = self.tools.reserve(
            date=LUNES,
            start_time="17:00",
            patient_id="paciente-b",
        )

        self.assertTrue(primero["ok"])
        self.assertFalse(segundo["ok"])
        self.assertEqual(segundo["error_code"], "unavailable")
        self.assertEqual(len(self.agenda.appointments), 2)

    def test_reserve_fuera_del_horario(self):
        result = self.tools.reserve(
            date=LUNES,
            start_time="20:00",
            patient_id="paciente-3",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "invalid_slot")

    def test_reserve_en_dia_cerrado(self):
        result = self.tools.reserve(
            date=MARTES,
            start_time="10:00",
            patient_id="paciente-4",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "invalid_slot")

    def test_reserve_fecha_invalida(self):
        result = self.tools.reserve(
            date="navidad",
            start_time="16:00",
            patient_id="paciente-5",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "invalid_date")

    def test_reserve_hora_invalida(self):
        result = self.tools.reserve(
            date=LUNES,
            start_time="a las cuatro",
            patient_id="paciente-6",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "invalid_time")

    def test_reserve_sin_patient_id(self):
        result = self.tools.reserve(
            date=LUNES,
            start_time="16:00",
            patient_id="   ",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "invalid_patient_id")

    def test_reserve_priority_fuera_de_franja_configurada(self):
        agenda = Agenda(
            working_hours=WORKING_HOURS,
            priority_hours=PRIORITY_HOURS,
        )
        tools = AgendaTools(agenda=agenda)

        result = tools.reserve(
            date=LUNES,
            start_time="18:00",
            patient_id="paciente-7",
            priority=True,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "priority_not_allowed")

    def test_comportamiento_actual_normal_puede_usar_franja_priority(self):
        agenda = Agenda(
            working_hours=WORKING_HOURS,
            priority_hours=PRIORITY_HOURS,
        )
        tools = AgendaTools(agenda=agenda)

        for hora in ("15:00", "15:30"):
            result = tools.reserve(
                date=LUNES,
                start_time=hora,
                patient_id="paciente-x",
                priority=False,
            )
            self.assertTrue(result["ok"])

        bloqueado = tools.reserve(
            date=LUNES,
            start_time="15:00",
            patient_id="paciente-prio",
            priority=True,
        )

        self.assertFalse(bloqueado["ok"])
        self.assertEqual(bloqueado["error_code"], "unavailable")

    def test_resultados_serializables(self):
        import json

        exito = self.tools.reserve(
            date=MIERCOLES,
            start_time="19:30",
            patient_id="paciente-json",
        )
        error = self.tools.reserve(
            date=MIERCOLES,
            start_time="19:30",
            patient_id="paciente-json",
        )

        json.dumps(exito)
        json.dumps(error)


if __name__ == "__main__":
    unittest.main()
