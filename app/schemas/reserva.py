"""Schemas Pydantic de reserva, separados del modelo ORM (Art. III.2).

Solo validan FORMATO; ninguna regla de negocio (RN-1…RN-7) vive aquí (Art. I.3). Las fechas y
horas de entrada pasan por los mismos parsers estrictos que usan los tools MCP
(`app/utils/fechas.py`), de modo que REST y MCP aceptan exactamente el mismo formato:
fecha `YYYY-MM-DD` y hora `HH:MM`. Así `09:00:30`, `9:00` o `2030-01-15T10:00:00` se rechazan
con 422 (FR-025).
"""

from datetime import date, time

from pydantic import BaseModel, ConfigDict, field_validator

from app.utils.fechas import parsear_fecha, parsear_hora


class _ReservaEntrada(BaseModel):
    fecha: date
    hora_inicio: time
    hora_fin: time

    @field_validator("fecha", mode="before")
    @classmethod
    def _fecha_estricta(cls, valor):
        return parsear_fecha(valor) if isinstance(valor, str) else valor

    @field_validator("hora_inicio", "hora_fin", mode="before")
    @classmethod
    def _hora_estricta(cls, valor):
        return parsear_hora(valor) if isinstance(valor, str) else valor


class ReservaCrear(_ReservaEntrada):
    """Cuerpo de `POST /reservas/`: los tres campos son obligatorios."""


class ReservaActualizar(_ReservaEntrada):
    """Cuerpo de `PUT /reservas/{id}`: sustitución completa, los tres campos obligatorios."""


class ReservaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    fecha: date
    hora_inicio: time
    hora_fin: time
