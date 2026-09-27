"""Tests de `app/main.py`: la fábrica, los endpoints publicados y el arranque (lifespan)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from starlette.routing import Mount

from app.core import database
from app.main import app, crear_app

ENDPOINTS_ESPERADOS = {
    ("POST", "/auth/registro"),
    ("POST", "/auth/login"),
    ("POST", "/reservas/"),
    ("GET", "/reservas/"),
    ("GET", "/reservas/{reserva_id}"),
    ("PUT", "/reservas/{reserva_id}"),
    ("DELETE", "/reservas/{reserva_id}"),
}
METODOS_HTTP = {"get", "post", "put", "patch", "delete"}


def _operaciones(aplicacion: FastAPI) -> set[tuple[str, str]]:
    return {
        (metodo.upper(), ruta)
        for ruta, operaciones in aplicacion.openapi()["paths"].items()
        for metodo in operaciones
        if metodo in METODOS_HTTP
    }


def test_la_aplicacion_publica_exactamente_los_7_endpoints_rest():
    assert _operaciones(crear_app()) == ENDPOINTS_ESPERADOS


def test_el_modulo_expone_la_app_que_carga_uvicorn():
    assert isinstance(app, FastAPI)
    assert _operaciones(app) == ENDPOINTS_ESPERADOS


def test_crear_app_devuelve_una_aplicacion_nueva_cada_vez():
    assert crear_app() is not crear_app()


def test_el_lifespan_crea_las_tablas_al_arrancar(db_url):
    database.configurar_motor(db_url)  # BD vacía: sin `crear_tablas()` previo
    try:
        assert inspect(database.motor).get_table_names() == []

        with TestClient(crear_app()):
            assert {"usuarios", "reservas"} <= set(inspect(database.motor).get_table_names())
    finally:
        database.motor.dispose()
        database.motor = None
        database.SessionLocal = None


def test_docs_y_openapi_responden(motor_temporal):
    with TestClient(crear_app()) as cliente:
        assert cliente.get("/docs").status_code == 200
        assert cliente.get("/openapi.json").json()["info"]["title"] == "API de reservas"


# --- MCP montado en la misma aplicación (T041) -------------------------------------------

CABECERAS_MCP = {"Accept": "application/json, text/event-stream"}


def _llamada_mcp(metodo: str, parametros: dict | None = None) -> dict:
    return {"jsonrpc": "2.0", "id": 1, "method": metodo, "params": parametros or {}}


def test_el_mount_de_mcp_es_lo_ultimo_que_se_registra():
    rutas = crear_app().routes

    assert isinstance(rutas[-1], Mount)
    assert not any(isinstance(ruta, Mount) for ruta in rutas[:-1])


def test_post_mcp_responde_y_publica_los_tres_tools(motor_temporal):
    with TestClient(crear_app(), base_url="http://localhost:8000") as cliente:
        respuesta = cliente.post("/mcp", json=_llamada_mcp("tools/list"), headers=CABECERAS_MCP)

    assert respuesta.status_code == 200
    nombres = {tool["name"] for tool in respuesta.json()["result"]["tools"]}
    assert nombres == {"crear_reserva", "listar_reservas", "cancelar_reserva"}


def test_rest_sigue_funcionando_con_mcp_montado(motor_temporal):
    with TestClient(crear_app(), base_url="http://localhost:8000") as cliente:
        assert cliente.get("/docs").status_code == 200
        login = cliente.post("/auth/login", data={"username": "nadie@example.com", "password": "x"})
        assert login.status_code == 401  # ruta REST alcanzada, no tapada por el mount
        assert cliente.get("/reservas/").status_code == 401


def test_cada_aplicacion_tiene_su_propio_servidor_mcp(motor_temporal):
    # `session_manager.run()` solo puede ejecutarse una vez por instancia (research R3.7):
    # dos aplicaciones seguidas funcionan porque cada `crear_app()` crea el suyo.
    for _ in range(2):
        with TestClient(crear_app(), base_url="http://localhost:8000") as cliente:
            respuesta = cliente.post("/mcp", json=_llamada_mcp("tools/list"), headers=CABECERAS_MCP)
            assert respuesta.status_code == 200
