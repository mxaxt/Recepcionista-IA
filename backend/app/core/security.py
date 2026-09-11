"""Proteccion minima de las APIs de gestion (/agenda y /reviews).

Modelo de token compartido: el operador fija ADMIN_API_TOKEN en el
entorno y los clientes legitimos la envian en el header X-Admin-Token.
No es un sistema de autenticacion de usuarios: solo evita que una app
publicada en internet pueda recibir reservas o aprobaciones de
revision anonimas.

Si ADMIN_API_TOKEN no esta definido, los endpoints quedan abiertos
(desarrollo local y suite de tests, que corren sin secretos). En
produccion (Render) app.main se niega a arrancar sin esa variable.

El Agent interno NO pasa por HTTP: usa AgendaTools y el servicio de
reviews directamente, por lo que proteger los routers no lo afecta.
"""

import os

from fastapi import Header, HTTPException

ADMIN_API_TOKEN_ENV = "ADMIN_API_TOKEN"

ADMIN_TOKEN_HEADER = "X-Admin-Token"


def require_admin_token(
    x_admin_token: str | None = Header(
        default=None,
        alias=ADMIN_TOKEN_HEADER,
    ),
) -> None:
    expected = os.getenv(ADMIN_API_TOKEN_ENV)

    if not expected:
        return

    if x_admin_token != expected:
        raise HTTPException(
            status_code=401,
            detail="Token de administracion requerido o invalido.",
        )
