import unittest
from typing import Any

from app.agents.agent import Agent
from app.memory.conversation import ConversationMemory
from app.providers.base import LLMProvider
from app.providers.fake_provider import FakeProvider


def clasificacion(
    status: str = "NORMAL",
    priority: bool = False,
    urgency: bool = False,
    root_canal: bool = False,
    confirmed: bool = True,
) -> dict[str, Any]:
    return {
        "status": status,
        "priority": priority,
        "urgency": urgency,
        "root_canal": root_canal,
        "double_check": {
            "confirmed": confirmed,
            "analysis_1": {"urgency": urgency, "root_canal": root_canal},
            "analysis_2": {"urgency": urgency, "root_canal": root_canal},
        },
    }


class FakeClassifier:

    def __init__(self, result: dict[str, Any] | None = None):
        self.result = result if result is not None else clasificacion()
        self.mensajes_recibidos: list[str] = []

    async def classify(self, message: str) -> dict[str, Any]:
        self.mensajes_recibidos.append(message)
        return self.result


class RecordingProvider(LLMProvider):

    def __init__(self, content: str = "respuesta simulada"):
        self.content = content
        self.llamados: list[dict[str, Any]] = []

    async def generate(
        self,
        messages: list[dict[str, Any]],
        system_instruction: str | None = None,
        tools: list | None = None,
    ) -> dict:
        self.llamados.append({
            "messages": list(messages),
            "system_instruction": system_instruction,
            "tools": tools,
        })
        return {"content": self.content}


class AgentTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.memory = ConversationMemory()
        self.provider = RecordingProvider()
        self.classifier = FakeClassifier()
        self.agent = Agent(
            provider=self.provider,
            memory=self.memory,
            system_prompt="PROMPT_BASE",
            classifier=self.classifier,
        )

    async def test_chat_devuelve_respuesta_del_provider(self):
        respuesta = await self.agent.chat("s1", "Hola")
        self.assertEqual(respuesta, "respuesta simulada")

    async def test_chat_clasifica_el_mensaje_del_paciente(self):
        await self.agent.chat("s1", "tengo dolor de muela")
        self.assertEqual(self.classifier.mensajes_recibidos, ["tengo dolor de muela"])

    async def test_chat_guarda_usuario_y_asistente_en_memoria(self):
        await self.agent.chat("s1", "Hola")

        historial = self.memory.get_messages("s1")

        self.assertEqual(
            historial,
            [
                {"role": "user", "content": "Hola"},
                {"role": "assistant", "content": "respuesta simulada"},
            ],
        )

    async def test_chat_pasa_system_prompt_y_contexto_de_clasificacion(self):
        await self.agent.chat("s1", "Hola")

        system_instruction = self.provider.llamados[0]["system_instruction"]

        self.assertTrue(system_instruction.startswith("PROMPT_BASE"))
        self.assertIn("INFORMACIÓN INTERNA DE RECEPCIÓN", system_instruction)
        self.assertIn("Estado:\nNORMAL", system_instruction)
        self.assertIn("Prioridad:\nFalse", system_instruction)
        self.assertIn("Posible urgencia:\nFalse", system_instruction)
        self.assertIn("Menciona tratamiento de conducto:\nFalse", system_instruction)
        self.assertIn("Doble check confirmado:\nTrue", system_instruction)

    async def test_contexto_refleja_clasificacion_priority(self):
        classifier = FakeClassifier(
            clasificacion(
                status="PRIORITY",
                priority=True,
                urgency=True,
                root_canal=False,
                confirmed=True,
            )
        )
        agent = Agent(
            provider=self.provider,
            memory=self.memory,
            system_prompt="PROMPT_BASE",
            classifier=classifier,
        )

        await agent.chat("s1", "tengo la cara muy hinchada")

        system_instruction = self.provider.llamados[0]["system_instruction"]

        self.assertIn("Estado:\nPRIORITY", system_instruction)
        self.assertIn("Posible urgencia:\nTrue", system_instruction)

    async def test_el_provider_recibe_el_historial_acumulado(self):
        await self.agent.chat("s1", "primero")
        await self.agent.chat("s1", "segundo")

        segundo_llamado = self.provider.llamados[1]["messages"]

        self.assertEqual(
            segundo_llamado,
            [
                {"role": "user", "content": "primero"},
                {"role": "assistant", "content": "respuesta simulada"},
                {"role": "user", "content": "segundo"},
            ],
        )

    async def test_las_sesiones_no_se_mezelan_en_memoria(self):
        await self.agent.chat("s1", "mensaje a")
        await self.agent.chat("s2", "mensaje b")

        self.assertEqual(
            [m["content"] for m in self.memory.get_messages("s1")],
            ["mensaje a", "respuesta simulada"],
        )
        self.assertEqual(
            [m["content"] for m in self.memory.get_messages("s2")],
            ["mensaje b", "respuesta simulada"],
        )

    async def test_agente_funciona_con_fake_provider(self):
        agent = Agent(
            provider=FakeProvider(),
            memory=ConversationMemory(),
            system_prompt="PROMPT_BASE",
            classifier=FakeClassifier(),
        )

        respuesta = await agent.chat("s1", "Hola")

        self.assertEqual(respuesta, "Hola 👋 Soy la recepcionista virtual.")


if __name__ == "__main__":
    unittest.main()
