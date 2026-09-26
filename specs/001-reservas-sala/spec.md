# Feature Specification: Reservas de una sala compartida

**Feature Branch**: `001-reservas-sala` (no se creó rama git; el directorio de spec es independiente de la rama)

**Created**: 2026-09-26

**Status**: Draft

**Input**: User description: "Sistema de reservas de un espacio compartido (una sala). Los usuarios se registran, inician sesión y gestionan sus reservas por REST y por MCP."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registro e inicio de sesión (Priority: P1)

Una persona crea una cuenta con su email y una contraseña, e inicia sesión para obtener un
token de acceso con el que podrá operar sobre sus reservas. La contraseña nunca se devuelve
en ninguna respuesta.

**Why this priority**: Sin identidad no existe la propiedad de las reservas (RN-3); es la base
de todo lo demás.

**Independent Test**: Registrar un usuario, iniciar sesión con sus credenciales y comprobar que
se recibe un token; repetir el registro con el mismo email y comprobar el rechazo.

**Acceptance Scenarios**:

1. **Given** un email no registrado, **When** se registra con email y contraseña válidos,
   **Then** se crea el usuario (201) y la respuesta no contiene la contraseña.
2. **Given** un email ya registrado, **When** se intenta registrar de nuevo, **Then** se
   rechaza con 400 (RN-5).
3. **Given** un usuario registrado, **When** inicia sesión con email y contraseña correctos,
   **Then** recibe un token de acceso y su tipo (200).
4. **Given** credenciales incorrectas, **When** se intenta iniciar sesión, **Then** se
   rechaza con 401.
5. **Given** datos de registro mal formados (p. ej. email inválido), **When** se envían,
   **Then** se rechazan con 422.

---

### User Story 2 - Crear y consultar mis reservas (Priority: P1)

Un usuario autenticado reserva la sala indicando fecha, hora de inicio y hora de fin, y puede
listar sus reservas (con paginación) y consultar una por su identificador.

**Why this priority**: Es el valor central del sistema: reservar la sala sin conflictos.

**Independent Test**: Con un usuario autenticado, crear una reserva válida, listarla y
obtenerla por id; intentar crear otra que se solape y una con horas inválidas.

**Acceptance Scenarios**:

1. **Given** un usuario autenticado y un horario libre, **When** crea una reserva, **Then**
   se crea (201) asociada a ese usuario.
2. **Given** una reserva existente de cualquier usuario en un horario, **When** otro (o el
   mismo) usuario crea una reserva que se solapa en fecha y horario, **Then** se rechaza con
   400 (RN-1).
3. **Given** una hora de fin anterior o igual a la hora de inicio, **When** se crea la
   reserva, **Then** se rechaza con 400 (RN-2).
4. **Given** un usuario con reservas propias y ajenas en el sistema, **When** lista sus
   reservas indicando `skip` y `limit`, **Then** recibe solo las suyas, respetando la
   paginación (200).
5. **Given** un usuario autenticado, **When** consulta por id una reserva propia, **Then**
   la recibe (200).
6. **Given** una solicitud sin token o con token inválido, **When** intenta listar o crear
   reservas, **Then** se rechaza con 401.
7. **Given** datos con formato inválido (fecha u hora mal formadas), **When** se envían,
   **Then** se rechazan con 422.

---

### User Story 3 - Modificar y eliminar mis reservas (Priority: P2)

Un usuario autenticado cambia la fecha/horario de una reserva propia o la elimina. Nadie puede
ver, modificar ni eliminar reservas de otra persona.

**Why this priority**: Completa el ciclo de vida de la reserva y concentra la regla de
propiedad (RN-3), pero requiere que crear/consultar ya funcione.

**Independent Test**: Crear una reserva con el usuario A; con el usuario B intentar verla,
modificarla y eliminarla (403); con A modificarla y eliminarla correctamente.

**Acceptance Scenarios**:

1. **Given** una reserva propia, **When** el dueño la modifica a un horario libre y válido,
   **Then** se actualiza (200).
2. **Given** una reserva propia, **When** se modifica a un horario que solapa con *otra*
   reserva, **Then** se rechaza con 400 (RN-4 / RN-1).
3. **Given** una reserva propia, **When** se modifica a un horario que solo solapa con la
   propia reserva (p. ej. ampliar su duración), **Then** se acepta: la reserva no cuenta
   como conflicto consigo misma (RN-4).
