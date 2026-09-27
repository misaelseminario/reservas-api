"""Repository real de `Usuario` (SQLAlchemy 2). Solo persiste y consulta, sin reglas de negocio."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Usuario


class UsuarioRepository:
    """Cumple `UsuarioRepositoryProtocol`. Sin estado: la sesión llega por parámetro."""

    def crear(self, db: Session, email: str, password_hash: str) -> Usuario:
        usuario = Usuario(email=email, password_hash=password_hash)
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario

    def obtener_por_email(self, db: Session, email: str) -> Usuario | None:
        return db.execute(select(Usuario).where(Usuario.email == email)).scalar_one_or_none()

    def obtener_por_id(self, db: Session, usuario_id: int) -> Usuario | None:
        return db.get(Usuario, usuario_id)


# Instancia de módulo: valor por defecto del parámetro `repo` de los servicios (Art. II.1).
usuario_repository = UsuarioRepository()
