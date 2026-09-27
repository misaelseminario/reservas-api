"""Servicios de reservas: TODAS las reglas de negocio de `Reserva` (Art. I.3).

Cada función recibe la sesión `db` y el repository por parámetro, con el real como valor por
defecto (DIP, Art. II.1). No conoce HTTP ni MCP: lanza excepciones de dominio y los routers y
tools las traducen. Este mismo módulo lo usan REST y MCP (Art. VI.1).
"""

from datetime import date, datetime, time

from sqlalchemy.orm import Session

from app.models import Reserva
from app.repositories.base import ReservaRepositoryProtocol
from app.repositories.reserva_repository import reserva_repository
from app.services.excepciones import (
    ConfirmacionRequeridaError,
    FechaPasadaError,
    HorarioInvalidoError,
    NoEsDuenoError,
    ReservaNoEncontradaError,
    ReservaSolapadaError,
)

# Límites de paginación: única definición. Los importan el router y el tool MCP de listar.
SKIP_MINIMO = 0
LIMITE_MINIMO = 1
LIMITE_MAXIMO = 100
LIMITE_POR_DEFECTO = 100


def _se_solapan(inicio_a: time, fin_a: time, inicio_b: time, fin_b: time) -> bool:
    """RN-1: dos rangos se solapan si `inicio_a < fin_b` Y `fin_a > inicio_b`.

    Las comparaciones son estrictas: dos reservas contiguas (una termina cuando empieza la
    otra) NO se solapan.
    """
    return inicio_a < fin_b and fin_a > inicio_b


def _validar_horario(
    fecha: date, hora_inicio: time, hora_fin: time, ahora: datetime | None
) -> None:
    """RN-2 (fin posterior a inicio) y RN-7 (no empezar en el pasado), en ese orden."""
    if hora_fin <= hora_inicio:
        raise HorarioInvalidoError()

    if ahora is None:
        ahora = datetime.now()
    if datetime.combine(fecha, hora_inicio) < ahora:
        raise FechaPasadaError()


def _validar_sin_solapamiento(
    db: Session,
    repo: ReservaRepositoryProtocol,
    fecha: date,
    hora_inicio: time,
    hora_fin: time,
    excluir_id: int | None = None,
) -> None:
    """RN-1: la sala no puede estar ya reservada en ese rango, por ningún usuario.

    `excluir_id` descarta una reserva de la comparación (RN-4: al modificar, la reserva no se
    solapa consigo misma). Compara contra las reservas de TODOS los usuarios (excepción (a) del
    Art. III.3).
    """
    for existente in repo.listar_por_fecha(db, fecha):
        if existente.id == excluir_id:
            continue
        if _se_solapan(hora_inicio, hora_fin, existente.hora_inicio, existente.hora_fin):
            raise ReservaSolapadaError()


def crear_reserva(
    db: Session,
    usuario_id: int,
    fecha: date,
    hora_inicio: time,
    hora_fin: time,
    *,
    ahora: datetime | None = None,
    repo: ReservaRepositoryProtocol = reserva_repository,
) -> Reserva:
    """Crea una reserva para `usuario_id` (RN-1, RN-2, RN-7).

    `ahora` es inyectable para que los tests no dependan del reloj; por defecto, la hora local
    del servidor. Orden de validación fijo: RN-2, RN-7, RN-1.
    """
    _validar_horario(fecha, hora_inicio, hora_fin, ahora)
    _validar_sin_solapamiento(db, repo, fecha, hora_inicio, hora_fin)
    return repo.crear(db, usuario_id, fecha, hora_inicio, hora_fin)


def listar_reservas(
    db: Session,
    usuario_id: int,
    skip: int = SKIP_MINIMO,
    limit: int = LIMITE_POR_DEFECTO,
    *,
    repo: ReservaRepositoryProtocol = reserva_repository,
) -> list[Reserva]:
    """Reservas del propio usuario, ordenadas por fecha y hora (FR-011). Nunca las ajenas.

    Los límites de `skip`/`limit` los valida la capa de entrada con las constantes de arriba.
    """
    return repo.listar_por_usuario(db, usuario_id, skip, limit)


def obtener_reserva(
    db: Session,
    usuario_id: int,
    reserva_id: int,
    *,
    repo: ReservaRepositoryProtocol = reserva_repository,
) -> Reserva:
    """RN-3: solo el dueño ve su reserva. Inexistente → 404; existe pero es ajena → 403."""
    if not repo.existe(db, reserva_id):
        raise ReservaNoEncontradaError()
    reserva = repo.obtener_de_usuario(db, reserva_id, usuario_id)
    if reserva is None:
        raise NoEsDuenoError()
    return reserva


def actualizar_reserva(
    db: Session,
    usuario_id: int,
    reserva_id: int,
    fecha: date,
    hora_inicio: time,
    hora_fin: time,
    *,
    ahora: datetime | None = None,
    repo: ReservaRepositoryProtocol = reserva_repository,
) -> Reserva:
    """Modifica una reserva propia y re-aplica RN-1, RN-2 y RN-7 (RN-4, con RN-3).

    Orden: existencia (404) → propiedad (403) → RN-2 → RN-7 → RN-1. La reserva no se cuenta a
    sí misma al buscar solapamientos.
    """
    reserva = obtener_reserva(db, usuario_id, reserva_id, repo=repo)
    _validar_horario(fecha, hora_inicio, hora_fin, ahora)
    _validar_sin_solapamiento(db, repo, fecha, hora_inicio, hora_fin, excluir_id=reserva_id)
    return repo.actualizar(db, reserva, fecha, hora_inicio, hora_fin)


def eliminar_reserva(
    db: Session,
    usuario_id: int,
    reserva_id: int,
    *,
    confirmar: bool,
    repo: ReservaRepositoryProtocol = reserva_repository,
) -> None:
    """Cancela una reserva propia (RN-6, con RN-3). Única función de borrado, para REST y MCP.

    `confirmar` es obligatorio y solo `True` autoriza el borrado: la confirmación la exige el
    servidor, no depende de que el cliente o el modelo pregunten (Art. VI.5). Sin ella se lanza
    `ConfirmacionRequeridaError` ANTES de tocar el repository. Orden: confirmación →
    existencia (404) → propiedad (403) → eliminar.
    """
    if confirmar is not True:
        raise ConfirmacionRequeridaError()
    reserva = obtener_reserva(db, usuario_id, reserva_id, repo=repo)
    repo.eliminar(db, reserva)
