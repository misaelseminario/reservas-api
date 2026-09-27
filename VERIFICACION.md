# Verificación de requisitos — reservas-api

Cada ítem indica el `archivo:línea` donde se cumple. Las rutas son relativas a la raíz del
repositorio y las líneas empiezan en 1.

- **Estado verificado**: commit `7d41023` (árbol limpio), 2026-09-26.
- **Cómo se comprobó**: las líneas se sacaron leyendo los archivos, no de memoria. Después un
  script comprobó que cada archivo citado existe, que la línea existe y que, en las tablas de
  tests, el nombre del test está en la línea indicada.
- **Ejecución de los tests**: `uv run pytest --cov=app --cov-report=term-missing` → **383
  tests pasan** (154 unitarios, 41 de integración, 188 de API). Cobertura global **99 %**
  (488 sentencias, 2 sin cubrir: `app/core/database.py:31` y `:53`). Cobertura de
  `app/services/` **100 %** (94 sentencias).

> **Aviso sobre los «Requisitos mínimos del proyecto».** El enunciado original del curso no
> está en el repositorio ni consta en la sesión de trabajo. Por eso los ítems de las cinco
> categorías (Arquitectura, Seguridad, REST + MCP, Testing, Spec-Driven Development) se
> derivaron de la Constitución v1.1.0 y de la spec. Si el enunciado exige algo que no aparece
> aquí, hay que añadirlo a estas tablas.

## Índice

