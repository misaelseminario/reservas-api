"""Dependencias compartidas de los routers: usuario autenticado y traducción de errores.

Aquí NO hay reglas de negocio (Art. I.2): la validación del JWT la hace
`services/auth.py::obtener_usuario_actual` (la misma función que usa MCP) y esta capa solo
traduce sus excepciones de dominio a `HTTPException` (Art. V.3).
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Usuario
from app.services.auth import obtener_usuario_actual
from app.services.excepciones import (
    ConfirmacionRequeridaError,
    EmailYaRegistradoError,
    ErrorDeDominio,
    FechaPasadaError,
    HorarioInvalidoError,
    NoAutenticadoError,
    NoEsDuenoError,
    ReservaNoEncontradaError,
    ReservaSolapadaError,
)

# `auto_error=False`: sin cabecera `Authorization` el esquema entrega `None` y el error 401 lo
# construye `traducir_excepcion` con el mensaje propio en español.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

_CODIGOS_HTTP: dict[type[ErrorDeDominio], int] = {
    EmailYaRegistradoError: status.HTTP_400_BAD_REQUEST,
    ReservaSolapadaError: status.HTTP_400_BAD_REQUEST,
    HorarioInvalidoError: status.HTTP_400_BAD_REQUEST,
    FechaPasadaError: status.HTTP_400_BAD_REQUEST,
    # No ocurre por REST (`DELETE` llama al servicio con `confirmar=True`); si ocurriera, es
    # una regla de negocio violada (Art. V.2) y no debe convertirse en un 500.
    ConfirmacionRequeridaError: status.HTTP_400_BAD_REQUEST,
    NoEsDuenoError: status.HTTP_403_FORBIDDEN,
    ReservaNoEncontradaError: status.HTTP_404_NOT_FOUND,
    NoAutenticadoError: status.HTTP_401_UNAUTHORIZED,
}


def traducir_excepcion(exc: ErrorDeDominio) -> HTTPException:
    """Convierte una excepción de dominio en su `HTTPException` (`detail = str(exc)`).

    Uso: `raise traducir_excepcion(exc) from exc`.
    """
    codigo = _CODIGOS_HTTP.get(type(exc), status.HTTP_400_BAD_REQUEST)
    cabeceras = {"WWW-Authenticate": "Bearer"} if codigo == status.HTTP_401_UNAUTHORIZED else None
    return HTTPException(status_code=codigo, detail=str(exc), headers=cabeceras)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """Usuario autenticado a partir del JWT. Único origen del `usuario_id` (Art. IV.6)."""
    try:
        return obtener_usuario_actual(db, token)
    except NoAutenticadoError as exc:
        raise traducir_excepcion(exc) from exc
