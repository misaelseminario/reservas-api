# Tasks: Reservas de una sala compartida

**Input**: `specs/001-reservas-sala/` — [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Prerequisites**: Constitución v1.1.0 (`.specify/memory/constitution.md`), `uv` instalado, CPython 3.13.

**Tests**: solicitados explícitamente (Art. VII y FR-026). Cada tarea de `services/` incluye su test unitario con repository falso en memoria; **`unittest.mock` está prohibido** (Art. VII.2).

**Organización**: las fases siguen el **orden de dependencia por capas** pedido (setup → core → models → schemas → repositories → services → routers → mcp → tests de integración y API → verificación). Dentro de las capas de negocio, cada tarea lleva su etiqueta de historia de usuario para conservar la trazabilidad con la spec:

| Etiqueta | Historia (spec.md) | Prioridad |
|----------|--------------------|-----------|
| `[US1]` | Registro e inicio de sesión | P1 |
| `[US2]` | Crear y consultar mis reservas | P1 |
| `[US3]` | Modificar y eliminar mis reservas | P2 |
| `[US4]` | Gestionar reservas mediante MCP | P2 |

Las tareas sin etiqueta son infraestructura compartida o verificación transversal.

## Formato: `- [ ] T### [P?] [US?] Descripción con ruta`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin depender de tareas incompletas).
- Todas las rutas son relativas a la raíz del repositorio (`reservas-api/`).
- Las líneas indentadas bajo una tarea son parte de esa tarea (detalle obligatorio).
- Toda la documentación, docstrings y mensajes de error visibles se redactan en **español** (Constitución, «Stack y Restricciones Técnicas»).

---

## Phase 1: Setup (proyecto, dependencias, entorno)

**Purpose**: esqueleto del proyecto, dependencias con versión exacta y configuración de entorno.

- [X] T001 Crear el esqueleto de carpetas con un `__init__.py` vacío en cada paquete: `app/`, `app/core/`, `app/models/`, `app/schemas/`, `app/repositories/`, `app/services/`, `app/routers/`, `app/mcp/`, `app/utils/`, `tests/`, `tests/unit/`, `tests/integration/`, `tests/api/`.
- [X] T002 Crear `pyproject.toml` (proyecto gestionado con `uv`, **sin** `[build-system]`):
  - `[project]`: `name = "reservas-api"`, `version = "0.1.0"`, `requires-python = ">=3.13"`.
  - `dependencies` con versión **exacta** (`==`), sin rangos (Art. VII.6): `fastapi==0.141.1`, `uvicorn==0.54.0`, `sqlalchemy==2.1.1`, `pydantic==2.13.5`, `pydantic-settings==2.15.0`, `pyjwt==2.15.0`, `bcrypt==5.0.0`, `mcp==1.30.0` (**no** 2.x: `FastMCP` no existe allí, research R2), `python-multipart==0.0.32`, `email-validator==2.3.0`.
  - `[dependency-groups] dev`: `pytest==9.1.1`, `pytest-cov==7.1.0`, `httpx==0.28.1`.
  - `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `pythonpath = ["."]`, y `filterwarnings = ["ignore:Using .httpx. with .starlette.testclient. is deprecated"]` (solo ese aviso de Starlette 1.7, research R12).
  - `[tool.coverage.run]`: `source = ["app"]`.
- [X] T003 Generar el entorno con `uv lock --python 3.13` y `uv sync`; comprobar con `uv run python -c "import fastapi, sqlalchemy, mcp; from mcp.server.fastmcp import FastMCP"` que resuelve sin error y que `uv.lock` mantiene exactamente las versiones de T002 (depende de T002). Si `uv sync` falla con «Failed to persist temporary file» (rutas largas de Windows), exportar `UV_PROJECT_ENVIRONMENT` a una ruta corta y repetir (research R13). Versionar `uv.lock`.
- [X] T004 [P] Crear `.env.example` en la raíz **sin valores reales**, con las cuatro variables comentadas en español: `SECRET_KEY=` (indicar cómo generarla: `python -c "import secrets; print(secrets.token_hex(32))"`), `ALGORITHM=HS256`, `ACCESS_TOKEN_EXPIRE_MINUTES=30`, `DATABASE_URL=sqlite:///./reservas.db` (Art. IV.4).
- [X] T005 [P] Crear `.gitignore` en la raíz (hoy no existe) incluyendo como mínimo: `.env`, `.venv/`, `*.db`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.coverage`, `htmlcov/`. **No** ignorar `.env.example` ni `uv.lock`.
- [X] T006 Crear el `.env` local copiando `.env.example` (depende de T004 y T005) y rellenar `SECRET_KEY` con un valor aleatorio generado; verificar con `git check-ignore .env` (debe imprimir `.env`) y que `git status` **no** lo lista. Este archivo NO se versiona.
- [X] T007 [P] Crear `tests/conftest.py` que, **antes de importar nada de `app`**, fije con `os.environ.setdefault(...)` valores de prueba para `SECRET_KEY` (cadena fija de ≥ 32 caracteres), `ALGORITHM="HS256"`, `ACCESS_TOKEN_EXPIRE_MINUTES="30"` y `DATABASE_URL="sqlite:///./test_placeholder.db"`, para que los tests no dependan del `.env` real. (Los fixtures de BD/cliente se añaden en T042.)

---

## Phase 2: Core (`app/core/`)

**Purpose**: configuración, base de datos y seguridad. Bloquea todas las capas siguientes.

- [X] T008 Crear `app/core/config.py`: clase `Settings(BaseSettings)` con los campos `SECRET_KEY: str`, `ALGORITHM: str`, `ACCESS_TOKEN_EXPIRE_MINUTES: int`, `DATABASE_URL: str`, **sin valores por defecto** (Art. IV.3), `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`; y `get_settings()` con `@lru_cache`. Nada hardcodeado.
- [X] T009 [P] Crear `app/core/database.py` (depende de T008), estilo SQLAlchemy 2:
  - `class Base(DeclarativeBase)`.
  - `configurar_motor(url: str)`: crea el motor con `connect_args={"check_same_thread": False}` si la URL es SQLite, registra el evento `connect` que ejecuta `PRAGMA foreign_keys=ON`, y (re)enlaza `SessionLocal = sessionmaker(...)`. El motor por defecto se crea de forma perezosa con `get_settings().DATABASE_URL`.
  - `crear_tablas()`: `Base.metadata.create_all(bind=motor)`.
  - `get_db()`: generador para `Depends` (abre sesión, `yield`, cierra en `finally`).
  - `abrir_sesion()`: `@contextmanager` equivalente para usar fuera de FastAPI (tools MCP, Art. III.1 / research R6).
  - Debe poder reconfigurarse (`configurar_motor(otra_url)`) para que los tests apunten a un SQLite temporal.
- [X] T010 [P] Crear `app/core/security.py` (depende de T008), sin importar nada de `services/` ni capas superiores (Art. I.5):
  - `hashear_password(password: str) -> str` con `bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()`, y `verificar_password(password: str, password_hash: str) -> bool` con `bcrypt.checkpw`. **Solo la librería `bcrypt`, sin passlib.** Nunca loguear contraseñas.
  - `crear_token(sub: str) -> str`: JWT con PyJWT, claims `sub` (string) y `exp` (ahora UTC + `ACCESS_TOKEN_EXPIRE_MINUTES`), firmado con `SECRET_KEY`/`ALGORITHM` de `get_settings()`.
  - `decodificar_token(token: str) -> int | None`: decodifica exigiendo `exp` y `sub` (`options={"require": ["exp", "sub"]}`); devuelve `int(sub)` o **`None`** ante cualquier fallo (firma inválida, expirado, mal formado, `sub` no numérico); **no lanza excepciones de dominio** (research R4).
- [X] T011 [P] Crear `tests/unit/test_security.py` (depende de T010): hash ≠ contraseña y verifica OK/KO; dos hashes de la misma contraseña difieren; `crear_token` → `decodificar_token` devuelve el mismo id; token con otra firma, token mal formado, cadena vacía y token expirado (crear con `exp` en el pasado usando PyJWT directamente) → `None`; `sub` no numérico → `None`. Sin `unittest.mock`.

**Checkpoint**: `uv run pytest tests/unit/test_security.py` pasa; `uv run python -c "from app.core.database import configurar_motor"` importa sin error.

---

## Phase 3: Models (`app/models/`)

**Purpose**: entidades ORM. Las restricciones se citan tal cual de `data-model.md`.

- [X] T012 [P] Crear `app/models/usuario.py`: `Usuario(Base)`, `__tablename__ = "usuarios"`, con `Mapped[...]`/`mapped_column`:
  - `id`: Integer, PK, autoincremental.
  - `email`: String(254), NOT NULL, **UNIQUE**, indexado (RN-5); se guarda siempre en minúsculas (lo normaliza `services/auth.py`, RN-5).
  - `password_hash`: NOT NULL; hash bcrypt, nunca la contraseña (Art. IV.2). (`data-model.md` lo escribe «String(60..)»: un hash bcrypt mide 60 caracteres, usar `String(60)`.)
  - Relación `reservas` (1 → N) con `Reserva`.
- [X] T013 [P] Crear `app/models/reserva.py`: `Reserva(Base)`, `__tablename__ = "reservas"`:
  - `id`: Integer, PK, autoincremental.
  - `usuario_id`: Integer, NOT NULL, **FK → `usuarios.id`**, indexado (Art. III.3).
  - `fecha`: Date, NOT NULL, indexado.
  - `hora_inicio`: Time, NOT NULL. `hora_fin`: Time, NOT NULL.
  - **Sin** `CHECK` en BD para `hora_fin > hora_inicio` (la regla vive solo en `services/`, Art. I.3). Sin `sala_id`. Sin cascada de borrado de usuarios. Relación inversa `usuario`.
- [X] T014 Crear `app/models/__init__.py` que importe y reexporte `Usuario` y `Reserva` (para que `Base.metadata` los registre antes de `create_all`); depende de T012 y T013.

**Checkpoint**: `uv run python -c "from app.core.database import configurar_motor, crear_tablas; import app.models; configurar_motor('sqlite:///:memory:'); crear_tablas()"` termina sin error.

---

## Phase 4: Schemas (`app/schemas/`)

**Purpose**: contratos de entrada/salida separados de los modelos ORM (Art. III.2). Solo validan **formato**, no reglas de negocio.

- [X] T015 [P] Crear `app/schemas/usuario.py`:
  - `UsuarioCrear`: `email: EmailStr`, `password: str` con validador: mínimo 8 caracteres y máximo **72 bytes** al codificar en UTF-8 (bcrypt 5 lanza `ValueError` por encima de 72, research R5) → 422.
  - `UsuarioLeer`: `id: int`, `email: EmailStr`, `model_config = ConfigDict(from_attributes=True)`. **Sin `password` ni `password_hash`** (Art. III.2, FR-004).
  - `Token`: `access_token: str`, `token_type: str` (valor `"bearer"`).
- [X] T016 [P] Crear `app/schemas/reserva.py`:
  - `ReservaCrear` y `ReservaActualizar`: `fecha: date`, `hora_inicio: time`, `hora_fin: time`, los tres obligatorios (modificar es sustitución completa); formato inválido → 422. **Depende de T035** (`utils` es transversal: ejecutar T035 antes de T016): un `field_validator("fecha", mode="before")` y otro para `hora_inicio`/`hora_fin` que, si el valor es `str`, lo pasan por `parsear_fecha`/`parsear_hora` de `app/utils/fechas.py`; el `ValueError` se convierte en 422. Así `09:00:30`, `9:00` o `2030-01-15T10:00:00` se rechazan igual que por MCP (FR-025).
  - `ReservaLeer`: `id`, `usuario_id`, `fecha`, `hora_inicio`, `hora_fin`, con `from_attributes=True`.
  - Ninguna regla RN aquí (Art. I.3).
- [X] T017 [P] Crear `tests/unit/test_schemas.py` (depende de T015 y T016): `UsuarioLeer.model_fields` no contiene `password`/`password_hash`, y serializar un `Usuario` no los incluye; contraseña de 7 caracteres → `ValidationError`; de 73 bytes (p. ej. 40 caracteres `é`) → `ValidationError`; de exactamente 72 bytes → válida; email inválido → error; `ReservaCrear` acepta `"2030-01-15"`/`"09:00"` y rechaza `"15/01/2030"`, `"25:00"`, `"09:00:30"`, `"9:00"` y `"2030-01-15T10:00:00"`.

**Checkpoint**: `uv run pytest tests/unit/test_schemas.py` pasa.

---

## Phase 5: Repositories (`app/repositories/`)

**Purpose**: persistencia y consultas, sin validar reglas de negocio (Art. I.4). La sesión es siempre el **primer parámetro**. Los métodos que escriben hacen `commit`.

- [X] T018 Crear `app/repositories/base.py` con dos `typing.Protocol` según `data-model.md` («Contrato del repository»):
  - `ReservaRepositoryProtocol`: `crear(db, usuario_id, fecha, hora_inicio, hora_fin) -> Reserva`; `listar_por_usuario(db, usuario_id, skip, limit) -> list[Reserva]`; `obtener_de_usuario(db, reserva_id, usuario_id) -> Reserva | None`; `existe(db, reserva_id) -> bool`; `listar_por_fecha(db, fecha) -> list[Reserva]`; `actualizar(db, reserva, fecha, hora_inicio, hora_fin) -> Reserva`; `eliminar(db, reserva) -> None`.
  - `UsuarioRepositoryProtocol`: `crear(db, email, password_hash) -> Usuario`; `obtener_por_email(db, email) -> Usuario | None`; `obtener_por_id(db, usuario_id) -> Usuario | None`.
- [X] T019 [P] Crear `app/repositories/usuario_repository.py`: clase sin estado `UsuarioRepository` que cumple el Protocol (T018) con SQLAlchemy 2 (`select()`), y la **instancia de módulo** `usuario_repository = UsuarioRepository()` (será el valor por defecto de los servicios, Art. II.1). Sin validaciones de negocio.
- [X] T020 [P] Crear `app/repositories/reserva_repository.py`: clase sin estado `ReservaRepository` que cumple el Protocol (T018) y la instancia `reserva_repository = ReservaRepository()`:
  - `listar_por_usuario`: **siempre** `WHERE usuario_id = :usuario_id`, orden estable `fecha, hora_inicio, id`, con `OFFSET skip` / `LIMIT limit`.
  - `obtener_de_usuario`: **siempre** filtrada por `id` **y** `usuario_id` (Art. III.3).
  - `existe`: devuelve solo `bool`, **nunca datos** de la reserva. Es una de las dos excepciones al filtro por `usuario_id` recogidas en el Art. III.3 v1.1.0, únicamente para distinguir 404 de 403.
  - `listar_por_fecha`: devuelve **todas** las reservas con `fecha == fecha`, de cualquier usuario, ordenadas por `hora_inicio, id`, **sin filtro de `usuario_id`** (excepción del Art. III.3 para el solapamiento). **No contiene la fórmula de solapamiento** ni ningún `excluir_id`: eso es regla de negocio y vive en `services/reservas.py` (T025, T027; Art. I.3 e I.4). El repository no expone `hay_solapamiento`.
  - `crear`/`actualizar`/`eliminar`: persisten y hacen `commit` (`refresh` cuando devuelven la entidad).

**Checkpoint**: `uv run python -c "from app.repositories.reserva_repository import reserva_repository"` importa sin error. Los repositories reales se verifican en T043.

---

## Phase 6: Services (`app/services/`) — todas las reglas de negocio

**Purpose**: **TODAS** las reglas de negocio (Art. I.3). Cada función recibe la sesión `db` y el `repo` como parámetro con la instancia real como **valor por defecto** (DIP, Art. II.1); nunca importa el repository dentro del cuerpo. Cada tarea incluye su test unitario con repository falso (sin `unittest.mock`) y la regla RN que cubre.

- [X] T021 Crear `app/services/excepciones.py` con las excepciones de dominio, todas heredando de una base `ErrorDeDominio(Exception)` cuyo `str(exc)` es el mensaje visible en español (única fuente de mensajes, usada tal cual por routers y tools MCP, FR-025): 
  - `ReservaSolapadaError` («La sala ya está reservada en ese horario», RN-1), `HorarioInvalidoError` («La hora de fin debe ser posterior a la hora de inicio», RN-2), `NoEsDuenoError` («No tienes permiso sobre esta reserva», RN-3), `ReservaNoEncontradaError` («Reserva no encontrada», RN-3/FR-015), `EmailYaRegistradoError` («El email ya está registrado», RN-5), `ConfirmacionRequeridaError` («Confirmación requerida: repite con confirmar=true», RN-6), `FechaPasadaError` («No se puede reservar en una fecha y hora pasadas», RN-7).
  - `NoAutenticadoError` (mensaje por defecto «No autenticado»; permite un mensaje personalizado, p. ej. «Credenciales incorrectas»).
  - Los mensajes nunca incluyen contraseñas ni datos de otros usuarios.
- [X] T022 Crear `tests/unit/fakes.py` (depende de T018 y T021) con `FakeReservaRepository` y `FakeUsuarioRepository`: **clases en memoria** (listas/diccionarios) que cumplen los Protocols de T018, con `db` ignorado (los tests pasan `db=None`). Reglas del fake: `listar_por_usuario`/`obtener_de_usuario` filtran por `usuario_id` y ordenan por `fecha, hora_inicio, id`; `existe` devuelve `bool`; `listar_por_fecha` devuelve las reservas guardadas con esa fecha, de cualquier usuario, **sin aplicar ninguna fórmula de solapamiento** (así los tests de RN-1 y de contiguas prueban de verdad la lógica del servicio, no la del fake); `eliminar` quita de la lista y expone un contador/lista para afirmar «no se eliminó nada». **Prohibido `unittest.mock`, `MagicMock`, `patch`** (Art. VII.2).
- [X] T023 [P] [US1] Crear `app/services/auth.py::registrar_usuario(db, email, password, *, repo=usuario_repository) -> Usuario` **(RN-5)**: normaliza `email = email.lower()` antes de buscar y de guardar (`Usuario@X.com` y `usuario@x.com` son el mismo usuario); si `repo.obtener_por_email(db, email)` devuelve un usuario → `EmailYaRegistradoError`; si no, `hashear_password` (T010) y `repo.crear` con el email en minúsculas; nunca guarda ni devuelve la contraseña en claro. Test unitario `tests/unit/test_auth_registro.py` con `FakeUsuarioRepository` (depende de T021, T022): registro nuevo OK (el hash guardado ≠ contraseña); **email duplicado → `EmailYaRegistradoError` (RN-5)**; registrar `Usuario@X.com` y luego `usuario@x.com` → `EmailYaRegistradoError`, y el email guardado está en minúsculas; el usuario devuelto no expone la contraseña.
- [X] T024 [US1] En el mismo `app/services/auth.py` (depende de T023) añadir:
  - `autenticar_usuario(db, email, password, *, repo=usuario_repository) -> str`: normaliza `email = email.lower()`, busca por email, `verificar_password`; si el email no existe o la contraseña es incorrecta → `NoAutenticadoError("Credenciales incorrectas")` (mismo error en ambos casos); si es correcto devuelve `crear_token(str(usuario.id))`.
  - `obtener_usuario_actual(db, token: str | None, *, repo=usuario_repository) -> Usuario` (**única función de validación del JWT para REST y MCP**, FR-007/FR-023, research R4): `token` ausente/vacío, `decodificar_token(token) is None` o usuario inexistente → `NoAutenticadoError()` («No autenticado»).
  - Test unitario `tests/unit/test_auth_login.py` con `FakeUsuarioRepository`: login correcto devuelve token que `obtener_usuario_actual` resuelve al mismo usuario; registrado `Usuario@X.com`, el login con `usuario@x.com` y con `USUARIO@X.COM` devuelve token válido (RN-5); contraseña incorrecta y email inexistente → `NoAutenticadoError`; token `None`, `""`, basura, expirado y de un usuario que ya no existe → `NoAutenticadoError` (cubre FR-005, FR-006, FR-007; SC-003 lado servicio).
- [X] T025 [P] [US2] Crear `app/services/reservas.py::crear_reserva(db, usuario_id, fecha, hora_inicio, hora_fin, *, ahora=None, repo=reserva_repository) -> Reserva` **(RN-1, RN-2, RN-7)**. `ahora=None` → `datetime.now()` (inyectable para los tests, research R7). Orden de validación fijo (research R8):
  1. **RN-2**: `hora_fin <= hora_inicio` → `HorarioInvalidoError` (incluye horas iguales y rangos que cruzan medianoche como 23:00→01:00).
  2. **RN-7**: `datetime.combine(fecha, hora_inicio) < ahora` → `FechaPasadaError` (empezar exactamente `ahora` se acepta).
  3. **RN-1**: obtener `repo.listar_por_fecha(db, fecha)` y, si alguna reserva `r` cumple `hora_inicio < r.hora_fin and hora_fin > r.hora_inicio` (fórmula `inicio_nueva < fin_existente AND fin_nueva > inicio_existente`, comparaciones **estrictas** para que las contiguas no solapen) → `ReservaSolapadaError`. Implementar la fórmula en una función privada reutilizable del propio `app/services/reservas.py` (p. ej. `_se_solapan(inicio_a, fin_a, inicio_b, fin_b)`), que también usará T027.
  4. `repo.crear(db, usuario_id, ...)`.
  - Test unitario `tests/unit/test_reservas_crear.py` con `FakeReservaRepository` y `ahora` fijo (nunca el reloj real), **un caso al menos por regla**:
    - **RN-1**: idéntica, contenida, que contiene y parcial → `ReservaSolapadaError`; misma hora en **otra fecha** → se acepta; solapa con reserva de **otro usuario** → error.
    - **Reservas contiguas (test propio e independiente)**: 09:00–10:00 existente y 10:00–11:00 nueva → aceptada; y en el orden inverso (existente 10:00–11:00, nueva 09:00–10:00) → aceptada.
    - **RN-2**: `fin == inicio`, `fin < inicio` y 23:00→01:00 → `HorarioInvalidoError`.
    - **RN-7**: fecha ayer → `FechaPasadaError`; hoy con hora de inicio anterior a `ahora` → error; inicio **exactamente** `ahora` → aceptada.
    - Duración de 1 minuto y de todo el día → aceptadas (sin límites, spec).
- [X] T026 [US2] En el mismo `app/services/reservas.py` (depende de T025) añadir las constantes de paginación `SKIP_MINIMO = 0`, `LIMITE_MINIMO = 1`, `LIMITE_MAXIMO = 100`, `LIMITE_POR_DEFECTO = 100` (única definición de estos límites; las importan el router T032 y el tool MCP T039) y `listar_reservas(db, usuario_id, skip=SKIP_MINIMO, limit=LIMITE_POR_DEFECTO, *, repo=reserva_repository) -> list[Reserva]` (solo del usuario, FR-011) y `obtener_reserva(db, usuario_id, reserva_id, *, repo=reserva_repository) -> Reserva` **(RN-3)**: `not repo.existe` → `ReservaNoEncontradaError`; existe pero `obtener_de_usuario` devuelve `None` → `NoEsDuenoError`. Test unitario `tests/unit/test_reservas_consulta.py` con `FakeReservaRepository`: **RN-3** — reserva ajena → `NoEsDuenoError`, id inexistente → `ReservaNoEncontradaError` (inexistente ≠ ajena); listar devuelve solo las del usuario (mezcladas con ajenas), respeta `skip`/`limit` y con `skip` mayor que el total devuelve `[]`; obtener propia OK.
- [X] T027 [US3] En el mismo `app/services/reservas.py` (depende de T026) añadir `actualizar_reserva(db, usuario_id, reserva_id, fecha, hora_inicio, hora_fin, *, ahora=None, repo=reserva_repository) -> Reserva` **(RN-4, con RN-3, RN-1, RN-2, RN-7)**. Orden (research R8): existencia (404) → propiedad (403, RN-3) → RN-2 → RN-7 → RN-1 con la misma fórmula de T025 sobre `repo.listar_por_fecha(db, fecha)`, **excluyendo en el servicio la propia reserva** (se descartan las reservas con `r.id == reserva_id` antes de comparar) → `repo.actualizar`. Test unitario `tests/unit/test_reservas_actualizar.py` con `FakeReservaRepository` y `ahora` fijo:
  - **RN-4**: ampliar la duración de la propia reserva (solapa solo consigo misma) → aceptada; modificar sin cambios → aceptada; mover a un horario que solapa con **otra** reserva → `ReservaSolapadaError`; mover a un horario contiguo a otra → aceptada.
  - Re-aplica reglas: `fin <= inicio` → `HorarioInvalidoError` (RN-2); inicio pasado → `FechaPasadaError` (RN-7).
  - **RN-3**: reserva ajena → `NoEsDuenoError`; inexistente → `ReservaNoEncontradaError`; en ambos casos la reserva no cambia.
- [X] T028 [US3] En el mismo `app/services/reservas.py` (depende de T027) añadir `eliminar_reserva(db, usuario_id, reserva_id, *, confirmar: bool, repo=reserva_repository) -> None` **(RN-6, RN-3)**: es la **única** función de borrado, compartida por `DELETE /reservas/{id}` (US3) y el tool `cancelar_reserva` (US4) (Art. VI.1). `confirmar` es keyword **obligatorio, sin valor por defecto**. Orden (research R11): `confirmar is not True` → `ConfirmacionRequeridaError` **antes de tocar la BD** → existencia (404) → propiedad (403) → `repo.eliminar`. Test unitario `tests/unit/test_reservas_eliminar.py` con `FakeReservaRepository`:
  - **RN-6**: `confirmar=False` → `ConfirmacionRequeridaError` y **la reserva sigue existiendo** (el fake no recibió ninguna llamada a `eliminar`, ni siquiera a `existe`); `confirmar=True` sobre reserva propia → se elimina.
  - **RN-3**: ajena → `NoEsDuenoError` y no se elimina; inexistente → `ReservaNoEncontradaError`; con `confirmar=False` sobre reserva ajena sigue devolviendo `ConfirmacionRequeridaError` (nada se revela ni se toca).
- [X] T029 Ejecutar `uv run pytest tests/unit --cov=app/services --cov-report=term-missing` y comprobar que todos los tests unitarios pasan, que hay **al menos un test por cada RN-1…RN-7 más el de contiguas** (repasar la tabla de trazabilidad de este archivo) y que `app/services` ya supera el 90 %; añadir los tests que falten. (Depende de T023–T028.)

**Checkpoint**: la lógica de negocio completa está probada de forma aislada, sin BD, sin HTTP y sin reloj real.

---

## Phase 7: Routers (`app/routers/`) y `app/main.py`

**Purpose**: entrada/salida HTTP. Reciben, llaman a `services/` y traducen excepciones → `HTTPException`; **sin reglas de negocio** (Art. I.2, V.3).

- [X] T030 Crear `app/routers/dependencias.py`:
  - `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)` (para responder con el mensaje propio en español).
  - `get_current_user(token = Depends(oauth2_scheme), db = Depends(get_db)) -> Usuario`: llama a `services.auth.obtener_usuario_actual`; `NoAutenticadoError` → `HTTPException(401, detail=str(exc), headers={"WWW-Authenticate": "Bearer"})`. El `usuario_id` sale **siempre** de aquí (Art. IV.6).
  - `traducir_excepcion(exc: ErrorDeDominio) -> HTTPException` con la tabla del contrato REST ([contracts/rest-api.md](contracts/rest-api.md)): `EmailYaRegistradoError`/`ReservaSolapadaError`/`HorarioInvalidoError`/`FechaPasadaError` → 400; `NoEsDuenoError` → 403; `ReservaNoEncontradaError` → 404; `NoAutenticadoError` → 401 (con `WWW-Authenticate`); `detail = str(exc)`.
- [X] T031 [P] [US1] Crear `app/routers/auth.py` (`APIRouter(prefix="/auth", tags=["auth"])`) (depende de T030):
  - `POST /auth/registro` (`response_model=UsuarioLeer`, **201**): llama a `registrar_usuario`; `EmailYaRegistradoError` → 400.
  - `POST /auth/login` (`response_model=Token`, **200**): recibe `OAuth2PasswordRequestForm` (`username` = email, `password`), llama a `autenticar_usuario`, responde `Token(access_token=..., token_type="bearer")`; credenciales inválidas → 401 «Credenciales incorrectas» (con `WWW-Authenticate: Bearer`).
- [X] T032 [P] [US2] Crear `app/routers/reservas.py` (`APIRouter(prefix="/reservas", tags=["reservas"])`, todas las rutas con `Depends(get_current_user)` → 401 sin token, FR-006) con: `POST /reservas/` (`ReservaCrear` → **201** `ReservaLeer`, `usuario_id=usuario.id` tomado del JWT, nunca del cuerpo); `GET /reservas/` con `skip: int = Query(SKIP_MINIMO, ge=SKIP_MINIMO)` y `limit: int = Query(LIMITE_POR_DEFECTO, ge=LIMITE_MINIMO, le=LIMITE_MAXIMO)` (constantes importadas de `app/services/reservas.py`, T026) (**200** `list[ReservaLeer]`); `GET /reservas/{reserva_id}` (**200**). Cada ruta llama al servicio de T025/T026 y traduce con `traducir_excepcion`.
- [X] T033 [US3] En el mismo `app/routers/reservas.py` (depende de T032) añadir `PUT /reservas/{reserva_id}` (`ReservaActualizar` → **200** `ReservaLeer`, llama a `actualizar_reserva`) y `DELETE /reservas/{reserva_id}` (**204** sin cuerpo; llama a `eliminar_reserva(..., confirmar=True)` de forma **explícita**: el propio verbo `DELETE` es la acción explícita, research R11).
- [X] T034 Crear `app/main.py` (depende de T031, T033) con una **fábrica** `crear_app() -> FastAPI`: `FastAPI(title="API de reservas", lifespan=...)` cuyo `lifespan` ejecuta `crear_tablas()` al arrancar (importando `app.models` para registrar las tablas), e incluye `auth.router` y `reservas.router`; y al final del módulo `app = crear_app()` (es lo que carga `uvicorn app.main:app`). **No** monta MCP todavía (T041). Comprobar `uv run uvicorn app.main:app --port 8000` y que `/docs` lista los 7 endpoints REST.

**Checkpoint**: la API REST (US1, US2, US3) funciona de extremo a extremo con SQLite real; MVP REST utilizable.

---

## Phase 8: MCP (`app/mcp/`, `app/utils/`) — Historia 4

**Purpose**: segunda vía de acceso. Cada tool llama a la **misma función de `services/`** que su endpoint (Art. VI.1), resuelve el usuario con el JWT del header y devuelve `{"error": "..."}` en lugar de excepciones (Art. VI.3).

- [X] T035 [P] [US4] Crear `app/utils/fechas.py`: `parsear_fecha(texto: str) -> date` (formato `YYYY-MM-DD`), `parsear_hora(texto: str) -> time` (formato `HH:MM`), ambos lanzan `ValueError` con mensaje en español si el formato no es válido (formato estricto: `09:00:30` y `9:00` se rechazan); los reutilizan también los schemas de reserva (T016), de modo que REST y MCP aceptan exactamente el mismo formato; y `reserva_a_dict(reserva) -> dict` que devuelve `{"id": int, "fecha": "YYYY-MM-DD", "hora_inicio": "HH:MM", "hora_fin": "HH:MM"}`. Es conversión de formato, **no** lógica de negocio (Art. I.2, research R10).
- [X] T036 [P] [US4] Crear `tests/unit/test_fechas.py` (depende de T035): formatos válidos; `"15/01/2030"`, `"2030-13-01"`, `"9:00 AM"`, `"25:00"`, `"09:00:30"`, `"9:00"`, `""` → `ValueError`; `reserva_a_dict` con una `Reserva` en memoria (sin BD) devuelve horas `HH:MM`.
- [X] T037 [US4] Crear `app/mcp/autenticacion.py`: `obtener_usuario_desde_contexto(ctx: Context, db) -> Usuario` que lee `ctx.request_context.request.headers.get("authorization")` (`request` puede ser `None`), extrae el token solo si el esquema es `Bearer` (insensible a mayúsculas) y llama a **`services.auth.obtener_usuario_actual`** (la misma función que REST); cualquier fallo → `NoAutenticadoError` (research R3, R4). Sin usuario fijo (Art. VI.6).
- [X] T038 [US4] Crear `app/mcp/server.py` (depende de T035, T037) con una **fábrica** `crear_servidor_mcp() -> FastMCP` que construye `FastMCP("reservas", stateless_http=True, json_response=True, streamable_http_path="/mcp")` (importar con `from mcp.server.fastmcp import FastMCP, Context`, **import absoluto**), registra los tools dentro de la función y devuelve el servidor. Una instancia nueva por app: `StreamableHTTPSessionManager.run()` solo puede ejecutarse una vez por instancia (research R3.3). Primer tool, dentro de la fábrica: **`crear_reserva(ctx: Context, fecha: str, hora_inicio: str, hora_fin: str) -> dict`**:
  - Abre sesión con `abrir_sesion()`, resuelve el usuario (T037), convierte los textos con `utils/fechas.py` y llama a `services.reservas.crear_reserva` (misma función que `POST /reservas/`).
  - Éxito → `reserva_a_dict(reserva)`. `ErrorDeDominio` → `{"error": str(exc)}`; `ValueError` de formato → `{"error": "Formato de fecha u hora inválido: use YYYY-MM-DD y HH:MM"}`. Nunca propaga excepciones (Art. VI.3).
  - Docstring (es la descripción publicada) según [contracts/mcp-tools.md](contracts/mcp-tools.md): parámetros con formato `YYYY-MM-DD` / `HH:MM`, reglas (fin posterior a inicio sin cruzar medianoche, no en el pasado, sin solapar; contiguas permitidas) y errores posibles (Art. VI.4).
- [X] T039 [US4] En la fábrica `crear_servidor_mcp()` de `app/mcp/server.py` (depende de T038) añadir el tool **`listar_reservas(ctx: Context, skip: int = SKIP_MINIMO, limit: int = LIMITE_POR_DEFECTO) -> dict`**: valida `skip >= SKIP_MINIMO` y `LIMITE_MINIMO <= limit <= LIMITE_MAXIMO` con las **constantes de `services/reservas.py`** (T026; los mismos límites que REST, sin números repetidos aquí; si no → `{"error": "Parámetros de paginación inválidos: skip >= 0 y 1 <= limit <= 100"}`, mensaje construido con esas constantes), llama a `services.reservas.listar_reservas` y devuelve `{"reservas": [reserva_a_dict(r), ...]}`; sin token → `{"error": "No autenticado"}`. Docstring con parámetros, valores por defecto, orden (fecha y hora de inicio), solo las propias y errores posibles.
- [X] T040 [US4] En la fábrica `crear_servidor_mcp()` de `app/mcp/server.py` (depende de T039) añadir el tool **`cancelar_reserva(ctx: Context, reserva_id: int, confirmar: bool = False) -> dict`** **(RN-6, RN-3)**: llama a `services.reservas.eliminar_reserva(..., confirmar=confirmar)` (la misma función que `DELETE`); éxito → `{"mensaje": f"Reserva {reserva_id} cancelada"}`; `ErrorDeDominio` → `{"error": str(exc)}` (incluye `ConfirmacionRequeridaError`: **no se elimina nada**). La confirmación la valida el servidor, nunca depende del asistente (Art. VI.5). Docstring que advierta que es destructiva, exija `confirmar=true` e indique los errores posibles.
- [X] T041 [US4] Actualizar `crear_app()` en `app/main.py` (depende de T034 y T040): crear `mcp = crear_servidor_mcp()` **dentro** de `crear_app()`; el `lifespan` (cierre sobre ese `mcp`) debe envolver la app con `async with mcp.session_manager.run():` (FastAPI no ejecuta el lifespan de la sub-app montada, research R3.3) además de `crear_tablas()`; y como **último** registro de la app (después de los routers REST, o taparía sus rutas) ejecutar `app.mount("/", mcp.streamable_http_app())`. Comprobar que `POST http://localhost:8000/mcp` responde y que `/docs` y `/auth/login` siguen funcionando.

