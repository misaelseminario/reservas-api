"""Identidad en MCP: resuelve el usuario real a partir del header `Authorization: Bearer <JWT>`.

Es el MISMO JWT que devuelve `POST /auth/login` y se valida con la MISMA función que REST,
`services/auth.py::obtener_usuario_actual` (Art. VI.6, research R4). Aquí solo se extrae el token
de la petición HTTP; no se valida nada por cuenta propia. NUNCA hay un usuario fijo: el servidor
MCP corre con `stateless_http=True`, de modo que cada llamada lleva y valida su propio token.
"""

from mcp.server.fastmcp import Context
from sqlalchemy.orm import Session

from app.models import Usuario
from app.services.auth import obtener_usuario_actual


def _extraer_token_bearer(ctx: Context) -> str | None:
    """Token del header `Authorization`, o `None` si falta, no es `Bearer` o está vacío."""
    try:
        peticion = ctx.request_context.request
    except ValueError:  # el SDK lo lanza si el contexto se usa fuera de una petición
        return None
    if peticion is None:  # p. ej. transporte sin HTTP; el SDK admite `request=None`
        return None

    cabecera = peticion.headers.get("authorization")
    if not cabecera:
        return None
    esquema, _, token = cabecera.partition(" ")
    if esquema.lower() != "bearer":
        return None
    return token.strip() or None


def obtener_usuario_desde_contexto(ctx: Context, db: Session) -> Usuario:
    """Usuario autenticado de la petición MCP en curso.

    Cualquier fallo (sin cabecera, esquema distinto de `Bearer`, token inválido o expirado,
    usuario inexistente) lanza `NoAutenticadoError`; el tool lo convierte en
    `{"error": "No autenticado"}`.
    """
    return obtener_usuario_actual(db, _extraer_token_bearer(ctx))
