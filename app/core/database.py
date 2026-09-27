"""Motor y sesiones de SQLAlchemy 2.

El motor por defecto se crea de forma perezosa con `DATABASE_URL` de la configuración.
`configurar_motor(url)` permite (re)apuntar a otra base de datos, p. ej. un SQLite temporal
en los tests. La sesión se inyecta por dependencia (Art. III.1): `get_db` para FastAPI y
`abrir_sesion` para código fuera de FastAPI (tools MCP).
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base declarativa de todos los modelos ORM."""


motor: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def configurar_motor(url: str) -> Engine:
    """Crea el motor para `url`, activa las claves foráneas en SQLite y enlaza `SessionLocal`."""
    global motor, SessionLocal

    if motor is not None:
        motor.dispose()

    es_sqlite = url.startswith("sqlite")
    argumentos = {"check_same_thread": False} if es_sqlite else {}
    nuevo_motor = create_engine(url, connect_args=argumentos)

    if es_sqlite:

        @event.listens_for(nuevo_motor, "connect")
        def _activar_claves_foraneas(conexion, _registro):
            cursor = conexion.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    motor = nuevo_motor
    SessionLocal = sessionmaker(bind=nuevo_motor, autoflush=False, expire_on_commit=False)
    return nuevo_motor


def _sesion_local() -> sessionmaker[Session]:
    """Devuelve la fábrica de sesiones, creando el motor por defecto la primera vez."""
    if SessionLocal is None:
        configurar_motor(get_settings().DATABASE_URL)
    return SessionLocal


def crear_tablas() -> None:
    """Crea todas las tablas registradas en `Base.metadata` (importar `app.models` antes)."""
    _sesion_local()
    Base.metadata.create_all(bind=motor)


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: abre una sesión, la entrega y la cierra siempre."""
    db = _sesion_local()()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def abrir_sesion() -> Generator[Session, None, None]:
    """Equivalente de `get_db` para usar fuera de FastAPI (tools MCP)."""
    db = _sesion_local()()
    try:
        yield db
    finally:
        db.close()
