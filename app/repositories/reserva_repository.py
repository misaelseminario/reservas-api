"""Repository real de `Reserva` (SQLAlchemy 2). Solo persiste y consulta.

NO contiene reglas de negocio (Art. I.4): la fórmula de solapamiento (RN-1) vive en
`services/reservas.py`. Toda consulta de datos de `Reserva` filtra por `usuario_id` (Art. III.3),
salvo las dos excepciones que ese artículo permite y que se señalan abajo: `listar_por_fecha`
y `existe`.
"""

from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Reserva


class ReservaRepository:
    """Cumple `ReservaRepositoryProtocol`. Sin estado: la sesión llega por parámetro."""

    def crear(
        self, db: Session, usuario_id: int, fecha: date, hora_inicio: time, hora_fin: time
    ) -> Reserva:
        reserva = Reserva(
            usuario_id=usuario_id, fecha=fecha, hora_inicio=hora_inicio, hora_fin=hora_fin
        )
        db.add(reserva)
        db.commit()
        db.refresh(reserva)
        return reserva

    def listar_por_usuario(
        self, db: Session, usuario_id: int, skip: int, limit: int
    ) -> list[Reserva]:
        # Siempre filtrada por dueño. Orden estable: fecha, hora_inicio, id.
        consulta = (
            select(Reserva)
            .where(Reserva.usuario_id == usuario_id)
            .order_by(Reserva.fecha, Reserva.hora_inicio, Reserva.id)
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(consulta).scalars().all())

    def obtener_de_usuario(
        self, db: Session, reserva_id: int, usuario_id: int
    ) -> Reserva | None:
        # Siempre por id Y usuario_id: nunca se lee una reserva sin dueño (Art. III.3).
        consulta = select(Reserva).where(
            Reserva.id == reserva_id, Reserva.usuario_id == usuario_id
        )
        return db.execute(consulta).scalar_one_or_none()

    def existe(self, db: Session, reserva_id: int) -> bool:
        # Excepción (b) del Art. III.3: sin filtro por usuario_id, únicamente para distinguir
        # 404 de 403. Devuelve solo un booleano; NUNCA datos de la reserva.
        consulta = select(Reserva.id).where(Reserva.id == reserva_id)
        return db.execute(consulta).first() is not None

    def listar_por_fecha(self, db: Session, fecha: date) -> list[Reserva]:
        # Excepción (a) del Art. III.3: todas las reservas de esa fecha, de cualquier usuario,
        # sin filtro por usuario_id. El servicio aplica la fórmula de solapamiento (RN-1).
        consulta = (
            select(Reserva)
            .where(Reserva.fecha == fecha)
            .order_by(Reserva.hora_inicio, Reserva.id)
        )
        return list(db.execute(consulta).scalars().all())

    def actualizar(
        self, db: Session, reserva: Reserva, fecha: date, hora_inicio: time, hora_fin: time
    ) -> Reserva:
        reserva.fecha = fecha
        reserva.hora_inicio = hora_inicio
        reserva.hora_fin = hora_fin
        db.commit()
        db.refresh(reserva)
        return reserva

    def eliminar(self, db: Session, reserva: Reserva) -> None:
        db.delete(reserva)
        db.commit()


# Instancia de módulo: valor por defecto del parámetro `repo` de los servicios (Art. II.1).
reserva_repository = ReservaRepository()
