from fastapi import FastAPI

from app.agents.agent import Agent
from app.providers.fake_provider import FakeProvider


app = FastAPI(
    title="Recepcionista",
    version="0.1.0",
)


provider = FakeProvider()
agent = Agent(provider)


@app.get("/")
async def root():

    response = await agent.chat("Quiero sacar un turno")

    return {
        "response": response
    }