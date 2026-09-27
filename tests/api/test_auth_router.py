"""Smoke test del router `/auth` contra un SQLite real temporal (sin fakes ni dobles).

La matriz completa de casos de registro y login (422, mayúsculas, etc.) es la tarea T044.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import decodificar_token
from app.routers import auth

CLAVE = "clave-segura-1"


@pytest.fixture
def cliente_rest(motor_temporal) -> TestClient:
    app = FastAPI()
    app.include_router(auth.router)
    return TestClient(app)


def _registrar(cliente, email="ana@example.com", password=CLAVE):
    return cliente.post("/auth/registro", json={"email": email, "password": password})


def test_registro_valido_responde_201_sin_password(cliente_rest):
    respuesta = _registrar(cliente_rest)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo == {"id": 1, "email": "ana@example.com"}
    assert "password" not in cuerpo and "password_hash" not in cuerpo


def test_registro_con_email_duplicado_responde_400(cliente_rest):
    _registrar(cliente_rest)

    respuesta = _registrar(cliente_rest, email="ANA@example.com")

    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": "El email ya está registrado"}


def test_registro_con_password_corta_responde_422(cliente_rest):
    assert _registrar(cliente_rest, password="corta").status_code == 422


def test_login_correcto_devuelve_un_token_del_usuario(cliente_rest):
    usuario_id = _registrar(cliente_rest).json()["id"]

    respuesta = cliente_rest.post(
        "/auth/login", data={"username": "ana@example.com", "password": CLAVE}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["token_type"] == "bearer"
    assert decodificar_token(cuerpo["access_token"]) == usuario_id


@pytest.mark.parametrize(
    ("email", "password"),
    [("ana@example.com", "otra-clave-9"), ("nadie@example.com", CLAVE)],
)
def test_login_con_credenciales_invalidas_responde_401(cliente_rest, email, password):
    _registrar(cliente_rest)

    respuesta = cliente_rest.post("/auth/login", data={"username": email, "password": password})

    assert respuesta.status_code == 401
    assert respuesta.json() == {"detail": "Credenciales incorrectas"}
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"
