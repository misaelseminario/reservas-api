# Research (Fase 0): Reservas de una sala compartida

**Fecha**: 2026-09-26 | **Plan**: [plan.md](plan.md)

Todas las decisiones del stack ya venían dadas por la petición del plan; esta fase resolvió
los puntos que no se podían asumir sin comprobarlos. Las versiones y los comportamientos de
más abajo se **verificaron** resolviendo las dependencias con `uv` sobre CPython 3.13.15 y
ejecutando un spike descartable (fuera del repositorio). No queda ningún «NEEDS
CLARIFICATION».

## R1. Versiones exactas compatibles con Python 3.13

**Decisión**: fijar con `==` en `pyproject.toml` las versiones resueltas por `uv lock
--python 3.13` el 2026-09-26:

| Paquete | Versión | Uso |
|---------|---------|-----|
| fastapi | 0.141.1 | API REST |
| uvicorn | 0.54.0 | servidor ASGI |
| sqlalchemy | 2.1.1 | ORM |
| pydantic | 2.13.5 | schemas |
| pydantic-settings | 2.15.0 | lectura de `.env` |
| pyjwt | 2.15.0 | JWT |
| bcrypt | 5.0.0 | hash de contraseñas (uso directo, sin passlib) |
| mcp | **1.30.0** | MCP con `FastMCP` (ver R2) |
| python-multipart | 0.0.32 | requerido por `OAuth2PasswordRequestForm` (formulario) |
| email-validator | 2.3.0 | requerido por `EmailStr` de Pydantic |
| pytest (dev) | 9.1.1 | tests |
| pytest-cov (dev) | 7.1.0 | cobertura |
| httpx (dev) | 0.28.1 | cliente de `TestClient` |

`python-multipart` y `email-validator` no estaban en la lista de la petición, pero son
dependencias en tiempo de ejecución imprescindibles de FastAPI/Pydantic para el formulario de
login y para validar el email (422); se añaden y se fijan igual.

**Rationale**: Art. VII.6 exige versiones exactas. Las dependencias transitivas (starlette
1.7.0, anyio, sse-starlette, coverage…) quedan congeladas por `uv.lock`, que se versiona.

**Alternativas**: rangos `>=`/`~=` (rechazado por Art. VII.6); `uvicorn[standard]` (rechazado:
sin necesidad de `uvloop`/`watchfiles` en este alcance).

## R2. `mcp` 2.x eliminó `FastMCP` → fijar `mcp==1.30.0`

**Hallazgo**: la última versión de `mcp` (2.2.0) **no contiene** `mcp.server.fastmcp`; al
importarlo lanza `ModuleNotFoundError` indicando que `FastMCP` pasó a llamarse `MCPServer` y
que otras APIs cambiaron (guía de migración del SDK). La petición pide explícitamente FastMCP.

**Decisión**: usar la última 1.x, `mcp==1.30.0` (`from mcp.server.fastmcp import FastMCP,
Context`), que se resuelve limpiamente en 3.13.

**Rationale**: respeta el requisito literal (FastMCP) y el spike confirmó que funciona
completo (R3). No es una desviación de la Constitución.

**Alternativas**: `mcp==2.2.0` con `MCPServer` (rechazado: cambia la API pedida y no la hemos
verificado; podría reconsiderarse como migración futura).

**Riesgo residual**: 1.30.0 es la rama anterior; una migración a 2.x queda fuera de alcance.

## R3. MCP streamable HTTP dentro de FastAPI — comportamiento verificado

Spike con `FastMCP` + `FastAPI` + `TestClient`. Resultados:

1. **Montaje**: `FastMCP("reservas", stateless_http=True, json_response=True,
   streamable_http_path="/mcp")` y `app.mount("/", mcp.streamable_http_app())`.
   Con `streamable_http_path="/"` y `app.mount("/mcp", …)` la ruta `/mcp` responde **307 →
   `/mcp/`** (mala experiencia para clientes MCP), por eso se descarta.
2. **Orden**: el mount en `/` es una ruta comodín; debe registrarse **después** de los
   routers REST, o los taparía (`/health` de prueba siguió funcionando al montarlo al final).
3. **Ciclo de vida**: FastAPI no ejecuta el lifespan de la sub-app montada; el lifespan de
   `app/main.py` debe envolver `async with mcp.session_manager.run():`.
