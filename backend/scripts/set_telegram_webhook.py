"""Utilidad de desarrollo: apunta el webhook del bot a una URL publica.

Uso (tunel HTTPS ya en marcha):

    python scripts/set_telegram_webhook.py https://<tu-tunel>/telegram/webhook

El token se lee de backend/.env (TELEGRAM_BOT_TOKEN) y el secret opcional
de TELEGRAM_WEBHOOK_SECRET. Nunca se imprime el token.
"""

import argparse
import os
import sys
from pathlib import Path

# El script se ejecuta como `python scripts/set_telegram_webhook.py ...`
# desde backend/: Python pone scripts/ en sys.path, no el directorio
# padre, asi que se agrega backend/ antes de importar el paquete app.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from dotenv import load_dotenv

from app.services.telegram_client import API_BASE_URL


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    parser = argparse.ArgumentParser(description="Configurar webhook del bot")
    parser.add_argument("url", help="URL publica del webhook")
    parser.add_argument(
        "--secret",
        default=os.getenv("TELEGRAM_WEBHOOK_SECRET"),
        help="secret_token opcional (por defecto TELEGRAM_WEBHOOK_SECRET)",
    )
    args = parser.parse_args()

    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        print("Falta TELEGRAM_BOT_TOKEN en backend/.env")
        return 1

    payload: dict = {"url": args.url}

    if args.secret:
        payload["secret_token"] = args.secret

    response = httpx.post(
        f"{API_BASE_URL}/bot{token}/setWebhook",
        json=payload,
        timeout=15,
    )

    body = response.json()

    if body.get("ok"):
        print(f"Webhook configurado en: {args.url}")
        return 0

    print(f"Error: {body.get('description')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