**Checkpoint**: los tres tools MCP funcionan con el mismo JWT que REST.

---

## Phase 9: Tests de integración y de API

**Purpose**: comprobar las capas reales juntas: SQLite real (Art. VII.4), y `TestClient` para 401, 403 y 404 (Art. VII.5), más el acceso MCP.

- [X] T042 Ampliar `tests/conftest.py` (depende de T007, T041) con fixtures: `db_url` (archivo SQLite temporal `tmp_path / "test.db"`); `motor_temporal` (llama a `configurar_motor(db_url)` y `crear_tablas()`, y al terminar deja limpio); `client` (de alcance función y **dependiente de `motor_temporal`**: `with TestClient(crear_app(), base_url="http://localhost:8000") as c: yield c`, como **context manager** para ejecutar el lifespan y el `session_manager` de MCP; una `crear_app()` nueva por test, porque el `session_manager` no puede ejecutarse dos veces (research R3.3); el `base_url` con puerto es obligatorio: el SDK devuelve 421 con otro `Host`, research R3.5); y helpers `registrar_y_autenticar(client, email) -> dict` (cabecera `{"Authorization": "Bearer ..."}`) y `fecha_futura()` (p. ej. hoy + 30 días, en formato `YYYY-MM-DD`). Sin `unittest.mock`.
- [X] T043 [P] Crear `tests/integration/test_reservas_sqlite.py` (depende de T042) — **repositories y servicios reales contra un SQLite real (archivo temporal), sin fakes** (Art. VII.4): ciclo crear → solapar → listar → obtener → modificar → eliminar; **matriz de solapamiento de `data-model.md` verificada contra SQL real** (09:00–10:00 vs 10:00–11:00 y a la inversa → no solapa; idéntica, contenida, que contiene y parcial → solapa; mismo horario otra fecha → no solapa), porque aquí se prueba con datos reales que `listar_por_fecha` de T020 devuelve las reservas correctas y que la fórmula de T025 las clasifica bien; al modificar, el servicio ignora la propia reserva (RN-4, T027); `listar_por_fecha` devuelve solo las reservas de esa fecha y de **cualquier** usuario, y el solapamiento se detecta contra reservas de cualquier usuario; `listar_por_usuario` solo devuelve las del usuario y respeta `skip`/`limit` y el orden `fecha, hora_inicio, id`; `existe` devuelve `True`/`False` sin filtrar por dueño; `email` duplicado viola la restricción UNIQUE; la FK rechaza un `usuario_id` inexistente (`PRAGMA foreign_keys=ON`); el hash de contraseña guardado no es la contraseña.
- [X] T044 [P] [US1] Crear `tests/api/test_auth_api.py` (depende de T042): registro válido → 201 y el cuerpo **no contiene** `password` ni `password_hash` (FR-004, SC-004); email duplicado → 400 (RN-5); email inválido, contraseña corta o de 73 bytes → 422; registrar `Usuario@X.com` y luego `usuario@x.com` → 400 (RN-5), y el cuerpo del 201 trae el email en minúsculas; login con otra combinación de mayúsculas → 200; login correcto → 200 con `access_token` y `token_type == "bearer"`; contraseña incorrecta y email inexistente → 401.
- [X] T045 [P] [US2] Crear `tests/api/test_reservas_401.py` (depende de T042) — **caso 401 obligatorio**: `GET /reservas/`, `POST /reservas/`, `GET/PUT/DELETE /reservas/1` **sin token** → 401; con token inválido (basura) → 401; con token firmado con otra clave → 401; con token expirado → 401; la respuesta incluye `WWW-Authenticate: Bearer`.
- [X] T046 [P] [US3] Crear `tests/api/test_reservas_403.py` (depende de T042) — **caso 403 obligatorio (RN-3)**: el usuario A crea una reserva; el usuario B, con su token válido, hace `GET`, `PUT` y `DELETE` sobre `/reservas/{id_de_A}` → 403 en los tres; la reserva de A **sigue intacta** (verificado con el token de A) y el cuerpo del 403 no revela datos de A (SC-002).
- [X] T047 [P] [US3] Crear `tests/api/test_reservas_404.py` (depende de T042) — **caso 404 obligatorio**: `GET`, `PUT` y `DELETE` sobre un id inexistente (p. ej. 9999) con token válido → 404; y comprobar que inexistente da 404 mientras la reserva ajena da 403 (no se confunden).
- [X] T048 [P] [US2] Crear `tests/api/test_reservas_api.py` (depende de T042) — flujos REST con `fecha_futura()`: crear → 201 con `usuario_id` del JWT (aunque el cliente envíe otro `usuario_id` en el cuerpo, se ignora); solapada → 400 (RN-1); **contigua → 201**; `23:00→01:00` y `fin == inicio` → 400 (RN-2); fecha de ayer → 400 (RN-7); formatos inválidos → 422 (incluido `hora_inicio: "09:00:30"`); `PUT` propio a horario libre → 200, ampliar propia → 200, solapar con otra → 400, inicio pasado → 400 (RN-4); `DELETE` propio → 204 y ya no aparece en el listado; listado con `skip`/`limit` y `limit=0` o `skip=-1` → 422; `skip` mayor que el total → `[]`.
- [X] T049 [P] [US4] Crear `tests/api/test_mcp.py` (depende de T042): llamadas JSON-RPC a `POST /mcp` con cabeceras `Accept: application/json, text/event-stream` y `Authorization: Bearer <token>` (`tools/call`): `crear_reserva` OK y con horario solapado/horas inválidas/fecha pasada/formato inválido → `{"error": ...}` con el **mismo mensaje** que el `detail` REST (FR-025, SC-006); `listar_reservas` devuelve solo las propias y respeta `skip`/`limit`; **`cancelar_reserva` sin `confirmar` → `{"error": "Confirmación requerida…"}` y la reserva sigue existiendo (`GET /reservas/{id}` → 200)** (caso obligatorio 7, SC-005); con `confirmar=true` y reserva propia → elimina (`GET` → 404); reserva ajena o inexistente → `{"error": ...}` y no se elimina; **sin cabecera `Authorization` o con token inválido, los tres tools → `{"error": "No autenticado"}`** y no se ejecuta ninguna operación (SC-003).

