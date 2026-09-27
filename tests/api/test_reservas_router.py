"""Smoke test de `POST /reservas/`, `GET /reservas/` y `GET /reservas/{id}` con SQLite real.

Ampliado en T033 (PUT y DELETE). Los casos 401, 403 y 404 completos y el resto de flujos son
las tareas T045-T048.
"""

from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import auth, reservas

FECHA = (date.today() + timedelta(days=30)).isoformat()
OTRA_FECHA = (date.today() + timedelta(days=31)).isoformat()
CLAVE = "clave-segura-1"


@pytest.fixture
def cliente_rest(motor_temporal) -> TestClient:
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(reservas.router)
    return TestClient(app)


def _autenticar(cliente, email) -> dict:
    cliente.post("/auth/registro", json={"email": email, "password": CLAVE})
    token = cliente.post("/auth/login", data={"username": email, "password": CLAVE}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


@pytest.fixture
def ana(cliente_rest) -> dict:
    return _autenticar(cliente_rest, "ana@example.com")


@pytest.fixture
def luis(cliente_rest) -> dict:
    return _autenticar(cliente_rest, "luis@example.com")


def _crear(cliente, cabeceras, inicio, fin, fecha=FECHA, **extra):
    cuerpo = {"fecha": fecha, "hora_inicio": inicio, "hora_fin": fin, **extra}
    return cliente.post("/reservas/", json=cuerpo, headers=cabeceras)


# --- autenticación -----------------------------------------------------------------------


def test_las_tres_rutas_sin_token_responden_401(cliente_rest):
    cuerpo = {"fecha": FECHA, "hora_inicio": "09:00", "hora_fin": "10:00"}

    respuestas = [
        cliente_rest.post("/reservas/", json=cuerpo),
        cliente_rest.get("/reservas/"),
        cliente_rest.get("/reservas/1"),
    ]

    assert [r.status_code for r in respuestas] == [401, 401, 401]
    assert all(r.headers["WWW-Authenticate"] == "Bearer" for r in respuestas)


# --- POST /reservas/ ---------------------------------------------------------------------


def test_crear_responde_201_con_el_usuario_del_jwt(cliente_rest, ana):
    respuesta = _crear(cliente_rest, ana, "09:00", "10:00")

    assert respuesta.status_code == 201
    assert respuesta.json() == {
        "id": 1,
        "usuario_id": 1,
        "fecha": FECHA,
        "hora_inicio": "09:00:00",
        "hora_fin": "10:00:00",
    }


def test_crear_ignora_un_usuario_id_enviado_en_el_cuerpo(cliente_rest, ana, luis):
    respuesta = _crear(cliente_rest, luis, "09:00", "10:00", usuario_id=1)  # 1 es Ana

    assert respuesta.status_code == 201
    assert respuesta.json()["usuario_id"] == 2  # Luis, según su token
    assert cliente_rest.get("/reservas/", headers=ana).json() == []


@pytest.mark.parametrize(
    ("inicio", "fin", "detalle"),
    [
        ("10:30", "11:30", "La sala ya está reservada en ese horario"),
        ("11:00", "10:00", "La hora de fin debe ser posterior a la hora de inicio"),
    ],
)
def test_crear_con_regla_violada_responde_400_con_el_mensaje(cliente_rest, ana, inicio, fin, detalle):
    _crear(cliente_rest, ana, "10:00", "12:00")

    respuesta = _crear(cliente_rest, ana, inicio, fin)

    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": detalle}


def test_crear_contigua_responde_201(cliente_rest, ana):
    _crear(cliente_rest, ana, "09:00", "10:00")

    assert _crear(cliente_rest, ana, "10:00", "11:00").status_code == 201


def test_crear_en_el_pasado_responde_400(cliente_rest, ana):
    respuesta = _crear(cliente_rest, ana, "09:00", "10:00", fecha="2000-01-01")

    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": "No se puede reservar en una fecha y hora pasadas"}


def test_crear_solapando_con_otro_usuario_responde_400(cliente_rest, ana, luis):
    _crear(cliente_rest, ana, "09:00", "11:00")

    assert _crear(cliente_rest, luis, "10:00", "12:00").status_code == 400


def test_crear_con_formato_invalido_responde_422(cliente_rest, ana):
    assert _crear(cliente_rest, ana, "09:00:30", "10:00").status_code == 422


# --- GET /reservas/ ----------------------------------------------------------------------


def test_listar_devuelve_solo_las_propias_ordenadas(cliente_rest, ana, luis):
    _crear(cliente_rest, ana, "15:00", "16:00")
    _crear(cliente_rest, luis, "12:00", "13:00")
    _crear(cliente_rest, ana, "09:00", "10:00")
    _crear(cliente_rest, ana, "09:00", "10:00", fecha=OTRA_FECHA)

    respuesta = cliente_rest.get("/reservas/", headers=ana)

    assert respuesta.status_code == 200
    assert [(r["fecha"], r["hora_inicio"]) for r in respuesta.json()] == [
        (FECHA, "09:00:00"),
        (FECHA, "15:00:00"),
        (OTRA_FECHA, "09:00:00"),
    ]
    assert {r["usuario_id"] for r in respuesta.json()} == {1}


def test_listar_respeta_skip_y_limit(cliente_rest, ana):
    for hora in range(8, 12):
        _crear(cliente_rest, ana, f"{hora:02d}:00", f"{hora + 1:02d}:00")

    pagina = cliente_rest.get("/reservas/?skip=1&limit=2", headers=ana).json()
    assert [r["hora_inicio"] for r in pagina] == ["09:00:00", "10:00:00"]
    assert cliente_rest.get("/reservas/?skip=50", headers=ana).json() == []


@pytest.mark.parametrize("consulta", ["limit=0", "limit=101", "skip=-1"])
def test_listar_con_paginacion_invalida_responde_422(cliente_rest, ana, consulta):
    assert cliente_rest.get(f"/reservas/?{consulta}", headers=ana).status_code == 422


# --- GET /reservas/{id} ------------------------------------------------------------------


def test_obtener_una_reserva_propia_responde_200(cliente_rest, ana):
    creada = _crear(cliente_rest, ana, "09:00", "10:00").json()

    respuesta = cliente_rest.get(f"/reservas/{creada['id']}", headers=ana)

    assert respuesta.status_code == 200
    assert respuesta.json() == creada


def test_obtener_una_reserva_ajena_responde_403_sin_revelar_datos(cliente_rest, ana, luis):
    ajena = _crear(cliente_rest, ana, "09:00", "10:00").json()

    respuesta = cliente_rest.get(f"/reservas/{ajena['id']}", headers=luis)

    assert respuesta.status_code == 403
    assert respuesta.json() == {"detail": "No tienes permiso sobre esta reserva"}


def test_obtener_un_id_inexistente_responde_404(cliente_rest, ana):
    respuesta = cliente_rest.get("/reservas/9999", headers=ana)

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Reserva no encontrada"}


# --- PUT /reservas/{id} (T033) -----------------------------------------------------------


def _actualizar(cliente, cabeceras, reserva_id, inicio, fin, fecha=FECHA, **extra):
    cuerpo = {"fecha": fecha, "hora_inicio": inicio, "hora_fin": fin, **extra}
    return cliente.put(f"/reservas/{reserva_id}", json=cuerpo, headers=cabeceras)


def test_put_y_delete_sin_token_responden_401(cliente_rest):
    cuerpo = {"fecha": FECHA, "hora_inicio": "09:00", "hora_fin": "10:00"}

    assert cliente_rest.put("/reservas/1", json=cuerpo).status_code == 401
    assert cliente_rest.delete("/reservas/1").status_code == 401


def test_put_a_un_horario_libre_responde_200_con_los_datos_nuevos(cliente_rest, ana):
    reserva = _crear(cliente_rest, ana, "09:00", "10:00").json()

    respuesta = _actualizar(cliente_rest, ana, reserva["id"], "14:00", "15:00", fecha=OTRA_FECHA)

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "id": reserva["id"],
        "usuario_id": 1,
        "fecha": OTRA_FECHA,
        "hora_inicio": "14:00:00",
        "hora_fin": "15:00:00",
    }
    assert cliente_rest.get(f"/reservas/{reserva['id']}", headers=ana).json() == respuesta.json()


