"""Modelo ORM `Reserva` (tabla `reservas`).

Sin `sala_id` (hay una única sala). Las invariantes de negocio (`hora_fin > hora_inicio`,
sin solapamiento, inicio no pasado) las garantiza `services/`, no la BD: no se añade
ningún `CHECK` (Art. I.3). Sin borrado en cascada de usuarios.
"""

from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.usuario import Usuario


class Reserva(Base):
    __tablename__ = "reservas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # FK al dueño, indexada (Art. III.3).
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id"), nullable=False, index=True
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time] = mapped_column(Time, nullable=False)

    usuario: Mapped["Usuario"] = relationship(back_populates="reservas")