4. **Identidad**: dentro de un tool, `ctx.request_context.request.headers["authorization"]`
   devuelve `Bearer …` tal cual lo envió el cliente (y `None` si no se envió). Se usa
   `stateless_http=True` para que **cada** llamada lleve y valide su propio token (ninguna
   sesión queda «pegada» a la identidad de la primera petición).
5. **Protección DNS-rebinding**: por defecto solo admite `Host` = `localhost:*`,
   `127.0.0.1:*`, `[::1]:*`. Un `Host` sin puerto (`localhost`) o distinto (`testserver`)
   recibe **421**. Los tests MCP deben usar `TestClient(crear_app(), base_url="http://localhost:8000")`.
   Consecuencia operativa: el servidor MCP funciona tal cual en `localhost:8000`; publicarlo
   bajo otro nombre de host exigiría configurar `TransportSecuritySettings` (fuera de
   alcance; queda anotado en la spec como despliegue local).
6. **Peticiones**: el cliente debe enviar `Accept: application/json, text/event-stream`.

7. **Una sola ejecución por instancia**: `StreamableHTTPSessionManager.run()` lanza
   `RuntimeError` si se llama dos veces (verificado en `mcp==1.30.0`,
   `server/streamable_http_manager.py`). Por eso `crear_servidor_mcp()` y `crear_app()` son
   fábricas: cada app (y cada test) tiene su propio servidor MCP.

**Decisión**: `stateless_http=True`, `json_response=True`, mount final en `/`, ruta MCP `/mcp`.

## R4. Un único punto de validación del JWT (REST y MCP)

**Decisión**: `services/auth.py::obtener_usuario_actual(db, token, repo=usuario_repository)`
decodifica el JWT (primitiva `core/security.py::decodificar_token`) y carga el `Usuario`.
- REST: la dependencia `get_current_user` (en `routers/`, con `OAuth2PasswordBearer`) la llama.
- MCP: `mcp/autenticacion.py` extrae el Bearer de la cabecera y llama a la **misma** función.

Cualquier fallo (sin token, token mal formado, firmado con otra clave, expirado, `sub` no
numérico, usuario inexistente) lanza `NoAutenticadoError`: REST → 401 con cabecera
`WWW-Authenticate: Bearer`; MCP → `{"error": "No autenticado"}`.

**Rationale**: Art. IV.6 y VI.6; FR-023 y FR-025. `sub` = `str(usuario.id)` (PyJWT ≥ 2.10
exige `sub` de tipo string); claim `exp` obligatorio.

## R5. Hash con `bcrypt` directo

- `hashpw(password.encode(), gensalt())` / `checkpw(...)`, funciones en `core/security.py`.
- **bcrypt 5.0.0 lanza `ValueError` si la contraseña supera 72 bytes** (verificado). Para que
  eso sea un 422 y no un 500, el schema de entrada limita la contraseña a un máximo de 72
  **bytes** (validador Pydantic) y mínimo 8 caracteres.
- El hash se guarda como `str` (decodificado); la contraseña jamás se loguea (Art. IV.2).

## R6. SQLAlchemy 2.1 + SQLite

- Estilo 2.0: `DeclarativeBase`, `Mapped[...]`, `mapped_column`, `select()`.
- `create_engine(url, connect_args={"check_same_thread": False})` (FastAPI usa un pool de
  hilos) y `PRAGMA foreign_keys=ON` por evento `connect`, para que la FK `usuario_id` se
  aplique de verdad en SQLite.
- Tablas creadas con `Base.metadata.create_all()` en el arranque. **Sin Alembic**: la spec
  no pide migraciones; se documenta como límite.
- `fecha` → `Date`, `hora_inicio`/`hora_fin` → `Time` (naive, un único huso: spec, supuestos).
- Sesión: `get_db()` (generador para `Depends`) y `abrir_sesion()` (context manager para MCP)
  sobre la misma `SessionLocal`. El motor es reconfigurable (`configurar_motor(url)`) para
  que los tests apunten a un archivo SQLite temporal.
- Síncrono, no `async`: el tráfico es bajo (spec). Los tools MCP son funciones síncronas; la
  E/S de SQLite bloquea el bucle brevemente, aceptable a esta escala (anotado como límite).

## R7. «Ahora» inyectable (RN-7)

**Decisión**: los servicios que crean o modifican reservas reciben `ahora: datetime | None =
None`; si es `None` usan `datetime.now()` (naive, hora local del servidor = «huso común» de la
spec). Los tests pasan un `datetime` fijo; no hay reloj real ni `freezegun`.
Regla: `datetime.combine(fecha, hora_inicio) < ahora` → `FechaPasadaError` (empezar
exactamente «ahora» se acepta, según la spec).

