"""Repositories falsos en memoria para los tests unitarios de `services/` (Art. VII.2).

Son clases escritas a mano que cumplen los Protocols de `app/repositories/base.py`. El
parámetro `db` se ignora: los tests pasan `db=None`. Está PROHIBIDO usar dobles de prueba
generados por librerías (Art. VII.2).

Los fakes NO aplican ninguna regla de negocio. En particular, `listar_por_fecha` devuelve las
reservas de esa fecha sin fórmula de solapamiento: así los tests de RN-1 y de reservas
contiguas prueban de verdad la lógica del servicio y no la del fake.
"""

from datetime import date, time

from sqlalchemy.orm import Session

from app.models import Reserva, Usuario


class FakeReservaRepository:
    """`ReservaRepositoryProtocol` en memoria.

    - `reservas`: lista con lo almacenado (objetos `Reserva` en memoria, sin sesión de BD).
    - `llamadas`: nombre de cada método invocado, en orden, para afirmar que el servicio
      no tocó el repository (p. ej. RN-6: sin confirmación no hay ni siquiera `existe`).
    - `eliminadas`: ids de las reservas que se eliminaron.
    """

    def __init__(self) -> None:
        self.reservas: list[Reserva] = []
        self.llamadas: list[str] = []
        self.eliminadas: list[int] = []
        self._siguiente_id = 1

    def sembrar(
        self, usuario_id: int, fecha: date, hora_inicio: time, hora_fin: time
    ) -> Reserva:
        """Prepara datos de un test. No forma parte del Protocol y no se registra en `llamadas`."""
        reserva = Reserva(
            id=self._siguiente_id,
            usuario_id=usuario_id,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
        )
        self._siguiente_id += 1
        self.reservas.append(reserva)
        return reserva

    def crear(
        self,
        db: Session | None,
        usuario_id: int,
        fecha: date,
        hora_inicio: time,
        hora_fin: time,
    ) -> Reserva:
        self.llamadas.append("crear")
        return self.sembrar(usuario_id, fecha, hora_inicio, hora_fin)

    def listar_por_usuario(
        self, db: Session | None, usuario_id: int, skip: int, limit: int
    ) -> list[Reserva]:
        self.llamadas.append("listar_por_usuario")
        propias = [r for r in self.reservas if r.usuario_id == usuario_id]
        propias.sort(key=lambda r: (r.fecha, r.hora_inicio, r.id))
        return propias[skip : skip + limit]

    def obtener_de_usuario(
        self, db: Session | None, reserva_id: int, usuario_id: int
    ) -> Reserva | None:
        self.llamadas.append("obtener_de_usuario")
        for reserva in self.reservas:
            if reserva.id == reserva_id and reserva.usuario_id == usuario_id:
                return reserva
        return None

    def existe(self, db: Session | None, reserva_id: int) -> bool:
        self.llamadas.append("existe")
        return any(r.id == reserva_id for r in self.reservas)

    def listar_por_fecha(self, db: Session | None, fecha: date) -> list[Reserva]:
        self.llamadas.append("listar_por_fecha")
        del_dia = [r for r in self.reservas if r.fecha == fecha]
        del_dia.sort(key=lambda r: (r.hora_inicio, r.id))
        return del_dia

    def actualizar(
        self,
        db: Session | None,
        reserva: Reserva,
        fecha: date,
        hora_inicio: time,
        hora_fin: time,
    ) -> Reserva:
        self.llamadas.append("actualizar")
        reserva.fecha = fecha
        reserva.hora_inicio = hora_inicio
        reserva.hora_fin = hora_fin
        return reserva

    def eliminar(self, db: Session | None, reserva: Reserva) -> None:
        self.llamadas.append("eliminar")
        self.reservas.remove(reserva)
        self.eliminadas.append(reserva.id)


class FakeUsuarioRepository:
    """`UsuarioRepositoryProtocol` en memoria.

    `obtener_por_email` compara el texto tal cual, sin normalizar: la normalización a
    minúsculas (RN-5) es del servicio, y así los tests la prueban de verdad.
    """

    def __init__(self) -> None:
        self.usuarios: list[Usuario] = []
        self._siguiente_id = 1

    def crear(self, db: Session | None, email: str, password_hash: str) -> Usuario:
        usuario = Usuario(id=self._siguiente_id, email=email, password_hash=password_hash)
        self._siguiente_id += 1
        self.usuarios.append(usuario)
        return usuario

    def obtener_por_email(self, db: Session | None, email: str) -> Usuario | None:
        for usuario in self.usuarios:
            if usuario.email == email:
                return usuario
        return None

    def obtener_por_id(self, db: Session | None, usuario_id: int) -> Usuario | None:
        for usuario in self.usuarios:
            if usuario.id == usuario_id:
                return usuario
        return None
