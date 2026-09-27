"""Tests de los fixtures y helpers de `tests/conftest.py` (T042)."""

import re
from datetime import date, timedelta

from tests.conftest import crear_reserva_rest, fecha_futura, registrar_y_autenticar


def test_client_ejecuta_el_lifespan_y_sirve_rest_y_mcp(client):
    assert client.get("/openapi.json").status_code == 200
    respuesta = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={"Accept": "application/json, text/event-stream"},
    )
    assert respuesta.status_code == 200
    assert len(respuesta.json()["result"]["tools"]) == 3


def test_cada_test_recibe_su_propia_base_de_datos(client):
    # Si la BD se compartiera entre tests, este registro fallaría con 400 (RN-5) al repetirse.
    registrar_y_autenticar(client, "ana@example.com")


def test_cada_test_recibe_su_propia_base_de_datos_otra_vez(client):
    registrar_y_autenticar(client, "ana@example.com")


def test_registrar_y_autenticar_devuelve_una_cabecera_bearer_valida(client):
    cabeceras = registrar_y_autenticar(client, "ana@example.com")

    assert list(cabeceras) == ["Authorization"]
    assert cabeceras["Authorization"].startswith("Bearer ")
    assert client.get("/reservas/", headers=cabeceras).status_code == 200


def test_fecha_futura_tiene_formato_iso_y_es_posterior_a_hoy():
    valor = fecha_futura()

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor)
    assert date.fromisoformat(valor) == date.today() + timedelta(days=30)
    assert date.fromisoformat(fecha_futura(5)) == date.today() + timedelta(days=5)


def test_crear_reserva_rest_usa_la_fecha_futura_por_defecto(client):
    cabeceras = registrar_y_autenticar(client, "ana@example.com")

    respuesta = crear_reserva_rest(client, cabeceras, "09:00", "10:00")

    assert respuesta.status_code == 201
    assert respuesta.json()["fecha"] == fecha_futura()
