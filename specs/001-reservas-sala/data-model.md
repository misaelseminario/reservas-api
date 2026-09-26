# Modelo de datos: Reservas de una sala compartida

**Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

## Entidades (modelos ORM, `app/models/`)

### Usuario — tabla `usuarios` (`app/models/usuario.py`)

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id` | Integer | PK, autoincremental |
| `email` | String(254) | NOT NULL, **UNIQUE**, indexado (RN-5); se guarda en minúsculas (lo normaliza el servicio) |
| `password_hash` | String(60..) | NOT NULL; hash bcrypt, nunca la contraseña (Art. IV.2) |

Relación: `Usuario 1 ── N Reserva` (`usuario.reservas`).

### Reserva — tabla `reservas` (`app/models/reserva.py`)

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id` | Integer | PK, autoincremental |
| `usuario_id` | Integer | NOT NULL, **FK → `usuarios.id`**, indexado (Art. III.3) |
| `fecha` | Date | NOT NULL, indexado |
| `hora_inicio` | Time | NOT NULL |
| `hora_fin` | Time | NOT NULL |

Sin `sala_id` (una única sala). Invariantes que garantiza el **servicio** (no la BD):
`hora_fin > hora_inicio` (RN-2), sin solapamiento con ninguna otra reserva de la misma fecha
(RN-1) e inicio no pasado al crear/modificar (RN-7). No se añade `CHECK` en BD para RN-2: la
regla vive solo en `services/` (Art. I.3); la BD no se usa como segunda fuente de reglas.

Sin borrado en cascada de usuarios (la baja de usuarios está fuera de alcance).

## Regla de solapamiento (RN-1)

Para una reserva candidata `(fecha, ini, fin)` existe conflicto si hay otra reserva `r` con
`r.fecha == fecha` **y** `ini < r.hora_fin` **y** `fin > r.hora_inicio`. Al modificar se
ignora la propia reserva (`r.id != reserva_id`, RN-4). Se comprueba contra **todas** las
reservas de esa fecha, de cualquier usuario.

**Dónde vive**: la fórmula se evalúa en `services/reservas.py` (Art. I.3) sobre la lista que
devuelve `repo.listar_por_fecha(db, fecha)`; el repository solo consulta y no contiene la
fórmula (Art. I.4). `listar_por_fecha` es una de las dos consultas de `Reserva` sin filtro de
`usuario_id` que permite el Art. III.3 (la otra es `existe`).

| Existente | Candidata | ¿Solapa? |
|-----------|-----------|----------|
| 09:00–10:00 | 10:00–11:00 | No (contigua) |
| 10:00–11:00 | 09:00–10:00 | No (contigua) |
| 09:00–10:00 | 09:00–10:00 | Sí (idéntica) |
| 09:00–12:00 | 10:00–11:00 | Sí (contenida) |
| 10:00–11:00 | 09:00–12:00 | Sí (contiene) |
| 09:00–10:00 (otro día) | 09:00–10:00 | No |

## Contrato del repository (`app/repositories/`)

`base.py` define los `Protocol` que cumplen el repository real y el falso de los tests. La
sesión de BD es siempre el primer parámetro (Art. I.4). Los repositories **no** validan
reglas; los que escriben hacen `commit`.

**`ReservaRepositoryProtocol`**

| Método | Filtra por `usuario_id` | Descripción |
|--------|:-----------------------:|-------------|
| `crear(db, usuario_id, fecha, hora_inicio, hora_fin) -> Reserva` | — (asigna) | Inserta y devuelve la reserva |
| `listar_por_usuario(db, usuario_id, skip, limit) -> list[Reserva]` | Sí | Orden estable: `fecha, hora_inicio, id` |
| `obtener_de_usuario(db, reserva_id, usuario_id) -> Reserva \| None` | Sí | Lectura de datos, siempre con dueño |
| `existe(db, reserva_id) -> bool` | **No** (solo booleano) | Distingue 404/403; ver R9 |
| `listar_por_fecha(db, fecha) -> list[Reserva]` | **No** (excepción III.3) | Todas las reservas de esa fecha, de cualquier usuario, orden `hora_inicio, id`; el servicio aplica RN-1 |
| `actualizar(db, reserva, fecha, hora_inicio, hora_fin) -> Reserva` | — | Persiste el cambio |
| `eliminar(db, reserva) -> None` | — | Borra |