1. [Requisitos mínimos del proyecto](#1-requisitos-mínimos-del-proyecto)
2. [Los 7 artículos de la Constitución](#2-los-7-artículos-de-la-constitución)
3. [Reglas de negocio RN-1…RN-7 y reservas contiguas → tests](#3-reglas-de-negocio-rn-1rn-7-y-reservas-contiguas--tests)
4. [Casos de error con prueba obligatoria](#4-casos-de-error-con-prueba-obligatoria)
5. [Correcciones al agente](#5-correcciones-al-agente)

---

## 1. Requisitos mínimos del proyecto

### 1.1 Arquitectura

| # | Requisito | Dónde se cumple |
|---|-----------|-----------------|
| A1 | Monolito modular con capas `routers/`, `mcp/`, `services/`, `repositories/`, `models/`, `schemas/`, `utils/` y `core/` | `app/routers/reservas.py:24`, `app/mcp/server.py:66`, `app/services/reservas.py:74`, `app/repositories/reserva_repository.py:17`, `app/models/reserva.py:20`, `app/schemas/reserva.py:17`, `app/utils/fechas.py:22`, `app/core/config.py:12`; ensamblado en `app/main.py:20-38`; estructura planificada en `specs/001-reservas-sala/plan.md:175` |
| A2 | Routers y tools solo reciben, llaman a `services/` y traducen; sin reglas de negocio | `app/routers/reservas.py:34-39`, `app/mcp/server.py:96-103` y `:47-63` |
| A3 | Todas las reglas de negocio viven en `services/` | `app/services/reservas.py:37` (RN-1), `:44-50` (RN-2, RN-7), `:117-121` (RN-3), `:143` (RN-4), `:162-163` (RN-6); `app/services/auth.py:32-34` (RN-5) |
| A4 | Los repositories solo persisten y consultan | `app/repositories/reserva_repository.py:3-4` (declaración) y `:20-81` (métodos sin reglas); `app/repositories/usuario_repository.py:9-23` |
| A5 | Dependencias en un solo sentido: `routers`/`mcp` → `services` → `repositories` → `models` | `app/services/reservas.py:12-22` (importa `models`, `repositories`, `excepciones`), `app/repositories/reserva_repository.py:14` (solo `models`), `app/models/reserva.py:14` (solo `core.database`), `app/services/excepciones.py:1-6` (declara que no importa nada de otras capas). Ninguna capa inferior importa una superior (revisado con `grep` de `from app` en cada capa). `app/utils/fechas.py:13` importa `models` solo bajo `TYPE_CHECKING` |
| A6 | Inversión de dependencias: los services reciben el repository por parámetro, con el real por defecto | `app/services/reservas.py:82`, `:100`, `:114`, `:134`, `:153`; `app/services/auth.py:26`, `:43`, `:60`; contratos en `app/repositories/base.py:18` y `:42` |
| A7 | Una excepción de dominio por regla, traducida en la capa de entrada | `app/services/excepciones.py:18-63`; REST en `app/routers/dependencias.py:31-52`; MCP en `app/mcp/server.py:59-60` |
| A8 | Sesión de BD inyectada por dependencia | `app/core/database.py:63-69` (`get_db`) y `:72-79` (`abrir_sesion`); `app/routers/reservas.py:31`, `:47`, `:57`, `:71`, `:86` |
| A9 | Responsabilidad única por módulo | `app/core/config.py:1-5`, `app/core/security.py:1-7`, `app/core/database.py:1-7`, `app/utils/fechas.py:1-6`, `app/routers/dependencias.py:1-6`, `app/mcp/autenticacion.py:1-7` |

### 1.2 Seguridad

| # | Requisito | Dónde se cumple |
|---|-----------|-----------------|
| S1 | OAuth2 (password flow) + JWT | `app/routers/dependencias.py:29` (`OAuth2PasswordBearer`); `app/routers/auth.py:29-36` (login con `OAuth2PasswordRequestForm`); `app/core/security.py:31-37` (`crear_token`) |
| S2 | Modelo `Usuario` propio con email único | `app/models/usuario.py:14-23` (email único en `:19`); RN-5 en `app/services/auth.py:32-34`; `tests/integration/test_reservas_sqlite.py:238` `test_email_duplicado_viola_la_restriccion_unique` |
| S3 | Contraseñas con bcrypt, nunca en texto plano | `app/core/security.py:17-19` y `:22-28`; `app/models/usuario.py:21` (solo `password_hash`); `app/services/auth.py:35`; `tests/integration/test_reservas_sqlite.py:252` `test_el_hash_guardado_no_es_la_contrasena`; `tests/unit/test_security.py:28` `test_el_hash_no_es_la_contrasena` |
| S4 | La contraseña nunca aparece en una respuesta | `app/schemas/usuario.py:32-38` (`UsuarioLeer` sin `password`); `tests/unit/test_schemas.py:18` `test_usuario_leer_no_tiene_password_ni_hash`; `tests/api/test_auth_api.py:24` `test_registro_valido_responde_201_sin_password_ni_hash` |
| S5 | Contraseña de 8 caracteres o más y 72 bytes o menos (límite de bcrypt), con 422 si no cumple | `app/schemas/usuario.py:9-11` y `:21-28`; `tests/api/test_auth_api.py:57` `test_registro_con_contrasena_corta_responde_422`, `:61` `test_registro_con_contrasena_de_73_bytes_responde_422`, `:65` `test_registro_con_contrasena_de_72_bytes_responde_201` |
| S6 | Secretos solo en `.env`, leídos con pydantic-settings, sin valores por defecto ni hardcodeados | `app/core/config.py:12-18` (cuatro variables sin valor por defecto); se usan en `app/core/security.py:33-36` y `:46-52` y en `app/core/database.py:53`. Un `grep` de `SECRET_KEY` en `app/` solo encuentra estos usos |
| S7 | `.env` ignorado y `.env.example` versionado | `.gitignore:2`; `.env.example:6` (`SECRET_KEY`), `:9` (`ALGORITHM`), `:12` (`ACCESS_TOKEN_EXPIRE_MINUTES`), `:15` (`DATABASE_URL`). `git ls-files` no lista ningún `.env` ni `*.db` (los ignora `.gitignore:8`) |
| S8 | Todos los endpoints de Reserva exigen token: sin token o con token inválido → 401 | `app/routers/reservas.py:30`, `:46`, `:56`, `:70`, `:85` (`Depends(get_current_user)`); `app/routers/dependencias.py:55-63`; `tests/api/test_reservas_401.py:44` `test_sin_token_responde_401` (5 rutas) |
| S9 | El `usuario_id` sale del JWT, nunca del cliente | `app/routers/dependencias.py:59-63`; `app/routers/reservas.py:36` (`usuario.id`); `app/schemas/reserva.py:17-20` (el cuerpo no tiene `usuario_id`); `tests/api/test_reservas_api.py:49` `test_el_usuario_id_sale_del_jwt_aunque_el_cliente_envie_otro` |
| S10 | Un usuario no ve ni toca las reservas de otro (403) y una inexistente da 404 | `app/services/reservas.py:117-121`; `app/repositories/reserva_repository.py:44-51`; `tests/api/test_reservas_403.py:38`, `tests/api/test_reservas_404.py:48` `test_inexistente_da_404_y_ajena_da_403_sin_confundirse` |
| S11 | El JWT se valida con firma, expiración y `sub` obligatorios | `app/core/security.py:40-56`; `tests/unit/test_security.py:53` `test_token_con_otra_firma_devuelve_none`, `:67` `test_token_expirado_devuelve_none`, `:77` `test_token_sin_exp_o_sin_sub_devuelve_none` |
| S12 | El login no revela qué emails existen | `app/services/auth.py:47-52`; `tests/unit/test_auth_login.py:63` `test_email_inexistente_y_contrasena_incorrecta_dan_el_mismo_mensaje`; `tests/api/test_auth_api.py:113` `test_contrasena_incorrecta_y_email_inexistente_dan_la_misma_respuesta` |
| S13 | MCP nunca usa un usuario fijo | `app/mcp/autenticacion.py:1-7` y `:34-41`; `tests/integration/test_mcp_autenticacion.py:69` `test_cada_token_resuelve_a_su_propio_usuario_sin_usuario_fijo` |
| S14 | No se registran contraseñas ni tokens | `app/core/security.py:5-6`; el único registro de log del proyecto es `app/mcp/server.py:62` (mensaje fijo, sin datos del usuario) |

### 1.3 REST + MCP

| # | Requisito | Dónde se cumple |
|---|-----------|-----------------|
| R1 | 7 endpoints REST: `POST /auth/registro`, `POST /auth/login`, `POST /reservas/`, `GET /reservas/`, `GET/PUT/DELETE /reservas/{id}` | `app/routers/auth.py:20` y `:29`; `app/routers/reservas.py:27`, `:42`, `:53`, `:66`, `:82`; `tests/api/test_main.py:32` `test_la_aplicacion_publica_exactamente_los_7_endpoints_rest` |
| R2 | Códigos de estado: 201 crear, 200 leer/actualizar, 204 eliminar, 400 regla, 401, 403, 404, 422 | `app/routers/reservas.py:27` (201) y `:82` (204); `app/routers/dependencias.py:31-42`; `tests/api/test_reservas_api.py:36` `test_crear_responde_201_con_los_datos_de_la_reserva`, `:243` `test_delete_propio_responde_204_y_desaparece_del_listado` |
| R3 | Listado con paginación `skip` / `limit` | `app/routers/reservas.py:44-45`; constantes únicas en `app/services/reservas.py:24-28`; `tests/api/test_reservas_api.py:129` `test_listar_con_skip_y_limit` |
| R4 | Errores REST con `HTTPException` y un `detail` claro | `app/routers/dependencias.py:45-52`; `tests/api/test_reservas_api.py:65` (comprueba el `detail` de RN-1) |
| R5 | MCP con las tools `crear_reserva`, `listar_reservas` y `cancelar_reserva` | `app/mcp/server.py:79-80`, `:107-110`, `:130-131`; `tests/api/test_main.py:80` `test_post_mcp_responde_y_publica_los_tres_tools` |
| R6 | Cada tool llama a la misma función de `services/` que su endpoint | `app/mcp/server.py:103` ↔ `app/routers/reservas.py:35-37` (`crear_reserva`); `app/mcp/server.py:125` ↔ `app/routers/reservas.py:50` (`listar_reservas`); `app/mcp/server.py:148` ↔ `app/routers/reservas.py:91` (`eliminar_reserva`) |
| R7 | Transporte streamable HTTP, en la misma app FastAPI, ruta `/mcp` | `app/mcp/server.py:72-77`; `app/main.py:22`, `:29`, `:37`; `tests/api/test_main.py:73` `test_el_mount_de_mcp_es_lo_ultimo_que_se_registra`, `:89` `test_rest_sigue_funcionando_con_mcp_montado` |
| R8 | Identidad por `Authorization: Bearer <JWT>`, el mismo JWT que REST | `app/mcp/autenticacion.py:16-31` y `:41`; `app/mcp/server.py:57`; `tests/api/test_mcp.py:107` `test_la_reserva_se_crea_a_nombre_del_usuario_del_token`, `:131` `test_sin_token_valido_devuelve_no_autenticado_y_no_crea_nada` |
| R9 | Errores MCP con formato `{"error": "..."}`, nunca excepciones | `app/mcp/server.py:59-63`; `tests/api/test_mcp.py:160` `test_una_regla_violada_devuelve_error_estructurado_y_no_guarda`, `:203` `test_un_fallo_inesperado_devuelve_error_estructurado_sin_detalles_internos` |
| R10 | `cancelar_reserva` exige confirmación validada por el servidor | `app/services/reservas.py:162-163`; `app/mcp/server.py:131`, `:134-136`, `:148`; `tests/api/test_mcp.py:357` `test_cancelar_sin_confirmar_pide_confirmacion_y_no_elimina_nada` |
| R11 | Descripciones de las tools específicas y verificables (parámetros, formatos, reglas, errores) | `app/mcp/server.py:81-94`, `:111-120`, `:132-144`; `tests/api/test_mcp.py:86` `test_crear_reserva_se_publica_con_una_descripcion_verificable`, `:224` `test_listar_reservas_se_publica_con_una_descripcion_verificable`, `:342` `test_cancelar_reserva_se_publica_como_accion_destructiva_con_confirmacion` |
| R12 | REST y MCP dan el mismo resultado de negocio ante la misma situación (FR-025) | `app/services/excepciones.py:3-4` (mensaje único por regla); `tests/api/test_mcp.py:266` `test_listar_coincide_con_lo_que_devuelve_rest`, `:414` `test_cancelar_elimina_lo_mismo_que_delete_rest`, `:443` `test_los_errores_mcp_tienen_el_mismo_mensaje_que_el_detail_de_rest` |
| R13 | Las limitaciones de MCP quedan documentadas en el código | `app/mcp/server.py:8-15`; `tests/api/test_mcp.py:424` `test_argumentos_fuera_del_esquema_los_rechaza_el_sdk_sin_ejecutar_el_tool` |

### 1.4 Testing

| # | Requisito | Dónde se cumple |
|---|-----------|-----------------|
| T1 | Al menos un test unitario por regla de negocio | Tabla de la [sección 3](#3-reglas-de-negocio-rn-1rn-7-y-reservas-contiguas--tests) |
| T2 | Tests de `services/` con repository falso en memoria, sin `unittest.mock` | `tests/unit/fakes.py:19-104` (`FakeReservaRepository`) y `:107-134` (`FakeUsuarioRepository`); se inyecta con `repo=` en `tests/unit/test_reservas_crear.py:26-31`. Un `grep -i` de `mock`, `unittest` y `monkeypatch` en `app/` y `tests/` no da resultados |
| T3 | Al menos un test de integración con SQLite real | `tests/integration/test_reservas_sqlite.py:40-42` (fixture `db`), `:62` `test_ciclo_crear_solapar_listar_obtener_modificar_eliminar`, `:86` `test_los_datos_persisten_en_el_archivo_y_los_lee_otra_sesion`, `:111` `test_matriz_de_solapamiento_contra_sqlite_real`; archivo temporal por test en `tests/conftest.py:26-28` y `:32-44` |
| T4 | Tests de API con `TestClient` para 401, 403 y 404 | `tests/conftest.py:48-59` (fixture `client`); `tests/api/test_reservas_401.py:44-108`; `tests/api/test_reservas_403.py:38`, `:48`, `:60`; `tests/api/test_reservas_404.py:19`, `:26`, `:33` |
| T5 | Cobertura medida con `pytest --cov=app --cov-report=term-missing`; `services/` ≥ 90 % y global ≥ 70 % | `pyproject.toml:33-34` (`source = ["app"]`). Resultado del 2026-09-26: global **99 %**, `app/services/reservas.py` 100 %, `app/services/auth.py` 100 %, `app/services/excepciones.py` 100 % |
| T6 | Versiones fijadas con `==` | `pyproject.toml:7-16` (10 dependencias) y `:21-23` (3 de desarrollo). Las 13 coinciden con `uv.lock` |
| T7 | Tests deterministas: la hora actual se inyecta | `app/services/reservas.py:41`, `:81`, `:133` (parámetro `ahora`); `tests/unit/test_reservas_crear.py:145` `test_rn7_empezar_exactamente_ahora_se_acepta` |

### 1.5 Spec-Driven Development

| # | Requisito | Dónde se cumple |
|---|-----------|-----------------|
| D1 | La Constitución se ratifica antes de especificar | `.specify/memory/constitution.md:1-124`; línea de versión en `:124`; commit `6f48033` |
| D2 | La spec describe el qué, con clarificaciones registradas | `specs/001-reservas-sala/spec.md:11-19` (5 clarificaciones); `:341-342` (las decisiones técnicas se dejan al plan) |
| D3 | Requisitos funcionales y criterios de éxito medibles | `specs/001-reservas-sala/spec.md:188-257` (FR-001…FR-026) y `:302-322` (SC-001…SC-008) |
| D4 | Contrato REST y MCP y casos de error con prueba obligatoria | `specs/001-reservas-sala/spec.md:259-280` y `:282-292` (verificados en la [sección 4](#4-casos-de-error-con-prueba-obligatoria)) |
| D5 | El plan incluye el «Constitution Check» de los 7 artículos | `specs/001-reservas-sala/plan.md:42-116` (por artículo en `:50`, `:60`, `:68`, `:76`, `:87`, `:96`, `:107`); reevaluación tras el diseño en `:236-242` |
| D6 | Research, modelo de datos, contratos y quickstart | `specs/001-reservas-sala/research.md:1`, `specs/001-reservas-sala/data-model.md:1`, `specs/001-reservas-sala/contracts/rest-api.md:1`, `specs/001-reservas-sala/contracts/mcp-tools.md:1`, `specs/001-reservas-sala/quickstart.md:1` |
| D7 | Tareas por capas con trazabilidad regla → tarea → test; todas marcadas | `specs/001-reservas-sala/tasks.md:29-228` (fases) y `:232-247` (trazabilidad); 52 tareas `[X]`, 0 pendientes |
| D8 | Análisis de consistencia y correcciones aplicadas antes de implementar | Commits `5909b25` y `e48f50e`; detalle en la [sección 5.3](#53-otras-correcciones-tras-speckit-analyze). Los hallazgos LOW D1, D2, F1 y F2 no se aplicaron (no bloquean nada; ver [5.3](#53-otras-correcciones-tras-speckit-analyze)) |
| D9 | El agente implementa una tarea a la vez y declara toda desviación esperando aprobación | `.specify/memory/constitution.md:107-111`; desviación aprobada en `specs/001-reservas-sala/plan.md:232` (Art. III.3) |
| D10 | Verificación final de restricciones, del servidor real y de cobertura | `specs/001-reservas-sala/tasks.md:226` (T050), `:227` (T051), `:228` (T052) |

---

## 2. Los 7 artículos de la Constitución

Texto de referencia: `.specify/memory/constitution.md:1-124` (v1.1.0).

Línea de cada artículo: I `.specify/memory/constitution.md:9`, II `.specify/memory/constitution.md:22`, III `.specify/memory/constitution.md:31`, IV `.specify/memory/constitution.md:43`, V `.specify/memory/constitution.md:57`, VI `.specify/memory/constitution.md:67`, VII `.specify/memory/constitution.md:85`.

### Artículo I — Arquitectura en capas

| Regla | Dónde se cumple |
|-------|-----------------|
| I.1 Estructura obligatoria | `app/routers/reservas.py:24`, `app/mcp/server.py:66`, `app/services/reservas.py:74`, `app/repositories/reserva_repository.py:17`, `app/models/reserva.py:20`, `app/schemas/reserva.py:17`, `app/utils/fechas.py:22`, `app/core/config.py:12` |
| I.2 Routers y `mcp/` sin reglas de negocio | `app/routers/reservas.py:34-39`, `:60-63`, `:74-79`, `:90-93`; `app/routers/auth.py:23-26`; `app/mcp/server.py:96-103`, `:122-126`, `:146-149` |
| I.3 `services/` contiene todas las reglas | `app/services/reservas.py:31-37`, `:40-50`, `:53-71`, `:117-121`, `:162-163`; `app/services/auth.py:32-34` |
| I.4 `repositories/` solo persiste y recibe la sesión por parámetro | `app/repositories/reserva_repository.py:3-4`; `db: Session` es el primer parámetro en `:21`, `:32`, `:45`, `:53`, `:59`, `:70`, `:79`; contrato en `app/repositories/base.py:6-7` |
| I.5 Flujo de dependencias en un solo sentido | Ver A5 en la [sección 1.1](#11-arquitectura); `app/core/security.py:3` declara que no importa de capas superiores |

### Artículo II — SOLID y patrón Repository

| Regla | Dónde se cumple |
|-------|-----------------|
| II.1 El repository entra por parámetro, con uno real por defecto; nunca se importa fijo dentro de la función | `app/services/reservas.py:82`, `:100`, `:114`, `:134`, `:153`; `app/services/auth.py:26`, `:43`, `:60`. Los repositories reales se importan una vez, como valor por defecto, en `app/services/reservas.py:14` y `app/services/auth.py:17`. Ningún cuerpo de función los usa directamente |
| II.2 Una excepción de dominio por regla, en `services/` | `app/services/excepciones.py:18` (`ReservaSolapadaError`), `:24` (`HorarioInvalidoError`), `:30` (`NoEsDuenoError`), `:36` (`ReservaNoEncontradaError`), `:42` (`EmailYaRegistradoError`), `:48` (`ConfirmacionRequeridaError`), `:54` (`FechaPasadaError`), `:60` (`NoAutenticadoError`) |
| II.3 Cada módulo tiene una única responsabilidad | Ver A9 en la [sección 1.1](#11-arquitectura) |

### Artículo III — Persistencia

| Regla | Dónde se cumple |
|-------|-----------------|
| III.1 ORM SQLAlchemy y sesión inyectada por dependencia | `app/core/database.py:18-19` (`Base`), `:63-69` (`get_db`), `:72-79` (`abrir_sesion`); `app/models/reserva.py:20-32`; `app/routers/reservas.py:31`, `:47`, `:57`, `:71`, `:86` |
| III.2 Schemas de entrada y salida separados del ORM; la contraseña no sale nunca | Entrada `app/schemas/usuario.py:14-29` y `app/schemas/reserva.py:17-38`; salida `app/schemas/usuario.py:32-38` y `app/schemas/reserva.py:41-48`; `password_hash` solo en `app/models/usuario.py:21`; `tests/unit/test_schemas.py:23` `test_serializar_un_usuario_no_incluye_password_ni_hash` |
| III.3 `usuario_id` como FK y consultas de `Reserva` siempre filtradas por dueño, salvo (a) el solapamiento y (b) `existe` | FK en `app/models/reserva.py:25-27`. Filtradas: `app/repositories/reserva_repository.py:37` (`listar_por_usuario`) y `:49` (`obtener_de_usuario`). Excepción (a): `:59-67` (`listar_por_fecha`). Excepción (b): `:53-57` (`existe`, devuelve solo un `bool`). Texto del artículo en `.specify/memory/constitution.md:36-41`. Tests: `tests/integration/test_reservas_sqlite.py:154` `test_listar_por_fecha_devuelve_solo_esa_fecha_de_cualquier_usuario`, `:166` `test_listar_por_usuario_solo_devuelve_las_del_usuario`, `:192` `test_obtener_de_usuario_exige_id_y_dueno`, `:199` `test_existe_no_filtra_por_dueno` |

### Artículo IV — Seguridad

| Regla | Dónde se cumple |
|-------|-----------------|
| IV.1 OAuth2 password flow + JWT; `Usuario` propio con email único | Ver S1 y S2 en la [sección 1.2](#12-seguridad) |
| IV.2 bcrypt; nunca texto plano ni en logs | Ver S3 y S14 |
| IV.3 Secretos solo en `.env`, con pydantic-settings, sin hardcodear | Ver S6; `app/core/config.py:3-4` lo declara |
| IV.4 `.env` en `.gitignore`; `.env.example` versionado con todas las variables | `.gitignore:2`; `.env.example:6`, `:9`, `:12`, `:15`; `git ls-files` lista `.env.example` y no lista `.env` |
| IV.5 Endpoints de Reserva con token; sin él o inválido → 401 | Ver S8 |
| IV.6 `usuario_id` siempre del JWT | Ver S9 |

### Artículo V — Convención REST

| Regla | Dónde se cumple |
|-------|-----------------|
| V.1 Recursos en plural y en español | `app/routers/reservas.py:24` (`/reservas`), `app/routers/auth.py:17` (`/auth`), `:20` (`/registro`), `:29` (`/login`) |
| V.2 Códigos de estado | Ver R2; traducción de excepciones en `app/routers/dependencias.py:31-42` (400, 401, 403, 404) y `422` de validación en `tests/api/test_reservas_api.py:103` `test_crear_con_formato_invalido_responde_422` |
| V.3 `HTTPException` con `detail`; los routers traducen cada excepción de dominio | `app/routers/dependencias.py:45-52`; `app/routers/reservas.py:38-39`, `:62-63`, `:78-79`, `:92-93`; `app/routers/auth.py:25-26`, `:34-35` |
| V.4 CRUD completo con `skip` y `limit` | `app/routers/reservas.py:27`, `:42`, `:53`, `:66`, `:82`; `:44-45` (paginación); `tests/api/test_reservas_api.py:36`, `:129`, `:160`, `:172`, `:243` |

### Artículo VI — MCP

| Regla | Dónde se cumple |
|-------|-----------------|
| VI.1 Cada tool llama a una función de `services/` (la misma que REST) | Ver R6 |
| VI.2 Mínimo 3 tools | `app/mcp/server.py:80` (`crear_reserva`), `:108` (`listar_reservas`), `:131` (`cancelar_reserva`) |
| VI.3 Errores como `{"error": "..."}`, nunca excepciones crudas | `app/mcp/server.py:59-63`; formato inválido en `:101-102`, paginación inválida en `:123-124` |
| VI.4 Descripciones específicas y verificables | Ver R11 |
| VI.5 Confirmación de la acción destructiva, gestionada por el servidor | `app/services/reservas.py:151-152` (`confirmar` obligatorio, solo por nombre) y `:162-163`; `app/mcp/server.py:131`, `:148`; `tests/unit/test_reservas_eliminar.py:28` `test_rn6_sin_confirmar_lanza_confirmacion_requerida_y_no_toca_el_repository`; `tests/api/test_mcp.py:357` |
| VI.6 Transporte HTTP e identidad con el mismo JWT; limitaciones documentadas | `app/mcp/autenticacion.py:16-41`; `app/services/auth.py:56-75` (validación única); `app/routers/dependencias.py:61` (misma función en REST); limitaciones en `app/mcp/server.py:8-15` |

### Artículo VII — Testing

| Regla | Dónde se cumple |
|-------|-----------------|
| VII.1 Un test unitario por regla de negocio | [Sección 3](#3-reglas-de-negocio-rn-1rn-7-y-reservas-contiguas--tests) |
| VII.2 Repository falso; prohibido `unittest.mock` | Ver T2: `tests/unit/fakes.py:19-104`; `grep` sin resultados |
| VII.3 Cobertura con `--cov=app --cov-report=term-missing`; `services/` ≥ 90 % y global ≥ 70 % | Ver T5: global 99 %, `services/` 100 % |
| VII.4 Al menos un test de integración con SQLite real | Ver T3: `tests/integration/test_reservas_sqlite.py` (24 tests) |
| VII.5 Tests de API con `TestClient` para 401, 403 y 404 | Ver T4 |
| VII.6 Versiones exactas en `pyproject.toml` | Ver T6: `pyproject.toml:7-16` y `:21-23` |

### Stack y flujo de trabajo

| Punto | Dónde se cumple |
|-------|-----------------|
| Python 3.13 y `uv` | `pyproject.toml:5` (`requires-python = ">=3.13"`); `.python-version:1`; `uv.lock` versionado |
| SQLite con SQLAlchemy | `.env.example:15`; `app/core/database.py:26-47` |
| Documentación en español | `.specify/memory/constitution.md`, `specs/001-reservas-sala/*.md`, este archivo y `README.md` |
| Una tarea a la vez; desviaciones declaradas y aprobadas | `.specify/memory/constitution.md:107-111`; ejemplo en `specs/001-reservas-sala/plan.md:232` |

---

## 3. Reglas de negocio RN-1…RN-7 y reservas contiguas → tests

Formato de cada celda: `` `archivo:línea` `nombre_del_test` ``. Los tests marcados «(param.)»
están parametrizados; la línea es la del `def`. Las tablas de trazabilidad regla → tarea →
test están en `specs/001-reservas-sala/tasks.md:232-247`.

| Regla | Test unitario (repository falso) | Integración, API y MCP |
|-------|----------------------------------|------------------------|
| **RN-1** Sin solapamiento, con reservas de cualquier usuario (`inicio_nueva < fin_existente AND fin_nueva > inicio_existente`) | `tests/unit/test_reservas_crear.py:60` `test_rn1_una_reserva_que_solapa_lanza_reserva_solapada` (param.: idéntica, contenida, que contiene, parcial por cada extremo, comparte inicio, comparte final)<br>`tests/unit/test_reservas_crear.py:69` `test_rn1_solapar_con_la_reserva_de_otro_usuario_tambien_es_error`<br>`tests/unit/test_reservas_crear.py:78` `test_rn1_la_misma_hora_en_otra_fecha_se_acepta` | `tests/integration/test_reservas_sqlite.py:111` `test_matriz_de_solapamiento_contra_sqlite_real` (param.)<br>`tests/api/test_reservas_api.py:59` `test_crear_solapada_responde_400_rn1`<br>`tests/api/test_mcp.py:160` `test_una_regla_violada_devuelve_error_estructurado_y_no_guarda` (param.)<br>`tests/api/test_mcp.py:169` `test_solapar_con_la_reserva_de_otro_usuario_devuelve_error` |
| **Contiguas** Una termina cuando empieza la otra: se permiten, en ambos órdenes | `tests/unit/test_reservas_crear.py:90` `test_contiguas_la_nueva_empieza_cuando_termina_la_existente`<br>`tests/unit/test_reservas_crear.py:99` `test_contiguas_la_nueva_termina_cuando_empieza_la_existente`<br>`tests/unit/test_reservas_actualizar.py:77` `test_rn4_mover_a_un_horario_contiguo_a_otra_reserva_se_acepta` | `tests/integration/test_reservas_sqlite.py:122` `test_las_reservas_contiguas_se_permiten_en_ambos_ordenes`<br>`tests/api/test_reservas_api.py:69` `test_crear_contigua_responde_201`<br>`tests/api/test_mcp.py:114` `test_reservas_contiguas_se_aceptan` |
| **RN-2** `hora_fin` posterior a `hora_inicio` en el mismo día (23:00 → 01:00 es inválido) | `tests/unit/test_reservas_crear.py:119` `test_rn2_hora_fin_no_posterior_lanza_horario_invalido` (param.: fin = inicio, fin < inicio, cruza medianoche)<br>`tests/unit/test_reservas_actualizar.py:106` `test_rn2_al_modificar_fin_no_posterior_lanza_horario_invalido` (param.) | `tests/integration/test_reservas_sqlite.py:128` `test_horario_invalido_no_llega_a_la_base_de_datos`<br>`tests/api/test_reservas_api.py:77` `test_crear_con_horas_invalidas_responde_400_rn2` (param.)<br>`tests/api/test_mcp.py:160` `test_una_regla_violada_devuelve_error_estructurado_y_no_guarda` (param.) |
| **RN-3** Solo el dueño accede a su reserva: ajena → 403, inexistente → 404 | `tests/unit/test_reservas_consulta.py:91` `test_rn3_obtener_una_reserva_ajena_lanza_no_es_dueno`<br>`tests/unit/test_reservas_consulta.py:98` `test_rn3_obtener_un_id_inexistente_lanza_reserva_no_encontrada`<br>`tests/unit/test_reservas_consulta.py:118` `test_rn3_el_error_de_reserva_ajena_no_revela_datos_del_otro_usuario`<br>`tests/unit/test_reservas_actualizar.py:135` `test_rn3_modificar_una_reserva_ajena_lanza_no_es_dueno_y_no_cambia`<br>`tests/unit/test_reservas_eliminar.py:77` `test_rn3_eliminar_una_reserva_ajena_lanza_no_es_dueno_y_no_se_elimina` | `tests/integration/test_reservas_sqlite.py:206` `test_rn3_reserva_ajena_da_403_e_inexistente_da_404`<br>`tests/api/test_reservas_403.py:38` `test_get_de_una_reserva_ajena_responde_403`<br>`tests/api/test_reservas_403.py:48` `test_put_de_una_reserva_ajena_responde_403_y_no_la_modifica`<br>`tests/api/test_reservas_403.py:60` `test_delete_de_una_reserva_ajena_responde_403_y_no_la_elimina`<br>`tests/api/test_reservas_404.py:19` `test_get_de_una_reserva_inexistente_responde_404`<br>`tests/api/test_mcp.py:376` `test_cancelar_una_reserva_ajena_devuelve_error_y_no_elimina` |
| **RN-4** Al modificar se re-aplican RN-1, RN-2 y RN-7, y la reserva no se solapa consigo misma | `tests/unit/test_reservas_actualizar.py:40` `test_rn4_ampliar_la_propia_reserva_se_acepta_aunque_solape_consigo_misma`<br>`tests/unit/test_reservas_actualizar.py:49` `test_rn4_modificar_sin_cambios_se_acepta`<br>`tests/unit/test_reservas_actualizar.py:57` `test_rn4_mover_a_un_horario_que_solapa_con_otra_reserva_lanza_solapada`<br>`tests/unit/test_reservas_actualizar.py:68` `test_rn4_solapar_con_otra_reserva_del_mismo_usuario_tambien_es_error`<br>`tests/unit/test_reservas_actualizar.py:88` `test_rn4_mover_a_otra_fecha_compara_contra_esa_fecha` | `tests/integration/test_reservas_sqlite.py:134` `test_al_modificar_la_reserva_no_se_solapa_consigo_misma_pero_si_con_otra`<br>`tests/api/test_reservas_api.py:190` `test_put_ampliar_la_propia_reserva_responde_200`<br>`tests/api/test_reservas_api.py:199` `test_put_que_solapa_con_otra_reserva_responde_400_y_no_modifica` |
| **RN-5** Email único, sin distinguir mayúsculas | `tests/unit/test_auth_registro.py:26` `test_rn5_email_duplicado_lanza_email_ya_registrado`<br>`tests/unit/test_auth_registro.py:36` `test_rn5_el_email_se_compara_sin_distinguir_mayusculas`<br>`tests/unit/test_auth_registro.py:46` `test_rn5_el_email_se_guarda_en_minusculas`<br>`tests/unit/test_auth_login.py:43` `test_rn5_login_no_distingue_mayusculas_del_email` (param.) | `tests/integration/test_reservas_sqlite.py:238` `test_email_duplicado_viola_la_restriccion_unique`<br>`tests/api/test_auth_api.py:34` `test_registro_con_email_duplicado_responde_400`<br>`tests/api/test_auth_api.py:43` `test_registro_con_el_mismo_email_en_otra_capitalizacion_responde_400` |
| **RN-6** Cancelar exige `confirmar=true`, validado por el servidor | `tests/unit/test_reservas_eliminar.py:28` `test_rn6_sin_confirmar_lanza_confirmacion_requerida_y_no_toca_el_repository`<br>`tests/unit/test_reservas_eliminar.py:42` `test_rn6_solo_true_autoriza_el_borrado` (param.)<br>`tests/unit/test_reservas_eliminar.py:52` `test_rn6_confirmar_es_un_argumento_obligatorio`<br>`tests/unit/test_reservas_eliminar.py:63` `test_rn6_confirmando_una_reserva_propia_se_elimina` | `tests/integration/test_reservas_sqlite.py:215` `test_eliminar_sin_confirmar_no_borra_nada_y_ajena_tampoco`<br>`tests/api/test_mcp.py:357` `test_cancelar_sin_confirmar_pide_confirmacion_y_no_elimina_nada` (param.)<br>`tests/api/test_mcp.py:365` `test_cancelar_confirmando_una_reserva_propia_la_elimina` |
| **RN-7** No crear ni modificar una reserva que empieza en el pasado | `tests/unit/test_reservas_crear.py:131` `test_rn7_una_fecha_de_ayer_lanza_fecha_pasada`<br>`tests/unit/test_reservas_crear.py:138` `test_rn7_hoy_con_inicio_anterior_a_ahora_lanza_fecha_pasada`<br>`tests/unit/test_reservas_crear.py:145` `test_rn7_empezar_exactamente_ahora_se_acepta`<br>`tests/unit/test_reservas_actualizar.py:115` `test_rn7_al_modificar_un_inicio_pasado_lanza_fecha_pasada` | `tests/api/test_reservas_api.py:84` `test_crear_con_fecha_de_ayer_responde_400_rn7`<br>`tests/api/test_reservas_api.py:210` `test_put_con_inicio_pasado_responde_400_y_no_modifica`<br>`tests/api/test_mcp.py:177` `test_una_fecha_pasada_devuelve_error` |

---

## 4. Casos de error con prueba obligatoria

Los 8 casos están en `specs/001-reservas-sala/spec.md:282-292`.

| # | Caso | Test |
|---|------|------|
| 1 | Solapada → 400 | `tests/api/test_reservas_api.py:59` `test_crear_solapada_responde_400_rn1` |
| 2 | `hora_fin` ≤ `hora_inicio` → 400 | `tests/api/test_reservas_api.py:77` `test_crear_con_horas_invalidas_responde_400_rn2` |
| 3 | Sin token → 401 | `tests/api/test_reservas_401.py:44` `test_sin_token_responde_401` (param.: 5 rutas) |
| 4 | Reserva ajena → 403 | `tests/api/test_reservas_403.py:38` `test_get_de_una_reserva_ajena_responde_403` |
| 5 | Reserva inexistente → 404 | `tests/api/test_reservas_404.py:19` `test_get_de_una_reserva_inexistente_responde_404` |
| 6 | Email ya registrado → 400 | `tests/api/test_auth_api.py:34` `test_registro_con_email_duplicado_responde_400` |
| 7 | `cancelar_reserva` sin confirmar → no elimina | `tests/api/test_mcp.py:357` `test_cancelar_sin_confirmar_pide_confirmacion_y_no_elimina_nada` (param.) |
| 8 | Fecha pasada → 400 | `tests/api/test_reservas_api.py:84` `test_crear_con_fecha_de_ayer_responde_400_rn7` |

---

## 5. Correcciones al agente

Decisiones del usuario que cambiaron lo que el agente había propuesto. En las dos primeras el
agente detectó el problema, lo declaró y esperó la decisión del usuario; no las resolvió por su
cuenta.

### 5.1 Enmienda del Art. III.3: `existe(reserva_id) -> bool`

- **Qué propuso el agente.** El plan resolvía la distinción entre 404 (no existe) y 403 (existe
  pero es ajena) con un método `existe(db, reserva_id) -> bool` que consulta por id sin filtrar
  por `usuario_id`. El artículo III.3, en su versión 1.0.0, solo exceptuaba de ese filtro la
  verificación de solapamiento. El agente lo dejó declarado como desviación en el Complexity
  Tracking y ofreció tres salidas: aprobarlo, enmendar el artículo o responder 404 también para
  reservas ajenas (esto último rompía FR-014).
- **Decisión del usuario.** Enmendar la Constitución con una versión MINOR (1.1.0): el
  repository puede exponer `existe(reserva_id) -> bool` sin filtrar por `usuario_id`, solo para
  distinguir 404 de 403, y nunca devuelve datos de la reserva.
- **Dónde queda.**
  - Texto del artículo: `.specify/memory/constitution.md:36-41` (excepciones (a) y (b)).
  - Versión y fecha: `.specify/memory/constitution.md:124` (v1.1.0, *Last Amended* 2026-09-26).
  - Desviación registrada como aprobada: `specs/001-reservas-sala/plan.md:232`.
  - Código: `app/repositories/reserva_repository.py:53-57`, contrato en
    `app/repositories/base.py:31`, uso en `app/services/reservas.py:117-118`.
  - Tests: `tests/integration/test_reservas_sqlite.py:199` `test_existe_no_filtra_por_dueno` y
    `tests/api/test_reservas_404.py:48` `test_inexistente_da_404_y_ajena_da_403_sin_confundirse`.
  - Commit: `d126713`.

### 5.2 Traslado de la fórmula de solapamiento: de `repositories/` a `services/`

- **Qué propuso el agente.** El plan ponía la consulta `hay_solapamiento` en el repository, con
  la fórmula de solapamiento dentro de la consulta. El agente advirtió el riesgo al generar
  `tasks.md`: el repository falso de los tests tenía que reimplementar la fórmula, así que los
  tests unitarios de RN-1 y de reservas contiguas probaban en parte el fake y no el servicio.
  Además, una regla de negocio en `repositories/` se aparta de los Art. I.3 e I.4. Ofreció la
  alternativa y preguntó antes de cambiarla.
- **Decisión del usuario.** El repository solo expone `listar_por_fecha(fecha)`, sin filtrar por
  `usuario_id` (la excepción (a) del Art. III.3, que ya existía). La fórmula
  `inicio_nueva < fin_existente AND fin_nueva > inicio_existente` vive en
  `services/reservas.py`. Al modificar, el servicio excluye la propia reserva. Se elimina
  `hay_solapamiento` del repository, y T043 se mantiene como test de integración con SQLite real.
- **Dónde queda.**
  - Fórmula: `app/services/reservas.py:31-37` (`_se_solapan`; las comparaciones estrictas dejan
    pasar las contiguas).
  - Comprobación contra todas las reservas de la fecha: `app/services/reservas.py:53-71`.
  - La reserva propia se excluye en `app/services/reservas.py:68-69` y se pasa `excluir_id` en
    `app/services/reservas.py:143`.
  - Repository sin fórmula: `app/repositories/reserva_repository.py:3-4` (declaración) y
    `app/repositories/reserva_repository.py:59-67` (`listar_por_fecha`).
  - Contrato del repository: `app/repositories/base.py:33`.
  - El fake no aplica la fórmula: `tests/unit/fakes.py:7-9` y `:81-85`. Por eso los tests de RN-1
    prueban de verdad el servicio.
  - La fórmula se contrasta contra SQL real en
    `tests/integration/test_reservas_sqlite.py:111` `test_matriz_de_solapamiento_contra_sqlite_real`.
  - Diseño: `specs/001-reservas-sala/data-model.md:34-45`.
  - `hay_solapamiento` ya no aparece en `app/` ni en `tests/` (comprobado con `grep`).
  - Commit: `12473e3`.

### 5.3 Otras correcciones tras `/speckit-analyze`

El análisis dio 8 hallazgos. Se aplicaron A1, B1, C1 y C2 (commits `5909b25` y `e48f50e`).
Los LOW D1, D2, F1 y F2 no se aplicaron. En F2 el código sí usa `String(60)`
(`app/models/usuario.py:21`), pero `specs/001-reservas-sala/data-model.md:13` sigue diciendo
«String(60..)».

| Hallazgo | Corrección | Dónde queda |
|----------|------------|-------------|
| A1 (HIGH) `session_manager.run()` solo se puede ejecutar una vez por instancia | `crear_app()` y `crear_servidor_mcp()` son fábricas: cada app y cada test tienen su propio servidor MCP | `app/main.py:20-41`, `app/mcp/server.py:66-77`, `tests/conftest.py:48-59`, `tests/api/test_main.py:97` `test_cada_aplicacion_tiene_su_propio_servidor_mcp` |
| B1 (MEDIUM) Límites de paginación duplicados en router y tool | Constantes únicas en `services/`, sin excepción de dominio nueva | `app/services/reservas.py:24-28`; se importan en `app/routers/reservas.py:17-22` y `app/mcp/server.py:29-34` |
| C1 (MEDIUM) Email sin regla de mayúsculas | Se normaliza a minúsculas al registrar y al iniciar sesión | `app/services/auth.py:32` y `:50`; `tests/unit/test_auth_registro.py:46`, `tests/api/test_auth_api.py:93` `test_login_con_otra_combinacion_de_mayusculas_responde_200` |
| C2 (LOW) REST aceptaba `HH:MM:SS` y MCP solo `HH:MM` | Los schemas usan los mismos parsers estrictos que MCP | `app/utils/fechas.py:15-16` y `:32-42`; `app/schemas/reserva.py:22-30`; `tests/api/test_reservas_api.py:103` `test_crear_con_formato_invalido_responde_422` (param.) |
