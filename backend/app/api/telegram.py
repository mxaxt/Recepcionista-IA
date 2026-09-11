"""Canal Telegram (webhook entrante) para la recepcionista.

Solo protocolo: valida el update, mapea chat -> session_id y delega en
`agent.chat` (cualquier objeto con ese interface) y en `client.send_message`
(cualquier objeto con ese interface). No conoce Gemini, ni la agenda,
ni reglas de negocio.

La fabrica de router permite inyectar Agent y cliente reales en main.py
y dobles falsos en los tests, sin imports circulares.
"""

import logging

from fastapi import APIRouter, Header, HTTPException

from app.schemas.telegram import TelegramUpdate


logger = logging.getLogger("app.telegram")

TELEGRAM_SESSION_PREFIX = "telegram"

GENERIC_ERROR_MESSAGE = (
    "Hubo un problema al procesar tu mensaje. "
    "Intenta de nuevo en unos minutos."
)


def create_telegram_router(
    agent,
    client,
    webhook_secret: str | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/telegram", tags=["telegram"])

    @router.post("/webhook")
    async def telegram_webhook(
        update: TelegramUpdate,
        x_telegram_bot_api_secret_token: str | None = Header(
            default=None,
            alias="X-Telegram-Bot-Api-Secret-Token",
        ),
    ) -> dict:
        if webhook_secret is not None and (
            x_telegram_bot_api_secret_token != webhook_secret
        ):
            raise HTTPException(
                status_code=403,
                detail="Secret del webhook invalido.",
            )

        text = update.user_text
        chat_id = update.chat_id

        if text is None or chat_id is None:
            return {"status": "ignored"}

        session_id = f"{TELEGRAM_SESSION_PREFIX}:{chat_id}"

        try:
            response = await agent.chat(session_id, text)
        except Exception as exc:
            # Se loggea solo el tipo: nunca el mensaje de la excepcion,
            # para no arrastrar datos sensibles al log.
            logger.warning(
                "El agente fallo procesando un mensaje de Telegram (%s).",
                type(exc).__name__,
            )
            # Se responde igualmente 200 para no provocar reintentos de
            # Telegram sobre un agente que esta fallando.
            await client.send_message(chat_id, GENERIC_ERROR_MESSAGE)
            return {"status": "error"}

        await client.send_message(chat_id, response)

        return {"status": "ok"}

    return router