**Checkpoint**: las tres capas de tests (unit, integration, api) pasan.

---

## Phase 10: Verificación final

**Purpose**: comprobar las restricciones de la Constitución y los criterios de éxito.

- [X] T050 Comprobar las restricciones estáticas de la Constitución (ver [quickstart.md](quickstart.md) §6): `grep -rn "unittest.mock\|from mock\|MagicMock" tests/ app/` sin resultados (Art. VII.2); todas las dependencias de `pyproject.toml` con `==` y coinciden con `uv.lock` (Art. VII.6); `git check-ignore .env` imprime `.env` y `.env.example` sí está versionado (Art. IV.4); ningún secreto hardcodeado (`grep -rn "SECRET_KEY\s*=" app/` solo en `config.py` como campo sin valor); ninguna capa importa de una capa superior (`grep` de `from app.routers`/`from app.mcp` dentro de `app/services/`, `app/repositories/`, `app/models/` y `app/core/` sin resultados, Art. I.5); ningún `router`/`tool` contiene reglas de negocio (revisión visual de `app/routers/` y `app/mcp/`, Art. I.2).
- [X] T051 Ejecutar la validación de [quickstart.md](quickstart.md) §3–§5 contra el servidor real (`uv run uvicorn app.main:app --port 8000`): registro, login, reservas (201, contigua 201, solapada 400, horas inválidas 400, fecha pasada 400, 401, 403, 404) y las llamadas MCP (cancelar sin confirmar, con confirmar, sin token). Anotar cualquier diferencia con lo esperado y corregirla en el código, no en el contrato.
- [X] T052 **Verificación final de cobertura** (depende de todas las anteriores): ejecutar `uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=70` y `uv run coverage report --include="app/services/*" --fail-under=90`. Criterios de aceptación: **todos los tests pasan; cobertura global ≥ 70 % y `app/services/` ≥ 90 %** (Art. VII.3). Si falla algún umbral, añadir tests de las líneas en `term-missing` (empezando por `services/`) y repetir. Confirmar además que hay al menos una prueba por cada RN-1…RN-7, la de contiguas y los 8 casos de error de la spec (SC-008), con la tabla de trazabilidad de abajo. Copiar el resumen de cobertura al mensaje de cierre.

