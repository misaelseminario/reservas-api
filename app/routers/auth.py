"""Router de autenticación: registro e inicio de sesión (`/auth/...`).

Solo recibe, llama a `services/auth.py` y traduce errores (Art. I.2). La normalización del
email y la unicidad (RN-5) viven en el servicio.
"""

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.dependencias import traducir_excepcion
from app.schemas.usuario import Token, UsuarioCrear, UsuarioLeer
from app.services.auth import autenticar_usuario, registrar_usuario
from app.services.excepciones import ErrorDeDominio

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/registro", response_model=UsuarioLeer, status_code=status.HTTP_201_CREATED)
def registro(datos: UsuarioCrear, db: Session = Depends(get_db)):
    """Registra un usuario. Email ya registrado (sin distinguir mayúsculas) → 400."""
    try:
        return registrar_usuario(db, datos.email, datos.password)
    except ErrorDeDominio as exc:
        raise traducir_excepcion(exc) from exc


@router.post("/login", response_model=Token)
def login(formulario: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Devuelve un JWT. `username` es el email. Credenciales inválidas → 401."""
    try:
        token = autenticar_usuario(db, formulario.username, formulario.password)
    except ErrorDeDominio as exc:
        raise traducir_excepcion(exc) from exc
    return Token(access_token=token, token_type="bearer")
