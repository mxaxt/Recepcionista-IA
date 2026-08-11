from app.providers.base import LLMProvider


class FakeProvider(LLMProvider):

    async def generate(
        self,
        messages: list[dict],
        tools: list | None = None,
    ) -> dict:

        return {
            "content": "Hola 👋 Soy la recepcionista virtual."
        }