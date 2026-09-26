# reservas-api Constitution

API de reservas de un espacio compartido. Esta constitución rige todo el código, las
especificaciones y las decisiones de diseño del proyecto. Cada regla está numerada
(p. ej. «Art. III.3») para poder citarla y verificarla en revisiones.

## Core Principles

### Artículo I — Arquitectura en capas (monolito modular)

1. La estructura obligatoria es `app/routers/`, `app/mcp/`, `app/services/`,
   `app/repositories/`, `app/models/`, `app/schemas/`, `app/utils/`, más `app/core/` para
   configuración y seguridad.
2. `routers/` y `mcp/` solo reciben la entrada, llaman a `services/` y traducen el
   resultado o los errores. NUNCA contienen reglas de negocio.
3. `services/` contiene TODAS las reglas de negocio.
4. `repositories/` solo persiste y consulta; no valida reglas de negocio. Recibe la sesión
   de BD por parámetro.
5. Toda dependencia fluye en un solo sentido: `routers/`/`mcp/` → `services/` →
   `repositories/` → `models/`. Ninguna capa importa de una capa superior.

### Artículo II — SOLID y patrón Repository

1. `services/` recibe el repository como parámetro (DIP), con un repository real por
   defecto; NUNCA lo importa fijo dentro de la función.
2. Cada regla de negocio lanza su propia excepción de dominio (p. ej.
   `ReservaSolapadaError`, `HorarioInvalidoError`, `ReservaNoEncontradaError`,
   `NoEsDuenoError`), definida en `services/` o `utils/`.
3. Cada módulo tiene una única responsabilidad.

### Artículo III — Persistencia

1. Se usa el ORM SQLAlchemy; la sesión de BD se inyecta por dependencia.
2. Los schemas Pydantic de entrada y de salida están separados de los modelos ORM. La
   contraseña NUNCA aparece en un schema de salida.
3. Cada modelo con datos de usuario incluye `usuario_id` como FK. Ninguna consulta de
   datos de Reserva puede omitir el filtro por `usuario_id`, excepto la verificación de
   solapamiento, que por regla de negocio compara contra todas las reservas existentes.

### Artículo IV — Seguridad

1. La autenticación usa OAuth2 (password flow) + JWT, con un modelo `Usuario` propio cuyo
   email es único.
2. Las contraseñas se hashean con bcrypt; NUNCA se guardan en texto plano ni se escriben en
   logs.
3. Los secretos (`SECRET_KEY`, algoritmo, expiración, `DATABASE_URL`) viven solo en `.env`
   y se leen con pydantic-settings. NUNCA se hardcodean.
4. `.env` está en `.gitignore`; `.env.example` se versiona sin valores reales y documenta
   todas las variables.
5. Todos los endpoints de Reserva requieren token: sin token o con token inválido → 401.
6. El `usuario_id` se obtiene siempre del JWT (`get_current_user`); NUNCA se acepta desde
   el cliente.

### Artículo V — Convención REST

1. Los recursos van en plural y en español: `/reservas/`, `/auth/registro`, `/auth/login`.
2. Códigos de estado: 201 crear, 200 leer/actualizar, 204 eliminar, 400 regla de negocio
   violada, 401 sin autenticación, 403 no es dueño, 404 no existe, 422 validación.
3. Los errores se devuelven con `HTTPException` y un `detail` claro; los routers traducen
   cada excepción de dominio a su código HTTP.
4. El CRUD de Reserva está completo: crear, listar (`skip`, `limit`), obtener por id,
   actualizar y eliminar.

### Artículo VI — MCP

1. Cada tool de MCP llama a una función de `services/`, sin excepción. Ejemplo: la tool
   `crear_reserva` y `POST /reservas/` llaman a la misma función
   `services/reservas.py::crear_reserva()`.
2. Existen como mínimo 3 tools: `crear_reserva`, `listar_reservas`, `cancelar_reserva`.
3. Los errores en MCP se devuelven con formato estructurado `{"error": "..."}`; NUNCA como
   excepciones crudas.
4. Las descripciones de las tools son específicas y verificables: indican parámetros,
   formato (fecha `YYYY-MM-DD`, hora `HH:MM`), reglas que aplican y errores posibles.
5. Toda tool con efecto destructivo (`cancelar_reserva`) exige confirmación explícita
   gestionada por el servidor (p. ej. parámetro `confirmar=true` validado en el servidor);
   NUNCA depende de que el modelo decida preguntar.
6. Identidad: el servidor MCP usa transporte HTTP y resuelve el usuario real con el mismo
   JWT que usa REST (header `Authorization: Bearer`). Si alguna parte no lo permite, la
   limitación queda documentada explícitamente en el código; NUNCA se usa un usuario fijo
   sin comentar.

### Artículo VII — Testing

1. Existe como mínimo un test unitario por cada regla de negocio explícita de `spec.md`.
2. Los tests unitarios de `services/` usan un repository falso (clase en memoria) inyectado
   por parámetro. Está PROHIBIDO `unittest.mock`.
3. La cobertura se mide con `pytest --cov=app --cov-report=term-missing`. Umbrales:
   `services/` ≥ 90 % y global ≥ 70 %.
4. Existe al menos 1 test de integración contra una base de datos SQLite real (no el
   repository falso).
5. Hay tests de API con `TestClient` para los casos 401, 403 y 404.
6. Las versiones de las dependencias están fijadas exactamente en `pyproject.toml` para
   evitar breaking changes.

## Stack y Restricciones Técnicas

- Lenguaje y framework: Python 3.13, FastAPI.
- Persistencia: SQLite con SQLAlchemy.
- Gestión de entorno y dependencias: `uv`, con `pyproject.toml` como fuente de verdad
  (ver Art. VII.6).
- Toda la documentación de especificación (constitución, spec, plan, tareas) se redacta en
  español.

## Flujo de Trabajo del Agente

- El agente implementa una tarea a la vez.
- Si necesita desviarse de un artículo, lo declara y espera aprobación; NUNCA decide en
  silencio.

## Governance

- Esta constitución prevalece sobre cualquier otra práctica o preferencia del proyecto.
- Cualquier cambio a esta constitución se registra con versión y fecha en la línea de
  versión al final de este documento.
- Versionado semántico: MAJOR para eliminar o redefinir de forma incompatible un artículo;
  MINOR para añadir un artículo o ampliar materialmente sus reglas; PATCH para
  aclaraciones y correcciones de redacción.
- Toda revisión de código o PR debe verificar el cumplimiento de los artículos; las
  desviaciones requieren la aprobación explícita descrita en «Flujo de Trabajo del Agente».

**Version**: 1.0.0 | **Ratified**: 2026-09-26 | **Last Amended**: 2026-09-26
