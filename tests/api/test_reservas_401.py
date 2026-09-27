"""Caso 401 obligatorio de la spec (T045): sin credenciales válidas no se accede a nada.

Cubre token ausente, basura, firmado con otra clave y expirado, en las cinco rutas protegidas
de `/reservas/`. Las respuestas 401 incluyen `WWW-Authenticate: Bearer`.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from tests.conftest import fecha_futura, registrar_y_autenticar

CUERPO = {"fecha": fecha_futura(), "hora_inicio": "09:00", "hora_fin": "10:00"}

# (método, ruta, cuerpo JSON o None)
RUTAS_PROTEGIDAS = [
    ("GET", "/reservas/", None),
    ("POST", "/reservas/", CUERPO),
    ("GET", "/reservas/1", None),
    ("PUT", "/reservas/1", CUERPO),
    ("DELETE", "/reservas/1", None),
]
IDS = [f"{metodo} {ruta}" for metodo, ruta, _ in RUTAS_PROTEGIDAS]


def _token(*, clave=None, expira_en=timedelta(minutes=30), sub="1") -> str:
    ajustes = get_settings()
    carga = {"sub": sub, "exp": datetime.now(timezone.utc) + expira_en}
    return jwt.encode(carga, clave or ajustes.SECRET_KEY, algorithm=ajustes.ALGORITHM)


def _llamar(client, metodo, ruta, cuerpo, cabeceras=None):
    return client.request(metodo, ruta, json=cuerpo, headers=cabeceras)


def _comprobar_401(respuesta):
    assert respuesta.status_code == 401
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), RUTAS_PROTEGIDAS, ids=IDS)
def test_sin_token_responde_401(client, metodo, ruta, cuerpo):
    _comprobar_401(_llamar(client, metodo, ruta, cuerpo))


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), RUTAS_PROTEGIDAS, ids=IDS)
def test_con_token_basura_responde_401(client, metodo, ruta, cuerpo):
    cabeceras = {"Authorization": "Bearer esto-no-es-un-jwt"}

    _comprobar_401(_llamar(client, metodo, ruta, cuerpo, cabeceras))


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), RUTAS_PROTEGIDAS, ids=IDS)
def test_con_token_firmado_con_otra_clave_responde_401(client, metodo, ruta, cuerpo):
    registrar_y_autenticar(client, "ana@example.com")  # el usuario 1 existe: solo falla la firma
    token = _token(clave="otra-clave-distinta-de-32-o-mas-caracteres")
    cabeceras = {"Authorization": f"Bearer {token}"}

    _comprobar_401(_llamar(client, metodo, ruta, cuerpo, cabeceras))


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), RUTAS_PROTEGIDAS, ids=IDS)
def test_con_token_expirado_responde_401(client, metodo, ruta, cuerpo):
    registrar_y_autenticar(client, "ana@example.com")  # el usuario 1 existe: solo falla `exp`
    cabeceras = {"Authorization": f"Bearer {_token(expira_en=timedelta(minutes=-5))}"}

    _comprobar_401(_llamar(client, metodo, ruta, cuerpo, cabeceras))


def test_con_esquema_distinto_de_bearer_responde_401(client):
    ana = registrar_y_autenticar(client, "ana@example.com")
    token = ana["Authorization"].removeprefix("Bearer ")

    _comprobar_401(client.get("/reservas/", headers={"Authorization": f"Basic {token}"}))


def test_con_token_de_un_usuario_que_ya_no_existe_responde_401(client):
    # Firma y `exp` correctas, pero el `sub` no corresponde a ningún usuario.
    cabeceras = {"Authorization": f"Bearer {_token(sub='9999')}"}

    _comprobar_401(client.get("/reservas/", headers=cabeceras))


def test_con_token_sin_sub_responde_401(client):
    ajustes = get_settings()
    sin_sub = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
        ajustes.SECRET_KEY,
        algorithm=ajustes.ALGORITHM,
    )

    _comprobar_401(client.get("/reservas/", headers={"Authorization": f"Bearer {sin_sub}"}))


def test_el_401_no_revela_datos_de_reservas(client):
    ana = registrar_y_autenticar(client, "ana@example.com")
    creada = client.post("/reservas/", json=CUERPO, headers=ana)
    assert creada.status_code == 201

    respuesta = client.get(f"/reservas/{creada.json()['id']}")

    _comprobar_401(respuesta)
    assert CUERPO["fecha"] not in respuesta.text


def test_un_token_valido_si_da_acceso(client):
    # Control: descarta que los 401 anteriores se deban a otra causa.
    ana = registrar_y_autenticar(client, "ana@example.com")

    assert client.get("/reservas/", headers=ana).status_code == 200
