# Implementation Plan: Reservas de una sala compartida

**Branch**: `001-reservas-sala` (directorio de feature; la rama git actual es `master`) | **Date**: 2026-09-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-reservas-sala/spec.md`

## Summary

API de reservas de una única sala compartida: registro/login (OAuth2 + JWT) y CRUD de
reservas propias con siete reglas de negocio (RN-1…RN-7), expuesta por **REST** (FastAPI) y
por **MCP** (FastMCP, streamable HTTP montado en `/mcp` en la misma app). Ambas vías llaman a
las mismas funciones de `services/`, que contienen todas las reglas; los routers y los tools
solo traducen entrada y errores. Persistencia con SQLAlchemy 2 sobre SQLite. Las reglas se
prueban con repositories falsos en memoria y un «ahora» inyectable, sin `unittest.mock`.

Detalle de las decisiones verificadas: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13 (`requires-python = ">=3.13"`), gestionado con `uv` (`pyproject.toml` + `uv.lock`)

**Primary Dependencies** (versiones **exactas**, resueltas con `uv lock --python 3.13` el 2026-09-26; ver [research.md](research.md) R1):
`fastapi==0.141.1`, `uvicorn==0.54.0`, `sqlalchemy==2.1.1`, `pydantic==2.13.5`,
`pydantic-settings==2.15.0`, `pyjwt==2.15.0`, `bcrypt==5.0.0`, `mcp==1.30.0` (**no** 2.x: ver
R2), `python-multipart==0.0.32`, `email-validator==2.3.0`.
Grupo dev: `pytest==9.1.1`, `pytest-cov==7.1.0`, `httpx==0.28.1`.

**Storage**: SQLite, archivo `reservas.db` (`DATABASE_URL=sqlite:///./reservas.db`); tablas creadas con `create_all` (sin migraciones)

**Testing**: pytest + pytest-cov + httpx (`TestClient`); repositories falsos en memoria; SQLite temporal para integración

**Target Platform**: servidor local (`uvicorn app.main:app`, `localhost:8000`); desarrollo en Windows, código portable

**Project Type**: web-service (monolito modular por capas; un solo proyecto)

**Performance Goals**: no se fijan objetivos numéricos; uso ligero y mayormente secuencial (spec, supuestos). Un usuario nuevo completa registro → login → primera reserva en < 2 min (SC-007)

**Constraints**: reglas de negocio solo en `services/` (Art. I); un solo sentido de dependencias; sin `unittest.mock`; secretos solo en `.env`; solicitudes simultáneas por el mismo horario **no** protegidas (limitación aceptada en la spec); MCP solo accesible con `Host` localhost (R3)

**Scale/Scope**: una sala, sin roles, 2 entidades (Usuario, Reserva), 7 endpoints REST + 3 tools MCP

## Constitution Check

*GATE: debe pasar antes de la Fase 0 y se reevalúa tras el diseño de la Fase 1.*

Resultado: **PASA**. La única desviación (Art. III.3, `existe -> bool`) fue **aprobada** y la
Constitución se enmendó a la versión 1.1.0 (ver «Complexity Tracking»). Para cada artículo, la
decisión del plan que lo cumple:

### Art. I — Arquitectura en capas — ✅

| Regla | Decisión del plan que la cumple |
|-------|---------------------------------|
| I.1 estructura obligatoria | Se crea exactamente `app/routers/`, `app/mcp/`, `app/services/`, `app/repositories/`, `app/models/`, `app/schemas/`, `app/utils/` y `app/core/` (Project Structure). |
| I.2 routers/mcp sin reglas | Routers y tools solo parsean entrada, llaman a un servicio y traducen excepciones (decisión 3). El parseo de texto → `date`/`time` de MCP vive en `utils/fechas.py` y no es regla de negocio (R10). |
| I.3 reglas en services | RN-1…RN-7 (y unicidad de email, propiedad, confirmación) están en `services/reservas.py` y `services/auth.py`. |
| I.4 repositories | Solo `crear/listar/obtener/existe/listar_por_fecha/actualizar/eliminar`; la sesión es el primer parámetro; sin validaciones (data-model.md, «Contrato del repository»). |
| I.5 un sentido | `routers`/`mcp` → `services` → `repositories` → `models`; `core`, `schemas` y `utils` son transversales y no importan capas superiores (`core/` no importa `services/`; por eso `decodificar_token` devuelve `int \| None` y la excepción se lanza en `services/auth.py`, R4). |

### Art. II — SOLID y Repository — ✅

