import unittest
from datetime import date, time

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.telegram import GENERIC_ERROR_MESSAGE, create_telegram_router
from app.services.telegram_client import (
    MAX_TELEGRAM_MESSAGE_CHARS,
    TelegramClient,
)


FAKE_TOKEN = "fake-token-para-tests"

SECRET = "fake-webhook-secret"


def update_payload(chat_id=42, text="hola", caption=None, with_message=True):
    payload = {"update_id": 1}

    if not with_message:
        return payload

    message = {"chat": {"id": chat_id}}

    if text is not None:
        message["text"] = text

    if caption is not None:
        message["caption"] = caption

    payload["message"] = message

    return payload


class FakeAgent:

    def __init__(self, response="respuesta simulada"):
        self.response = response
        self.calls: list[tuple[str, str]] = []

    async def chat(self, session_id, message):
        self.calls.append((session_id, message))

        return self.response


class ExplodingAgent:

    async def chat(self, session_id, message):
        raise RuntimeError("boom secreto")


class FakeClient:

    def __init__(self, fail=False):
        self.sent: list[tuple[int, str]] = []
        self.fail = fail

    async def send_message(self, chat_id, text):
        if self.fail:
            raise AssertionError("no deberia haber enviado nada")

        self.sent.append((chat_id, text))


def build_client(agent, client, webhook_secret=None) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_telegram_router(
            agent=agent,
            client=client,
            webhook_secret=webhook_secret,
        )
    )

    return TestClient(app)


