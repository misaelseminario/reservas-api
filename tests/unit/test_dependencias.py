"""Tests de `routers/dependencias.py`: traducción de excepciones y 401 sin token.

Sin BD (se sobreescribe `get_db` con `None`) y sin dobles de terceros. La resolución de un token
válido contra la BD real se prueba en los tests de API (T044-T049).
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.routers.dependencias import get_current_user, traducir_excepcion
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


@pytest.mark.parametrize(
    ("excepcion", "codigo"),
    [
        (EmailYaRegistradoError, 400),
        (ReservaSolapadaError, 400),
        (HorarioInvalidoError, 400),
        (FechaPasadaError, 400),
        (NoEsDuenoError, 403),
        (ReservaNoEncontradaError, 404),
        (NoAutenticadoError, 401),
        (ConfirmacionRequeridaError, 400),
    ],
)
def test_cada_excepcion_de_dominio_se_traduce_a_su_codigo_http(excepcion, codigo):
    error = excepcion()

    http = traducir_excepcion(error)

    assert http.status_code == codigo
    assert http.detail == str(error)


def test_solo_el_401_lleva_la_cabecera_www_authenticate():
    assert traducir_excepcion(NoAutenticadoError()).headers == {"WWW-Authenticate": "Bearer"}
    assert traducir_excepcion(NoEsDuenoError()).headers is None
    assert traducir_excepcion(ReservaNoEncontradaError()).headers is None


def test_el_detalle_del_401_de_login_conserva_el_mensaje_propio():
    http = traducir_excepcion(NoAutenticadoError("Credenciales incorrectas"))

    assert (http.status_code, http.detail) == (401, "Credenciales incorrectas")


def test_una_excepcion_de_dominio_sin_tabla_no_produce_un_500():
    class NuevaReglaError(ErrorDeDominio):
        mensaje_por_defecto = "Otra regla"

    assert traducir_excepcion(NuevaReglaError()).status_code == 400


# --- get_current_user: sin token o con token inválido → 401 (Art. IV.5) ------------------


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: None

    @app.get("/protegida")
    def protegida(usuario=Depends(get_current_user)):
        return {"id": usuario.id}

    return TestClient(app)


def test_sin_token_responde_401_no_autenticado(client):
    respuesta = client.get("/protegida")

    assert respuesta.status_code == 401
    assert respuesta.json() == {"detail": "No autenticado"}
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


def test_con_token_basura_responde_401_no_autenticado(client):
    respuesta = client.get("/protegida", headers={"Authorization": "Bearer esto-no-es-un-jwt"})

    assert respuesta.status_code == 401
    assert respuesta.json() == {"detail": "No autenticado"}
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


def test_con_esquema_distinto_de_bearer_responde_401(client):
    respuesta = client.get("/protegida", headers={"Authorization": "Basic abc123"})

    assert respuesta.status_code == 401
