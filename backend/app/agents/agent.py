from app.providers.base import LLMProvider


class Agent:

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def chat(self, message: str) -> str:

        messages = [
            {
                "role": "user",
                "content": message,
            }
        ]

        response = await self.provider.generate(messages)

        return response["content"]