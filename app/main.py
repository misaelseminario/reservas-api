"""Punto de entrada de la aplicación: `uvicorn app.main:app`.

`crear_app()` es una fábrica: cada llamada devuelve una aplicación nueva con su PROPIO servidor
MCP, porque `StreamableHTTPSessionManager.run()` solo puede ejecutarse una vez por instancia
(research R3.7). Así los tests crean una aplicación por caso. Aquí solo se ensambla; no hay
lógica de negocio.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registra las tablas en Base.metadata antes de create_all)
from app.core.database import crear_tablas
from app.mcp.server import crear_servidor_mcp
from app.routers import auth, reservas


def crear_app() -> FastAPI:
    mcp = crear_servidor_mcp()
    app_mcp = mcp.streamable_http_app()  # crea el `session_manager`; debe ir antes del lifespan

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        crear_tablas()
        # FastAPI no ejecuta el lifespan de la sub-app montada: hay que arrancar aquí el
        # gestor de sesiones de MCP (research R3.3).
        async with mcp.session_manager.run():
            yield

    aplicacion = FastAPI(title="API de reservas", lifespan=lifespan)
    aplicacion.include_router(auth.router)
    aplicacion.include_router(reservas.router)
    # Último registro: el mount en "/" es una ruta comodín y taparía las rutas REST que vayan
    # después (research R3.2). La ruta MCP queda en `/mcp` (`streamable_http_path`).
    aplicacion.mount("/", app_mcp)
    return aplicacion


app = crear_app()
