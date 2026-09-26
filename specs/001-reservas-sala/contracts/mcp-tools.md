# Contrato MCP

**Plan**: [../plan.md](../plan.md) | REST equivalente: [rest-api.md](rest-api.md) | Decisiones: [../research.md](../research.md) (R3, R10, R11)

## Transporte e identidad

- SDK oficial `mcp==1.30.0`, `FastMCP("reservas")`, transporte **streamable HTTP**,
  `stateless_http=True`, `json_response=True`.
- Montado en la misma app FastAPI: endpoint **`POST http://localhost:8000/mcp`** (el mount va
  en `/` y es lo último que se registra; la ruta MCP es `/mcp`).
- Cada petición MCP debe enviar `Authorization: Bearer <access_token>` (el mismo JWT que
  devuelve `POST /auth/login`) y `Accept: application/json, text/event-stream`.
- Cada tool resuelve el usuario **en cada llamada** con la misma función que REST
  (`services/auth.py::obtener_usuario_actual`). Sin cabecera, sin esquema `Bearer`, token
  inválido/expirado o usuario inexistente → `{"error": "No autenticado"}` y **no se ejecuta
  ninguna operación**.
- Solo se admite `localhost:*`, `127.0.0.1:*` y `[::1]:*` como `Host` (protección
  DNS-rebinding por defecto del SDK); otro host recibe 421.
- Los tools llaman a las **mismas funciones de `services/`** que los endpoints (Art. VI.1) y
  devuelven siempre un `dict`; los errores son `{"error": "<mensaje>"}`, nunca excepciones.

## Tools

### `crear_reserva(fecha: str, hora_inicio: str, hora_fin: str)`

Descripción publicada al cliente MCP (texto de la docstring del tool):

> Crea una reserva de la sala para el usuario autenticado. Parámetros: `fecha` en formato
> `YYYY-MM-DD` (p. ej. 2030-01-15); `hora_inicio` y `hora_fin` en formato `HH:MM` de 24 horas
> (p. ej. 09:00 y 10:00). Reglas: la hora de fin debe ser posterior a la de inicio dentro del
> mismo día (no se puede cruzar la medianoche); la fecha y hora de inicio no pueden ser
> anteriores al momento actual; no puede solaparse con ninguna reserva existente de cualquier
> usuario (las reservas contiguas, una que termina cuando empieza la otra, sí se permiten).
> Devuelve `{"id", "fecha", "hora_inicio", "hora_fin"}`. Errores posibles:
> `{"error": "No autenticado"}`, `{"error": "Formato de fecha u hora inválido…"}`, horario
> solapado, horas inválidas, fecha pasada.

| Resultado | Respuesta |
|-----------|-----------|
| Éxito | `{"id": 1, "fecha": "2030-01-15", "hora_inicio": "09:00", "hora_fin": "10:00"}` |
| Error | `{"error": "..."}` (ver tabla de mensajes en [data-model.md](../data-model.md)) |

### `listar_reservas(skip: int = 0, limit: int = 100)`

> Lista las reservas del usuario autenticado (solo las suyas), ordenadas por fecha y hora de
> inicio. Parámetros: `skip` (≥ 0, reservas a saltar, por defecto 0) y `limit` (1 a 100,
> máximo de reservas a devolver, por defecto 100). Devuelve `{"reservas": [{"id", "fecha",
> "hora_inicio", "hora_fin"}, …]}`; con `skip` mayor que el total devuelve lista vacía.
> Errores posibles: `{"error": "No autenticado"}`, `{"error": "Parámetros de paginación
> inválidos…"}`.

| Resultado | Respuesta |
|-----------|-----------|
| Éxito | `{"reservas": [{"id": 1, "fecha": "2030-01-15", "hora_inicio": "09:00", "hora_fin": "10:00"}]}` |

### `cancelar_reserva(reserva_id: int, confirmar: bool = False)`

> Cancela (elimina) una reserva del usuario autenticado. **Acción destructiva**: el servidor
> exige `confirmar=true`; si no se indica o es false, NO se elimina nada y se devuelve un
> aviso de confirmación requerida. Parámetros: `reserva_id` (id de la reserva, entero) y
> `confirmar` (booleano, debe ser true para ejecutar). Solo el dueño puede cancelar su
> reserva. Devuelve `{"mensaje": "Reserva <id> cancelada"}`. Errores posibles:
> `{"error": "No autenticado"}`, `{"error": "Confirmación requerida: repite con
> confirmar=true"}`, `{"error": "Reserva no encontrada"}`, `{"error": "No tienes permiso
> sobre esta reserva"}`.

| Situación | Respuesta | Efecto en BD |
|-----------|-----------|--------------|
| `confirmar` ausente/false | `{"error": "Confirmación requerida: …"}` | Ninguno |
| `confirmar=true`, propia | `{"mensaje": "Reserva 1 cancelada"}` | Se elimina |
| `confirmar=true`, ajena | `{"error": "No tienes permiso sobre esta reserva"}` | Ninguno |
| `confirmar=true`, inexistente | `{"error": "Reserva no encontrada"}` | Ninguno |

Orden de validación en el servicio: confirmación (sin tocar BD) → existencia → propiedad →
borrado.

## Equivalencia REST ↔ MCP (FR-025)

| Situación | REST | MCP |
|-----------|------|-----|
| Sin/mal token | 401 | `{"error": "No autenticado"}` |
| Solapamiento / horas / fecha pasada | 400 | `{"error": ...}` con el mismo mensaje |
| Reserva ajena | 403 | `{"error": "No tienes permiso…"}` |
| Reserva inexistente | 404 | `{"error": "Reserva no encontrada"}` |

Alcance: no hay tool de modificación (excluido por la spec).
