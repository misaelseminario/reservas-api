"""Tests unitarios de `actualizar_reserva` (RN-4, con RN-3, RN-1, RN-2 y RN-7).

Repository falso en memoria y `ahora` fijo: sin BD, sin reloj real y sin dobles de terceros.
"""

from datetime import date, datetime, time

import pytest

from app.services.excepciones import (
    FechaPasadaError,
    HorarioInvalidoError,
    NoEsDuenoError,
    ReservaNoEncontradaError,
    ReservaSolapadaError,
)
from app.services.reservas import actualizar_reserva
from tests.unit.fakes import FakeReservaRepository

AHORA = datetime(2030, 1, 10, 12, 0)
FECHA = date(2030, 1, 15)
ANA = 1
LUIS = 2


@pytest.fixture
def repo() -> FakeReservaRepository:
    return FakeReservaRepository()


def _actualizar(repo, reserva_id, inicio, fin, *, fecha=FECHA, usuario_id=ANA):
    return actualizar_reserva(
        None, usuario_id, reserva_id, fecha, inicio, fin, ahora=AHORA, repo=repo
    )


# --- RN-4: modificar re-aplica las reglas sin contarse a sí misma ------------------------


def test_rn4_ampliar_la_propia_reserva_se_acepta_aunque_solape_consigo_misma(repo):
    propia = repo.sembrar(ANA, FECHA, time(10), time(11))

    actualizada = _actualizar(repo, propia.id, time(10), time(12))

    assert actualizada is propia
    assert (propia.hora_inicio, propia.hora_fin) == (time(10), time(12))


def test_rn4_modificar_sin_cambios_se_acepta(repo):
    propia = repo.sembrar(ANA, FECHA, time(10), time(11))

    _actualizar(repo, propia.id, time(10), time(11))

    assert (propia.fecha, propia.hora_inicio, propia.hora_fin) == (FECHA, time(10), time(11))


def test_rn4_mover_a_un_horario_que_solapa_con_otra_reserva_lanza_solapada(repo):
    propia = repo.sembrar(ANA, FECHA, time(9), time(10))
    repo.sembrar(LUIS, FECHA, time(11), time(12))

    with pytest.raises(ReservaSolapadaError):
        _actualizar(repo, propia.id, time(11, 30), time(12, 30))

    assert (propia.hora_inicio, propia.hora_fin) == (time(9), time(10))
    assert "actualizar" not in repo.llamadas


def test_rn4_solapar_con_otra_reserva_del_mismo_usuario_tambien_es_error(repo):
    # Solo se excluye la reserva que se modifica, no las demás del mismo dueño.
    propia = repo.sembrar(ANA, FECHA, time(9), time(10))
    repo.sembrar(ANA, FECHA, time(11), time(12))

    with pytest.raises(ReservaSolapadaError):
        _actualizar(repo, propia.id, time(11), time(13))


def test_rn4_mover_a_un_horario_contiguo_a_otra_reserva_se_acepta(repo):
    propia = repo.sembrar(ANA, FECHA, time(9), time(10))
    repo.sembrar(LUIS, FECHA, time(11), time(12))

    _actualizar(repo, propia.id, time(10), time(11))
    assert (propia.hora_inicio, propia.hora_fin) == (time(10), time(11))

    _actualizar(repo, propia.id, time(12), time(13))
    assert (propia.hora_inicio, propia.hora_fin) == (time(12), time(13))


def test_rn4_mover_a_otra_fecha_compara_contra_esa_fecha(repo):
    propia = repo.sembrar(ANA, FECHA, time(9), time(10))
    otra_fecha = date(2030, 1, 16)
    repo.sembrar(LUIS, otra_fecha, time(9), time(10))

    with pytest.raises(ReservaSolapadaError):
        _actualizar(repo, propia.id, time(9), time(10), fecha=otra_fecha)

    _actualizar(repo, propia.id, time(10), time(11), fecha=otra_fecha)
    assert (propia.fecha, propia.hora_inicio) == (otra_fecha, time(10))


# --- RN-2 y RN-7 se vuelven a aplicar al modificar ---------------------------------------


@pytest.mark.parametrize(
    ("inicio", "fin"), [(time(10), time(10)), (time(11), time(10)), (time(23), time(1))]
)
def test_rn2_al_modificar_fin_no_posterior_lanza_horario_invalido(repo, inicio, fin):
    propia = repo.sembrar(ANA, FECHA, time(9), time(10))

    with pytest.raises(HorarioInvalidoError):
        _actualizar(repo, propia.id, inicio, fin)

    assert (propia.hora_inicio, propia.hora_fin) == (time(9), time(10))


def test_rn7_al_modificar_un_inicio_pasado_lanza_fecha_pasada(repo):
    propia = repo.sembrar(ANA, FECHA, time(9), time(10))

    with pytest.raises(FechaPasadaError):
        _actualizar(repo, propia.id, time(9), time(10), fecha=date(2030, 1, 9))

    assert propia.fecha == FECHA


def test_rn7_al_modificar_empezar_exactamente_ahora_se_acepta(repo):
    propia = repo.sembrar(ANA, FECHA, time(9), time(10))

    _actualizar(repo, propia.id, time(12, 0), time(13), fecha=date(2030, 1, 10))

    assert (propia.fecha, propia.hora_inicio) == (date(2030, 1, 10), time(12, 0))


# --- RN-3: solo el dueño; inexistente ≠ ajena --------------------------------------------


def test_rn3_modificar_una_reserva_ajena_lanza_no_es_dueno_y_no_cambia(repo):
    ajena = repo.sembrar(LUIS, FECHA, time(9), time(10))

    with pytest.raises(NoEsDuenoError):
        _actualizar(repo, ajena.id, time(14), time(15), usuario_id=ANA)

    assert (ajena.fecha, ajena.hora_inicio, ajena.hora_fin) == (FECHA, time(9), time(10))
    assert "actualizar" not in repo.llamadas


def test_rn3_modificar_un_id_inexistente_lanza_reserva_no_encontrada(repo):
    repo.sembrar(ANA, FECHA, time(9), time(10))

    with pytest.raises(ReservaNoEncontradaError):
        _actualizar(repo, 999, time(14), time(15))

    assert "actualizar" not in repo.llamadas


def test_orden_existencia_y_propiedad_van_antes_que_las_reglas_de_horario(repo):
    # Con un rango inválido, una reserva ajena o inexistente sigue dando 403/404 (research R8).
    ajena = repo.sembrar(LUIS, FECHA, time(9), time(10))

    with pytest.raises(NoEsDuenoError):
        _actualizar(repo, ajena.id, time(11), time(10))
    with pytest.raises(ReservaNoEncontradaError):
        _actualizar(repo, 999, time(11), time(10))
