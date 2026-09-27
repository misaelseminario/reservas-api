"""Conversión de fechas y horas entre texto y objetos de Python.

Es solo conversión de formato, NO lógica de negocio (Art. I.2). Los usan los schemas de
reserva (REST) y los tools MCP, de modo que ambas vías aceptan exactamente el mismo formato:
fecha `YYYY-MM-DD` y hora `HH:MM`, con ceros y sin segundos.
"""

import re
from datetime import date, time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.reserva import Reserva

_PATRON_FECHA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_PATRON_HORA = re.compile(r"[0-9]{2}:[0-9]{2}")

_MENSAJE_FECHA = "Fecha inválida: use el formato YYYY-MM-DD"
_MENSAJE_HORA = "Hora inválida: use el formato HH:MM"


def parsear_fecha(texto: str) -> date:
    """Convierte `YYYY-MM-DD` en `date`. Lanza `ValueError` si el formato no es válido."""
    if not isinstance(texto, str) or not _PATRON_FECHA.fullmatch(texto):
        raise ValueError(_MENSAJE_FECHA)
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise ValueError(_MENSAJE_FECHA) from None


def parsear_hora(texto: str) -> time:
    """Convierte `HH:MM` en `time`. Lanza `ValueError` si el formato no es válido.

    Formato estricto: se rechazan `09:00:30` (con segundos) y `9:00` (sin cero inicial).
    """
    if not isinstance(texto, str) or not _PATRON_HORA.fullmatch(texto):
        raise ValueError(_MENSAJE_HORA)
    try:
        return time(int(texto[:2]), int(texto[3:]))
    except ValueError:
        raise ValueError(_MENSAJE_HORA) from None


def reserva_a_dict(reserva: "Reserva") -> dict:
    """Representación de una reserva para los tools MCP (fecha `YYYY-MM-DD`, horas `HH:MM`)."""
    return {
        "id": reserva.id,
        "fecha": reserva.fecha.strftime("%Y-%m-%d"),
        "hora_inicio": reserva.hora_inicio.strftime("%H:%M"),
        "hora_fin": reserva.hora_fin.strftime("%H:%M"),
    }
