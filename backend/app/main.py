import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from app.agents.agent import Agent
from app.api.agenda import router as agenda_router
from app.api.reviews import router as reviews_router
from app.classifiers.intent_classifier import IntentClassifier
from app.core.agenda_container import get_agenda
from app.core.review_container import get_priority_review_service
from app.memory.conversation import ConversationMemory
from app.providers.gemini_provider import GeminiProvider
from app.schemas.chat import ChatRequest
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


@app.get("/")
async def root():

    response = await agent.chat(
        "default",
        "Hola"
    )

    return {
        "response": response
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