"""Tests unitarios de `eliminar_reserva` (RN-6, con RN-3). Repository falso, sin BD."""

from datetime import date, time

import pytest

from app.services.excepciones import (
    ConfirmacionRequeridaError,
    NoEsDuenoError,
    ReservaNoEncontradaError,
)
from app.services.reservas import eliminar_reserva
from tests.unit.fakes import FakeReservaRepository

FECHA = date(2030, 1, 15)
ANA = 1
LUIS = 2


@pytest.fixture
def repo() -> FakeReservaRepository:
    return FakeReservaRepository()


# --- RN-6: cancelar exige confirmación, validada en el servidor --------------------------


def test_rn6_sin_confirmar_lanza_confirmacion_requerida_y_no_toca_el_repository(repo):
    propia = repo.sembrar(ANA, FECHA, time(9), time(10))

    with pytest.raises(
        ConfirmacionRequeridaError, match="Confirmación requerida: repite con confirmar=true"
    ):
        eliminar_reserva(None, ANA, propia.id, confirmar=False, repo=repo)

    assert repo.reservas == [propia]
    assert repo.llamadas == []  # ni `eliminar`, ni siquiera `existe`
    assert repo.eliminadas == []


@pytest.mark.parametrize("valor", [None, 0, 1, "true", "True"])
def test_rn6_solo_true_autoriza_el_borrado(repo, valor):
    propia = repo.sembrar(ANA, FECHA, time(9), time(10))

    with pytest.raises(ConfirmacionRequeridaError):
        eliminar_reserva(None, ANA, propia.id, confirmar=valor, repo=repo)

    assert repo.reservas == [propia]
    assert repo.llamadas == []


def test_rn6_confirmar_es_un_argumento_obligatorio(repo):
    propia = repo.sembrar(ANA, FECHA, time(9), time(10))

    with pytest.raises(TypeError):
        eliminar_reserva(None, ANA, propia.id, repo=repo)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        eliminar_reserva(None, ANA, propia.id, True, repo=repo)  # type: ignore[misc]

    assert repo.reservas == [propia]


def test_rn6_confirmando_una_reserva_propia_se_elimina(repo):
    propia = repo.sembrar(ANA, FECHA, time(9), time(10))
    otra = repo.sembrar(ANA, FECHA, time(11), time(12))

    resultado = eliminar_reserva(None, ANA, propia.id, confirmar=True, repo=repo)

    assert resultado is None
    assert repo.reservas == [otra]
    assert repo.eliminadas == [propia.id]


# --- RN-3: solo el dueño; inexistente ≠ ajena --------------------------------------------


def test_rn3_eliminar_una_reserva_ajena_lanza_no_es_dueno_y_no_se_elimina(repo):
    ajena = repo.sembrar(LUIS, FECHA, time(9), time(10))

    with pytest.raises(NoEsDuenoError):
        eliminar_reserva(None, ANA, ajena.id, confirmar=True, repo=repo)

    assert repo.reservas == [ajena]
    assert repo.eliminadas == []


def test_rn3_eliminar_un_id_inexistente_lanza_reserva_no_encontrada(repo):
    existente = repo.sembrar(ANA, FECHA, time(9), time(10))

    with pytest.raises(ReservaNoEncontradaError):
        eliminar_reserva(None, ANA, 999, confirmar=True, repo=repo)

    assert repo.reservas == [existente]
    assert repo.eliminadas == []


def test_sin_confirmar_sobre_una_reserva_ajena_sigue_pidiendo_confirmacion(repo):
    # La confirmación se exige primero: no se revela ni se toca nada de la reserva ajena.
    ajena = repo.sembrar(LUIS, FECHA, time(9), time(10))

    with pytest.raises(ConfirmacionRequeridaError):
        eliminar_reserva(None, ANA, ajena.id, confirmar=False, repo=repo)

    assert repo.reservas == [ajena]
    assert repo.llamadas == []


def test_sin_confirmar_sobre_un_id_inexistente_tambien_pide_confirmacion(repo):
    with pytest.raises(ConfirmacionRequeridaError):
        eliminar_reserva(None, ANA, 999, confirmar=False, repo=repo)

    assert repo.llamadas == []
