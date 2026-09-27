"""Repositories y servicios REALES contra un SQLite REAL (archivo temporal), sin fakes (T043).

Es la prueba de integración exigida por el Art. VII.4: aquí se comprueba con datos reales que
las consultas de los repositories devuelven lo correcto y que la fórmula de solapamiento de
`services/reservas.py` (RN-1) clasifica bien contra SQL real. Cada test usa su propio archivo
(`motor_temporal`).
"""

from datetime import date, datetime, time

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.database import abrir_sesion
from app.core.security import verificar_password
from app.repositories.reserva_repository import reserva_repository
from app.repositories.usuario_repository import usuario_repository
from app.services import auth as servicio_auth
from app.services import reservas as servicio
from app.services.excepciones import (
    ConfirmacionRequeridaError,
    HorarioInvalidoError,
    NoEsDuenoError,
    ReservaNoEncontradaError,
    ReservaSolapadaError,
)

DIA = date(2030, 1, 15)
OTRO_DIA = date(2030, 1, 16)
AHORA = datetime(2029, 12, 1, 8, 0)  # reloj inyectado: todo lo de 2030 es futuro
CLAVE = "clave-segura-1"


def h(texto: str) -> time:
    return time.fromisoformat(texto)


@pytest.fixture
def db(motor_temporal):
    with abrir_sesion() as sesion:
        yield sesion


@pytest.fixture
def ana(db):
    return servicio_auth.registrar_usuario(db, "ana@example.com", CLAVE)


@pytest.fixture
def luis(db):
    return servicio_auth.registrar_usuario(db, "luis@example.com", CLAVE)


def _crear(db, usuario, inicio, fin, dia=DIA):
    return servicio.crear_reserva(db, usuario.id, dia, h(inicio), h(fin), ahora=AHORA)


# --- ciclo completo -----------------------------------------------------------------------


def test_ciclo_crear_solapar_listar_obtener_modificar_eliminar(db, ana):
    creada = _crear(db, ana, "09:00", "10:00")
    assert (creada.id, creada.usuario_id, creada.fecha) == (1, ana.id, DIA)
    assert (creada.hora_inicio, creada.hora_fin) == (h("09:00"), h("10:00"))

    with pytest.raises(ReservaSolapadaError):
        _crear(db, ana, "09:30", "10:30")

    assert [r.id for r in servicio.listar_reservas(db, ana.id)] == [creada.id]
    assert servicio.obtener_reserva(db, ana.id, creada.id).id == creada.id

    modificada = servicio.actualizar_reserva(
        db, ana.id, creada.id, DIA, h("11:00"), h("12:00"), ahora=AHORA
    )
    assert (modificada.hora_inicio, modificada.hora_fin) == (h("11:00"), h("12:00"))
    db.expire_all()  # releer desde el archivo, no de la caché de la sesión
    assert servicio.obtener_reserva(db, ana.id, creada.id).hora_inicio == h("11:00")

    servicio.eliminar_reserva(db, ana.id, creada.id, confirmar=True)
    assert servicio.listar_reservas(db, ana.id) == []
    with pytest.raises(ReservaNoEncontradaError):
        servicio.obtener_reserva(db, ana.id, creada.id)


def test_los_datos_persisten_en_el_archivo_y_los_lee_otra_sesion(db, ana):
    creada = _crear(db, ana, "09:00", "10:00")

    with abrir_sesion() as otra_sesion:
        leida = servicio.obtener_reserva(otra_sesion, ana.id, creada.id)

    assert (leida.fecha, leida.hora_inicio, leida.hora_fin) == (DIA, h("09:00"), h("10:00"))


# --- matriz de solapamiento de data-model.md contra SQL real ------------------------------

# Existente: 09:00-10:00 el DIA. (inicio, fin, día, ¿debe solaparse?)
MATRIZ = [
    ("10:00", "11:00", DIA, False),  # contigua: la nueva empieza cuando termina la existente
    ("08:00", "09:00", DIA, False),  # contigua a la inversa
    ("09:00", "10:00", DIA, True),  # idéntica
    ("09:15", "09:45", DIA, True),  # contenida
    ("08:00", "11:00", DIA, True),  # que contiene
    ("09:30", "10:30", DIA, True),  # parcial por el final
    ("08:30", "09:30", DIA, True),  # parcial por el inicio
    ("09:00", "10:00", OTRO_DIA, False),  # mismo horario, otra fecha
]


@pytest.mark.parametrize(("inicio", "fin", "dia", "solapa"), MATRIZ)
def test_matriz_de_solapamiento_contra_sqlite_real(db, ana, luis, inicio, fin, dia, solapa):
    _crear(db, ana, "09:00", "10:00")  # la existente es de Ana; la nueva, de Luis (RN-1 global)

    if solapa:
        with pytest.raises(ReservaSolapadaError):
            _crear(db, luis, inicio, fin, dia)
        assert servicio.listar_reservas(db, luis.id) == []
    else:
        assert _crear(db, luis, inicio, fin, dia).id == 2


def test_las_reservas_contiguas_se_permiten_en_ambos_ordenes(db, ana, luis):
    _crear(db, ana, "10:00", "11:00")
    assert _crear(db, luis, "09:00", "10:00").id == 2  # termina justo cuando empieza la otra
    assert _crear(db, luis, "11:00", "12:00").id == 3  # empieza justo cuando termina la otra


def test_horario_invalido_no_llega_a_la_base_de_datos(db, ana):
    with pytest.raises(HorarioInvalidoError):
        _crear(db, ana, "10:00", "10:00")
    assert servicio.listar_reservas(db, ana.id) == []


