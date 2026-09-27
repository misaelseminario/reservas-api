"""Seguridad: hash de contraseñas con bcrypt y tokens JWT con PyJWT.

Este módulo no importa nada de `services/` ni de capas superiores (Art. I.5) y no lanza
excepciones de dominio: `decodificar_token` devuelve `None` ante cualquier fallo y es
`services/auth.py` quien decide qué error de dominio corresponde. Nunca se registran en
logs contraseñas ni tokens (Art. IV.2).
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings


def hashear_password(password: str) -> str:
    """Devuelve el hash bcrypt (texto) de la contraseña."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar_password(password: str, password_hash: str) -> bool:
    """Comprueba la contraseña contra su hash bcrypt."""
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        # Hash mal formado o contraseña que bcrypt no admite (> 72 bytes): no coincide.
        return False


def crear_token(sub: str) -> str:
    """Crea un JWT firmado con `sub` (id de usuario como texto) y `exp` (UTC)."""
    ajustes = get_settings()
    expira = datetime.now(timezone.utc) + timedelta(minutes=ajustes.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": sub, "exp": expira}, ajustes.SECRET_KEY, algorithm=ajustes.ALGORITHM
    )


def decodificar_token(token: str) -> int | None:
    """Devuelve el id de usuario del token o `None` si no es válido por cualquier motivo.

    Exige `exp` y `sub`. Firma inválida, token expirado o mal formado y `sub` no numérico
    devuelven `None`; no se lanza ninguna excepción.
    """
    ajustes = get_settings()
    try:
        carga = jwt.decode(
            token,
            ajustes.SECRET_KEY,
            algorithms=[ajustes.ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return int(carga["sub"])
    except (jwt.PyJWTError, ValueError, TypeError):
        return None