---

## Trazabilidad: regla de negocio → tarea de servicio → test

| Regla | Descripción | Implementa | Test unitario (repo falso) | Test contra BD/API |
|-------|-------------|------------|----------------------------|--------------------|
| RN-1 | Sin solapamiento (cualquier usuario) | T025 | T025 `test_reservas_crear.py` | T043, T048 |
| Contiguas | Una termina cuando empieza la otra: permitidas | T025 | T025 (test propio, ambos órdenes) | T043, T048 |
| RN-2 | `hora_fin > hora_inicio`, sin cruzar medianoche | T025 | T025 | T048 |
| RN-3 | Solo el dueño (403); inexistente (404) | T026, T027, T028 | T026, T027, T028 | T046, T047, T049 |
| RN-4 | Modificar re-aplica RN-1/2/7 sin contarse a sí misma | T027 | T027 `test_reservas_actualizar.py` | T043, T048 |
| RN-5 | Email único | T023 | T023 `test_auth_registro.py` | T043, T044 |
| RN-6 | Cancelar exige `confirmar=true` (servidor) | T028 | T028 `test_reservas_eliminar.py` | T049 |
| RN-7 | No crear/modificar en el pasado | T025, T027 | T025, T027 (`ahora` inyectado) | T048 |

Los 8 casos de error de la spec: (1) solapada → T025/T048; (2) horas → T025/T048; (3) 401 → T045/T049; (4) 403 → T046; (5) 404 → T047; (6) email duplicado → T023/T044; (7) cancelar sin confirmar → T028/T049; (8) fecha pasada → T025/T027/T048.