def test_al_modificar_la_reserva_no_se_solapa_consigo_misma_pero_si_con_otra(db, ana, luis):
    propia = _crear(db, ana, "09:00", "10:00")
    _crear(db, luis, "11:00", "12:00")

    ampliada = servicio.actualizar_reserva(
        db, ana.id, propia.id, DIA, h("08:30"), h("10:30"), ahora=AHORA
    )
    assert (ampliada.hora_inicio, ampliada.hora_fin) == (h("08:30"), h("10:30"))  # RN-4

    with pytest.raises(ReservaSolapadaError):
        servicio.actualizar_reserva(
            db, ana.id, propia.id, DIA, h("10:30"), h("11:30"), ahora=AHORA
        )
    db.expire_all()
    assert servicio.obtener_reserva(db, ana.id, propia.id).hora_fin == h("10:30")  # intacta


# --- repositories reales --------------------------------------------------------------------


def test_listar_por_fecha_devuelve_solo_esa_fecha_de_cualquier_usuario(db, ana, luis):
    a = _crear(db, ana, "09:00", "10:00")
    b = _crear(db, luis, "11:00", "12:00")
    _crear(db, ana, "09:00", "10:00", OTRO_DIA)

    resultado = reserva_repository.listar_por_fecha(db, DIA)

    assert [r.id for r in resultado] == [a.id, b.id]
    assert {r.usuario_id for r in resultado} == {ana.id, luis.id}
    assert reserva_repository.listar_por_fecha(db, date(2031, 1, 1)) == []


def test_listar_por_usuario_solo_devuelve_las_del_usuario(db, ana, luis):
    _crear(db, ana, "09:00", "10:00")
    _crear(db, luis, "11:00", "12:00")

    propias = reserva_repository.listar_por_usuario(db, ana.id, 0, 100)

    assert [r.usuario_id for r in propias] == [ana.id]
    assert reserva_repository.listar_por_usuario(db, 999, 0, 100) == []


def test_listar_por_usuario_ordena_por_fecha_hora_inicio_e_id_y_pagina(db, ana):
    tarde = _crear(db, ana, "15:00", "16:00")
    manana = _crear(db, ana, "09:00", "10:00")
    otro_dia = _crear(db, ana, "08:00", "09:00", OTRO_DIA)

    todas = reserva_repository.listar_por_usuario(db, ana.id, 0, 100)
    assert [r.id for r in todas] == [manana.id, tarde.id, otro_dia.id]

    assert [r.id for r in reserva_repository.listar_por_usuario(db, ana.id, 1, 1)] == [tarde.id]
    assert [r.id for r in reserva_repository.listar_por_usuario(db, ana.id, 0, 2)] == [
        manana.id,
        tarde.id,
    ]
    assert reserva_repository.listar_por_usuario(db, ana.id, 5, 100) == []


def test_obtener_de_usuario_exige_id_y_dueno(db, ana, luis):
    reserva = _crear(db, ana, "09:00", "10:00")

    assert reserva_repository.obtener_de_usuario(db, reserva.id, ana.id).id == reserva.id
    assert reserva_repository.obtener_de_usuario(db, reserva.id, luis.id) is None


def test_existe_no_filtra_por_dueno(db, ana):
    reserva = _crear(db, ana, "09:00", "10:00")

    assert reserva_repository.existe(db, reserva.id) is True
    assert reserva_repository.existe(db, 9999) is False


def test_rn3_reserva_ajena_da_403_e_inexistente_da_404(db, ana, luis):
    reserva = _crear(db, ana, "09:00", "10:00")

    with pytest.raises(NoEsDuenoError):
        servicio.obtener_reserva(db, luis.id, reserva.id)
    with pytest.raises(ReservaNoEncontradaError):
        servicio.obtener_reserva(db, luis.id, 9999)


def test_eliminar_sin_confirmar_no_borra_nada_y_ajena_tampoco(db, ana, luis):
    reserva = _crear(db, ana, "09:00", "10:00")

    with pytest.raises(ConfirmacionRequeridaError):
        servicio.eliminar_reserva(db, ana.id, reserva.id, confirmar=False)
    with pytest.raises(NoEsDuenoError):
        servicio.eliminar_reserva(db, luis.id, reserva.id, confirmar=True)

    assert reserva_repository.existe(db, reserva.id) is True


# --- usuarios y restricciones de la BD ------------------------------------------------------


def test_usuario_repository_crea_y_busca_por_email_y_por_id(db):
    creado = usuario_repository.crear(db, "ana@example.com", "hash")

    assert usuario_repository.obtener_por_email(db, "ana@example.com").id == creado.id
    assert usuario_repository.obtener_por_id(db, creado.id).email == "ana@example.com"
    assert usuario_repository.obtener_por_email(db, "nadie@example.com") is None
    assert usuario_repository.obtener_por_id(db, 999) is None


def test_email_duplicado_viola_la_restriccion_unique(db):
    usuario_repository.crear(db, "ana@example.com", "hash")

    with pytest.raises(IntegrityError):
        usuario_repository.crear(db, "ana@example.com", "otro-hash")


def test_la_clave_foranea_rechaza_un_usuario_inexistente(db):
    assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1

    with pytest.raises(IntegrityError):
        reserva_repository.crear(db, 999, DIA, h("09:00"), h("10:00"))


def test_el_hash_guardado_no_es_la_contrasena(db, ana):
    guardado = db.execute(
        text("SELECT password_hash FROM usuarios WHERE id = :id"), {"id": ana.id}
    ).scalar_one()

    assert guardado != CLAVE
    assert CLAVE not in guardado
    assert guardado.startswith("$2")  # bcrypt
    assert verificar_password(CLAVE, guardado) is True
