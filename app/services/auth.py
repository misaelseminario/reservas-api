"""Servicios de autenticación: registro y (T024) login y validación del JWT.

Contiene las reglas de negocio de usuarios (Art. I.3). No conoce HTTP ni MCP: los routers y
los tools traducen las excepciones de dominio a su formato de error.
"""

from sqlalchemy.orm import Session

from app.core.security import (
    crear_token,
    decodificar_token,
    hashear_password,
    verificar_password,
)
from app.models import Usuario
from app.repositories.base import UsuarioRepositoryProtocol
from app.repositories.usuario_repository import usuario_repository
from app.services.excepciones import EmailYaRegistradoError, NoAutenticadoError


def registrar_usuario(
    db: Session,
    email: str,
    password: str,
    *,
    repo: UsuarioRepositoryProtocol = usuario_repository,
) -> Usuario:
    """RN-5: el email es único. `Usuario@X.com` y `usuario@x.com` son el mismo usuario.

    Guarda solo el hash de la contraseña (Art. IV.2); nunca la devuelve ni la conserva.
    """
    email = email.lower()
    if repo.obtener_por_email(db, email) is not None:
        raise EmailYaRegistradoError()
    return repo.crear(db, email, hashear_password(password))


def autenticar_usuario(
    db: Session,
    email: str,
    password: str,
    *,
    repo: UsuarioRepositoryProtocol = usuario_repository,
) -> str:
    """Devuelve un JWT si las credenciales son correctas.

    El email se normaliza a minúsculas (RN-5). Email inexistente y contraseña incorrecta dan
    el MISMO error, para no revelar qué emails están registrados.
    """
    usuario = repo.obtener_por_email(db, email.lower())
    if usuario is None or not verificar_password(password, usuario.password_hash):
        raise NoAutenticadoError("Credenciales incorrectas")
    return crear_token(str(usuario.id))


def obtener_usuario_actual(
    db: Session,
    token: str | None,
    *,
    repo: UsuarioRepositoryProtocol = usuario_repository,
) -> Usuario:
    """Única función que valida el JWT y resuelve el usuario, para REST y para MCP (FR-007, FR-023).

    Token ausente o vacío, inválido, expirado, o de un usuario que ya no existe →
    `NoAutenticadoError`. El `usuario_id` sale siempre del token, nunca del cliente (Art. IV.6).
    """
    if not token:
        raise NoAutenticadoError()
    usuario_id = decodificar_token(token)
    if usuario_id is None:
        raise NoAutenticadoError()
    usuario = repo.obtener_por_id(db, usuario_id)
    if usuario is None:
        raise NoAutenticadoError()
    return usuario
