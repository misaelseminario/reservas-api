"""Flujos REST de reservas con la aplicación completa y SQLite real (T048).

Cubre RN-1 (solapada y contigua), RN-2 (horas inválidas), RN-4 (modificar), RN-7 (pasado),
los formatos inválidos (422), la identidad tomada del JWT y la paginación del listado.
Los casos 401, 403 y 404 tienen sus propios archivos (T045-T047).
"""

from datetime import date, timedelta

import pytest

from tests.conftest import crear_reserva_rest, fecha_futura, registrar_y_autenticar

FECHA = fecha_futura()
OTRA_FECHA = fecha_futura(31)
AYER = (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture
def ana(client):
    return registrar_y_autenticar(client, "ana@example.com")


@pytest.fixture
def luis(client):
    return registrar_y_autenticar(client, "luis@example.com")


def _cuerpo(inicio, fin, fecha=FECHA):
    return {"fecha": fecha, "hora_inicio": inicio, "hora_fin": fin}


# --- crear ---------------------------------------------------------------------------------


def test_crear_responde_201_con_los_datos_de_la_reserva(client, ana):
    respuesta = crear_reserva_rest(client, ana, "09:00", "10:00")

    assert respuesta.status_code == 201
    assert respuesta.json() == {
        "id": 1,
        "usuario_id": 1,
        "fecha": FECHA,
        "hora_inicio": "09:00:00",
        "hora_fin": "10:00:00",
    }


def test_el_usuario_id_sale_del_jwt_aunque_el_cliente_envie_otro(client, ana, luis):
    cuerpo = {**_cuerpo("09:00", "10:00"), "usuario_id": 2}  # intenta reservar "como Luis"

    respuesta = client.post("/reservas/", json=cuerpo, headers=ana)

    assert respuesta.status_code == 201
    assert respuesta.json()["usuario_id"] == 1  # el de Ana, dueña del token
    assert client.get("/reservas/", headers=luis).json() == []


def test_crear_solapada_responde_400_rn1(client, ana, luis):
    crear_reserva_rest(client, ana, "09:00", "10:00")

    respuesta = crear_reserva_rest(client, luis, "09:30", "10:30")

    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": "La sala ya está reservada en ese horario"}
    assert client.get("/reservas/", headers=luis).json() == []


def test_crear_contigua_responde_201(client, ana, luis):
    crear_reserva_rest(client, ana, "09:00", "10:00")

    assert crear_reserva_rest(client, luis, "10:00", "11:00").status_code == 201
    assert crear_reserva_rest(client, luis, "08:00", "09:00").status_code == 201


@pytest.mark.parametrize(("inicio", "fin"), [("23:00", "01:00"), ("10:00", "10:00")])
def test_crear_con_horas_invalidas_responde_400_rn2(client, ana, inicio, fin):
    respuesta = crear_reserva_rest(client, ana, inicio, fin)

    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": "La hora de fin debe ser posterior a la hora de inicio"}


def test_crear_con_fecha_de_ayer_responde_400_rn7(client, ana):
    respuesta = crear_reserva_rest(client, ana, "09:00", "10:00", fecha=AYER)

    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": "No se puede reservar en una fecha y hora pasadas"}


@pytest.mark.parametrize(
    "cuerpo",
    [
        _cuerpo("09:00:30", "10:00"),  # segundos no admitidos
        _cuerpo("9:00", "10:00"),  # hora sin cero a la izquierda
        _cuerpo("09:00", "25:00"),  # hora inexistente
        _cuerpo("09:00", "10:00", fecha="15/01/2030"),  # fecha en otro formato
        _cuerpo("09:00", "10:00", fecha="2030-02-30"),  # fecha inexistente
        {"fecha": FECHA, "hora_inicio": "09:00"},  # falta hora_fin
        {},
    ],
)
def test_crear_con_formato_invalido_responde_422(client, ana, cuerpo):
    assert client.post("/reservas/", json=cuerpo, headers=ana).status_code == 422
    assert client.get("/reservas/", headers=ana).json() == []  # no se creó nada


# --- listar y obtener -----------------------------------------------------------------------


def test_listar_devuelve_solo_las_propias_ordenadas(client, ana, luis):
    crear_reserva_rest(client, ana, "15:00", "16:00")
    crear_reserva_rest(client, ana, "09:00", "10:00")
    crear_reserva_rest(client, luis, "11:00", "12:00")

    respuesta = client.get("/reservas/", headers=ana)

    assert respuesta.status_code == 200
    assert [(r["hora_inicio"], r["usuario_id"]) for r in respuesta.json()] == [
        ("09:00:00", 1),
        ("15:00:00", 1),
    ]


def test_listar_sin_reservas_devuelve_lista_vacia(client, ana):
    assert client.get("/reservas/", headers=ana).json() == []


def test_listar_con_skip_y_limit(client, ana):
    for hora in range(8, 13):  # cinco reservas: 08-09, 09-10, ..., 12-13
        crear_reserva_rest(client, ana, f"{hora:02d}:00", f"{hora + 1:02d}:00")

    def inicios(**parametros):
        cuerpo = client.get("/reservas/", params=parametros, headers=ana).json()
        return [r["hora_inicio"][:2] for r in cuerpo]

    assert inicios() == ["08", "09", "10", "11", "12"]
    assert inicios(limit=2) == ["08", "09"]
    assert inicios(skip=3) == ["11", "12"]
    assert inicios(skip=1, limit=2) == ["09", "10"]


def test_listar_con_skip_mayor_que_el_total_devuelve_lista_vacia(client, ana):
    crear_reserva_rest(client, ana, "09:00", "10:00")

    respuesta = client.get("/reservas/", params={"skip": 50}, headers=ana)

    assert respuesta.status_code == 200
    assert respuesta.json() == []


@pytest.mark.parametrize(
    "parametros",
    [{"limit": 0}, {"skip": -1}, {"limit": 101}, {"limit": "x"}, {"skip": "x"}],
)
def test_listar_con_paginacion_invalida_responde_422(client, ana, parametros):
    assert client.get("/reservas/", params=parametros, headers=ana).status_code == 422


def test_obtener_una_reserva_propia_responde_200(client, ana):
    creada = crear_reserva_rest(client, ana, "09:00", "10:00").json()

    respuesta = client.get(f"/reservas/{creada['id']}", headers=ana)

    assert respuesta.status_code == 200
    assert respuesta.json() == creada


# --- modificar (RN-4) -----------------------------------------------------------------------


def test_put_propio_a_un_horario_libre_responde_200(client, ana):
    creada = crear_reserva_rest(client, ana, "09:00", "10:00").json()

    respuesta = client.put(
        f"/reservas/{creada['id']}", json=_cuerpo("14:00", "15:00", OTRA_FECHA), headers=ana
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "id": creada["id"],
        "usuario_id": 1,
        "fecha": OTRA_FECHA,
        "hora_inicio": "14:00:00",
        "hora_fin": "15:00:00",
    }
    assert client.get(f"/reservas/{creada['id']}", headers=ana).json() == respuesta.json()


def test_put_ampliar_la_propia_reserva_responde_200(client, ana):
    creada = crear_reserva_rest(client, ana, "09:00", "10:00").json()

    respuesta = client.put(f"/reservas/{creada['id']}", json=_cuerpo("08:00", "11:00"), headers=ana)

    assert respuesta.status_code == 200  # no se solapa consigo misma
    assert respuesta.json()["hora_inicio"] == "08:00:00"


def test_put_que_solapa_con_otra_reserva_responde_400_y_no_modifica(client, ana, luis):
    propia = crear_reserva_rest(client, ana, "09:00", "10:00").json()
    crear_reserva_rest(client, luis, "11:00", "12:00")

    respuesta = client.put(f"/reservas/{propia['id']}", json=_cuerpo("10:30", "11:30"), headers=ana)

    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": "La sala ya está reservada en ese horario"}
    assert client.get(f"/reservas/{propia['id']}", headers=ana).json() == propia


def test_put_con_inicio_pasado_responde_400_y_no_modifica(client, ana):
    propia = crear_reserva_rest(client, ana, "09:00", "10:00").json()

    respuesta = client.put(
        f"/reservas/{propia['id']}", json=_cuerpo("09:00", "10:00", AYER), headers=ana
    )

    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": "No se puede reservar en una fecha y hora pasadas"}
    assert client.get(f"/reservas/{propia['id']}", headers=ana).json() == propia


def test_put_con_horas_invalidas_responde_400(client, ana):
    propia = crear_reserva_rest(client, ana, "09:00", "10:00").json()

    respuesta = client.put(f"/reservas/{propia['id']}", json=_cuerpo("11:00", "10:00"), headers=ana)

    assert respuesta.status_code == 400


def test_put_con_formato_invalido_responde_422(client, ana):
    propia = crear_reserva_rest(client, ana, "09:00", "10:00").json()

    respuesta = client.put(
        f"/reservas/{propia['id']}", json=_cuerpo("09:00:30", "10:00"), headers=ana
    )

    assert respuesta.status_code == 422


# --- eliminar --------------------------------------------------------------------------------


def test_delete_propio_responde_204_y_desaparece_del_listado(client, ana):
    creada = crear_reserva_rest(client, ana, "09:00", "10:00").json()

    respuesta = client.delete(f"/reservas/{creada['id']}", headers=ana)

    assert respuesta.status_code == 204
    assert respuesta.content == b""
    assert client.get("/reservas/", headers=ana).json() == []


def test_tras_eliminar_el_horario_queda_libre_para_cualquiera(client, ana, luis):
    creada = crear_reserva_rest(client, ana, "09:00", "10:00").json()
    client.delete(f"/reservas/{creada['id']}", headers=ana)

    assert crear_reserva_rest(client, luis, "09:00", "10:00").status_code == 201
