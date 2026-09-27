"""Tests unitarios de `listar_reservas` y `obtener_reserva` (RN-3). Repository falso, sin BD."""

from datetime import date, time, timedelta

import pytest

from app.services.excepciones import NoEsDuenoError, ReservaNoEncontradaError
from app.services.reservas import (
    LIMITE_MAXIMO,
    LIMITE_MINIMO,
    LIMITE_POR_DEFECTO,
    SKIP_MINIMO,
    listar_reservas,
    obtener_reserva,
)
from tests.unit.fakes import FakeReservaRepository

ANA = 1
LUIS = 2
DIA = date(2030, 1, 15)


@pytest.fixture
def repo() -> FakeReservaRepository:
    return FakeReservaRepository()


# --- constantes de paginación ------------------------------------------------------------


def test_constantes_de_paginacion():
    assert (SKIP_MINIMO, LIMITE_MINIMO, LIMITE_MAXIMO, LIMITE_POR_DEFECTO) == (0, 1, 100, 100)


# --- listar ------------------------------------------------------------------------------


def test_listar_devuelve_solo_las_reservas_del_usuario_aunque_haya_ajenas(repo):
    propia_1 = repo.sembrar(ANA, DIA, time(9), time(10))
    repo.sembrar(LUIS, DIA, time(10), time(11))
    propia_2 = repo.sembrar(ANA, DIA, time(11), time(12))
    repo.sembrar(LUIS, date(2030, 1, 16), time(9), time(10))

    assert listar_reservas(None, ANA, repo=repo) == [propia_1, propia_2]


def test_listar_ordena_por_fecha_y_hora(repo):
    tarde = repo.sembrar(ANA, DIA, time(15), time(16))
    manana = repo.sembrar(ANA, DIA, time(9), time(10))
    dia_anterior = repo.sembrar(ANA, date(2030, 1, 14), time(20), time(21))

    assert listar_reservas(None, ANA, repo=repo) == [dia_anterior, manana, tarde]


def test_listar_de_un_usuario_sin_reservas_devuelve_lista_vacia(repo):
    repo.sembrar(LUIS, DIA, time(9), time(10))

    assert listar_reservas(None, ANA, repo=repo) == []


def test_listar_respeta_skip_y_limit(repo):
    reservas = [repo.sembrar(ANA, DIA, time(h), time(h + 1)) for h in range(8, 13)]

    assert listar_reservas(None, ANA, 0, 2, repo=repo) == reservas[0:2]
    assert listar_reservas(None, ANA, 2, 2, repo=repo) == reservas[2:4]
    assert listar_reservas(None, ANA, 4, 2, repo=repo) == reservas[4:5]


def test_listar_con_skip_mayor_que_el_total_devuelve_lista_vacia(repo):
    repo.sembrar(ANA, DIA, time(9), time(10))

    assert listar_reservas(None, ANA, 50, 10, repo=repo) == []


def test_listar_por_defecto_usa_skip_cero_y_limite_por_defecto(repo):
    for dias in range(LIMITE_POR_DEFECTO + 5):
        repo.sembrar(ANA, date(2031, 1, 1) + timedelta(days=dias), time(9), time(10))

    assert len(listar_reservas(None, ANA, repo=repo)) == LIMITE_POR_DEFECTO


# --- obtener (RN-3) ----------------------------------------------------------------------


def test_obtener_una_reserva_propia_la_devuelve(repo):
    propia = repo.sembrar(ANA, DIA, time(9), time(10))

    assert obtener_reserva(None, ANA, propia.id, repo=repo) is propia


def test_rn3_obtener_una_reserva_ajena_lanza_no_es_dueno(repo):
    ajena = repo.sembrar(LUIS, DIA, time(9), time(10))

    with pytest.raises(NoEsDuenoError, match="No tienes permiso sobre esta reserva"):
        obtener_reserva(None, ANA, ajena.id, repo=repo)


def test_rn3_obtener_un_id_inexistente_lanza_reserva_no_encontrada(repo):
    repo.sembrar(ANA, DIA, time(9), time(10))

    with pytest.raises(ReservaNoEncontradaError, match="Reserva no encontrada"):
        obtener_reserva(None, ANA, 999, repo=repo)


def test_rn3_inexistente_y_ajena_son_errores_distintos(repo):
    # 404 y 403 no se confunden: NoEsDuenoError no es un caso de ReservaNoEncontradaError.
    ajena = repo.sembrar(LUIS, DIA, time(9), time(10))

    with pytest.raises(NoEsDuenoError) as ajena_exc:
        obtener_reserva(None, ANA, ajena.id, repo=repo)
    with pytest.raises(ReservaNoEncontradaError) as inexistente_exc:
        obtener_reserva(None, ANA, 999, repo=repo)

    assert not isinstance(ajena_exc.value, ReservaNoEncontradaError)
    assert not isinstance(inexistente_exc.value, NoEsDuenoError)


def test_rn3_el_error_de_reserva_ajena_no_revela_datos_del_otro_usuario(repo):
    ajena = repo.sembrar(LUIS, DIA, time(9), time(10))

    with pytest.raises(NoEsDuenoError) as exc:
        obtener_reserva(None, ANA, ajena.id, repo=repo)

    mensaje = str(exc.value)
    assert str(LUIS) not in mensaje and "2030" not in mensaje and "09:00" not in mensaje
