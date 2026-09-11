"""Tests de la Fase 0 de preparacion para deployment.

Cubren: health endpoint estatico, fail-fast de variables de produccion
(RENDER=true), token compartido para /agenda y /reviews, y timezone
explícito del consultorio en AgendaTools.
"""

import os
import subprocess
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.agenda import get_agenda, router as agenda_router
from app.api.reviews import get_priority_review_service
from app.api.reviews import router as reviews_router
from app.core.config import CLINIC_TIMEZONE_NAME, clinic_now, clinic_today
from app.services.agenda import Agenda
from app.services.priority_review import PriorityReviewService
from app.tools.agenda_tools import AgendaTools

from app.core.security import ADMIN_TOKEN_HEADER


BACKEND_DIR = Path(__file__).resolve().parents[1]

LUNES_DEMO = "2026-09-14"

WORKING_HOURS = {
    "monday": [("15:00", "19:00")],
    "wednesday": [("10:00", "12:00"), ("16:00", "20:00")],
}


def _import_main():
    os.environ.setdefault("GEMINI_API_KEY", "clave-de-test")

    import app.main as main_module

    return main_module


def _run_app_import(extra_env: dict) -> subprocess.CompletedProcess:
    env = {**os.environ, **extra_env}

    return subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


class HealthEndpointTests(unittest.TestCase):

    def test_get_raiz_es_estatico_y_no_llama_al_agente(self):
        main_module = _import_main()

        chat_mock = AsyncMock(
            side_effect=AssertionError("el health no debe llamar al agente")
        )

        with patch.object(main_module.agent, "chat", new=chat_mock):
            response = TestClient(main_module.app).get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        chat_mock.assert_not_awaited()

    def test_chat_conserva_su_comportamiento(self):
        main_module = _import_main()

        with patch.object(
            main_module.agent,
            "chat",
            new=AsyncMock(return_value="respuesta simulada"),
        ):
            response = TestClient(main_module.app).post(
                "/chat",
                json={"session_id": "s1", "message": "hola"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"response": "respuesta simulada"})


class ProduccionFailFastTests(unittest.TestCase):
    """app.main debe negarse a arrancar en Render sin sus secretos."""

    SECRET_ENV_VARS = (
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_WEBHOOK_SECRET",
        "ADMIN_API_TOKEN",
    )

    def test_render_sin_secretos_falla_al_arrancar(self):
        env = {"RENDER": "true", "GEMINI_API_KEY": "clave-de-test"}

        for var in self.SECRET_ENV_VARS:
            # Vale también "" : load_dotenv respeta las existentes y la
            # validacion trata vacio como ausente.
            env[var] = ""

        result = _run_app_import(env)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TELEGRAM_WEBHOOK_SECRET", result.stderr)
        self.assertIn("ADMIN_API_TOKEN", result.stderr)

    def test_render_con_todos_los_secretos_arranca(self):
        result = _run_app_import(
            {
                "RENDER": "true",
                "GEMINI_API_KEY": "clave-de-test",
                "TELEGRAM_BOT_TOKEN": "token-de-test",
                "TELEGRAM_WEBHOOK_SECRET": "secret-de-test",
                "ADMIN_API_TOKEN": "admin-de-test",
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_desarrollo_sin_secretos_de_produccion_arranca(self):
        env = {
            "GEMINI_API_KEY": "clave-de-test",
            "TELEGRAM_WEBHOOK_SECRET": "",
            "ADMIN_API_TOKEN": "",
        }
        env_no_render = {**os.environ, **env}
        env_no_render.pop("RENDER", None)

        result = subprocess.run(
            [sys.executable, "-c", "import app.main"],
            cwd=BACKEND_DIR,
            env=env_no_render,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


class AdminTokenTests(unittest.TestCase):

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

    def _sin_token_de_admin(self):
        return patch.dict(os.environ, {}, clear=False)

    def test_sin_admin_token_configurado_los_routers_quedan_abiertos(self):
        with self._sin_token_de_admin():
            os.environ.pop("ADMIN_API_TOKEN", None)

            slots = self.client.get(
                "/agenda/slots",
                params={"date": LUNES_DEMO},
            )
            reviews = self.client.get("/reviews")

        self.assertEqual(slots.status_code, 200)
        self.assertEqual(reviews.status_code, 200)

    def test_con_admin_token_exige_header_en_agenda_y_reviews(self):
        with patch.dict(os.environ, {"ADMIN_API_TOKEN": "secreto-admin"}):
            self.assertEqual(
                self.client.get(
                    "/agenda/slots",
                    params={"date": LUNES_DEMO},
                ).status_code,
                401,
            )
            self.assertEqual(
                self.client.get("/reviews").status_code,
                401,
            )
            self.assertEqual(
                self.client.get(
                    "/agenda/slots",
                    params={"date": LUNES_DEMO},
                    headers={ADMIN_TOKEN_HEADER: "equivocado"},
                ).status_code,
                401,
            )

    def test_header_correcto_autoriza_el_acceso(self):
        with patch.dict(os.environ, {"ADMIN_API_TOKEN": "secreto-admin"}):
            headers = {ADMIN_TOKEN_HEADER: "secreto-admin"}

            slots = self.client.get(
                "/agenda/slots",
                params={"date": LUNES_DEMO},
                headers=headers,
            )
            reviews = self.client.get("/reviews", headers=headers)

        self.assertEqual(slots.status_code, 200)
        self.assertEqual(reviews.status_code, 200)
        self.assertIn("15:00", slots.json()["slots"])

    def test_el_agent_interno_no_pasa_por_http(self):
        """AgendaTools sigue reservando in-process aunque exista el token."""
        with patch.dict(os.environ, {"ADMIN_API_TOKEN": "secreto-admin"}):
            tools = AgendaTools(agenda=self.agenda, horizon_days=7)

            result = tools.reserve(
                date=LUNES_DEMO,
                start_time="15:00",
                patient_id="paciente-agente",
            )

        self.assertTrue(result["ok"])


class ClinicTimezoneTests(unittest.TestCase):

    def test_zona_configurada_es_argentina(self):
        self.assertEqual(CLINIC_TIMEZONE_NAME, "America/Argentina/Buenos_Aires")

    def test_clinic_now_usa_utc_3(self):
        # Argentina no tiene DST: el offset debe ser -3 tanto con
        # ZoneInfo como con el fallback de offset fijo.
        self.assertEqual(clinic_now().utcoffset(), timedelta(hours=-3))

    def test_clinic_today_coincide_con_clinic_now(self):
        self.assertEqual(clinic_today(), clinic_now().date())

    def test_agenda_tools_toma_hoy_del_consultorio(self):
        tools = AgendaTools(agenda=self._agenda(), horizon_days=1)

        with patch(
            "app.tools.agenda_tools.clinic_today",
            return_value=date(2026, 9, 14),
        ):
            result = tools.check_availability()

        self.assertTrue(result["ok"])
        self.assertEqual(
            [dia["date"] for dia in result["availability"]],
            [LUNES_DEMO],
        )

    @staticmethod
    def _agenda() -> Agenda:
        return Agenda(working_hours=WORKING_HOURS)


if __name__ == "__main__":
    unittest.main()
