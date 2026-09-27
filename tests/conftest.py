"""Configuración común de los tests.

Las variables de entorno se fijan ANTES de importar nada de `app`, para que los tests no
dependan del `.env` real (que contiene el secreto de desarrollo). Los valores de aquí son
solo de prueba. Los fixtures de BD (`db_url`, `motor_temporal`) se adelantaron en T031 porque
los tests de los routers necesitan un SQLite real; el cliente y los helpers llegan en T042.
"""

import os

import pytest

os.environ.setdefault("SECRET_KEY", "clave-solo-para-tests-0123456789abcdef0123456789abcdef")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_placeholder.db")


@pytest.fixture
def db_url(tmp_path) -> str:
    """URL de un archivo SQLite temporal, distinto para cada test."""
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def motor_temporal(db_url):
    """Apunta la aplicación a un SQLite temporal con las tablas creadas; al terminar lo libera."""
    from app.core import database
    from app.core.database import configurar_motor, crear_tablas

    import app.models  # noqa: F401  (registra las tablas en Base.metadata)

    configurar_motor(db_url)
    crear_tablas()
    yield database.motor
    database.motor.dispose()
    database.motor = None
    database.SessionLocal = None
