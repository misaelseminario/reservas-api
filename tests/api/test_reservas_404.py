"""Caso 404 obligatorio de la spec (T047): una reserva inexistente da 404, no 403 ni 200.

También se comprueba que 404 (no existe) y 403 (existe pero es ajena) no se confunden.
"""

import pytest

from tests.conftest import crear_reserva_rest, fecha_futura, registrar_y_autenticar

ID_INEXISTENTE = 9999
CUERPO = {"fecha": fecha_futura(), "hora_inicio": "09:00", "hora_fin": "10:00"}


@pytest.fixture
def ana(client):
    return registrar_y_autenticar(client, "ana@example.com")


def test_get_de_una_reserva_inexistente_responde_404(client, ana):
    respuesta = client.get(f"/reservas/{ID_INEXISTENTE}", headers=ana)

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Reserva no encontrada"}


def test_put_de_una_reserva_inexistente_responde_404(client, ana):
    respuesta = client.put(f"/reservas/{ID_INEXISTENTE}", json=CUERPO, headers=ana)

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Reserva no encontrada"}


def test_delete_de_una_reserva_inexistente_responde_404(client, ana):
    respuesta = client.delete(f"/reservas/{ID_INEXISTENTE}", headers=ana)

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Reserva no encontrada"}


def test_una_reserva_ya_eliminada_responde_404(client, ana):
    creada = crear_reserva_rest(client, ana, "09:00", "10:00").json()
    assert client.delete(f"/reservas/{creada['id']}", headers=ana).status_code == 204

    assert client.get(f"/reservas/{creada['id']}", headers=ana).status_code == 404
    assert client.delete(f"/reservas/{creada['id']}", headers=ana).status_code == 404


def test_inexistente_da_404_y_ajena_da_403_sin_confundirse(client, ana):
    luis = registrar_y_autenticar(client, "luis@example.com")
    de_ana = crear_reserva_rest(client, ana, "09:00", "10:00").json()["id"]

    operaciones = [
        lambda i: client.get(f"/reservas/{i}", headers=luis),
        lambda i: client.put(f"/reservas/{i}", json=CUERPO, headers=luis),
        lambda i: client.delete(f"/reservas/{i}", headers=luis),
    ]

    for operacion in operaciones:
        assert operacion(ID_INEXISTENTE).status_code == 404
        assert operacion(de_ana).status_code == 403


def test_el_404_del_put_no_depende_de_que_el_horario_sea_valido(client, ana):
    # La existencia se comprueba antes que las reglas de horario (orden 404 → 403 → RN-2...).
    invertido = {"fecha": fecha_futura(), "hora_inicio": "12:00", "hora_fin": "11:00"}

    respuesta = client.put(f"/reservas/{ID_INEXISTENTE}", json=invertido, headers=ana)

    assert respuesta.status_code == 404


def test_un_id_no_numerico_responde_422(client, ana):
    assert client.get("/reservas/abc", headers=ana).status_code == 422
