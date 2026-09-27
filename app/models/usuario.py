"""Modelo ORM `Usuario` (tabla `usuarios`)."""

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.reserva import Reserva


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Único e indexado (RN-5). Se guarda siempre en minúsculas: lo normaliza `services/auth.py`.
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    # Hash bcrypt (60 caracteres), nunca la contraseña en claro (Art. IV.2).
    password_hash: Mapped[str] = mapped_column(String(60), nullable=False)

    reservas: Mapped[list["Reserva"]] = relationship(back_populates="usuario")
