import json
from typing import Any

from google import genai
from google.genai import types


class IntentClassifier:

    def __init__(self, api_key: str):

        self.client = genai.Client(
            api_key=api_key
        )

    async def _analyze_message(
        self,
        message: str
    ) -> dict[str, Any]:

        prompt = f"""
Analizá el siguiente mensaje de un paciente de un consultorio odontológico.

MENSAJE:

{message}

Detectá únicamente dos cosas:

1. URGENCY

Marcá true si el mensaje describe una posible situación que debería
ser atendida con prioridad.

Algunos ejemplos:

- inflamación importante de cara o cuello
- dificultad para respirar
- dificultad para tragar
- sangrado importante que no se detiene
- traumatismo importante
- fiebre acompañada de inflamación
- dolor acompañado de signos claros de complicación

IMPORTANTE:

El dolor por sí solo NO significa necesariamente urgencia.

Por ejemplo:

"Me duele mucho una muela"

no debería ser necesariamente urgency = true.

Pero:

"Me duele muchísimo una muela y tengo toda la cara hinchada"

sí puede ser urgency = true.


2. ROOT_CANAL

Marcá true si el paciente menciona explícitamente o claramente
un tratamiento de conducto.

Ejemplos:

- "Necesito un conducto"
- "Quiero hacerme un tratamiento de conducto"
- "¿Cuánto sale un conducto?"
- "Me dijeron que necesito endodoncia"
- "Creo que me tienen que hacer un conducto"

Si solamente menciona dolor y no habla de conducto,
root_canal debe ser false.


REGLAS:

- No diagnostiques.
- No inventes información.
- Analizá únicamente lo que dice el paciente.
- Las dos variables son independientes.
- Puede haber urgency=true y root_canal=true al mismo tiempo.
- Si no hay suficiente información para marcar una categoría,
usá false.


Respondé ÚNICAMENTE JSON válido con este formato:

{{
    "urgency": true,
    "root_canal": false
}}
"""

        response = await self.client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        return json.loads(response.text)

    async def classify(
        self,
        message: str
    ) -> dict[str, Any]:

        analysis_1 = await self._analyze_message(message)

        analysis_2 = await self._analyze_message(message)

        urgency_match = (
            analysis_1["urgency"]
            == analysis_2["urgency"]
        )

        root_canal_match = (
            analysis_1["root_canal"]
            == analysis_2["root_canal"]
        )

        confirmed = (
            urgency_match
            and root_canal_match
        )

        priority = (
            confirmed
            and (
                analysis_1["urgency"]
                or analysis_1["root_canal"]
            )
        )

        if not confirmed:
            status = "REVIEW"
        elif priority:
            status = "PRIORITY"
        else:
            status = "NORMAL"

        return {
            "status": status,
            "priority": priority,
            "urgency": analysis_1["urgency"],
            "root_canal": analysis_1["root_canal"],
            "double_check": {
                "confirmed": confirmed,
                "analysis_1": analysis_1,
                "analysis_2": analysis_2
            }
        }