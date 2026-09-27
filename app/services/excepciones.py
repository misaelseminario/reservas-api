"""Excepciones de dominio: una por cada regla de negocio (Art. II.2).

`str(exc)` es el mensaje visible, en español. Es la única fuente de mensajes: los routers y
los tools MCP lo usan tal cual (FR-025). Los mensajes nunca incluyen contraseñas ni datos de
otros usuarios. Este módulo no importa nada de otras capas.
"""


class ErrorDeDominio(Exception):
    """Base de todas las excepciones de dominio; `str(exc)` es el mensaje para el usuario."""

    mensaje_por_defecto = "Error de dominio"

    def __init__(self, mensaje: str | None = None) -> None:
        super().__init__(mensaje or self.mensaje_por_defecto)


class ReservaSolapadaError(ErrorDeDominio):
    """RN-1: la sala ya está reservada en ese horario."""

    mensaje_por_defecto = "La sala ya está reservada en ese horario"


class HorarioInvalidoError(ErrorDeDominio):
    """RN-2: la hora de fin debe ser posterior a la de inicio (sin cruzar medianoche)."""

    mensaje_por_defecto = "La hora de fin debe ser posterior a la hora de inicio"


class NoEsDuenoError(ErrorDeDominio):
    """RN-3: la reserva existe pero pertenece a otro usuario."""

    mensaje_por_defecto = "No tienes permiso sobre esta reserva"


class ReservaNoEncontradaError(ErrorDeDominio):
    """RN-3 / FR-015: la reserva no existe."""

    mensaje_por_defecto = "Reserva no encontrada"


class EmailYaRegistradoError(ErrorDeDominio):
    """RN-5: ya existe un usuario con ese email."""

    mensaje_por_defecto = "El email ya está registrado"


class ConfirmacionRequeridaError(ErrorDeDominio):
    """RN-6: cancelar exige confirmación explícita (`confirmar=true`), validada en el servidor."""

    mensaje_por_defecto = "Confirmación requerida: repite con confirmar=true"


class FechaPasadaError(ErrorDeDominio):
    """RN-7: no se puede crear ni modificar una reserva que empieza en el pasado."""

    mensaje_por_defecto = "No se puede reservar en una fecha y hora pasadas"


class NoAutenticadoError(ErrorDeDominio):
    """Falta el token, es inválido o el usuario ya no existe. Admite un mensaje propio."""

    mensaje_por_defecto = "No autenticado"
