"""Tests de API de `/auth/registro` y `/auth/login` con la aplicación completa (T044).

Cubre RN-5 (email único sin distinguir mayúsculas), FR-004/SC-004 (la contraseña nunca sale) y
los casos de validación de formato (422) y de credenciales incorrectas (401).
"""

import pytest

from app.core.security import decodificar_token
from tests.conftest import CLAVE_PRUEBA


def _registrar(client, email="ana@example.com", password=CLAVE_PRUEBA):
    return client.post("/auth/registro", json={"email": email, "password": password})


def _login(client, email="ana@example.com", password=CLAVE_PRUEBA):
    return client.post("/auth/login", data={"username": email, "password": password})


# --- registro ----------------------------------------------------------------------------


def test_registro_valido_responde_201_sin_password_ni_hash(client):
    respuesta = _registrar(client)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo == {"id": 1, "email": "ana@example.com"}
    assert "password" not in cuerpo and "password_hash" not in cuerpo
    assert CLAVE_PRUEBA not in respuesta.text


def test_registro_con_email_duplicado_responde_400(client):
    _registrar(client)

    respuesta = _registrar(client)

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"] == "El email ya está registrado"


def test_registro_con_el_mismo_email_en_otra_capitalizacion_responde_400(client):
    primero = _registrar(client, email="Usuario@X.com")
    segundo = _registrar(client, email="usuario@x.com")

    assert primero.status_code == 201
    assert primero.json()["email"] == "usuario@x.com"  # se guarda y devuelve en minúsculas
    assert segundo.status_code == 400  # RN-5


@pytest.mark.parametrize("email", ["no-es-un-email", "sin-arroba.com", "@x.com", ""])
def test_registro_con_email_invalido_responde_422(client, email):
    assert _registrar(client, email=email).status_code == 422


def test_registro_con_contrasena_corta_responde_422(client):
    assert _registrar(client, password="corta12").status_code == 422  # 7 caracteres < 8


def test_registro_con_contrasena_de_73_bytes_responde_422(client):
    assert _registrar(client, password="a" * 73).status_code == 422


def test_registro_con_contrasena_de_72_bytes_responde_201(client):
    assert _registrar(client, password="a" * 72).status_code == 201  # límite exacto de bcrypt


def test_registro_sin_campos_responde_422(client):
    assert client.post("/auth/registro", json={}).status_code == 422


def test_un_registro_rechazado_no_crea_el_usuario(client):
    _registrar(client, password="corta")

    assert _login(client, password="corta").status_code == 401


# --- login -------------------------------------------------------------------------------


def test_login_correcto_responde_200_con_token_bearer(client):
    _registrar(client)

    respuesta = _login(client)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["token_type"] == "bearer"
    assert decodificar_token(cuerpo["access_token"]) == 1  # el `sub` es el id del usuario


def test_login_con_otra_combinacion_de_mayusculas_responde_200(client):
    _registrar(client, email="usuario@x.com")

    assert _login(client, email="USUARIO@X.COM").status_code == 200
    assert _login(client, email="Usuario@X.com").status_code == 200


def test_login_con_contrasena_incorrecta_responde_401(client):
    _registrar(client)

    respuesta = _login(client, password="otra-clave-1")

    assert respuesta.status_code == 401
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


def test_login_con_email_inexistente_responde_401(client):
    assert _login(client, email="nadie@example.com").status_code == 401


def test_contrasena_incorrecta_y_email_inexistente_dan_la_misma_respuesta(client):
    # No se revela qué emails están registrados (Art. IV).
    _registrar(client)

    mala_clave = _login(client, password="otra-clave-1")
    sin_usuario = _login(client, email="nadie@example.com")

    assert mala_clave.status_code == sin_usuario.status_code == 401
    assert mala_clave.json() == sin_usuario.json()


def test_login_sin_datos_responde_422(client):
    assert client.post("/auth/login", data={}).status_code == 422


def test_el_token_del_login_sirve_para_acceder_a_las_reservas(client):
    _registrar(client)
    token = _login(client).json()["access_token"]

    respuesta = client.get("/reservas/", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 200
    assert respuesta.json() == []