**`UsuarioRepositoryProtocol`**: `crear(db, email, password_hash) -> Usuario`,
`obtener_por_email(db, email) -> Usuario | None`, `obtener_por_id(db, usuario_id) ->
Usuario | None`.

Implementación real: clases sin estado (`ReservaRepository`, `UsuarioRepository`) con una
instancia de módulo (`reserva_repository`, `usuario_repository`) que los servicios usan como
valor por defecto del parámetro `repo` (DIP, Art. II.1).

## Schemas Pydantic (`app/schemas/`), separados de los modelos (Art. III.2)

| Schema | Campos | Notas |
|--------|--------|-------|
| `UsuarioCrear` | `email: EmailStr`, `password: str` | 8 ≤ longitud; ≤ 72 **bytes** (R5) |
| `UsuarioLeer` | `id`, `email` | **Sin contraseña ni hash** |
| `Token` | `access_token: str`, `token_type: str` (`"bearer"`) | |
| `ReservaCrear` / `ReservaActualizar` | `fecha: date`, `hora_inicio: time`, `hora_fin: time` | Formato inválido → 422. `ReservaActualizar` es sustitución completa (3 campos obligatorios) |
| `ReservaLeer` | `id`, `usuario_id`, `fecha`, `hora_inicio`, `hora_fin` | `from_attributes=True` |

Los schemas solo validan **formato**; RN-1…RN-7 no viven en ellos.
`skip: int = Query(SKIP_MINIMO, ge=SKIP_MINIMO)`, `limit: int = Query(LIMITE_POR_DEFECTO, ge=LIMITE_MINIMO, le=LIMITE_MAXIMO)`, con las constantes (0, 1, 100, 100) definidas una sola vez en `services/reservas.py` y compartidas con el tool MCP (valores por defecto
razonables, exigidos por la spec; fuera de rango → 422).

## Reglas de negocio → excepción de dominio → traducción

Excepciones en `app/services/excepciones.py` (Art. II.2). Una por regla.

| Regla | Excepción | REST | MCP `{"error": ...}` |
|-------|-----------|------|----------------------|
| RN-1 solapamiento | `ReservaSolapadaError` | 400 | «La sala ya está reservada en ese horario» |
| RN-2 horas | `HorarioInvalidoError` | 400 | «La hora de fin debe ser posterior a la hora de inicio» |
| RN-3 propiedad | `NoEsDuenoError` | 403 | «No tienes permiso sobre esta reserva» |
| RN-3 / FR-015 inexistente | `ReservaNoEncontradaError` | 404 | «Reserva no encontrada» |
| RN-4 modificar | (reaplica RN-1/2/7 excluyendo la propia) | 400/403/404 | — (modificar no existe por MCP) |
| RN-5 email único | `EmailYaRegistradoError` | 400 | — |
| RN-6 confirmación | `ConfirmacionRequeridaError` | — (REST pasa `confirmar=True`) | «Confirmación requerida: repite con confirmar=true» |
| RN-7 fecha pasada | `FechaPasadaError` | 400 | «No se puede reservar en una fecha y hora pasadas» |
| Auth | `NoAutenticadoError` | 401 + `WWW-Authenticate: Bearer` | «No autenticado» |

`NoAutenticadoError` es la **única** excepción añadida a las siete pedidas: no representa una
regla de negocio sino el fallo de autenticación, y es lo que permite que REST (401) y MCP
(`{"error": "No autenticado"}`) compartan la misma función de validación. Los mensajes nunca
incluyen contraseñas ni datos de otros usuarios.

## Transiciones de estado

Una reserva solo existe o no existe: **creada → (modificada)* → eliminada**. No hay estados
intermedios ni borrado lógico. Las reservas pasadas no se tocan.
