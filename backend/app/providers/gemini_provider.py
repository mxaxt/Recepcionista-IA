from dotenv import load_dotenv
from fastapi import FastAPI

from app.agents.agent import Agent
from app.providers.gemini_provider import GeminiProvider


load_dotenv()


app = FastAPI(
    title="Recepcionista",
    version="0.1.0",
)


provider = GeminiProvider()
agent = Agent(provider)


@app.get("/")
async def root():

    response = await agent.chat("Hola")

    return {
        "response": response
    }