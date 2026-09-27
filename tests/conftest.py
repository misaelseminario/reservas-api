"""Configuración común de los tests.

Las variables de entorno se fijan ANTES de importar nada de `app`, para que los tests no
dependan del `.env` real (que contiene el secreto de desarrollo). Los valores de aquí son
solo de prueba. Los fixtures de BD (`db_url`, `motor_temporal`) se adelantaron en T031 porque
los tests de los routers necesitan un SQLite real; `client` y los helpers son de T042.

Sin dobles de prueba de ningún tipo (Art. VII.2): el cliente es la aplicación real sobre un SQLite real.
"""

import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SECRET_KEY", "clave-solo-para-tests-0123456789abcdef0123456789abcdef")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_placeholder.db")

CLAVE_PRUEBA = "clave-segura-1"


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


@pytest.fixture
def client(motor_temporal):
    """La aplicación completa (`crear_app()`: REST + MCP en `/mcp`) sobre el SQLite temporal.

    Se usa como context manager para que corran el lifespan y el `session_manager` de MCP. Cada
    test crea su propia aplicación, porque el `session_manager` solo puede ejecutarse una vez por
    instancia (research R3.3). El `base_url` con puerto es obligatorio: con otro `Host` el SDK de
    MCP responde 421 (research R3.5).
    """
    from app.main import crear_app

    with TestClient(crear_app(), base_url="http://localhost:8000") as cliente:
        yield cliente


def registrar_y_autenticar(client: TestClient, email: str) -> dict:
    """Registra al usuario, inicia sesión y devuelve la cabecera `{"Authorization": "Bearer ..."}`."""
    registro = client.post("/auth/registro", json={"email": email, "password": CLAVE_PRUEBA})
    assert registro.status_code == 201, registro.text
    login = client.post("/auth/login", data={"username": email, "password": CLAVE_PRUEBA})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def fecha_futura(dias: int = 30) -> str:
    """Fecha `YYYY-MM-DD` situada `dias` días después de hoy (por defecto 30)."""
    return (date.today() + timedelta(days=dias)).isoformat()


def crear_reserva_rest(client: TestClient, cabeceras: dict, inicio: str, fin: str, fecha=None):
    """`POST /reservas/` con la fecha indicada (por defecto `fecha_futura()`); devuelve la respuesta."""
    cuerpo = {"fecha": fecha or fecha_futura(), "hora_inicio": inicio, "hora_fin": fin}
    return client.post("/reservas/", json=cuerpo, headers=cabeceras)
