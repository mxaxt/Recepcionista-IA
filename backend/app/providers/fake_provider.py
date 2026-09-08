from typing import Any

from app.providers.base import LLMProvider


class FakeProvider(LLMProvider):

    async def generate(
        self,
        messages: list[dict[str, Any]],
        system_instruction: str | None = None,
        tools: list | None = None,
    ) -> dict:

        return {
            "content": "Hola 👋 Soy la recepcionista virtual."
        }