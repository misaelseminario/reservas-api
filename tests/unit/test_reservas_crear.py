"""Tests unitarios de `crear_reserva` (RN-1, RN-2, RN-7 y reservas contiguas).

Repository falso en memoria y `ahora` fijo: sin BD, sin reloj real y sin dobles de terceros.
"""

from datetime import date, datetime, time

import pytest

from app.services.excepciones import (
    FechaPasadaError,
    HorarioInvalidoError,
    ReservaSolapadaError,
)
from app.services.reservas import crear_reserva
from tests.unit.fakes import FakeReservaRepository

AHORA = datetime(2030, 1, 10, 12, 0)
HOY = date(2030, 1, 10)
FECHA = date(2030, 1, 15)
ANA = 1
LUIS = 2


@pytest.fixture
def repo() -> FakeReservaRepository:
    return FakeReservaRepository()


def _crear(repo, inicio, fin, *, fecha=FECHA, usuario_id=ANA, ahora=AHORA):
    return crear_reserva(None, usuario_id, fecha, inicio, fin, ahora=ahora, repo=repo)


# --- caso feliz --------------------------------------------------------------------------


def test_crear_reserva_valida_la_guarda_a_nombre_del_usuario(repo):
    reserva = _crear(repo, time(9), time(10))

    assert reserva.usuario_id == ANA
    assert (reserva.fecha, reserva.hora_inicio, reserva.hora_fin) == (FECHA, time(9), time(10))
    assert repo.reservas == [reserva]


# --- RN-1: sin solapamiento (contra reservas de cualquier usuario) -----------------------


@pytest.mark.parametrize(
    ("inicio", "fin"),
    [
        (time(10), time(12)),  # idéntica
        (time(10, 30), time(11, 30)),  # contenida
        (time(9), time(13)),  # que contiene
        (time(9), time(10, 30)),  # parcial, por el principio
        (time(11), time(13)),  # parcial, por el final
        (time(10), time(11)),  # comparte el inicio
        (time(11), time(12)),  # comparte el final
    ],
)
def test_rn1_una_reserva_que_solapa_lanza_reserva_solapada(repo, inicio, fin):
    repo.sembrar(ANA, FECHA, time(10), time(12))

    with pytest.raises(ReservaSolapadaError, match="La sala ya está reservada en ese horario"):
        _crear(repo, inicio, fin)

    assert len(repo.reservas) == 1


def test_rn1_solapar_con_la_reserva_de_otro_usuario_tambien_es_error(repo):
    repo.sembrar(LUIS, FECHA, time(10), time(12))

    with pytest.raises(ReservaSolapadaError):
        _crear(repo, time(11), time(13), usuario_id=ANA)

    assert len(repo.reservas) == 1


def test_rn1_la_misma_hora_en_otra_fecha_se_acepta(repo):
    repo.sembrar(ANA, FECHA, time(10), time(12))

    reserva = _crear(repo, time(10), time(12), fecha=date(2030, 1, 16))

    assert reserva.fecha == date(2030, 1, 16)
    assert len(repo.reservas) == 2


# --- Reservas contiguas: una termina cuando empieza la otra (test propio) ----------------


def test_contiguas_la_nueva_empieza_cuando_termina_la_existente(repo):
    repo.sembrar(LUIS, FECHA, time(9), time(10))

    reserva = _crear(repo, time(10), time(11))

    assert (reserva.hora_inicio, reserva.hora_fin) == (time(10), time(11))
    assert len(repo.reservas) == 2


def test_contiguas_la_nueva_termina_cuando_empieza_la_existente(repo):
    repo.sembrar(LUIS, FECHA, time(10), time(11))

    reserva = _crear(repo, time(9), time(10))

    assert (reserva.hora_inicio, reserva.hora_fin) == (time(9), time(10))
    assert len(repo.reservas) == 2


# --- RN-2: la hora de fin es posterior a la de inicio ------------------------------------


@pytest.mark.parametrize(
    ("inicio", "fin"),
    [
        (time(10), time(10)),  # fin == inicio
        (time(11), time(10)),  # fin < inicio
        (time(23), time(1)),  # cruza medianoche
    ],
)
def test_rn2_hora_fin_no_posterior_lanza_horario_invalido(repo, inicio, fin):
    with pytest.raises(
        HorarioInvalidoError, match="La hora de fin debe ser posterior a la hora de inicio"
    ):
        _crear(repo, inicio, fin)

    assert repo.reservas == []


# --- RN-7: no se reserva en el pasado ----------------------------------------------------


def test_rn7_una_fecha_de_ayer_lanza_fecha_pasada(repo):
    with pytest.raises(FechaPasadaError, match="No se puede reservar en una fecha y hora pasadas"):
        _crear(repo, time(9), time(10), fecha=date(2030, 1, 9))

    assert repo.reservas == []


def test_rn7_hoy_con_inicio_anterior_a_ahora_lanza_fecha_pasada(repo):
    with pytest.raises(FechaPasadaError):
        _crear(repo, time(11, 59), time(13), fecha=HOY)

    assert repo.reservas == []


def test_rn7_empezar_exactamente_ahora_se_acepta(repo):
    reserva = _crear(repo, time(12, 0), time(13), fecha=HOY)

    assert reserva.hora_inicio == time(12, 0)


def test_rn7_hoy_con_inicio_posterior_a_ahora_se_acepta(repo):
    assert _crear(repo, time(12, 1), time(13), fecha=HOY).hora_inicio == time(12, 1)


def test_sin_ahora_usa_el_reloj_y_rechaza_una_fecha_muy_antigua(repo):
    # Único test que no inyecta `ahora`: comprueba que el valor por defecto es el reloj real.
    with pytest.raises(FechaPasadaError):
        crear_reserva(None, ANA, date(2000, 1, 1), time(9), time(10), repo=repo)


# --- Orden de validación (research R8): RN-2 → RN-7 → RN-1 -------------------------------


def test_orden_rn2_va_antes_que_rn7(repo):
    # Rango inválido Y en el pasado: gana RN-2.
    with pytest.raises(HorarioInvalidoError):
        _crear(repo, time(10), time(9), fecha=date(2030, 1, 9))


def test_orden_rn7_va_antes_que_rn1(repo):
    # En el pasado Y solapada con una existente: gana RN-7.
    repo.sembrar(LUIS, date(2030, 1, 9), time(10), time(12))

    with pytest.raises(FechaPasadaError):
        _crear(repo, time(11), time(13), fecha=date(2030, 1, 9))


def test_rn2_y_rn7_no_consultan_el_repository(repo):
    with pytest.raises(HorarioInvalidoError):
        _crear(repo, time(10), time(10))
    with pytest.raises(FechaPasadaError):
        _crear(repo, time(9), time(10), fecha=date(2030, 1, 9))

    assert repo.llamadas == []


# --- Sin límites de duración (spec) ------------------------------------------------------


def test_una_reserva_de_un_minuto_se_acepta(repo):
    assert _crear(repo, time(9, 0), time(9, 1)).hora_fin == time(9, 1)


def test_una_reserva_de_todo_el_dia_se_acepta(repo):
    reserva = _crear(repo, time(0, 0), time(23, 59))

    assert (reserva.hora_inicio, reserva.hora_fin) == (time(0, 0), time(23, 59))
