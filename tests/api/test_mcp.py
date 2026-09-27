"""Tests del acceso MCP (`POST /mcp`, JSON-RPC `tools/call`) con SQLite real temporal.

Empezó en T038 (`crear_reserva`); T039 y T040 añadieron `listar_reservas` y `cancelar_reserva`,
y T049 completa la matriz. Las llamadas son JSON-RPC reales a `POST /mcp` de la aplicación
completa (`crear_app()`); el `base_url` con puerto es obligatorio (el SDK responde 421 con otro
`Host`).
"""

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import database
from app.main import crear_app
from app.services.reservas import LIMITE_MAXIMO, LIMITE_MINIMO, LIMITE_POR_DEFECTO, SKIP_MINIMO

FECHA = (date.today() + timedelta(days=30)).isoformat()
CLAVE = "clave-segura-1"
CABECERAS_MCP = {"Accept": "application/json, text/event-stream"}


@pytest.fixture
def cliente_mcp(motor_temporal) -> TestClient:
    """La aplicación real (`crear_app()`), con el lifespan y el MCP montado en `/mcp`."""
    with TestClient(crear_app(), base_url="http://localhost:8000") as cliente:
        yield cliente


def _autenticar(cliente, email) -> dict:
    cliente.post("/auth/registro", json={"email": email, "password": CLAVE})
    token = cliente.post("/auth/login", data={"username": email, "password": CLAVE}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


@pytest.fixture
def ana(cliente_mcp) -> dict:
    return _autenticar(cliente_mcp, "ana@example.com")


@pytest.fixture
def luis(cliente_mcp) -> dict:
    return _autenticar(cliente_mcp, "luis@example.com")


def _rpc(cliente, metodo, parametros, cabeceras=None) -> dict:
    respuesta = cliente.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": metodo, "params": parametros},
        headers={**CABECERAS_MCP, **(cabeceras or {})},
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["result"]


def _llamar(cliente, herramienta, argumentos, cabeceras=None) -> dict:
    """Ejecuta un tool y devuelve el `dict` que responde (su contenido de texto, en JSON)."""
    resultado = _rpc(
        cliente, "tools/call", {"name": herramienta, "arguments": argumentos}, cabeceras
    )
    assert resultado["isError"] is False  # los errores de negocio viajan como {"error": ...}
    return json.loads(resultado["content"][0]["text"])


def _crear(cliente, cabeceras, inicio, fin, fecha=FECHA):
    argumentos = {"fecha": fecha, "hora_inicio": inicio, "hora_fin": fin}
    return _llamar(cliente, "crear_reserva", argumentos, cabeceras)


def _descripcion(cliente, herramienta) -> str:
    """Descripción publicada de un tool, con los saltos de línea de la docstring normalizados."""
    herramientas = _rpc(cliente, "tools/list", {})["tools"]
    publicada = next(h for h in herramientas if h["name"] == herramienta)["description"]
    return " ".join(publicada.split())


def _reservas_rest(cliente, cabeceras) -> list[dict]:
    return cliente.get("/reservas/", headers=cabeceras).json()


# --- publicación del tool (Art. VI.2, VI.4) ----------------------------------------------


def test_crear_reserva_se_publica_con_una_descripcion_verificable(cliente_mcp):
    herramientas = _rpc(cliente_mcp, "tools/list", {})["tools"]

    crear = next(h for h in herramientas if h["name"] == "crear_reserva")
    descripcion = _descripcion(cliente_mcp, "crear_reserva")
    for esperado in ("YYYY-MM-DD", "HH:MM", "medianoche", "solapar", "contiguas", "No autenticado"):
        assert esperado in descripcion
    assert set(crear["inputSchema"]["properties"]) == {"fecha", "hora_inicio", "hora_fin"}
    assert "ctx" not in crear["inputSchema"]["properties"]  # el contexto no es parámetro del tool


# --- crear_reserva: caso feliz e identidad -----------------------------------------------


def test_crear_reserva_valida_devuelve_la_reserva_y_queda_guardada(cliente_mcp, ana):
    respuesta = _crear(cliente_mcp, ana, "09:00", "10:00")

    assert respuesta == {"id": 1, "fecha": FECHA, "hora_inicio": "09:00", "hora_fin": "10:00"}
    assert [r["id"] for r in _reservas_rest(cliente_mcp, ana)] == [1]


def test_la_reserva_se_crea_a_nombre_del_usuario_del_token(cliente_mcp, ana, luis):
    _crear(cliente_mcp, luis, "09:00", "10:00")

    assert _reservas_rest(cliente_mcp, ana) == []
    assert [r["usuario_id"] for r in _reservas_rest(cliente_mcp, luis)] == [2]


def test_reservas_contiguas_se_aceptan(cliente_mcp, ana):
    _crear(cliente_mcp, ana, "09:00", "10:00")

    assert "error" not in _crear(cliente_mcp, ana, "10:00", "11:00")


# --- crear_reserva: sin identidad → «No autenticado» y no se ejecuta nada ----------------


@pytest.mark.parametrize(
    "cabeceras",
    [
        pytest.param({}, id="sin-cabecera"),
        pytest.param({"Authorization": "Bearer esto-no-es-un-jwt"}, id="token-invalido"),
        pytest.param({"Authorization": "Basic abc123"}, id="esquema-basic"),
    ],
)
def test_sin_token_valido_devuelve_no_autenticado_y_no_crea_nada(cliente_mcp, ana, cabeceras):
    respuesta = _crear(cliente_mcp, cabeceras, "09:00", "10:00")

    assert respuesta == {"error": "No autenticado"}
    assert _reservas_rest(cliente_mcp, ana) == []


def test_la_autenticacion_se_evalua_antes_que_el_formato(cliente_mcp):
    respuesta = _llamar(
        cliente_mcp,
        "crear_reserva",
        {"fecha": "no-es-fecha", "hora_inicio": "x", "hora_fin": "y"},
    )

    assert respuesta == {"error": "No autenticado"}


# --- crear_reserva: errores de negocio con el mismo mensaje que REST ---------------------


@pytest.mark.parametrize(
    ("inicio", "fin", "mensaje"),
    [
        ("10:30", "11:30", "La sala ya está reservada en ese horario"),
        ("11:00", "10:00", "La hora de fin debe ser posterior a la hora de inicio"),
        ("10:00", "10:00", "La hora de fin debe ser posterior a la hora de inicio"),
        ("23:00", "01:00", "La hora de fin debe ser posterior a la hora de inicio"),
    ],
)
def test_una_regla_violada_devuelve_error_estructurado_y_no_guarda(
    cliente_mcp, ana, inicio, fin, mensaje
):
    _crear(cliente_mcp, ana, "10:00", "12:00")

    assert _crear(cliente_mcp, ana, inicio, fin) == {"error": mensaje}
    assert len(_reservas_rest(cliente_mcp, ana)) == 1


def test_solapar_con_la_reserva_de_otro_usuario_devuelve_error(cliente_mcp, ana, luis):
    _crear(cliente_mcp, ana, "09:00", "11:00")

    assert _crear(cliente_mcp, luis, "10:00", "12:00") == {
        "error": "La sala ya está reservada en ese horario"
    }


def test_una_fecha_pasada_devuelve_error(cliente_mcp, ana):
    assert _crear(cliente_mcp, ana, "09:00", "10:00", fecha="2000-01-01") == {
        "error": "No se puede reservar en una fecha y hora pasadas"
    }


@pytest.mark.parametrize(
    ("fecha", "inicio", "fin"),
    [
        ("15/01/2030", "09:00", "10:00"),
        (FECHA, "9:00", "10:00"),
        (FECHA, "09:00:30", "10:00"),
        (FECHA, "09:00", "25:00"),
        (FECHA + "T10:00:00", "09:00", "10:00"),
    ],
)
def test_un_formato_invalido_devuelve_error_de_formato(cliente_mcp, ana, fecha, inicio, fin):
    respuesta = _crear(cliente_mcp, ana, inicio, fin, fecha=fecha)

    assert respuesta == {"error": "Formato de fecha u hora inválido: use YYYY-MM-DD y HH:MM"}
    assert _reservas_rest(cliente_mcp, ana) == []


# --- un fallo inesperado tampoco sale como excepción cruda (Art. VI.3) -------------------


def test_un_fallo_inesperado_devuelve_error_estructurado_sin_detalles_internos(cliente_mcp, ana):
    with database.motor.begin() as conexion:  # BD rota de verdad: sin la tabla de usuarios
        conexion.execute(text("DROP TABLE reservas"))
        conexion.execute(text("DROP TABLE usuarios"))

    respuesta = _crear(cliente_mcp, ana, "09:00", "10:00")

    assert respuesta == {"error": "Error interno del servidor"}


# --- listar_reservas (T039) --------------------------------------------------------------

PAGINACION_INVALIDA = {
    "error": "Parámetros de paginación inválidos: skip >= 0 y 1 <= limit <= 100"
}


def _listar(cliente, cabeceras, **argumentos):
    return _llamar(cliente, "listar_reservas", argumentos, cabeceras)


def test_listar_reservas_se_publica_con_una_descripcion_verificable(cliente_mcp):
    herramientas = _rpc(cliente_mcp, "tools/list", {})["tools"]
    listar = next(h for h in herramientas if h["name"] == "listar_reservas")

    descripcion = _descripcion(cliente_mcp, "listar_reservas")
    for esperado in ("solo las suyas", "fecha y hora de inicio", "skip", "limit", "No autenticado"):
        assert esperado in descripcion
    propiedades = listar["inputSchema"]["properties"]
    assert set(propiedades) == {"skip", "limit"}
    assert (propiedades["skip"]["default"], propiedades["limit"]["default"]) == (
        SKIP_MINIMO,
        LIMITE_POR_DEFECTO,
    )


def test_la_descripcion_de_listar_cita_los_mismos_limites_que_las_constantes(cliente_mcp):
    descripcion = _descripcion(cliente_mcp, "listar_reservas")

    assert f"(>= {SKIP_MINIMO}" in descripcion
    assert f"por defecto {SKIP_MINIMO}" in descripcion
    assert f"de {LIMITE_MINIMO} a {LIMITE_MAXIMO}" in descripcion
    assert f"por defecto {LIMITE_POR_DEFECTO}" in descripcion


def test_listar_devuelve_solo_las_propias_ordenadas_y_sin_usuario_id(cliente_mcp, ana, luis):
    _crear(cliente_mcp, ana, "15:00", "16:00")
    _crear(cliente_mcp, luis, "12:00", "13:00")
    _crear(cliente_mcp, ana, "09:00", "10:00")
    otro_dia = (date.today() + timedelta(days=31)).isoformat()
    _crear(cliente_mcp, ana, "08:00", "09:00", fecha=otro_dia)

    respuesta = _listar(cliente_mcp, ana)

    assert respuesta == {
        "reservas": [
            {"id": 3, "fecha": FECHA, "hora_inicio": "09:00", "hora_fin": "10:00"},
            {"id": 1, "fecha": FECHA, "hora_inicio": "15:00", "hora_fin": "16:00"},
            {"id": 4, "fecha": otro_dia, "hora_inicio": "08:00", "hora_fin": "09:00"},
        ]
    }


def test_listar_coincide_con_lo_que_devuelve_rest(cliente_mcp, ana):
    _crear(cliente_mcp, ana, "11:00", "12:00")
    _crear(cliente_mcp, ana, "09:00", "10:00")

    ids_mcp = [r["id"] for r in _listar(cliente_mcp, ana)["reservas"]]

    assert ids_mcp == [r["id"] for r in _reservas_rest(cliente_mcp, ana)]


def test_listar_de_un_usuario_sin_reservas_devuelve_lista_vacia(cliente_mcp, ana, luis):
    _crear(cliente_mcp, luis, "09:00", "10:00")

    assert _listar(cliente_mcp, ana) == {"reservas": []}


def test_listar_respeta_skip_y_limit(cliente_mcp, ana):
    for hora in range(8, 12):
        _crear(cliente_mcp, ana, f"{hora:02d}:00", f"{hora + 1:02d}:00")

    pagina = _listar(cliente_mcp, ana, skip=1, limit=2)["reservas"]

    assert [r["hora_inicio"] for r in pagina] == ["09:00", "10:00"]
    assert _listar(cliente_mcp, ana, skip=50) == {"reservas": []}


def test_listar_sin_argumentos_usa_los_valores_por_defecto(cliente_mcp, ana):
    _crear(cliente_mcp, ana, "09:00", "10:00")

    assert len(_listar(cliente_mcp, ana)["reservas"]) == 1


@pytest.mark.parametrize("argumentos", [{"limit": LIMITE_MINIMO}, {"limit": LIMITE_MAXIMO}])
def test_listar_acepta_los_limites_extremos_validos(cliente_mcp, ana, argumentos):
    assert "error" not in _listar(cliente_mcp, ana, **argumentos)


@pytest.mark.parametrize(
    "argumentos",
    [
        {"skip": -1},
        {"limit": 0},
        {"limit": LIMITE_MAXIMO + 1},
        {"limit": -5},
    ],
)
def test_listar_con_paginacion_invalida_devuelve_error_estructurado(cliente_mcp, ana, argumentos):
    assert _listar(cliente_mcp, ana, **argumentos) == PAGINACION_INVALIDA


@pytest.mark.parametrize(
    "cabeceras",
    [
        pytest.param({}, id="sin-cabecera"),
        pytest.param({"Authorization": "Bearer esto-no-es-un-jwt"}, id="token-invalido"),
    ],
)
def test_listar_sin_token_valido_devuelve_no_autenticado(cliente_mcp, ana, cabeceras):
    _crear(cliente_mcp, ana, "09:00", "10:00")

    assert _listar(cliente_mcp, cabeceras) == {"error": "No autenticado"}
    assert _listar(cliente_mcp, cabeceras, limit=0) == {"error": "No autenticado"}


# --- cancelar_reserva (T040) -------------------------------------------------------------

CONFIRMACION_REQUERIDA = {"error": "Confirmación requerida: repite con confirmar=true"}


def _cancelar(cliente, cabeceras, reserva_id, **extra):
    return _llamar(cliente, "cancelar_reserva", {"reserva_id": reserva_id, **extra}, cabeceras)


def _existe(cliente, cabeceras, reserva_id) -> bool:
    return cliente.get(f"/reservas/{reserva_id}", headers=cabeceras).status_code == 200


def test_cancelar_reserva_se_publica_como_accion_destructiva_con_confirmacion(cliente_mcp):
    herramientas = _rpc(cliente_mcp, "tools/list", {})["tools"]
    cancelar = next(h for h in herramientas if h["name"] == "cancelar_reserva")

    descripcion = _descripcion(cliente_mcp, "cancelar_reserva")
    for esperado in ("DESTRUCTIVA", "confirmar=true", "Solo el dueño", "No autenticado"):
        assert esperado in descripcion
    assert "Confirmación requerida" in descripcion and "Reserva no encontrada" in descripcion
    propiedades = cancelar["inputSchema"]["properties"]
    assert set(propiedades) == {"reserva_id", "confirmar"}
    assert propiedades["confirmar"]["default"] is False  # nunca se confirma por omisión
    assert cancelar["inputSchema"]["required"] == ["reserva_id"]


@pytest.mark.parametrize("extra", [{}, {"confirmar": False}], ids=["omitido", "false"])
def test_cancelar_sin_confirmar_pide_confirmacion_y_no_elimina_nada(cliente_mcp, ana, extra):
    reserva = _crear(cliente_mcp, ana, "09:00", "10:00")

    assert _cancelar(cliente_mcp, ana, reserva["id"], **extra) == CONFIRMACION_REQUERIDA
    assert _existe(cliente_mcp, ana, reserva["id"])
    assert len(_reservas_rest(cliente_mcp, ana)) == 1


def test_cancelar_confirmando_una_reserva_propia_la_elimina(cliente_mcp, ana, luis):
    reserva = _crear(cliente_mcp, ana, "09:00", "10:00")

    respuesta = _cancelar(cliente_mcp, ana, reserva["id"], confirmar=True)

    assert respuesta == {"mensaje": f"Reserva {reserva['id']} cancelada"}
    assert not _existe(cliente_mcp, ana, reserva["id"])
    assert cliente_mcp.get(f"/reservas/{reserva['id']}", headers=ana).status_code == 404
    assert "error" not in _crear(cliente_mcp, luis, "09:00", "10:00")  # el horario quedó libre


def test_cancelar_una_reserva_ajena_devuelve_error_y_no_elimina(cliente_mcp, ana, luis):
    ajena = _crear(cliente_mcp, ana, "09:00", "10:00")

    respuesta = _cancelar(cliente_mcp, luis, ajena["id"], confirmar=True)

    assert respuesta == {"error": "No tienes permiso sobre esta reserva"}
    assert _existe(cliente_mcp, ana, ajena["id"])


def test_cancelar_un_id_inexistente_devuelve_reserva_no_encontrada(cliente_mcp, ana):
    assert _cancelar(cliente_mcp, ana, 9999, confirmar=True) == {"error": "Reserva no encontrada"}


def test_sin_confirmar_sobre_una_reserva_ajena_solo_pide_confirmacion(cliente_mcp, ana, luis):
    ajena = _crear(cliente_mcp, ana, "09:00", "10:00")

    assert _cancelar(cliente_mcp, luis, ajena["id"]) == CONFIRMACION_REQUERIDA
    assert _existe(cliente_mcp, ana, ajena["id"])


@pytest.mark.parametrize(
    "cabeceras",
    [
        pytest.param({}, id="sin-cabecera"),
        pytest.param({"Authorization": "Bearer esto-no-es-un-jwt"}, id="token-invalido"),
    ],
)
def test_cancelar_sin_token_valido_devuelve_no_autenticado_y_no_elimina(
    cliente_mcp, ana, cabeceras
):
    reserva = _crear(cliente_mcp, ana, "09:00", "10:00")

    assert _cancelar(cliente_mcp, cabeceras, reserva["id"], confirmar=True) == {
        "error": "No autenticado"
    }
    assert _existe(cliente_mcp, ana, reserva["id"])


def test_cancelar_elimina_lo_mismo_que_delete_rest(cliente_mcp, ana):
    por_mcp = _crear(cliente_mcp, ana, "09:00", "10:00")
    por_rest = _crear(cliente_mcp, ana, "11:00", "12:00")

    _cancelar(cliente_mcp, ana, por_mcp["id"], confirmar=True)
    assert cliente_mcp.delete(f"/reservas/{por_rest['id']}", headers=ana).status_code == 204

    assert _reservas_rest(cliente_mcp, ana) == []


def test_argumentos_fuera_del_esquema_los_rechaza_el_sdk_sin_ejecutar_el_tool(cliente_mcp, ana):
    # Limitación documentada en `app/mcp/server.py`: el SDK valida el esquema antes del tool.
    reserva = _crear(cliente_mcp, ana, "09:00", "10:00")

    for argumentos in ({"reserva_id": "abc", "confirmar": True}, {"confirmar": True}):
        resultado = _rpc(
            cliente_mcp,
            "tools/call",
            {"name": "cancelar_reserva", "arguments": argumentos},
            ana,
        )
        assert resultado["isError"] is True

    assert _existe(cliente_mcp, ana, reserva["id"])