4. **Given** una modificación con hora de fin no posterior a la de inicio, **When** se
   envía, **Then** se rechaza con 400 (RN-4 / RN-2).
5. **Given** la reserva de otro usuario, **When** se intenta ver, modificar o eliminar
   pasando su id manualmente, **Then** se rechaza con 403 (RN-3).
6. **Given** un id de reserva inexistente, **When** se consulta, modifica o elimina, **Then**
   se responde 404.
7. **Given** una reserva propia, **When** el dueño la elimina, **Then** se elimina (204) y
   deja de aparecer en su listado.
8. **Given** una solicitud sin token, **When** se intenta consultar, modificar o eliminar,
   **Then** se rechaza con 401.

---

### User Story 4 - Gestionar reservas mediante MCP (Priority: P2)

Un asistente conectado por MCP actúa en nombre de un usuario autenticado y dispone de tres
herramientas equivalentes a la funcionalidad de reservas: crear una reserva, listar las
propias y cancelar una. Cancelar exige confirmación explícita validada por el servidor.

**Why this priority**: Es la segunda vía de acceso pedida; reutiliza las mismas reglas que
el acceso REST, por lo que depende de las historias anteriores.

**Independent Test**: Con un token válido, usar cada herramienta; cancelar sin confirmar y
comprobar que la reserva sigue existiendo; cancelar confirmando y comprobar que desaparece.

**Acceptance Scenarios**:

1. **Given** una sesión MCP identificada con un token válido, **When** se usa `crear_reserva`
   con fecha, hora_inicio y hora_fin, **Then** se aplican las mismas reglas que en la
   creación por REST (RN-1, RN-2) y la reserva queda a nombre del usuario de la sesión.
2. **Given** una sesión MCP identificada, **When** se usa `listar_reservas` con `skip` y
   `limit`, **Then** se devuelven solo las reservas del usuario, igual que por REST.
3. **Given** una reserva propia, **When** se usa `cancelar_reserva` sin `confirmar=true`,
   **Then** no se elimina nada y la respuesta pide confirmación (RN-6).
4. **Given** una reserva propia, **When** se usa `cancelar_reserva` con `confirmar=true`,
   **Then** la reserva se elimina.
5. **Given** la reserva de otro usuario o una inexistente, **When** se usa
   `cancelar_reserva`, **Then** no se elimina nada y se devuelve un error con formato
   `{"error": "..."}` (RN-3).
6. **Given** cualquier fallo de regla de negocio en una herramienta MCP, **When** ocurre,
   **Then** la respuesta es `{"error": "..."}`, nunca una excepción sin controlar.
7. **Given** una sesión MCP sin token o con token inválido, **When** se usa cualquier
   herramienta, **Then** se devuelve un error con formato `{"error": "..."}` y no se
   ejecuta ninguna operación.

---

### Edge Cases

- **Reservas contiguas**: una reserva que termina a las 10:00 y otra que empieza a las 10:00
  el mismo día NO se solapan; se permiten.
- **Reserva idéntica**: mismo día y mismo horario que una existente → solapamiento (400).
- **Reserva contenida o que contiene** a otra existente → solapamiento (400).
- **Mismo horario, distinta fecha**: no hay solapamiento.
- **Horas iguales** (`hora_inicio == hora_fin`) → horas inválidas (400).
- **Reserva que cruza la medianoche**: no soportada; una reserva ocurre dentro de un solo
  día, por lo que `hora_fin` debe ser posterior a `hora_inicio` en ese mismo día.
- **Paginación fuera de rango** (`skip` mayor que el total): lista vacía, no error.
- **Id de reserva inexistente frente a ajeno**: inexistente → 404; existente de otro usuario
  → 403.
- **Modificar una reserva sin cambios**: se acepta (no se solapa consigo misma).
- **Mensajes de error**: nunca revelan la contraseña ni datos de otros usuarios.

## Requirements *(mandatory)*

### Functional Requirements

**Usuarios y acceso**

- **FR-001**: El sistema MUST permitir registrar un usuario con email y contraseña.
- **FR-002**: El sistema MUST rechazar (400) el registro de un email ya registrado (RN-5).
- **FR-003**: El sistema MUST rechazar (422) registros con datos mal formados.
- **FR-004**: El sistema MUST no exponer nunca la contraseña en ninguna respuesta.
- **FR-005**: El sistema MUST permitir iniciar sesión con email y contraseña y devolver un
  token de acceso y su tipo; con credenciales inválidas MUST responder 401.