| Regla | Decisión del plan que la cumple |
|-------|---------------------------------|
| II.1 DIP | Decisión 1: cada función de servicio recibe `repo` como parámetro con la instancia real como **valor por defecto** (`repo=reserva_repository`); nunca se importa fijo dentro del cuerpo. `Protocol`s en `repositories/base.py`. |
| II.2 excepción por regla | Decisión 2: las siete excepciones pedidas, en `services/excepciones.py`. Se añade `NoAutenticadoError` (auth, no regla de negocio; ver data-model.md). |
| II.3 responsabilidad única | Un módulo por responsabilidad: `services/reservas.py` (reservas), `services/auth.py` (registro/login/usuario actual), `core/security.py` (hash y JWT), `core/database.py` (motor/sesión), `core/config.py` (ajustes). |

### Art. III — Persistencia — ✅

| Regla | Decisión del plan que la cumple |
|-------|---------------------------------|
| III.1 ORM + sesión inyectada | SQLAlchemy 2.1; `get_db()` se inyecta con `Depends` en REST y `abrir_sesion()` (misma `SessionLocal`) en MCP. |
| III.2 schemas separados | `schemas/` independientes de `models/`; `UsuarioLeer` y `Token` no contienen contraseña ni hash. |
| III.3 `usuario_id` y filtro | `Reserva.usuario_id` es FK. Lectura/listado/borrado siempre con dueño (`listar_por_usuario`, `obtener_de_usuario`). Sin filtro solo `listar_por_fecha` (para el solapamiento) y `existe -> bool` (necesario para distinguir 403/404, R9), las dos excepciones que recoge expresamente el Art. III.3 desde la versión 1.1.0. |

### Art. IV — Seguridad — ✅

