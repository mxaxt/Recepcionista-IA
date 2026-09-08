import unittest
from datetime import date, time

from app.models.agenda import Appointment, AppointmentType
from app.services.agenda import Agenda


HORARIOS = {
    "monday": [("15:00", "19:00")],
    "wednesday": [("10:00", "12:00"), ("16:00", "20:00")],
    "friday": [("10:00", "12:00"), ("16:00", "20:00")],
}

LUNES = date(2026, 9, 7)
MIERCOLES = date(2026, 9, 9)
VIERNES = date(2026, 9, 11)
MARTES = date(2026, 9, 8)  # dia cerrado


class GeneracionDeSlotsTests(unittest.TestCase):

    def setUp(self):
        self.agenda = Agenda(HORARIOS)

    def test_genera_slots_de_30_minutos(self):
        slots = self.agenda.generate_day_slots(LUNES)

        self.assertEqual(slots[0], time(15, 0))
        self.assertEqual(slots[-1], time(18, 30))
        self.assertEqual(len(slots), 8)

        for slot in slots:
            self.assertEqual(slot.minute % 30, 0)

    def test_respeta_multiples_intervalos_del_dia(self):
        slots = self.agenda.generate_day_slots(MIERCOLES)

        self.assertEqual(
            slots,
            [
                time(10, 0), time(10, 30), time(11, 0), time(11, 30),
                time(16, 0), time(16, 30), time(17, 0), time(17, 30),
                time(18, 0), time(18, 30), time(19, 0), time(19, 30),
            ],
        )

    def test_no_genera_slots_fuera_del_horario(self):
        slots = self.agenda.generate_day_slots(LUNES)

        self.assertNotIn(time(14, 30), slots)
        self.assertNotIn(time(19, 0), slots)
        self.assertNotIn(time(19, 30), slots)

    def test_dia_sin_horario_no_tiene_slots(self):
        self.assertEqual(self.agenda.generate_day_slots(MARTES), [])

    def test_config_invalida_dia_desconocido(self):
        with self.assertRaises(ValueError):
            Agenda({"funday": [("10:00", "12:00")]})

    def test_config_invalida_horario_mal_formado(self):
        with self.assertRaises(ValueError):
            Agenda({"monday": [("25:00", "27:00")]})


class DisponibilidadTests(unittest.TestCase):

    def setUp(self):
        self.agenda = Agenda(HORARIOS)

    def test_dia_vacio_todos_los_slots_estan_disponibles(self):
        disponibles = self.agenda.get_available_slots(
            LUNES,
            AppointmentType.NORMAL,
        )

        self.assertEqual(disponibles, self.agenda.generate_day_slots(LUNES))

    def test_turno_existente_ocupa_su_slot(self):
        self.agenda.book_appointment(LUNES, time(15, 0), "paciente-1")

        disponibles = self.agenda.get_available_slots(
            LUNES,
            AppointmentType.NORMAL,
        )

        self.assertNotIn(time(15, 0), disponibles)
        self.assertIn(time(15, 30), disponibles)

    def test_turno_existente_impide_doble_reserva(self):
        self.agenda.book_appointment(LUNES, time(15, 0), "paciente-1")

        with self.assertRaises(ValueError):
            self.agenda.book_appointment(
                LUNES,
                time(15, 0),
                "paciente-2",
            )

        self.assertEqual(len(self.agenda.appointments), 1)

    def test_no_se_puede_reservar_fuera_del_horario(self):
        with self.assertRaises(ValueError):
            self.agenda.book_appointment(LUNES, time(20, 0), "paciente-1")

    def test_no_se_puede_reservar_en_dia_cerrado(self):
        with self.assertRaises(ValueError):
            self.agenda.book_appointment(MARTES, time(15, 0), "paciente-1")

    def test_agenda_puede_contener_turnos_ya_cargados(self):
        agenda = Agenda(HORARIOS)
        agenda.add_appointment(
            Appointment(
                date=MIERCOLES,
                start=time(16, 0),
                patient_id="paciente-previo",
                appointment_type=AppointmentType.PRIORITY,
            )
        )

        disponibles = agenda.get_available_slots(
            MIERCOLES,
            AppointmentType.NORMAL,
        )

        self.assertNotIn(time(16, 0), disponibles)
        self.assertIn(time(16, 30), disponibles)


