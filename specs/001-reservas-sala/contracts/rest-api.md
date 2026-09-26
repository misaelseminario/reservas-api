# Contrato REST

**Plan**: [../plan.md](../plan.md) | Modelos de los cuerpos: [../data-model.md](../data-model.md)

Base: `http://localhost:8000`. Recursos en plural y en español (Art. V.1). Cuerpos JSON salvo
el login (formulario). Formatos: fecha `YYYY-MM-DD`, hora `HH:MM`. Los errores controlados
tienen la forma `{"detail": "<mensaje claro>"}` (`HTTPException`, Art. V.3); los 422 usan el
detalle estándar de FastAPI.

Autenticación de las rutas marcadas «Sí»: cabecera `Authorization: Bearer <access_token>`
(`OAuth2PasswordBearer`, `tokenUrl="auth/login"`). Sin token, token inválido o expirado →
**401** con `WWW-Authenticate: Bearer`. El `usuario_id` sale siempre del JWT; ningún
endpoint lo acepta en el cuerpo ni en la ruta (Art. IV.6).

## Endpoints

| Método | Ruta | Auth | Petición | Éxito | Errores |
|--------|------|:----:|----------|-------|---------|
| POST | `/auth/registro` | No | `{email, password}` | **201** `UsuarioLeer` | 400 email ya registrado (RN-5), 422 |
| POST | `/auth/login` | No | formulario `username` (=email), `password` | **200** `{access_token, token_type}` | 401 credenciales inválidas |
| POST | `/reservas/` | Sí | `{fecha, hora_inicio, hora_fin}` | **201** `ReservaLeer` | 400 solapada (RN-1), 400 horas (RN-2), 400 fecha pasada (RN-7), 401, 422 |
| GET | `/reservas/?skip=0&limit=100` | Sí | query `skip ≥ 0`, `1 ≤ limit ≤ 100` | **200** `list[ReservaLeer]` (solo del usuario) | 401, 422 |
| GET | `/reservas/{id}` | Sí | — | **200** `ReservaLeer` | 401, 403 ajena (RN-3), 404 |
| PUT | `/reservas/{id}` | Sí | `{fecha, hora_inicio, hora_fin}` | **200** `ReservaLeer` | 400 solapada, 400 horas, 400 fecha pasada (RN-4), 401, 403, 404, 422 |
| DELETE | `/reservas/{id}` | Sí | — | **204** sin cuerpo | 401, 403, 404 |

## Traducción de excepciones (solo en `routers/`)

| Excepción de dominio | HTTP | `detail` |
|----------------------|:----:|----------|
| `EmailYaRegistradoError` | 400 | «El email ya está registrado» |
| `ReservaSolapadaError` | 400 | «La sala ya está reservada en ese horario» |
| `HorarioInvalidoError` | 400 | «La hora de fin debe ser posterior a la hora de inicio» |
| `FechaPasadaError` | 400 | «No se puede reservar en una fecha y hora pasadas» |
| `NoEsDuenoError` | 403 | «No tienes permiso sobre esta reserva» |
| `ReservaNoEncontradaError` | 404 | «Reserva no encontrada» |
| `NoAutenticadoError` | 401 | «No autenticado» (login: «Credenciales incorrectas») |
| `ConfirmacionRequeridaError` | — | No ocurre por REST: `DELETE` llama al servicio con `confirmar=True` |

## Reglas de comportamiento observables

- **Contiguas permitidas**: 09:00–10:00 y 10:00–11:00 el mismo día son válidas (201).
- **Sin cruzar la medianoche**: `23:00 → 01:00` → 400 (RN-2). `hora_fin == hora_inicio` → 400.
- **Inicio pasado** (fecha y hora de inicio anteriores a «ahora») → 400 al crear y al modificar.
- **PUT** sustituye los tres campos; la reserva no cuenta como conflicto consigo misma (RN-4);
  modificar sin cambios → 200.
- **Listado**: solo del usuario; orden `fecha, hora_inicio, id`; `skip` mayor que el total →
  `[]`.
- **Id inexistente → 404; existente de otro usuario → 403**, para ver, modificar y eliminar.
- Ninguna respuesta contiene `password` ni `password_hash`.
- Contraseña: 8 caracteres mínimo y 72 bytes máximo (si no, 422).

## Ejemplo mínimo

```text
POST /auth/registro        {"email": "ana@example.com", "password": "clave-segura-1"}   → 201 {"id": 1, "email": "ana@example.com"}
POST /auth/login           username=ana@example.com&password=clave-segura-1              → 200 {"access_token": "<jwt>", "token_type": "bearer"}
POST /reservas/            {"fecha": "2030-01-15", "hora_inicio": "09:00", "hora_fin": "10:00"} → 201 {"id": 1, "usuario_id": 1, ...}
```