class WebhookBasicoTests(unittest.TestCase):

    def setUp(self):
        self.agent = FakeAgent()
        self.client = FakeClient()
        self.http = build_client(self.agent, self.client)

    def test_mensaje_de_texto_viaja_al_agent_y_la_vuelta_a_telegram(self):
        response = self.http.post(
            "/telegram/webhook",
            json=update_payload(chat_id=1234, text="quiero un turno"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(
            self.agent.calls,
            [("telegram:1234", "quiero un turno")],
        )
        self.assertEqual(
            self.client.sent,
            [(1234, "respuesta simulada")],
        )

    def test_caption_deFoto_se_trata_como_texto(self):
        response = self.http.post(
            "/telegram/webhook",
            json=update_payload(chat_id=7, text=None, caption="dolor fuerte"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.agent.calls,
            [("telegram:7", "dolor fuerte")],
        )

    def test_update_sin_mensaje_se_ignora(self):
        response = self.http.post(
            "/telegram/webhook",
            json=update_payload(with_message=False),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ignored"})
        self.assertEqual(self.agent.calls, [])
        self.assertEqual(self.client.sent, [])

    def test_mensaje_vacio_o_de_solo_espacios_se_ignora(self):
        for text in ("", "   "):
            response = self.http.post(
                "/telegram/webhook",
                json=update_payload(text=text),
            )

            self.assertEqual(response.json()["status"], "ignored")

        self.assertEqual(self.agent.calls, [])
        self.assertEqual(self.client.sent, [])

    def test_payload_malformado_es_rechazado_por_validacion(self):
        response = self.http.post(
            "/telegram/webhook",
            json={"update_id": 1, "message": {"chat": {}}},
        )

        self.assertEqual(response.status_code, 422)

    def test_fallo_del_agente_responde_200_y_mensaje_generico(self):
        agent = ExplodingAgent()
        client = FakeClient()
        http = build_client(agent, client)

        response = http.post(
            "/telegram/webhook",
            json=update_payload(chat_id=9),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "error"})
        self.assertEqual(client.sent, [(9, GENERIC_ERROR_MESSAGE)])


class WebhookSecretTests(unittest.TestCase):

    def setUp(self):
        self.agent = FakeAgent()
        self.client = FakeClient()
        self.http = build_client(
            self.agent,
            self.client,
            webhook_secret=SECRET,
        )

    def test_sin_secret_configurado_se_acepta_sin_header(self):
        http = build_client(FakeAgent(), FakeClient())

        response = http.post(
            "/telegram/webhook",
            json=update_payload(),
        )

        self.assertEqual(response.status_code, 200)

    def test_sin_header_es_403(self):
        response = self.http.post(
            "/telegram/webhook",
            json=update_payload(),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.agent.calls, [])

    def test_header_incorrecto_es_403(self):
        response = self.http.post(
            "/telegram/webhook",
            json=update_payload(),
            headers={"X-Telegram-Bot-Api-Secret-Token": "malo"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.agent.calls, [])

    def test_header_correcto_pasa(self):
        response = self.http.post(
            "/telegram/webhook",
            json=update_payload(),
            headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.agent.calls), 1)


class SesionesRealesTests(unittest.IsolatedAsyncioTestCase):

    async def test_dos_chats_son_dos_sesiones_distintas_del_agent(self):
        from app.agents.agent import Agent
        from app.memory.conversation import ConversationMemory
        from app.providers.fake_provider import FakeProvider

        class NormalClassifier:

            async def classify(self, message):
                return {
                    "status": "NORMAL",
                    "priority": False,
                    "urgency": False,
                    "root_canal": False,
                    "double_check": {"confirmed": True},
                }

        memory = ConversationMemory()
        agent = Agent(
            provider=FakeProvider(),
            memory=memory,
            system_prompt="PROMPT_BASE",
            classifier=NormalClassifier(),
        )
        client = FakeClient()

        http = build_client(agent, client)

        for chat_id in (111, 222):
            response = http.post(
                "/telegram/webhook",
                json=update_payload(chat_id=chat_id, text=f"hola {chat_id}"),
            )
            self.assertEqual(response.json()["status"], "ok")

        sesion_1 = memory.get_messages("telegram:111")
        sesion_2 = memory.get_messages("telegram:222")

        self.assertEqual([m["content"] for m in sesion_1][0], "hola 111")
        self.assertEqual([m["content"] for m in sesion_2][0], "hola 222")
        self.assertEqual(len(sesion_1), 2)
        self.assertEqual(len(sesion_2), 2)


class TelegramClientTests(unittest.IsolatedAsyncioTestCase):

    def _client_capturando(self, captured, response_body=None, status=200):
        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)

            return httpx.Response(
                status,
                json=response_body or {"ok": True, "result": {}},
            )

        return TelegramClient(
            token=FAKE_TOKEN,
            transport=httpx.MockTransport(handler),
        )

    async def test_send_message_llama_sendMessage_con_chat_y_texto(self):
        import json

        captured = []
        client = self._client_capturando(captured)

        await client.send_message(55, "hola paciente")

        self.assertEqual(len(captured), 1)
        request = captured[0]

        self.assertTrue(str(request.url).endswith("/sendMessage"))
        self.assertIn(f"/bot{FAKE_TOKEN}/", str(request.url))

        body = json.loads(request.content)

        self.assertEqual(body["chat_id"], 55)
        self.assertEqual(body["text"], "hola paciente")

    async def test_texto_largo_se_divide_en_mensajes_de_4096(self):
        captured = []
        client = self._client_capturando(captured)

        texto = "a" * (MAX_TELEGRAM_MESSAGE_CHARS * 2 + 500)

        await client.send_message(1, texto)

        self.assertEqual(len(captured), 3)

        import json

        tamaños = [
            len(json.loads(r.content)["text"]) for r in captured
        ]

        self.assertEqual(
            tamaños,
            [
                MAX_TELEGRAM_MESSAGE_CHARS,
                MAX_TELEGRAM_MESSAGE_CHARS,
                500,
            ],
        )

    async def test_sin_token_falla_antes_de_enviar(self):
        captured = []

        def handler(request):
            captured.append(request)
            return httpx.Response(200, json={"ok": True})

        client = TelegramClient(
            token=None,
            transport=httpx.MockTransport(handler),
        )

        with self.assertRaises(ValueError) as ctx:
            await client.send_message(1, "hola")

        self.assertIn("TELEGRAM_BOT_TOKEN", str(ctx.exception))
        self.assertEqual(captured, [])

    async def test_error_de_telegram_no_filtra_el_token(self):
        import traceback

        def handler(request):
            return httpx.Response(
                401,
                json={"ok": False, "description": "Unauthorized"},
            )

        client = TelegramClient(
            token=FAKE_TOKEN,
            transport=httpx.MockTransport(handler),
        )

        with self.assertRaises(RuntimeError) as ctx:
            await client.send_message(1, "hola")

        tb = "".join(
            traceback.format_exception(ctx.exception)
        )

        self.assertNotIn(FAKE_TOKEN, str(ctx.exception))
        self.assertNotIn(FAKE_TOKEN, tb)
        self.assertIn("Unauthorized", str(ctx.exception))

    async def test_error_de_conexion_no_filtra_el_token(self):
        import traceback

        def handler(request):
            raise httpx.ConnectError("connection refused")

        client = TelegramClient(
            token=FAKE_TOKEN,
            transport=httpx.MockTransport(handler),
        )

        with self.assertRaises(RuntimeError) as ctx:
            await client.send_message(1, "hola")

        tb = "".join(traceback.format_exception(ctx.exception))

        self.assertNotIn(FAKE_TOKEN, str(ctx.exception))
        self.assertNotIn(FAKE_TOKEN, tb)


class TelegramMontadoEnAppMainTests(unittest.TestCase):

    def test_ruta_telegram_registrada_en_app_main(self):
        import os

        os.environ.setdefault("GEMINI_API_KEY", "clave-de-test")

        from app.main import app

        paths = set(app.openapi()["paths"])

        self.assertIn("/telegram/webhook", paths)


class ScriptWebhookTests(unittest.TestCase):

    def test_script_se_ejecuta_desde_backend_sin_module_not_found(self):
        import subprocess
        import sys
        from pathlib import Path

        backend_dir = Path(__file__).resolve().parents[1]
        script = backend_dir / "scripts" / "set_telegram_webhook.py"

        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Configurar webhook", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)


if __name__ == "__main__":
    unittest.main()