def test_put_ampliar_la_propia_reserva_responde_200(cliente_rest, ana):
    reserva = _crear(cliente_rest, ana, "10:00", "11:00").json()

    assert _actualizar(cliente_rest, ana, reserva["id"], "10:00", "12:00").status_code == 200


def test_put_sin_cambios_responde_200(cliente_rest, ana):
    reserva = _crear(cliente_rest, ana, "10:00", "11:00").json()

    assert _actualizar(cliente_rest, ana, reserva["id"], "10:00", "11:00").status_code == 200


def test_put_solapando_con_otra_reserva_responde_400_y_no_cambia(cliente_rest, ana, luis):
    propia = _crear(cliente_rest, ana, "09:00", "10:00").json()
    _crear(cliente_rest, luis, "11:00", "12:00")

    respuesta = _actualizar(cliente_rest, ana, propia["id"], "11:30", "12:30")

    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": "La sala ya está reservada en ese horario"}
    assert cliente_rest.get(f"/reservas/{propia['id']}", headers=ana).json() == propia


def test_put_con_horas_invalidas_o_inicio_pasado_responde_400(cliente_rest, ana):
    reserva = _crear(cliente_rest, ana, "09:00", "10:00").json()

    assert _actualizar(cliente_rest, ana, reserva["id"], "10:00", "10:00").status_code == 400
    assert (
        _actualizar(cliente_rest, ana, reserva["id"], "09:00", "10:00", fecha="2000-01-01").status_code
        == 400
    )