---

## Dependencies & Execution Order

### Orden de fases (estricto por capas)

```
Setup (T001-T007) → Core (T008-T011) → Models (T012-T014) → Schemas (T015-T017)
   → Repositories (T018-T020) → Services (T021-T029) → Routers + main (T030-T034)
   → MCP (T035-T041) → Tests integración y API (T042-T049) → Verificación (T050-T052)
```

Cada fase depende de la anterior; no se empieza una capa hasta que la inferior esté completa (un solo sentido de dependencias, Art. I.5).

### Dependencias entre tareas relevantes

- T003 ← T002; T006 ← T004, T005; T009, T010 ← T008; T014 ← T012, T013.
- T022 (fakes) ← T018 (Protocols) y T021 (excepciones); todos los tests de servicios ← T022.
- Cadenas en el **mismo archivo** (secuenciales, sin `[P]`): `services/auth.py` (T023 → T024), `services/reservas.py` (T025 → T026 → T027 → T028), `routers/reservas.py` (T032 → T033), `mcp/server.py` (T038 → T039 → T040), `main.py` (T034 → T041), `tests/conftest.py` (T007 → T042).
- T030 (dependencias de routers) ← T024 (auth) y T021; T032/T033 ← T025–T028.
- T038 ← T035, T037; T041 ← T040; T042 ← T041 (el cliente necesita la app completa con MCP montado).
- T016 ← T035 (`utils` es transversal: ejecutar T035 antes de T016, aunque T035 esté numerada en la fase MCP).

