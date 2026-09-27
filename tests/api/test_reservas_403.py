"""Caso 403 obligatorio de la spec (T046, RN-3): solo el dueño accede a su reserva.

El usuario B, con un token válido, no puede leer, modificar ni eliminar la reserva de A; la
reserva de A sigue intacta y el cuerpo del 403 no revela ningún dato de ella (SC-002).
"""

import pytest

from tests.conftest import crear_reserva_rest, fecha_futura, registrar_y_autenticar

FECHA = fecha_futura()
CUERPO_B = {"fecha": FECHA, "hora_inicio": "15:00", "hora_fin": "16:00"}


@pytest.fixture
def escenario(client):
    """Ana crea una reserva 09:00-10:00; Luis está autenticado y no tiene ninguna."""
    ana = registrar_y_autenticar(client, "ana@example.com")
    luis = registrar_y_autenticar(client, "luis@example.com")
    creada = crear_reserva_rest(client, ana, "09:00", "10:00")
    assert creada.status_code == 201
    return {"ana": ana, "luis": luis, "reserva": creada.json()}


def _intacta(client, escenario):
    """La reserva de Ana sigue igual, comprobado con el token de Ana."""
    respuesta = client.get(f"/reservas/{escenario['reserva']['id']}", headers=escenario["ana"])
    assert respuesta.status_code == 200
    assert respuesta.json() == escenario["reserva"]


def _no_revela_datos(respuesta, reserva):
    assert respuesta.json() == {"detail": "No tienes permiso sobre esta reserva"}
    for dato in (reserva["fecha"], "09:00", "10:00"):
        assert dato not in respuesta.text


def test_get_de_una_reserva_ajena_responde_403(client, escenario):
    reserva = escenario["reserva"]

    respuesta = client.get(f"/reservas/{reserva['id']}", headers=escenario["luis"])

    assert respuesta.status_code == 403
    _no_revela_datos(respuesta, reserva)
    _intacta(client, escenario)


def test_put_de_una_reserva_ajena_responde_403_y_no_la_modifica(client, escenario):
    reserva = escenario["reserva"]

    respuesta = client.put(
        f"/reservas/{reserva['id']}", json=CUERPO_B, headers=escenario["luis"]
    )

    assert respuesta.status_code == 403
    _no_revela_datos(respuesta, reserva)
    _intacta(client, escenario)


def test_delete_de_una_reserva_ajena_responde_403_y_no_la_elimina(client, escenario):
    reserva = escenario["reserva"]

    respuesta = client.delete(f"/reservas/{reserva['id']}", headers=escenario["luis"])

    assert respuesta.status_code == 403
    _no_revela_datos(respuesta, reserva)
    _intacta(client, escenario)


def test_el_403_del_put_no_depende_de_que_el_nuevo_horario_sea_valido(client, escenario):
    # La propiedad se comprueba antes que las reglas de horario: un ajeno recibe 403 aunque su
    # cuerpo solape o sea inválido, sin filtrar información sobre la reserva de Ana.
    reserva = escenario["reserva"]
    solapa_con_la_de_ana = {"fecha": FECHA, "hora_inicio": "09:30", "hora_fin": "10:30"}
    horas_invertidas = {"fecha": FECHA, "hora_inicio": "12:00", "hora_fin": "11:00"}

    for cuerpo in (solapa_con_la_de_ana, horas_invertidas):
        respuesta = client.put(
            f"/reservas/{reserva['id']}", json=cuerpo, headers=escenario["luis"]
        )
        assert respuesta.status_code == 403
    _intacta(client, escenario)


def test_el_listado_de_luis_no_incluye_la_reserva_de_ana(client, escenario):
    assert client.get("/reservas/", headers=escenario["luis"]).json() == []
    assert client.get("/reservas/", headers=escenario["ana"]).json() == [escenario["reserva"]]


def test_el_dueno_si_puede_leer_modificar_y_eliminar_su_reserva(client, escenario):
    # Control: el 403 anterior se debe a la propiedad y no a otra causa.
    reserva_id = escenario["reserva"]["id"]
    ana = escenario["ana"]

    assert client.get(f"/reservas/{reserva_id}", headers=ana).status_code == 200
    assert client.put(f"/reservas/{reserva_id}", json=CUERPO_B, headers=ana).status_code == 200
    assert client.delete(f"/reservas/{reserva_id}", headers=ana).status_code == 204
