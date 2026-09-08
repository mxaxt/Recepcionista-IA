from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Contrato que deben cumplir todos los proveedores de IA."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, Any]],
        system_instruction: str | None = None,
        tools: list | None = None,
    ) -> dict:
        """Genera una respuesta del modelo."""
        pass