- **FR-006**: Todas las operaciones sobre reservas MUST exigir un token válido; sin token o
  con token inválido MUST responder 401.
- **FR-007**: La identidad del usuario MUST obtenerse siempre del token, nunca de un dato
  enviado por el cliente.

**Reservas**

- **FR-008**: El sistema MUST permitir crear una reserva con fecha, hora de inicio y hora
  de fin, asociada al usuario autenticado (201).
- **FR-009**: El sistema MUST rechazar (400) una reserva cuyo horario se solape en fecha y
  horario con cualquier reserva existente, sin importar quién sea su dueño (RN-1).
- **FR-010**: El sistema MUST rechazar (400) una reserva cuya hora de fin no sea posterior a
  la hora de inicio (RN-2).
- **FR-011**: El sistema MUST listar únicamente las reservas del usuario autenticado, con
  paginación mediante `skip` y `limit` (200).
- **FR-012**: El sistema MUST permitir consultar una reserva por id (200) solo a su dueño.
- **FR-013**: El sistema MUST permitir modificar (200) y eliminar (204) una reserva solo a su
  dueño.
- **FR-014**: Cuando un usuario intente ver, modificar o eliminar una reserva de otro
  usuario, sin importar el id que pase, el sistema MUST responder 403 (RN-3).
- **FR-015**: Cuando la reserva indicada no exista, el sistema MUST responder 404 al
  consultarla, modificarla o eliminarla.
- **FR-016**: Al modificar una reserva, el sistema MUST volver a aplicar RN-1 y RN-2,
  excluyendo a la propia reserva de la verificación de solapamiento (RN-4).
- **FR-017**: Los datos de reserva con formato inválido MUST rechazarse con 422.

**Acceso por MCP**

- **FR-018**: El sistema MUST ofrecer por MCP la herramienta `crear_reserva(fecha,
  hora_inicio, hora_fin)` con las mismas reglas que la creación por REST, sobre el usuario
  autenticado de la sesión.
- **FR-019**: El sistema MUST ofrecer por MCP la herramienta `listar_reservas(skip, limit)`
  con el mismo comportamiento que el listado por REST.
- **FR-020**: El sistema MUST ofrecer por MCP la herramienta `cancelar_reserva(reserva_id,
  confirmar)`; si `confirmar` no es verdadero, el servidor MUST NOT eliminar nada y MUST
  responder pidiendo confirmación (RN-6). Con confirmación, MUST verificar antes que la
  reserva pertenece al usuario.
- **FR-021**: La confirmación de cancelación MUST validarla el servidor; no puede depender de
  que el asistente decida preguntar.
- **FR-022**: El usuario de la sesión MCP MUST obtenerse del mismo token que usa el acceso
  REST, enviado como credencial de portador en la cabecera de autorización.
- **FR-023**: Los errores en MCP MUST devolverse con formato `{"error": "..."}`.
- **FR-024**: Las reglas de negocio MUST ser idénticas por REST y por MCP: ambas vías
  MUST producir el mismo resultado ante la misma situación (aunque cambie el formato de la
  respuesta).

**Cobertura de pruebas exigida por el contrato**

- **FR-025**: Cada regla de negocio (RN-1 a RN-6) MUST tener al menos una prueba, y los
  siete casos de error explícitos listados en "Casos de error con prueba obligatoria"
  MUST tener su prueba.

### Contrato de la API (REST)

| Método | Ruta | Auth | Request | Éxito | Errores esperados |
|--------|------|------|---------|-------|-------------------|
| POST | /auth/registro | No | email, password | 201 Usuario (sin contraseña) | 400 email ya registrado, 422 |
| POST | /auth/login | No | formulario OAuth2: username (email), password | 200 access_token, token_type | 401 credenciales inválidas |
| POST | /reservas/ | Sí | fecha, hora_inicio, hora_fin | 201 Reserva | 400 horario solapado, 400 horas inválidas, 401, 422 |
| GET | /reservas/ | Sí | query: skip, limit | 200 lista (solo del usuario) | 401 |
| GET | /reservas/{id} | Sí | — | 200 Reserva | 401, 403 no es dueño, 404 |
| PUT | /reservas/{id} | Sí | fecha, hora_inicio, hora_fin | 200 Reserva | 400 solapado, 400 horas inválidas, 401, 403, 404, 422 |
| DELETE | /reservas/{id} | Sí | — | 204 | 401, 403 no es dueño, 404 |

