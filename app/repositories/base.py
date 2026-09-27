"""Contratos (`Protocol`) de los repositories.

Los cumplen tanto los repositories reales (SQLAlchemy) como los falsos en memoria de los
tests unitarios, de modo que `services/` depende de la abstracción (DIP, Art. II.1).

La sesión de BD es siempre el primer parámetro (Art. I.4). Los repositories solo persisten y
consultan: NO validan reglas de negocio.
"""

from datetime import date, time
from typing import Protocol

from sqlalchemy.orm import Session

from app.models import Reserva, Usuario


class ReservaRepositoryProtocol(Protocol):
    def crear(
        self, db: Session, usuario_id: int, fecha: date, hora_inicio: time, hora_fin: time
    ) -> Reserva: ...

    def listar_por_usuario(
        self, db: Session, usuario_id: int, skip: int, limit: int
    ) -> list[Reserva]: ...

    def obtener_de_usuario(
        self, db: Session, reserva_id: int, usuario_id: int
    ) -> Reserva | None: ...

    def existe(self, db: Session, reserva_id: int) -> bool: ...

    def listar_por_fecha(self, db: Session, fecha: date) -> list[Reserva]: ...

    def actualizar(
        self, db: Session, reserva: Reserva, fecha: date, hora_inicio: time, hora_fin: time
    ) -> Reserva: ...

    def eliminar(self, db: Session, reserva: Reserva) -> None: ...


class UsuarioRepositoryProtocol(Protocol):
    def crear(self, db: Session, email: str, password_hash: str) -> Usuario: ...

    def obtener_por_email(self, db: Session, email: str) -> Usuario | None: ...

    def obtener_por_id(self, db: Session, usuario_id: int) -> Usuario | None: ...
