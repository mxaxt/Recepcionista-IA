import os
from typing import Any

from google import genai
from google.genai import types

from app.providers.base import LLMProvider


class GeminiProvider(LLMProvider):

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "No se encontró GEMINI_API_KEY en las variables de entorno."
            )

        self.client = genai.Client(api_key=api_key)

    async def generate(
        self,
        messages: list[dict[str, Any]],
        system_instruction: str | None = None,
        tools: list | None = None,
    ) -> dict:

        conversation = []

        for message in messages:
            conversation.append(
                f"{message['role']}: {message['content']}"
            )

        conversation_text = "\n".join(conversation)

        config = types.GenerateContentConfig(
            system_instruction=system_instruction
        )

        response = await self.client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=conversation_text,
            config=config,
        )

        return {
            "content": response.text
        }