### Contrato equivalente por MCP

| Herramienta | Parámetros | Comportamiento |
|-------------|------------|----------------|
| `crear_reserva` | fecha, hora_inicio, hora_fin | Mismas reglas que POST /reservas/, sobre el usuario de la sesión |
| `listar_reservas` | skip, limit | Mismo comportamiento que GET /reservas/ |
| `cancelar_reserva` | reserva_id, confirmar | Sin `confirmar=true`: no elimina y pide confirmación. Con confirmación: verifica propiedad y elimina |

Errores MCP: `{"error": "..."}`. Identidad: mismo token que REST (cabecera de autorización
de portador).

### Casos de error con prueba obligatoria

1. Crear una reserva cuyo horario se solapa con una existente → 400.
2. Crear una reserva con hora_fin anterior o igual a hora_inicio → 400.
3. Listar o crear reservas sin token → 401.
4. Ver, modificar o cancelar una reserva de otro usuario pasando su id manualmente → 403.
5. Cancelar o consultar una reserva inexistente → 404.
6. Registrar un email ya existente → 400.
7. `cancelar_reserva` por MCP sin `confirmar=true` → no elimina, devuelve mensaje de
   confirmación requerida.

### Key Entities *(include if feature involves data)*

- **Usuario**: persona registrada. Atributos: email (único), contraseña (nunca expuesta).
  Es dueño de cero o más reservas.
- **Reserva**: ocupación de la sala en un intervalo. Atributos: fecha, hora de inicio, hora
  de fin; pertenece a exactamente un usuario. Dos reservas no pueden solaparse en fecha y
  horario, con independencia de su dueño.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de los intentos de crear o modificar una reserva que se solape con
  otra existente (de cualquier usuario) son rechazados; ninguna pareja de reservas
  solapadas llega a existir.
- **SC-002**: El 100 % de los intentos de ver, modificar o cancelar reservas de otro usuario
  son rechazados y no revelan sus datos.
- **SC-003**: El 100 % de las solicitudes sobre reservas sin credenciales válidas son
  rechazadas, tanto por REST como por MCP.
- **SC-004**: Ninguna respuesta del sistema contiene la contraseña de un usuario.
- **SC-005**: Una cancelación por MCP sin confirmación explícita elimina 0 reservas en el
  100 % de los casos.
- **SC-006**: Para la misma situación, REST y MCP aplican el mismo resultado de negocio en
  el 100 % de los casos verificados.
- **SC-007**: Un usuario nuevo puede registrarse, iniciar sesión y crear su primera reserva
  en menos de 2 minutos.
- **SC-008**: Las 6 reglas de negocio y los 7 casos de error explícitos cuentan cada uno con
  al menos una prueba que pasa.

## Assumptions

- Hay una única sala; no existe el concepto de varias salas ni de sala en las reservas.
- Fecha y hora son las de un único huso horario común; no se contemplan husos por usuario.
- Formatos de entrada: fecha `YYYY-MM-DD`, hora `HH:MM`.
- Dos reservas del mismo día son contiguas (no solapadas) si una termina exactamente cuando
  empieza la otra.
- Una reserva no cruza la medianoche.
- No se restringe crear reservas en fechas pasadas ni se impone duración mínima o máxima;
  queda fuera del alcance de esta versión.
- No hay roles ni administradores: todos los usuarios tienen los mismos permisos sobre sus
  propias reservas.
- Modificar es una sustitución completa de fecha y horario (los tres campos se envían).
- El listado se ordena de forma estable y determinista; `skip` y `limit` tienen valores por
  defecto razonables cuando no se indican.
- Alcance excluido: recuperación de contraseña, verificación de email, cierre de sesión,
  notificaciones, edición o baja de usuarios, y modificación de reservas por MCP.
- Las decisiones de arquitectura, seguridad y pruebas están gobernadas por
  `.specify/memory/constitution.md` y se detallarán en el plan, no en esta especificación.
