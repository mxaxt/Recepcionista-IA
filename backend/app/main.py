import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from app.agents.agent import Agent
from app.api.agenda import router as agenda_router
from app.api.reviews import router as reviews_router
from app.api.telegram import create_telegram_router
from app.classifiers.intent_classifier import IntentClassifier
from app.core.agenda_container import get_agenda
from app.core.review_container import get_priority_review_service
from app.core.security import ADMIN_API_TOKEN_ENV
from app.memory.conversation import ConversationMemory
from app.providers.gemini_provider import GeminiProvider
from app.schemas.chat import ChatRequest
from app.services.telegram_client import get_telegram_client
from app.tools.agenda_tools import AgendaTools


load_dotenv()


app = FastAPI(
    title="Recepcionista",
    version="0.1.0",
)


app.include_router(agenda_router)
app.include_router(reviews_router)


api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "No se encontró GEMINI_API_KEY en las variables de entorno."
    )


# Render define RENDER=true en el entorno de ejecucion. En produccion
# el webhook de Telegram y las APIs de gestion no pueden quedar sin
# sus secretos: se falla al arrancar (fail-fast) en lugar de exponer
# endpoints abiertos o validar el secret solo si existe.
if os.getenv("RENDER") == "true":
    faltantes = [
        variable
        for variable in (
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_WEBHOOK_SECRET",
            ADMIN_API_TOKEN_ENV,
        )
        if not os.getenv(variable)
    ]

    if faltantes:
        raise ValueError(
            "Faltan variables de entorno obligatorias en produccion: "
            + ", ".join(faltantes)
        )


provider = GeminiProvider()


memory = ConversationMemory()


prompt_path = (
    Path(__file__).resolve().parents[2]
    / "prompts"
    / "receptionist_system.md"
)

system_prompt = prompt_path.read_text(
    encoding="utf-8"
)


classifier = IntentClassifier(
    api_key=api_key
)


# El Agent comparte la misma Agenda en memoria que expone la API.
agenda_tools = AgendaTools(agenda=get_agenda())


agent = Agent(
    provider=provider,
    memory=memory,
    system_prompt=system_prompt,
    classifier=classifier,
    agenda=agenda_tools,
    reviews=get_priority_review_service(),
)


# Canal Telegram: webhook entrante sincronico; el token y el secret se
# leen del entorno, nunca del codigo. El secret es opcional solo en
# desarrollo: en produccion se exige arriba (fail-fast).
app.include_router(
    create_telegram_router(
        agent=agent,
        client=get_telegram_client(),
        webhook_secret=os.getenv("TELEGRAM_WEBHOOK_SECRET"),
    )
)


@app.get("/")
async def health():
    return {
        "status": "ok"
    }


@app.post("/chat")
async def chat(request: ChatRequest):

    response = await agent.chat(
        request.session_id,
        request.message
    )

    return {
        "response": response
    }


@app.post("/classify")
async def classify(request: ChatRequest):

    result = await classifier.classify(
        request.message
    )

    return result