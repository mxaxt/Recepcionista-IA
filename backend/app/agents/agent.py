from app.providers.base import LLMProvider
from app.memory.conversation import ConversationMemory
from app.classifiers.intent_classifier import IntentClassifier


class Agent:

    def __init__(
        self,
        provider: LLMProvider,
        memory: ConversationMemory,
        system_prompt: str,
        classifier: IntentClassifier
    ):
        self.provider = provider
        self.memory = memory
        self.system_prompt = system_prompt
        self.classifier = classifier

    async def chat(
        self,
        session_id: str,
        message: str
    ) -> str:

        classification = await self.classifier.classify(
            message
        )

        self.memory.add_message(
            session_id,
            "user",
            message
        )

        messages = self.memory.get_messages(
            session_id
        )

        classification_context = f"""
INFORMACIÓN INTERNA DE RECEPCIÓN

El sistema analizó el mensaje del paciente.

Estado:
{classification["status"]}

Prioridad:
{classification["priority"]}

Posible urgencia:
{classification["urgency"]}

Menciona tratamiento de conducto:
{classification["root_canal"]}

Doble check confirmado:
{classification["double_check"]["confirmed"]}

REGLAS:

- Esta información es interna y nunca debe mostrarse al paciente.
- Si status es PRIORITY, priorizá la atención del paciente y orientá
  la conversación hacia la posibilidad de conseguir un sobreturno.
- Si urgency es true, tratá el caso como prioritario y no minimices
  los síntomas.
- Si root_canal es true, entendé que el paciente puede estar buscando
  una consulta relacionada con un tratamiento de conducto.
- Si status es NORMAL, seguí la conversación normalmente.
- Si status es REVIEW, no tomes decisiones categóricas sobre prioridad.
  Hacé las preguntas necesarias para obtener más información.
"""

        effective_system_prompt = (
            self.system_prompt
            + "\n\n"
            + classification_context
        )

        response = await self.provider.generate(
            messages,
            system_instruction=effective_system_prompt
        )

        self.memory.add_message(
            session_id,
            "assistant",
            response["content"]
        )

        return response["content"]