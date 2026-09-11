# Recepcionista

Recepcionista virtual de un consultorio odontológico: canal de Telegram
(webhook entrante), clasificación de prioridad con doble check, agenda
de turnos y cola de revisión humana para sobreturnos priority.

- Backend: FastAPI + Uvicorn (`backend/`)
- Provider LLM: Gemini (`google-genai`)
- Prompts: `prompts/`

## Ejecución local

Requiere Python 3.13+.

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
copy ..\backend\.env.example .env   # (cp en Linux/macOS) y completar valores
```

Con `GEMINI_API_KEY` ausente, la app falla al arrancar a propósito.

## Variables de entorno

Se leen desde el entorno o desde `backend/.env` (via `python-dotenv`).
Ver `backend/.env.example`. Nunca commitear `.env`.

| Variable | Obligatoria | Uso |
|---|---|---|
| `GEMINI_API_KEY` | siempre | GeminiProvider e IntentClassifier |
| `TELEGRAM_BOT_TOKEN` | canal Telegram | sendMessage (Bot API) |
| `TELEGRAM_WEBHOOK_SECRET` | **producción** | validación del header `X-Telegram-Bot-Api-Secret-Token` en `/telegram/webhook` |
| `ADMIN_API_TOKEN` | **producción** | header `X-Admin-Token` para `/agenda` y `/reviews` |

En producción (Render define `RENDER=true`) la app **no arranca** si
faltan `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` o
`ADMIN_API_TOKEN` (fail-fast en `app/main.py`). En desarrollo, sin
`ADMIN_API_TOKEN` los endpoints de gestión quedan abiertos y sin
`TELEGRAM_WEBHOOK_SECRET` el webhook no valida el header.

## Ejecución con uvicorn

Desde el directorio `backend/`:

```bash
uvicorn app.main:app --reload
```

- Health check (estático, sin LLM): `GET http://127.0.0.1:8000/` → `{"status":"ok"}`
- Swagger: `http://127.0.0.1:8000/docs`

> Importante: `app.main` resuelve `prompts/receptionist_system.md`
> relativo a la **raíz del repo** (`backend/app/main.py` → `../../prompts`).
> Ejecutar siempre dentro de `backend/` con el repo completo clonado.

## Tests

Desde `backend/` (los tests son `unittest`, pytest no es necesario):

```bash
python -m unittest discover -s tests -v
```

## Despliegue en Render (plan free)

El repo incluye [`render.yaml`](render.yaml) (Blueprint):

1. Crear el servicio desde el repo con el Blueprint (o manualmente).
2. Valores clave del Blueprint:
   - `rootDir: backend` — build y start corren en `backend/`, pero el
     repo completo se clona y `prompts/` queda disponible.
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
   - `healthCheckPath: /`
3. En el dashboard de Render, completar `GEMINI_API_KEY` y
   `TELEGRAM_BOT_TOKEN`. `TELEGRAM_WEBHOOK_SECRET` y `ADMIN_API_TOKEN`
   se auto-generan (`generateValue: true`): copiar sus valores del
   dashboard.

### Webhook de Telegram

Después del primer deploy, apuntar el webhook del bot a la URL pública:

```bash
cd backend
python scripts/set_telegram_webhook.py https://<app>.onrender.com/telegram/webhook
```

El script usa `TELEGRAM_WEBHOOK_SECRET` de `backend/.env`: debe coincidir
con el valor configurado en Render, o el bot recibirá `403` en cada
update. Pasarlo explícito si hace falta:

```bash
python scripts/set_telegram_webhook.py https://<app>.onrender.com/telegram/webhook --secret <valor-de-render>
```

### Seguridad mínima de la API

- `/telegram/webhook` valida `X-Telegram-Bot-Api-Secret-Token`.
- `/agenda/*` y `/reviews/*` exigen `X-Admin-Token: <ADMIN_API_TOKEN>`
  cuando `ADMIN_API_TOKEN` está definido (siempre en producción).
- El Agent usa la Agenda y los servicios **in-process**, no por HTTP:
  proteger los routers no afecta la conversación.

## ⚠️ Estado actual: TODO es volátil

No hay persistencia todavía. Agenda, cola de revisión y memoria viven
en RAM del proceso y **se pierden en cada restart, redeploy o
spin-down del plan free**:

- Los turnos reservados vuelven al seed de demo
  (`app/core/agenda_container.py`, fechas hardcodeadas): un turno ya
  confirmado puede quedar libre otra vez (riesgo de doble booking).
- Los casos de revisión `PENDING` desaparecen.
- El decision log (datos de aprendizaje de decisiones humanas) se pierde.
- El historial de conversación por sesión se pierde.
- El plan free suspende la app tras ~15 min de inactividad: Telegram
  reintenta los deliveries, pero puede haber demoras o pérdidas.

La persistencia (fases siguientes) requiere base de datos **externa**
(el filesystem de Render free es efímero; SQLite local no sobrevive a
redeploys).

## Estructura

```
backend/
  app/
    main.py            # composición de la app, health, /chat, /classify
    api/               # /agenda, /reviews, /telegram/webhook
    agents/            # Agent (clasificador + memoria + provider)
    classifiers/       # IntentClassifier (doble check Gemini)
    core/              # config timezone, seguridad, contenedores singleton
    memory/            # ConversationMemory (RAM)
    models/ schemas/   # dataclasses de dominio y modelos pydantic
    providers/         # GeminiProvider / FakeProvider
    services/          # Agenda, PriorityReview, TelegramClient
    tools/             # AgendaTools (capability del Agent)
  scripts/             # set_telegram_webhook.py
  tests/               # unittest
prompts/               # system prompt de la recepcionista
render.yaml            # Blueprint de despliegue
```
