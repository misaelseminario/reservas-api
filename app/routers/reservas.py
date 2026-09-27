"""Router de reservas (`/reservas/...`). Todas las rutas exigen token (Art. IV.5).

Cada ruta recibe, llama a la función de `services/reservas.py` y traduce las excepciones de
dominio a `HTTPException` (Art. I.2, V.3); no contiene ninguna regla de negocio. El `usuario_id`
sale siempre del JWT (`get_current_user`), nunca del cuerpo ni de la ruta (Art. IV.6).
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Usuario
from app.routers.dependencias import get_current_user, traducir_excepcion
from app.schemas.reserva import ReservaActualizar, ReservaCrear, ReservaLeer
from app.services import reservas as servicio
from app.services.excepciones import ErrorDeDominio
from app.services.reservas import (
    LIMITE_MAXIMO,
    LIMITE_MINIMO,
    LIMITE_POR_DEFECTO,
    SKIP_MINIMO,
)

router = APIRouter(prefix="/reservas", tags=["reservas"])


@router.post("/", response_model=ReservaLeer, status_code=status.HTTP_201_CREATED)
def crear(
    datos: ReservaCrear,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crea una reserva a nombre del usuario autenticado (RN-1, RN-2, RN-7 → 400)."""
    try:
        return servicio.crear_reserva(
            db, usuario.id, datos.fecha, datos.hora_inicio, datos.hora_fin
        )
    except ErrorDeDominio as exc:
        raise traducir_excepcion(exc) from exc


@router.get("/", response_model=list[ReservaLeer])
def listar(
    skip: int = Query(SKIP_MINIMO, ge=SKIP_MINIMO),
    limit: int = Query(LIMITE_POR_DEFECTO, ge=LIMITE_MINIMO, le=LIMITE_MAXIMO),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista solo las reservas del usuario, ordenadas por fecha y hora de inicio."""
    return servicio.listar_reservas(db, usuario.id, skip, limit)


@router.get("/{reserva_id}", response_model=ReservaLeer)
def obtener(
    reserva_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Devuelve una reserva propia. Ajena → 403; inexistente → 404 (RN-3)."""
    try:
        return servicio.obtener_reserva(db, usuario.id, reserva_id)
    except ErrorDeDominio as exc:
        raise traducir_excepcion(exc) from exc


@router.put("/{reserva_id}", response_model=ReservaLeer)
def actualizar(
    reserva_id: int,
    datos: ReservaActualizar,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sustituye fecha y horas de una reserva propia; re-aplica las reglas (RN-4)."""
    try:
        return servicio.actualizar_reserva(
            db, usuario.id, reserva_id, datos.fecha, datos.hora_inicio, datos.hora_fin
        )
    except ErrorDeDominio as exc:
        raise traducir_excepcion(exc) from exc


@router.delete("/{reserva_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    reserva_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Elimina una reserva propia. El verbo `DELETE` es la acción explícita (RN-6, research R11):
    el servicio exige `confirmar` y aquí se pasa `True` a propósito."""
    try:
        servicio.eliminar_reserva(db, usuario.id, reserva_id, confirmar=True)
    except ErrorDeDominio as exc:
        raise traducir_excepcion(exc) from exc