class TiposDeTurnoTests(unittest.TestCase):

    def setUp(self):
        self.agenda = Agenda(
            HORARIOS,
            priority_hours={
                "monday": [("15:00", "16:00")],
                "wednesday": [("10:00", "11:00")],
            },
        )

    def test_turno_normal_se_reserva_en_toda_la_jornada(self):
        turno = self.agenda.book_appointment(
            LUNES,
            time(18, 0),
            "paciente-normal",
            AppointmentType.NORMAL,
        )

        self.assertEqual(turno.appointment_type, AppointmentType.NORMAL)
        self.assertEqual(turno.start, time(18, 0))

    def test_priority_limitado_por_configuracion(self):
        disponibles = self.agenda.get_available_slots(
            LUNES,
            AppointmentType.PRIORITY,
        )

        self.assertEqual(disponibles, [time(15, 0), time(15, 30)])

    def test_turno_priority_se_reserva_dentro_de_su_franja(self):
        turno = self.agenda.book_appointment(
            LUNES,
            time(15, 0),
            "paciente-prioridad",
            AppointmentType.PRIORITY,
        )

        self.assertEqual(turno.appointment_type, AppointmentType.PRIORITY)
        self.assertEqual(turno.duration_minutes, 30)

    def test_priority_rechaza_fuera_de_su_franja(self):
        with self.assertRaises(ValueError):
            self.agenda.book_appointment(
                LUNES,
                time(18, 0),
                "paciente-prioridad",
                AppointmentType.PRIORITY,
            )

    def test_sin_config_de_priority_se_puede_reservar_en_toda_la_jornada(self):
        agenda = Agenda(HORARIOS)

        turno = agenda.book_appointment(
            LUNES,
            time(18, 30),
            "paciente-prioridad",
            AppointmentType.PRIORITY,
        )

        self.assertEqual(turno.appointment_type, AppointmentType.PRIORITY)

    def test_priority_no_desaparece_slots_normales(self):
        agenda = Agenda(HORARIOS)
        agenda.book_appointment(
            LUNES,
            time(15, 0),
            "paciente-x",
            AppointmentType.PRIORITY,
        )

        normales = agenda.get_available_slots(
            LUNES,
            AppointmentType.NORMAL,
        )

        self.assertNotIn(time(15, 0), normales)
        self.assertEqual(len(normales), 7)


class ModeloTurnoTests(unittest.TestCase):

    def test_end_se_deriva_de_inicio_y_duracion(self):
        turno = Appointment(
            date=MIERCOLES,
            start=time(16, 0),
            patient_id="paciente-1",
        )

        self.assertEqual(turno.end, time(16, 30))

    def test_to_dict_serializa_campos(self):
        turno = Appointment(
            date=MIERCOLES,
            start=time(16, 0),
            patient_id="paciente-1",
            appointment_type=AppointmentType.PRIORITY,
        )

        self.assertEqual(
            turno.to_dict(),
            {
                "date": "2026-09-09",
                "start": "16:00",
                "end": "16:30",
                "patient_id": "paciente-1",
                "appointment_type": "priority",
                "duration_minutes": 30,
            },
        )

    def test_overlaps_detecta_interseccion(self):
        turno = Appointment(
            date=MIERCOLES,
            start=time(16, 0),
            patient_id="paciente-1",
        )

        self.assertTrue(turno.overlaps(time(16, 0), time(16, 30)))
        self.assertTrue(turno.overlaps(time(15, 45), time(16, 15)))
        self.assertFalse(turno.overlaps(time(15, 30), time(16, 0)))
        self.assertFalse(turno.overlaps(time(16, 30), time(17, 0)))
        self.assertFalse(turno.overlaps(time(15, 0), time(15, 30)))


if __name__ == "__main__":
    unittest.main()