### Oportunidades de paralelismo

- Setup: T004 y T005 (y T007) en paralelo con T002.
- Core: T009 y T010 en paralelo tras T008; T011 tras T010.
- Models: T012 y T013 en paralelo. Schemas: T015 y T016 en paralelo. Repositories: T019 y T020 en paralelo.
- Services: la cadena de `auth.py` (T023–T024) y la de `reservas.py` (T025–T028) son independientes entre sí (tras T021 y T022).
- Routers: T031 (`auth.py`) y T032 (`reservas.py`) en paralelo tras T030.
- MCP: T035/T036 (utils) en paralelo con T037.
- Tests de integración/API (T043–T049): todos en paralelo tras T042 (archivos distintos).

### Ejemplo de paralelismo (Phase 9)

```text
# Tras T042 (conftest con fixtures):
Task: "tests/integration/test_reservas_sqlite.py (SQLite real)"          # T043
Task: "tests/api/test_auth_api.py"                                        # T044
Task: "tests/api/test_reservas_401.py"                                    # T045
Task: "tests/api/test_reservas_403.py"                                    # T046
Task: "tests/api/test_reservas_404.py"                                    # T047
Task: "tests/api/test_reservas_api.py"                                    # T048
Task: "tests/api/test_mcp.py"                                             # T049
```

