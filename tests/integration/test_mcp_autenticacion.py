"""Tests de `mcp/autenticacion.py`: identidad a partir del header `Authorization`.

Contexto falso en memoria (clases propias con `Headers` reales de Starlette, sin dobles de
terceros) y SQLite real temporal para resolver usuarios.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from starlette.datastructures import Headers

from app.core.config import get_settings
from app.core.database import abrir_sesion
from app.core.security import crear_token
from app.mcp.autenticacion import obtener_usuario_desde_contexto
from app.services.auth import registrar_usuario
from app.services.excepciones import NoAutenticadoError


class _Peticion:
    def __init__(self, cabeceras: dict[str, str]):
        self.headers = Headers(cabeceras)


class _ContextoDePeticion:
    def __init__(self, peticion):
        self.request = peticion


class ContextoFalso:
    """Imita lo único que usa `autenticacion.py`: `ctx.request_context.request.headers`."""

    def __init__(self, cabeceras: dict[str, str] | None = None, *, sin_peticion: bool = False):
        peticion = None if sin_peticion else _Peticion(cabeceras or {})
        self.request_context = _ContextoDePeticion(peticion)


class ContextoFueraDePeticion:
    @property
    def request_context(self):
        raise ValueError("Context is not available outside of a request")


def _con_token(token: str) -> ContextoFalso:
    return ContextoFalso({"Authorization": f"Bearer {token}"})


@pytest.fixture
def db(motor_temporal):
    with abrir_sesion() as sesion:
        yield sesion


@pytest.fixture
def ana(db):
    return registrar_usuario(db, "ana@example.com", "clave-segura-1")


# --- caso feliz: la identidad sale del token ---------------------------------------------


def test_un_token_valido_resuelve_al_usuario_real(db, ana):
    usuario = obtener_usuario_desde_contexto(_con_token(crear_token(str(ana.id))), db)

    assert (usuario.id, usuario.email) == (ana.id, "ana@example.com")


def test_cada_token_resuelve_a_su_propio_usuario_sin_usuario_fijo(db, ana):
    luis = registrar_usuario(db, "luis@example.com", "clave-segura-1")

    de_ana = obtener_usuario_desde_contexto(_con_token(crear_token(str(ana.id))), db)
    de_luis = obtener_usuario_desde_contexto(_con_token(crear_token(str(luis.id))), db)

    assert (de_ana.id, de_luis.id) == (ana.id, luis.id)


@pytest.mark.parametrize("esquema", ["Bearer", "bearer", "BEARER"])
def test_el_esquema_bearer_no_distingue_mayusculas(db, ana, esquema):
    contexto = ContextoFalso({"authorization": f"{esquema} {crear_token(str(ana.id))}"})

    assert obtener_usuario_desde_contexto(contexto, db).id == ana.id


# --- todo lo demás es «No autenticado» ---------------------------------------------------


@pytest.mark.parametrize(
    "contexto",
    [
        pytest.param(ContextoFalso(), id="sin-cabecera"),
        pytest.param(ContextoFalso(sin_peticion=True), id="request-none"),
        pytest.param(ContextoFueraDePeticion(), id="fuera-de-peticion"),
        pytest.param(ContextoFalso({"Authorization": "Basic abc123"}), id="esquema-basic"),
        pytest.param(ContextoFalso({"Authorization": "Bearer"}), id="bearer-sin-token"),
        pytest.param(ContextoFalso({"Authorization": "Bearer    "}), id="bearer-token-vacio"),
        pytest.param(ContextoFalso({"Authorization": ""}), id="cabecera-vacia"),
        pytest.param(ContextoFalso({"Authorization": "token-sin-esquema"}), id="sin-esquema"),
        pytest.param(_con_token("esto-no-es-un-jwt"), id="token-basura"),
    ],
)
def test_sin_credenciales_validas_lanza_no_autenticado(db, ana, contexto):
    with pytest.raises(NoAutenticadoError, match="^No autenticado$"):
        obtener_usuario_desde_contexto(contexto, db)


def test_token_firmado_con_otra_clave_lanza_no_autenticado(db, ana):
    ajeno = jwt.encode(
        {"sub": str(ana.id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "otra-clave-distinta-0123456789abcdef0123456789abcdef",
        algorithm=get_settings().ALGORITHM,
    )

    with pytest.raises(NoAutenticadoError):
        obtener_usuario_desde_contexto(_con_token(ajeno), db)


def test_token_expirado_lanza_no_autenticado(db, ana):
    ajustes = get_settings()
    expirado = jwt.encode(
        {"sub": str(ana.id), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        ajustes.SECRET_KEY,
        algorithm=ajustes.ALGORITHM,
    )

    with pytest.raises(NoAutenticadoError):
        obtener_usuario_desde_contexto(_con_token(expirado), db)


def test_token_de_un_usuario_que_ya_no_existe_lanza_no_autenticado(db, ana):
    with pytest.raises(NoAutenticadoError):
        obtener_usuario_desde_contexto(_con_token(crear_token("9999")), db)