def test_put_ignora_un_usuario_id_del_cuerpo(cliente_rest, ana, luis):
    reserva = _crear(cliente_rest, ana, "09:00", "10:00").json()

    respuesta = _actualizar(cliente_rest, ana, reserva["id"], "09:00", "11:00", usuario_id=2)

    assert respuesta.status_code == 200
    assert respuesta.json()["usuario_id"] == 1
    assert cliente_rest.get("/reservas/", headers=luis).json() == []


def test_put_con_cuerpo_incompleto_o_formato_invalido_responde_422(cliente_rest, ana):
    reserva = _crear(cliente_rest, ana, "09:00", "10:00").json()

    incompleto = cliente_rest.put(
        f"/reservas/{reserva['id']}", json={"fecha": FECHA, "hora_inicio": "09:00"}, headers=ana
    )
    assert incompleto.status_code == 422
    assert _actualizar(cliente_rest, ana, reserva["id"], "9:00", "10:00").status_code == 422


def test_put_ajena_responde_403_y_no_cambia(cliente_rest, ana, luis):
    ajena = _crear(cliente_rest, ana, "09:00", "10:00").json()

    respuesta = _actualizar(cliente_rest, luis, ajena["id"], "14:00", "15:00")

    assert respuesta.status_code == 403
    assert cliente_rest.get(f"/reservas/{ajena['id']}", headers=ana).json() == ajena


def test_put_inexistente_responde_404(cliente_rest, ana):
    assert _actualizar(cliente_rest, ana, 9999, "14:00", "15:00").status_code == 404


# --- DELETE /reservas/{id} (T033) --------------------------------------------------------


def test_delete_propia_responde_204_sin_cuerpo_y_desaparece(cliente_rest, ana):
    reserva = _crear(cliente_rest, ana, "09:00", "10:00").json()

    respuesta = cliente_rest.delete(f"/reservas/{reserva['id']}", headers=ana)

    assert respuesta.status_code == 204
    assert respuesta.content == b""
    assert cliente_rest.get("/reservas/", headers=ana).json() == []
    assert cliente_rest.get(f"/reservas/{reserva['id']}", headers=ana).status_code == 404


def test_delete_ajena_responde_403_y_la_reserva_sigue_existiendo(cliente_rest, ana, luis):
    ajena = _crear(cliente_rest, ana, "09:00", "10:00").json()

    assert cliente_rest.delete(f"/reservas/{ajena['id']}", headers=luis).status_code == 403
    assert cliente_rest.get(f"/reservas/{ajena['id']}", headers=ana).json() == ajena


def test_delete_inexistente_responde_404(cliente_rest, ana):
    assert cliente_rest.delete("/reservas/9999", headers=ana).status_code == 404


def test_tras_eliminar_el_horario_queda_libre(cliente_rest, ana, luis):
    reserva = _crear(cliente_rest, ana, "09:00", "10:00").json()
    cliente_rest.delete(f"/reservas/{reserva['id']}", headers=ana)

    assert _crear(cliente_rest, luis, "09:00", "10:00").status_code == 201