---

## Implementation Strategy

### Entrega incremental (respetando el orden por capas)

1. **Setup + Core + Models + Schemas + Repositories** (T001–T020): base sin comportamiento visible.
2. **Services con sus tests unitarios** (T021–T029): la lógica de negocio queda completa y probada de forma aislada, con `services/` ≥ 90 % desde aquí.
3. **Routers + `main.py`** (T030–T034): **MVP REST** — US1 (registro/login) y US2 (crear/consultar), más US3 (modificar/eliminar). Punto de parada útil para validar con `uvicorn` y `/docs`.
4. **MCP** (T035–T041): US4 sobre las mismas reglas.
5. **Tests de integración y API** (T042–T049) y **verificación** (T050–T052).

### Notas

- Implementar **una tarea a la vez** (Constitución, «Flujo de Trabajo del Agente»). Si una tarea exige desviarse de un artículo, declararlo y esperar aprobación; nunca decidirlo en silencio.
- Verificar el test unitario de cada tarea de servicio antes de pasar a la siguiente.
- Hacer commit tras cada tarea o grupo lógico; `.env` jamás se versiona.
- Evitar: lógica de negocio en routers/tools, `unittest.mock`, el reloj real en tests de RN-7, y consultas de datos de `Reserva` sin filtro por `usuario_id` fuera de las dos excepciones del Art. III.3 (`listar_por_fecha`, `existe`).
