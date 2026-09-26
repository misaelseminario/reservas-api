# Quickstart: validar Reservas de una sala compartida

Guía de validación de extremo a extremo. Se cumple **cuando la implementación exista**
(`/speckit-tasks` + `/speckit-implement`). Contratos: [REST](contracts/rest-api.md),
[MCP](contracts/mcp-tools.md). Modelo: [data-model.md](data-model.md).

## 1. Prerrequisitos

- `uv` instalado y CPython 3.13 disponible (`uv` lo descarga si falta).
- Shell POSIX (Git Bash) para los `curl`; en PowerShell usar `curl.exe`.

## 2. Preparación

```bash
uv sync                      # crea .venv con las versiones exactas de pyproject.toml/uv.lock
cp .env.example .env         # y editar SECRET_KEY con un valor aleatorio propio
uv run python -c "import secrets; print(secrets.token_hex(32))"   # para generar SECRET_KEY
```

`.env` debe definir `SECRET_KEY`, `ALGORITHM` (`HS256`), `ACCESS_TOKEN_EXPIRE_MINUTES` y
`DATABASE_URL` (`sqlite:///./reservas.db`). `.env` no se versiona; `.env.example` sí.

> Si `uv sync` falla con «Failed to persist temporary file» (rutas largas de Windows), ver
> [research.md](research.md) R13.

## 3. Arranque

```bash
uv run uvicorn app.main:app --port 8000
```

Resultado esperado: servidor en `http://localhost:8000`; se crea `reservas.db`; documentación
interactiva en `/docs`; endpoint MCP en `/mcp`.

## 4. Escenario REST (Historias 1–3)

Usar una fecha futura (aquí `2030-01-15`).

```bash
BASE=http://localhost:8000
curl -s -X POST $BASE/auth/registro -H 'Content-Type: application/json' \
  -d '{"email":"ana@example.com","password":"clave-segura-1"}'          # 201, sin contraseña
curl -s -X POST $BASE/auth/registro -H 'Content-Type: application/json' \
  -d '{"email":"ana@example.com","password":"clave-segura-1"}'          # 400 email ya registrado
TOKEN=$(curl -s -X POST $BASE/auth/login -d 'username=ana@example.com&password=clave-segura-1' \
  | uv run python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s -X POST $BASE/reservas/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"fecha":"2030-01-15","hora_inicio":"09:00","hora_fin":"10:00"}'  # 201
curl -s -X POST $BASE/reservas/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"fecha":"2030-01-15","hora_inicio":"10:00","hora_fin":"11:00"}'  # 201 (contigua)
curl -s -X POST $BASE/reservas/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"fecha":"2030-01-15","hora_inicio":"09:30","hora_fin":"10:30"}'  # 400 solapada
curl -s -X POST $BASE/reservas/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"fecha":"2030-01-15","hora_inicio":"23:00","hora_fin":"01:00"}'  # 400 horas inválidas
curl -s -X POST $BASE/reservas/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"fecha":"2020-01-15","hora_inicio":"09:00","hora_fin":"10:00"}'  # 400 fecha pasada
curl -s $BASE/reservas/                                                  # 401 sin token
curl -s $BASE/reservas/999 -H "Authorization: Bearer $TOKEN"             # 404
```

Para el 403: registrar y autenticar a un segundo usuario y pedir `GET /reservas/1` con su
token → 403. Con el token del dueño, `PUT`/`DELETE /reservas/1` → 200 / 204.

## 5. Escenario MCP (Historia 4)

Cliente MCP (o `curl`) apuntando a `http://localhost:8000/mcp` con las cabeceras
`Authorization: Bearer $TOKEN` y `Accept: application/json, text/event-stream`. Ejemplo de
llamada a un tool:

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"cancelar_reserva","arguments":{"reserva_id":1}}}'
```

Resultados esperados:

| Llamada | Resultado |
|---------|-----------|
| `cancelar_reserva` sin `confirmar` | `{"error": "Confirmación requerida…"}`; la reserva **sigue existiendo** (`GET /reservas/1` → 200) |
| `cancelar_reserva` con `confirmar: true` | `{"mensaje": "Reserva 1 cancelada"}`; `GET /reservas/1` → 404 |
| Cualquier tool sin cabecera `Authorization` | `{"error": "No autenticado"}` |
| `crear_reserva` con horario solapado | `{"error": "La sala ya está reservada en ese horario"}` |

## 6. Suite automática y umbrales (Art. VII)

```bash
uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=70
uv run coverage report --include="app/services/*" --fail-under=90
```

Esperado: todos los tests pasan; cobertura global ≥ 70 % y `services/` ≥ 90 %.

Comprobaciones de las restricciones de la Constitución:

```bash
grep -rn "unittest.mock\|from mock\|MagicMock" tests/ app/   # sin resultados (Art. VII.2)
grep -rn "==" pyproject.toml                                  # todas las dependencias con versión exacta
git check-ignore .env                                         # imprime «.env» (Art. IV.4)
```

## 7. Trazabilidad de criterios de éxito

| Criterio | Cómo se valida |
|----------|----------------|
| SC-001 solapamiento | §4 (400) + tests unitarios RN-1 y contiguas |
| SC-002 reservas ajenas | §4 (403) + test de API 403 |
| SC-003 sin credenciales | §4 (401) + §5 «No autenticado» |
| SC-004 sin contraseña | respuestas de §4; test de schema |
| SC-005 cancelar sin confirmar | §5 + test unitario RN-6 + test MCP |
| SC-006 REST = MCP | mismo servicio; §5 vs §4 |
| SC-007 primera reserva < 2 min | §4 completo |
| SC-008 pruebas | §6 |