| Regla | Decisión del plan que la cumple |
|-------|---------------------------------|
| IV.1 OAuth2 + JWT, email único | `OAuth2PasswordBearer` + `POST /auth/login` (formulario) con PyJWT; modelo `Usuario` propio con `email` UNIQUE. |
| IV.2 bcrypt, sin logs | `bcrypt` directo (`hashpw/checkpw`) en `core/security.py`; solo se guarda `password_hash`; contraseña acotada a 72 bytes para evitar el `ValueError` de bcrypt 5 (R5); no se loguea. |
| IV.3 secretos en `.env` | `pydantic-settings` (`core/config.py`) lee `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `DATABASE_URL`; **sin valores por defecto** en código (decisión 6). |
| IV.4 `.env` ignorado | Decisión 6: `.env` en `.gitignore`; `.env.example` versionado, sin valores reales, documentando las cuatro variables. |
| IV.5 401 sin token | Todas las rutas `/reservas/*` dependen de `get_current_user`; fallo → 401 (test de API). |
| IV.6 usuario del JWT | El `usuario_id` solo sale de `get_current_user` (REST) o de la cabecera Bearer (MCP); ningún schema ni parámetro lo acepta. |

### Art. V — Convención REST — ✅

| Regla | Decisión del plan que la cumple |
|-------|---------------------------------|
| V.1 recursos en plural/español | `/reservas/`, `/auth/registro`, `/auth/login` ([rest-api.md](contracts/rest-api.md)). |
| V.2 códigos de estado | Tabla de endpoints con 201/200/204/400/401/403/404/422 del contrato. |
| V.3 `HTTPException` | Decisión 3: los routers traducen cada excepción de dominio a `HTTPException` con `detail` claro (tabla de traducción). |
| V.4 CRUD completo | POST, GET lista (`skip`, `limit`), GET por id, PUT y DELETE. |

### Art. VI — MCP — ✅

| Regla | Decisión del plan que la cumple |
|-------|---------------------------------|
| VI.1 tools → services | Cada tool llama a la misma función que su endpoint: `crear_reserva`, `listar_reservas`, `eliminar_reserva` (esta última la comparten `DELETE` y `cancelar_reserva`). |
| VI.2 ≥ 3 tools | `crear_reserva`, `listar_reservas`, `cancelar_reserva` ([mcp-tools.md](contracts/mcp-tools.md)). |
| VI.3 `{"error": ...}` | Decisión 3: los tools capturan las excepciones de dominio y devuelven `{"error": "..."}`; argumentos recibidos como `str` para que un formato inválido también sea `{"error"}` (R10). |
| VI.4 descripciones | Docstrings con parámetros, formatos `YYYY-MM-DD`/`HH:MM`, reglas y errores posibles ([mcp-tools.md](contracts/mcp-tools.md)). |
| VI.5 confirmación en servidor | `eliminar_reserva(..., confirmar)` lanza `ConfirmacionRequeridaError` antes de tocar la BD; `confirmar` por defecto `False` en el tool (R11). |
| VI.6 identidad = JWT | Streamable HTTP montado en `/mcp`; el tool lee `Authorization: Bearer` y usa `obtener_usuario_actual`, la misma función que REST; verificado con un spike (R3, R4). Sin token → `{"error": "No autenticado"}`. No hay usuario fijo ni limitación pendiente de documentar. |

### Art. VII — Testing — ✅

| Regla | Decisión del plan que la cumple |
|-------|---------------------------------|
| VII.1 test por regla | Decisión 5: un test unitario por RN-1…RN-7 más el de contiguas (tabla «Estrategia de tests»). |
| VII.2 repo falso, sin mock | `tests/unit/fakes.py` con repositories en memoria inyectados por parámetro; `unittest.mock` prohibido y verificado con `grep` en el quickstart. |
| VII.3 cobertura | `pytest --cov=app --cov-report=term-missing --cov-fail-under=70` y `coverage report --include="app/services/*" --fail-under=90` (R12). |
| VII.4 integración SQLite real | `tests/integration/` con archivo SQLite temporal (`tmp_path`) y repositories reales. |
| VII.5 tests de API | `tests/api/` con `TestClient`: 401, 403 y 404 (además de flujos MCP). |
| VII.6 versiones fijadas | Todas las dependencias con `==` en `pyproject.toml` (Technical Context) y `uv.lock` versionado. |

## Decisiones de diseño obligatorias (petición del plan)

1. **DIP + «ahora» inyectable.** Firmas de servicio: `crear_reserva(db, usuario_id, fecha,
   hora_inicio, hora_fin, *, ahora=None, repo=reserva_repository)`; `actualizar_reserva(db,
   usuario_id, reserva_id, fecha, hora_inicio, hora_fin, *, ahora=None, repo=…)`. `ahora=None`
   → `datetime.now()`; los tests pasan un `datetime` fijo (R7).
2. **Excepciones de dominio**: `ReservaSolapadaError`, `HorarioInvalidoError`,
   `FechaPasadaError`, `ReservaNoEncontradaError`, `NoEsDuenoError`,
   `EmailYaRegistradoError`, `ConfirmacionRequeridaError` (+ `NoAutenticadoError`).
3. **Traducción**: routers → `HTTPException`; tools MCP → `{"error": "..."}`.
4. **Solapamiento**: `inicio_nueva < fin_existente AND fin_nueva > inicio_existente`
   (contiguas permitidas), evaluada **íntegramente en `services/reservas.py`** (RN-1) sobre las
   reservas que devuelve `repo.listar_por_fecha(fecha)` (de cualquier usuario). Al modificar,
   el servicio excluye la propia reserva (RN-4). El repository no contiene la fórmula.
5. **Tests**: unitarios con repo falso; integración con SQLite real; API para 401/403/404.
6. **Entorno**: `.env.example` con las cuatro variables; `.env` en `.gitignore` (hoy no existe
   `.gitignore` en la raíz; se crea, incluyendo `.env`, `.venv/`, `*.db`, `__pycache__/`,
   `.pytest_cache/`, `.coverage`).

Orden de validación al crear/modificar (R8): existencia/propiedad → RN-2 → RN-7 → RN-1.

## Estrategia de tests

| Test | Nivel | Verifica |
|------|-------|----------|
| RN-1 solapamiento (idéntica, contenida, que contiene, parcial) | unit | `ReservaSolapadaError` con repo falso |
| **Contiguas** (10:00 fin / 10:00 inicio, en ambos órdenes) | unit | se aceptan; prueba independiente |
| RN-2 `fin <= inicio`, incluido 23:00→01:00 | unit | `HorarioInvalidoError` |
| RN-3 reserva ajena / inexistente | unit | `NoEsDuenoError` / `ReservaNoEncontradaError` |
| RN-4 modificar: excluye a sí misma; re-aplica RN-1/2/7 | unit | ampliar propia OK; solapar otra → error |
| RN-5 email duplicado | unit | `EmailYaRegistradoError` |
| RN-6 cancelar sin `confirmar` | unit | `ConfirmacionRequeridaError`, sin borrar |
| RN-7 inicio pasado (con `ahora` fijo; borde `== ahora` se acepta) | unit | `FechaPasadaError` |
| Ciclo completo con SQLite real (crear → solapar → listar → modificar → borrar; filtro por usuario) | integración | repositories reales sobre archivo temporal |
| 401 sin token / token inválido en `/reservas/` | api | 401 |
| 403 reserva de otro (GET/PUT/DELETE) | api | 403 |
| 404 reserva inexistente (GET/PUT/DELETE) | api | 404 |
| MCP: sin token → «No autenticado»; cancelar sin confirmar no borra; cancelar confirmando borra | api | `TestClient(base_url="http://localhost:8000")` |

## Project Structure

### Documentation (this feature)

```text
specs/001-reservas-sala/
├── plan.md              # Este archivo (/speckit-plan)
├── research.md          # Fase 0
├── data-model.md        # Fase 1
├── quickstart.md        # Fase 1
├── contracts/           # Fase 1
│   ├── rest-api.md
│   └── mcp-tools.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Fase 2 (/speckit-tasks — NO lo crea /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml           # uv; requires-python >=3.13; dependencias con ==; config de pytest/coverage
uv.lock
.env.example             # SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, DATABASE_URL
.gitignore               # incluye .env

app/
├── main.py              # crea FastAPI, lifespan (create_all + mcp.session_manager.run()), incluye routers, monta MCP en "/" al final
├── core/
│   ├── config.py        # Settings (pydantic-settings), get_settings()
│   ├── security.py      # hash/verify bcrypt; crear_token/decodificar_token (PyJWT)
│   └── database.py      # motor, SessionLocal, Base, get_db(), abrir_sesion(), configurar_motor()
├── models/
│   ├── usuario.py       # Usuario
│   └── reserva.py       # Reserva (FK usuario_id)
├── schemas/
│   ├── usuario.py       # UsuarioCrear, UsuarioLeer, Token
│   └── reserva.py       # ReservaCrear, ReservaActualizar, ReservaLeer
├── repositories/
│   ├── base.py          # Protocols
│   ├── reserva_repository.py   # ReservaRepository + reserva_repository
│   └── usuario_repository.py   # UsuarioRepository + usuario_repository
├── services/
│   ├── excepciones.py   # excepciones de dominio
│   ├── reservas.py      # crear/listar/obtener/actualizar/eliminar (RN-1..4, 6, 7)
│   └── auth.py          # registrar_usuario (RN-5), autenticar, obtener_usuario_actual
├── routers/
│   ├── dependencias.py  # oauth2_scheme, get_current_user (usa services/auth)
│   ├── auth.py          # /auth/registro, /auth/login
│   └── reservas.py      # /reservas/
├── mcp/
│   ├── server.py        # FastMCP + tools crear_reserva, listar_reservas, cancelar_reserva
│   └── autenticacion.py # Bearer de la cabecera -> usuario (misma función que REST)
└── utils/
    └── fechas.py        # parseo YYYY-MM-DD / HH:MM y formato de salida MCP

tests/
├── conftest.py          # variables de entorno de prueba, fixtures de BD/cliente
├── unit/                # fakes.py + tests de RN-1..RN-7 y contiguas
├── integration/         # SQLite real (archivo temporal)
└── api/                 # TestClient: 401, 403, 404 y MCP
```

**Structure Decision**: un único proyecto (monolito modular) con la estructura exacta que exige
el Art. I. `app/mcp/` se llama así por mandato de la Constitución y se importa como `app.mcp.server`; el
SDK sigue siendo el paquete `mcp` de nivel superior (`from mcp.server.fastmcp import FastMCP`).
No hay colisión mientras la raíz del repo —y no `app/`— sea lo que está en `sys.path`
(`uvicorn app.main:app` y pytest desde la raíz).

## Complexity Tracking

> Desviaciones e interpretaciones que el Art. «Flujo de Trabajo del Agente» obliga a declarar.

| Punto | Por qué es necesario | Alternativa más simple rechazada porque |
|-------|----------------------|------------------------------------------|
| **Art. III.3**: `ReservaRepository.existe(db, reserva_id) -> bool` consulta por id sin filtrar por `usuario_id` (solo devuelve un booleano, ningún dato). **Desviación aprobada** por el usuario el 2026-09-26: la Constitución se enmendó a la versión 1.1.0 y el Art. III.3 incluye ahora esta excepción de forma expresa. | La spec (FR-014/015) y el Art. V.2 exigen 404 para inexistente y 403 para ajena; sin esta comprobación no se pueden distinguir. Los datos de la reserva solo se leen con `obtener_de_usuario` (filtrado). | Responder 404 también para reservas ajenas evita la consulta, pero incumple FR-014, el contrato 403 y el test obligatorio nº 4 de la spec. |
| `mcp==1.30.0` en lugar de la última (2.2.0) | 2.x eliminó `FastMCP` (R2); la petición exige FastMCP. No contradice ningún artículo. | Usar `MCPServer` de 2.x cambia la API pedida y no está verificado. |
| Excepción extra `NoAutenticadoError` y dependencias `python-multipart`/`email-validator` | Necesarias para 401/«No autenticado» compartidos por REST y MCP, para el formulario de login y para `EmailStr` (422). No contradicen la Constitución. | Devolver `None`/`bool` desde la validación de JWT esconde el motivo y duplica la traducción en cada capa. |

## Reevaluación posterior al diseño (Fase 1)

Tras generar `data-model.md`, `contracts/` y `quickstart.md`, los siete artículos siguen
cumpliéndose. El diseño no introdujo violaciones nuevas: la única desviación, Art. III.3
(`existe`), fue aprobada y quedó recogida en la Constitución 1.1.0 (ver arriba). Los puntos que podrían tentar una regla de
negocio fuera de `services/` se resolvieron así: el parseo de texto de MCP está en
`utils/fechas.py` (formato, no negocio) y la confirmación de borrado vive en el servicio.
