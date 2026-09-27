# reservas-api

API para reservar una sala compartida. Los usuarios se registran, inician sesión y gestionan
sus reservas por **REST** (FastAPI) y por **MCP** (servidor FastMCP con transporte streamable
HTTP), ambos en la misma aplicación y con las mismas reglas de negocio.

Proyecto final del curso de Backend y MCP en Python (CEDIA), desarrollado con Spec-Kit
(constitución → spec → plan → tareas → implementación).

## Qué hace

- **Registro e inicio de sesión** con email y contraseña. El login devuelve un JWT.
- **Reservas de la sala**: crear, listar (con `skip` y `limit`), consultar, modificar y eliminar.
  Cada reserva tiene una fecha, una hora de inicio y una hora de fin.
- **Reglas de negocio** (RN-1 a RN-7): no se permiten solapamientos entre reservas de ningún
  usuario (las contiguas sí se permiten), la hora de fin debe ser posterior a la de inicio, solo
  el dueño accede a su reserva, el email es único, cancelar por MCP exige confirmación y no se
  puede reservar en el pasado.
- **MCP**: tres herramientas (`crear_reserva`, `listar_reservas`, `cancelar_reserva`) que usan el
  mismo JWT que REST.

## Stack

| Componente | Versión fijada |
|------------|----------------|
| Python | 3.13 (`requires-python = ">=3.13"`) |
| Gestor de entorno y dependencias | [uv](https://docs.astral.sh/uv/) |
| FastAPI / Uvicorn | 0.141.1 / 0.54.0 |
| SQLAlchemy (SQLite) | 2.1.1 |
| Pydantic / pydantic-settings | 2.13.5 / 2.15.0 |
| PyJWT / bcrypt (directo, sin passlib) | 2.15.0 / 5.0.0 |
| MCP (SDK oficial, FastMCP) | 1.30.0 |
| Tests: pytest / pytest-cov / httpx | 9.1.1 / 7.1.0 / 0.28.1 |

Todas las dependencias están fijadas con `==` en `pyproject.toml` y coinciden con `uv.lock`.

## Instalación

Requisitos: [uv](https://docs.astral.sh/uv/getting-started/installation/) instalado. Si no tienes
Python 3.13, uv lo descarga.

```bash
git clone https://github.com/misaelseminario/reservas-api.git
cd reservas-api
uv sync
```

`uv sync` crea `.venv` con las versiones exactas de `pyproject.toml` y `uv.lock`, incluidas las
de desarrollo (pytest, pytest-cov, httpx).

> **Windows.** Si `uv sync` falla con «Failed to persist temporary file» (rutas largas), activa
> las rutas largas de Windows o apunta el entorno a una ruta corta, por ejemplo
> `set UV_PROJECT_ENVIRONMENT=C:\pv` en `cmd` o `$env:UV_PROJECT_ENVIRONMENT = "C:\pv"` en
> PowerShell.

## Configuración (`.env`)

Los secretos y parámetros no están en el código: se leen de un archivo `.env` con
pydantic-settings, y la aplicación **no arranca si falta alguna variable**.

1. Copia la plantilla:

   ```bash
   cp .env.example .env          # en PowerShell: Copy-Item .env.example .env
   ```

2. Genera una clave secreta propia y pégala como valor de `SECRET_KEY`:

   ```bash
   uv run python -c "import secrets; print(secrets.token_hex(32))"
   ```

| Variable | Descripción | Valor en `.env.example` |
|----------|-------------|-------------------------|
| `SECRET_KEY` | Clave con la que se firman los JWT. Obligatoria, sin valor por defecto | vacío: hay que rellenarlo |
| `ALGORITHM` | Algoritmo de firma de los JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Minutos de validez del token | `30` |
| `DATABASE_URL` | URL de la base de datos | `sqlite:///./reservas.db` |

`.env` está en `.gitignore` y **no debe versionarse nunca**. `.env.example` sí se versiona, sin
valores reales. La base de datos `reservas.db` también está ignorada por git (`*.db`).

## Cómo correr la aplicación

```bash
uv run uvicorn app.main:app --reload
```

Al arrancar se crean las tablas en la base de datos si no existen. El servidor queda en
`http://localhost:8000`:

| URL | Qué es |
|-----|--------|
| `http://localhost:8000/docs` | Documentación interactiva (Swagger UI) de la API REST |
| `http://localhost:8000/mcp` | Endpoint MCP (streamable HTTP) |

### Ejemplo rápido con REST

Usa una fecha futura (aquí `2030-01-15`). En PowerShell escribe `curl.exe` en lugar de `curl`.

```bash
BASE=http://localhost:8000

# Registro (201, la respuesta no incluye la contraseña)
curl -s -X POST $BASE/auth/registro -H 'Content-Type: application/json' \
  -d '{"email":"ana@example.com","password":"clave-segura-1"}'

# Login: formulario OAuth2, `username` es el email
curl -s -X POST $BASE/auth/login -d 'username=ana@example.com&password=clave-segura-1'
# → {"access_token":"<token>","token_type":"bearer"}

# Crear una reserva
curl -s -X POST $BASE/reservas/ -H "Authorization: Bearer <token>" \
  -H 'Content-Type: application/json' \
  -d '{"fecha":"2030-01-15","hora_inicio":"09:00","hora_fin":"10:00"}'
```

### Endpoints REST

| Método | Ruta | Auth | Éxito | Errores |
|--------|------|:----:|-------|---------|
| POST | `/auth/registro` | No | 201 | 400 email ya registrado, 422 |
| POST | `/auth/login` | No | 200 | 401 credenciales incorrectas |
| POST | `/reservas/` | Sí | 201 | 400 (solapada, horas inválidas, fecha pasada), 401, 422 |
| GET | `/reservas/` | Sí | 200 | 401 |
| GET | `/reservas/{id}` | Sí | 200 | 401, 403 (ajena), 404 |
| PUT | `/reservas/{id}` | Sí | 200 | 400, 401, 403, 404, 422 |
| DELETE | `/reservas/{id}` | Sí | 204 | 401, 403, 404 |

Formatos: fecha `YYYY-MM-DD` y hora `HH:MM` (por ejemplo `09:00`; no se admiten segundos). El
listado admite `skip` (≥ 0) y `limit` (de 1 a 100, por defecto 100). La ruta del contrato es
`/reservas/`, con barra final.

### Herramientas MCP

| Herramienta | Parámetros | Resultado |
|-------------|------------|-----------|
| `crear_reserva` | `fecha`, `hora_inicio`, `hora_fin` | `{"id", "fecha", "hora_inicio", "hora_fin"}` |
| `listar_reservas` | `skip` (0), `limit` (100) | `{"reservas": [...]}` |
| `cancelar_reserva` | `reserva_id`, `confirmar` (`false`) | `{"mensaje": "Reserva <id> cancelada"}`. Sin `confirmar=true` no elimina nada y pide confirmación |

Los errores siempre tienen la forma `{"error": "<mensaje>"}`, con el mismo texto que el `detail`
de REST. Sin token válido, cualquier herramienta responde `{"error": "No autenticado"}` y no
ejecuta ninguna operación.

## Cómo correr los tests

```bash
uv run pytest --cov=app --cov-report=term-missing
```

Los tests no dependen de tu `.env` ni de `reservas.db`: cada test usa su propio SQLite
temporal. Resultado actual: **383 tests** (154 unitarios, 41 de integración y 188 de API),
cobertura global **99 %** y de `app/services/` **100 %**. Los umbrales de la constitución son
global ≥ 70 % y `services/` ≥ 90 %.

| Carpeta | Contenido |
|---------|-----------|
| `tests/unit/` | Reglas de negocio de `services/` con un repository falso en memoria (sin `unittest.mock`), schemas, seguridad y utilidades |
| `tests/integration/` | Repositories y servicios contra un SQLite real (archivo temporal) |
| `tests/api/` | La aplicación completa con `TestClient`: REST (incluidos los casos 401, 403 y 404) y MCP |

## Cómo probar MCP con MCP Inspector

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) es la herramienta oficial
para probar servidores MCP desde el navegador. Necesita Node.js.

1. **Arranca el servidor** (`uv run uvicorn app.main:app --reload`).
2. **Consigue un token.** Regístrate y haz login como en el ejemplo REST de arriba. Copia el
   valor de `access_token`. Caduca según `ACCESS_TOKEN_EXPIRE_MINUTES`; si las herramientas
   empiezan a responder `No autenticado`, haz login otra vez.
3. **Abre el Inspector:**

   ```bash
   npx @modelcontextprotocol/inspector
   ```

4. **Configura la conexión** en el panel de la izquierda:
   - **Transport Type**: `Streamable HTTP`
   - **URL**: `http://localhost:8000/mcp`
   - **Cabecera de autenticación** (sección «Authentication» o «Custom Headers»):
     `Authorization: Bearer <token>`

   Los nombres exactos de los campos pueden variar según la versión del Inspector.
5. Pulsa **Connect**. En la pestaña **Tools**, elige **List Tools**: deben aparecer
   `crear_reserva`, `listar_reservas` y `cancelar_reserva`. Ejecútalas con estos argumentos de
   ejemplo:
   - `crear_reserva`: `fecha` = `2030-01-15`, `hora_inicio` = `09:00`, `hora_fin` = `10:00`
   - `listar_reservas`: sin argumentos
   - `cancelar_reserva`: `reserva_id` = `1`. Sin `confirmar` (o con `false`) no elimina nada;
     con `confirmar` = `true` sí

Usa siempre `localhost` (o `127.0.0.1`) en la URL. Con otro nombre de host el servidor responde
`421` (ver «Limitaciones»).

**Comprobación sin Inspector.** La misma llamada, con `curl` (`Accept` es obligatorio):

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer <token>" -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"listar_reservas","arguments":{}}}'
```

> Esta guía del Inspector no se ha ejecutado en este proyecto. Lo que sí se validó contra el
> servidor real (`uvicorn`) es el mismo intercambio JSON-RPC con un cliente HTTP, siguiendo
> `specs/001-reservas-sala/quickstart.md` §5: 20 de 20 comprobaciones correctas.

## Estructura del proyecto

```text
app/
├── main.py            # ensambla la app: routers REST + servidor MCP montado en /mcp
├── core/              # config (pydantic-settings), database (SQLAlchemy), security (bcrypt, JWT)
├── models/            # modelos ORM: Usuario, Reserva
├── schemas/           # schemas Pydantic de entrada y salida
├── repositories/      # persistencia y consultas, sin reglas de negocio
├── services/          # TODAS las reglas de negocio y las excepciones de dominio
├── routers/           # endpoints REST: reciben, llaman a services y traducen errores
├── mcp/               # tools MCP y autenticación por JWT
└── utils/             # conversión de fechas y horas
tests/                 # unit/, integration/ y api/
specs/001-reservas-sala/   # spec, plan, research, data-model, contratos, quickstart y tareas
.specify/memory/constitution.md   # constitución del proyecto (7 artículos)
```

Las dependencias van en un solo sentido: `routers/` y `mcp/` → `services/` → `repositories/` →
`models/`. REST y MCP llaman a las mismas funciones de `services/`.

## Limitaciones documentadas

**Reservas**

- **Solicitudes simultáneas.** El solapamiento se comprueba al procesar cada solicitud, sin
  bloqueo. Si dos solicitudes por el mismo horario llegan a la vez, no se garantiza que solo
  una se acepte. Se asume poco tráfico (`specs/001-reservas-sala/spec.md`, clarificaciones y
  supuestos).
- **Una sola sala.** No existe el concepto de varias salas.
- **Sin cruzar la medianoche.** Una reserva pertenece a un solo día. Un rango como 23:00 → 01:00
  se rechaza (400). Para cubrir ese periodo hay que hacer dos reservas, una por día.
- **Sin duración mínima ni máxima**, y un único huso horario. «Ahora» (para no reservar en el
  pasado) es la hora local del servidor.
- **Sin roles.** Todos los usuarios tienen los mismos permisos sobre sus propias reservas.
- **Fuera de alcance:** recuperación de contraseña, verificación de email, cierre de sesión,
  notificaciones, edición o baja de usuarios y modificación de reservas por MCP (por MCP solo
  se crea, lista y cancela).

**Autenticación**

- **Contraseñas** de 8 caracteres o más y de 72 bytes o menos (límite de bcrypt); fuera de ese
  rango, 422.
- **Tokens sin revocación.** No hay cierre de sesión: un token sigue siendo válido hasta que
  caduca.
- **Email sin distinguir mayúsculas.** Se guarda y se busca en minúsculas.

**MCP**

- **Solo en `localhost`.** El SDK protege contra DNS-rebinding y solo admite los `Host`
  `localhost:*`, `127.0.0.1:*` y `[::1]:*`. Publicarlo bajo otro nombre exigiría configurar
  `TransportSecuritySettings` (despliegue local, fuera de alcance). Con otro host, 421.
- **Argumentos fuera del esquema.** Si un tool recibe argumentos que no cumplen su esquema (por
  ejemplo `reserva_id="abc"`), lo rechaza el propio SDK antes de ejecutarlo, con `isError: true`
  y sin la forma `{"error": ...}`. No se ejecuta ninguna operación.
- **Versión fijada `mcp==1.30.0`.** La serie 2.x eliminó `FastMCP`, que es lo que usa este
  proyecto.
- **Sin estado de sesión.** El servidor usa `stateless_http=True`: cada llamada lleva y valida
  su propio token.

**Datos**

- **Sin migraciones.** Las tablas se crean al arrancar (`create_all`); no hay Alembic. Cambiar un
  modelo exige recrear o migrar la base de datos a mano.

## Documentación de diseño

- [`.specify/memory/constitution.md`](.specify/memory/constitution.md): reglas del proyecto
  (7 artículos).
- [`specs/001-reservas-sala/`](specs/001-reservas-sala/): `spec.md`, `plan.md`, `research.md`,
  `data-model.md`, `contracts/`, `quickstart.md` y `tasks.md`.
- [`VERIFICACION.md`](VERIFICACION.md): dónde se cumple cada requisito, con `archivo:línea`, y
  qué test cubre cada regla de negocio.
