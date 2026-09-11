"""Adaptador de salida hacia la Bot API de Telegram.

Unico modulo que conoce la URL de Telegram y el token. No contiene
logica de conversacion ni de negocio: solo envia texto plano.

El token se lee exclusivamente desde la variable de entorno
TELEGRAM_BOT_TOKEN y nunca se loggea ni se incluye en mensajes de error.
"""

import os
from typing import Any

import httpx

API_BASE_URL = "https://api.telegram.org"

MAX_TELEGRAM_MESSAGE_CHARS = 4096

REQUEST_TIMEOUT_SECONDS = 15


def _split_text(text: str) -> list[str]:
    """Corta el texto en trozos aptos para un solo sendMessage."""
    if len(text) <= MAX_TELEGRAM_MESSAGE_CHARS:
        return [text]

    return [
        text[i:i + MAX_TELEGRAM_MESSAGE_CHARS]
        for i in range(0, len(text), MAX_TELEGRAM_MESSAGE_CHARS)
    ]


class TelegramClient:

    def __init__(
        self,
        token: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._token = token
        self._transport = transport

    def _method_url(self, method: str) -> str:
        return f"{API_BASE_URL}/bot{self._token}/{method}"

    async def send_message(self, chat_id: int, text: str) -> None:
        if not self._token:
            raise ValueError(
                "No se encontro TELEGRAM_BOT_TOKEN en las variables de "
                "entorno."
            )

        for chunk in _split_text(text):
            await self._post(
                "sendMessage",
                {"chat_id": chat_id, "text": chunk},
            )

    async def _post(self, method: str, payload: dict[str, Any]) -> None:
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=REQUEST_TIMEOUT_SECONDS,
            ) as http:
                response = await http.post(
                    self._method_url(method),
                    json=payload,
                )
        except httpx.HTTPError:
            # from None corta la cadena del traceback: httpx suele incluir
            # la URL completa (con token) en la representacion de sus errores.
            raise RuntimeError(
                f"No se pudo contactar a la API de Telegram (metodo {method})."
            ) from None

        try:
            body = response.json()
        except ValueError:
            raise RuntimeError(
                f"Telegram devolvio una respuesta no valida "
                f"(metodo {method}, HTTP {response.status_code})."
            ) from None

        if not body.get("ok"):
            raise RuntimeError(
                f"Telegram rechazo el mensaje: {body.get('description', '')}"
            )


def get_telegram_client() -> TelegramClient:
    """Factory de la app: el token viene siempre del entorno."""
    return TelegramClient(token=os.getenv("TELEGRAM_BOT_TOKEN"))
