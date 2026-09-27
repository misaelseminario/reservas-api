"""Servidor MCP (FastMCP, transporte streamable HTTP) montado en la misma app FastAPI en `/mcp`.

Cada tool llama a la MISMA función de `services/` que su endpoint REST (Art. VI.1), resuelve el
usuario real con el JWT del header `Authorization: Bearer` (Art. VI.6, ver `autenticacion.py`) y
devuelve siempre un `dict`: los errores son `{"error": "..."}`, nunca excepciones (Art. VI.3).
No hay reglas de negocio aquí (Art. I.2): solo conversión de formato y traducción de errores.

Limitaciones documentadas:
- Argumentos que no cumplen el esquema del tool (p. ej. `reserva_id="abc"`, o sin `reserva_id`)
  los rechaza el propio SDK ANTES de ejecutar el tool, con un resultado `isError: true` y un
  texto «Error executing tool ...»; no llegan a este módulo, así que no ejecutan ninguna
  operación, pero no tienen la forma `{"error": ...}`.
- El SDK protege contra DNS-rebinding y solo admite `Host` =
`localhost:*`, `127.0.0.1:*` y `[::1]:*`; publicarlo bajo otro nombre exigiría configurar
`TransportSecuritySettings` (despliegue local, fuera de alcance).
"""

import logging
from collections.abc import Callable

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy.orm import Session

from app.core.database import abrir_sesion
from app.mcp.autenticacion import obtener_usuario_desde_contexto
from app.models import Usuario
from app.services import reservas as servicio
from app.services.excepciones import ErrorDeDominio
from app.services.reservas import (
    LIMITE_MAXIMO,
    LIMITE_MINIMO,
    LIMITE_POR_DEFECTO,
    SKIP_MINIMO,
)
from app.utils.fechas import parsear_fecha, parsear_hora, reserva_a_dict

logger = logging.getLogger(__name__)

MENSAJE_FORMATO_INVALIDO = "Formato de fecha u hora inválido: use YYYY-MM-DD y HH:MM"
MENSAJE_PAGINACION_INVALIDA = (
    f"Parámetros de paginación inválidos: skip >= {SKIP_MINIMO} "
    f"y {LIMITE_MINIMO} <= limit <= {LIMITE_MAXIMO}"
)
MENSAJE_ERROR_INTERNO = "Error interno del servidor"


def _ejecutar_como_usuario(ctx: Context, operacion: Callable[[Session, Usuario], dict]) -> dict:
    """Abre la sesión, resuelve el usuario del JWT y ejecuta `operacion(db, usuario)`.

    Si no hay usuario autenticado NO se ejecuta la operación y se responde
    `{"error": "No autenticado"}`. Toda excepción de dominio se convierte en `{"error": ...}` con
    el mismo mensaje que usa REST; un fallo inesperado se registra y se devuelve como error
    genérico, sin exponer detalles internos.
    """
    try:
        with abrir_sesion() as db:
            usuario = obtener_usuario_desde_contexto(ctx, db)
            return operacion(db, usuario)
    except ErrorDeDominio as exc:
        return {"error": str(exc)}
    except Exception:
        logger.exception("Fallo inesperado en un tool MCP")
        return {"error": MENSAJE_ERROR_INTERNO}


def crear_servidor_mcp() -> FastMCP:
    """Construye un servidor MCP nuevo con sus tools registrados.

    Es una fábrica porque `StreamableHTTPSessionManager.run()` solo puede ejecutarse una vez por
    instancia: cada aplicación (y cada test) necesita la suya (research R3.7).
    """
    mcp = FastMCP(
        "reservas",
        stateless_http=True,  # cada llamada lleva y valida su propio token
        json_response=True,
        streamable_http_path="/mcp",
    )

    @mcp.tool()
    def crear_reserva(ctx: Context, fecha: str, hora_inicio: str, hora_fin: str) -> dict:
        """Crea una reserva de la sala para el usuario autenticado.

        Parámetros: `fecha` en formato YYYY-MM-DD (p. ej. 2030-01-15); `hora_inicio` y
        `hora_fin` en formato HH:MM de 24 horas (p. ej. 09:00 y 10:00).

        Reglas: la hora de fin debe ser posterior a la de inicio dentro del mismo día (no se
        puede cruzar la medianoche); la fecha y hora de inicio no pueden ser anteriores al
        momento actual; no puede solaparse con ninguna reserva existente de cualquier usuario
        (las reservas contiguas, una que termina cuando empieza la otra, sí se permiten).

        Devuelve {"id", "fecha", "hora_inicio", "hora_fin"}. Errores posibles:
        {"error": "No autenticado"}, {"error": "Formato de fecha u hora inválido..."}, horario
        solapado, horas inválidas o fecha pasada.
        """

        def operacion(db: Session, usuario: Usuario) -> dict:
            try:
                dia = parsear_fecha(fecha)
                inicio = parsear_hora(hora_inicio)
                fin = parsear_hora(hora_fin)
            except ValueError:
                return {"error": MENSAJE_FORMATO_INVALIDO}
            return reserva_a_dict(servicio.crear_reserva(db, usuario.id, dia, inicio, fin))

        return _ejecutar_como_usuario(ctx, operacion)

    @mcp.tool()
    def listar_reservas(
        ctx: Context, skip: int = SKIP_MINIMO, limit: int = LIMITE_POR_DEFECTO
    ) -> dict:
        """Lista las reservas del usuario autenticado (solo las suyas), ordenadas por fecha y
        hora de inicio.

        Parámetros: `skip` (>= 0, reservas a saltar, por defecto 0) y `limit` (de 1 a 100,
        máximo de reservas a devolver, por defecto 100).

        Devuelve {"reservas": [{"id", "fecha", "hora_inicio", "hora_fin"}, ...]}; con `skip`
        mayor que el total devuelve una lista vacía. Errores posibles:
        {"error": "No autenticado"}, {"error": "Parámetros de paginación inválidos..."}.
        """

        def operacion(db: Session, usuario: Usuario) -> dict:
            if skip < SKIP_MINIMO or not LIMITE_MINIMO <= limit <= LIMITE_MAXIMO:
                return {"error": MENSAJE_PAGINACION_INVALIDA}
            propias = servicio.listar_reservas(db, usuario.id, skip, limit)
            return {"reservas": [reserva_a_dict(reserva) for reserva in propias]}

        return _ejecutar_como_usuario(ctx, operacion)

    @mcp.tool()
    def cancelar_reserva(ctx: Context, reserva_id: int, confirmar: bool = False) -> dict:
        """Cancela (elimina) una reserva del usuario autenticado.

        ACCIÓN DESTRUCTIVA: el servidor exige `confirmar=true`; si no se indica o es false, NO
        se elimina nada y se devuelve un aviso de confirmación requerida. Parámetros:
        `reserva_id` (id de la reserva, entero) y `confirmar` (booleano, debe ser true para
        ejecutar). Solo el dueño puede cancelar su reserva.

        Devuelve {"mensaje": "Reserva <id> cancelada"}. Errores posibles:
        {"error": "No autenticado"},
        {"error": "Confirmación requerida: repite con confirmar=true"},
        {"error": "Reserva no encontrada"},
        {"error": "No tienes permiso sobre esta reserva"}.
        """

        def operacion(db: Session, usuario: Usuario) -> dict:
            # La confirmación la valida el servicio (Art. VI.5): se le pasa tal cual llega.
            servicio.eliminar_reserva(db, usuario.id, reserva_id, confirmar=confirmar)
            return {"mensaje": f"Reserva {reserva_id} cancelada"}

        return _ejecutar_como_usuario(ctx, operacion)

    return mcp
