"""Tests unitarios de `app/utils/fechas.py`. Sin dobles de prueba de terceros y sin base de datos."""

from datetime import date, time

import pytest

from app.models import Reserva
from app.utils.fechas import parsear_fecha, parsear_hora, reserva_a_dict


def test_parsear_fecha_valida():
    assert parsear_fecha("2030-01-15") == date(2030, 1, 15)


def test_parsear_hora_valida():
    assert parsear_hora("09:00") == time(9, 0)
    assert parsear_hora("23:59") == time(23, 59)
    assert parsear_hora("00:00") == time(0, 0)


@pytest.mark.parametrize(
    "texto",
    ["15/01/2030", "2030-13-01", "2030-02-30", "2030-1-5", "2030-01-15T10:00:00", ""],
)
def test_parsear_fecha_invalida_lanza_value_error(texto):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parsear_fecha(texto)


@pytest.mark.parametrize("texto", ["9:00 AM", "25:00", "09:00:30", "9:00", "09:60", ""])
def test_parsear_hora_invalida_lanza_value_error(texto):
    with pytest.raises(ValueError, match="HH:MM"):
        parsear_hora(texto)


def test_los_parsers_rechazan_valores_que_no_son_texto():
    with pytest.raises(ValueError):
        parsear_fecha(None)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        parsear_hora(900)  # type: ignore[arg-type]


def test_reserva_a_dict_devuelve_horas_hh_mm():
    # Reserva en memoria: no se abre ninguna sesión de BD.
    reserva = Reserva(
        id=7,
        usuario_id=1,
        fecha=date(2030, 1, 5),
        hora_inicio=time(9, 0, 0),
        hora_fin=time(10, 30, 45),
    )
    assert reserva_a_dict(reserva) == {
        "id": 7,
        "fecha": "2030-01-05",
        "hora_inicio": "09:00",
        "hora_fin": "10:30",
    }