## R8. Orden de validación en crear/modificar

1. (solo modificar) existencia → 404, propiedad → 403 (RN-3);
2. RN-2 `hora_fin > hora_inicio` (`HorarioInvalidoError`);
3. RN-7 inicio no pasado (`FechaPasadaError`);
4. RN-1 solapamiento contra todas las reservas, excluyendo la propia al modificar (RN-4).

**Rationale**: primero las comprobaciones sin acceso a BD; el solapamiento, lo último y lo más
caro. La spec no fija el orden; queda documentado para que REST y MCP coincidan (FR-025).

## R9. 403 frente a 404 y Art. III.3

La spec (FR-014/FR-015, Art. V.2) obliga a distinguir «no existe» (404) de «existe pero es de
otro» (403). Distinguirlos exige preguntar por el id **sin** filtrar por `usuario_id`, cosa
que el Art. III.3 (versión 1.0.0) solo permitía para el solapamiento.

**Decisión** (aprobada; la Constitución se enmendó a la versión 1.1.0 para recoger esta
excepción; ver Complexity Tracking del plan): el
repository ofrece `existe(db, reserva_id) -> bool` (solo un booleano, **no devuelve datos** de
la reserva) y `obtener_de_usuario(db, reserva_id, usuario_id)` (siempre filtrada). Los datos de
una reserva nunca se leen sin filtro de dueño; ningún dato ajeno se revela (SC-002).

**Alternativa rechazada**: responder 404 también para reservas ajenas (evita la consulta sin
filtro pero contradice FR-014 y el contrato 403).

## R10. Herramientas MCP: argumentos como texto

Si los tools declararan `fecha: date`, un formato inválido lo rechazaría la validación del SDK
con un error de protocolo (no `{"error": "..."}`, contra Art. VI.3). **Decisión**: los tools
reciben `str` (`YYYY-MM-DD`, `HH:MM`), los convierten con `utils/fechas.py` y devuelven
`{"error": "Formato de fecha inválido…"}` si fallan. `skip`/`limit` se validan con los mismos
límites que REST. La conversión no es lógica de negocio (Art. I.2).

## R11. Cancelación con confirmación (RN-6)

`services/reservas.py::eliminar_reserva(db, usuario_id, reserva_id, *, confirmar, repo=…)`
es la **única** función de borrado. Si `confirmar` no es `True` lanza
`ConfirmacionRequeridaError` **antes de tocar la BD**. REST `DELETE` pasa `confirmar=True`
explícitamente (el propio verbo HTTP es la acción explícita); el tool `cancelar_reserva` pasa
el valor recibido (por defecto `False`). Así la garantía vive en el servidor (Art. VI.5) y
REST/MCP comparten reglas (FR-025).

## R12. Tests y cobertura

- `TestClient` de Starlette 1.7 emite `StarletteDeprecationWarning` («Using `httpx` … install
  `httpx2` instead»): sigue funcionando con `httpx==0.28.1`, como pide la petición. Se filtra
  solo ese aviso concreto en `[tool.pytest.ini_options]`.
- `pytest --cov=app --cov-report=term-missing --cov-fail-under=70` cubre el umbral global; el
  umbral de `services/` ≥ 90 % se comprueba con `coverage report --include="app/services/*"
  --fail-under=90` (pytest-cov no admite umbrales por paquete).
- Repositories falsos en memoria en `tests/unit/fakes.py`; `unittest.mock` prohibido
  (Art. VII.2), lo que se verificará con un `grep` en el quickstart.
- Los tests fijan `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `DATABASE_URL`
  mediante variables de entorno en `tests/conftest.py` (sin depender del `.env` real).

## R13. Entorno de desarrollo en Windows

Detectado durante el spike: crear un entorno virtual bajo una ruta muy larga (la del
directorio temporal de la sesión) falló en Windows por el límite de longitud de ruta. La ruta
de este proyecto también es larga, así que `reservas-api\.venv` **podría** sufrir lo mismo (no
se ha comprobado). Si `uv sync` falla con «Failed to persist temporary file», habilitar las
rutas largas en Windows o fijar `UV_PROJECT_ENVIRONMENT` a una ruta corta (p. ej. `C:\pv`,
lo que funcionó en el spike).
