"""Tests unitarios de los schemas Pydantic. Sin dobles de prueba de terceros y sin base de datos."""

from datetime import date, time

import pytest
from pydantic import ValidationError

from app.models import Reserva, Usuario
from app.schemas.reserva import ReservaActualizar, ReservaCrear, ReservaLeer
from app.schemas.usuario import Token, UsuarioCrear, UsuarioLeer

EMAIL = "ana@example.com"


# --- usuario -----------------------------------------------------------------------------


def test_usuario_leer_no_tiene_password_ni_hash():
    assert "password" not in UsuarioLeer.model_fields
    assert "password_hash" not in UsuarioLeer.model_fields


def test_serializar_un_usuario_no_incluye_password_ni_hash():
    usuario = Usuario(id=1, email=EMAIL, password_hash="h" * 60)
    salida = UsuarioLeer.model_validate(usuario).model_dump()
    assert salida == {"id": 1, "email": EMAIL}
    assert "password" not in salida and "password_hash" not in salida


def test_password_de_7_caracteres_es_invalida():
    with pytest.raises(ValidationError):
        UsuarioCrear(email=EMAIL, password="1234567")


def test_password_de_8_caracteres_es_valida():
    assert UsuarioCrear(email=EMAIL, password="12345678").password == "12345678"


def test_password_de_73_bytes_es_invalida():
    # 40 caracteres 'é' = 80 bytes en UTF-8 (supera el límite de 72 de bcrypt).
    with pytest.raises(ValidationError):
        UsuarioCrear(email=EMAIL, password="é" * 40)
    # 36 'é' + 'a' = 73 bytes: justo por encima del límite.
    with pytest.raises(ValidationError):
        UsuarioCrear(email=EMAIL, password="é" * 36 + "a")


def test_password_de_exactamente_72_bytes_es_valida():
    password = "é" * 36  # 72 bytes
    assert len(password.encode("utf-8")) == 72
    assert UsuarioCrear(email=EMAIL, password=password).password == password


def test_email_invalido_es_error():
    with pytest.raises(ValidationError):
        UsuarioCrear(email="no-es-un-email", password="12345678")


def test_token_tiene_access_token_y_token_type():
    token = Token(access_token="abc", token_type="bearer")
    assert token.model_dump() == {"access_token": "abc", "token_type": "bearer"}


# --- reserva -----------------------------------------------------------------------------

VALIDA = {"fecha": "2030-01-15", "hora_inicio": "09:00", "hora_fin": "10:00"}


@pytest.mark.parametrize("schema", [ReservaCrear, ReservaActualizar])
def test_reserva_acepta_formato_correcto(schema):
    reserva = schema(**VALIDA)
    assert reserva.fecha == date(2030, 1, 15)
    assert reserva.hora_inicio == time(9, 0)
    assert reserva.hora_fin == time(10, 0)


@pytest.mark.parametrize("schema", [ReservaCrear, ReservaActualizar])
@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("fecha", "15/01/2030"),
        ("fecha", "2030-01-15T10:00:00"),
        ("hora_inicio", "25:00"),
        ("hora_inicio", "09:00:30"),
        ("hora_fin", "9:00"),
        ("hora_fin", "09:00:30"),
    ],
)
def test_reserva_rechaza_formatos_invalidos(schema, campo, valor):
    with pytest.raises(ValidationError):
        schema(**{**VALIDA, campo: valor})


@pytest.mark.parametrize("schema", [ReservaCrear, ReservaActualizar])
@pytest.mark.parametrize("campo", ["fecha", "hora_inicio", "hora_fin"])
def test_reserva_exige_los_tres_campos(schema, campo):
    datos = {clave: valor for clave, valor in VALIDA.items() if clave != campo}
    with pytest.raises(ValidationError):
        schema(**datos)


def test_el_schema_no_aplica_reglas_de_negocio():
    # RN-2 (fin > inicio) es regla de `services/`: el schema solo valida el formato.
    assert ReservaCrear(**{**VALIDA, "hora_fin": "08:00"}).hora_fin == time(8, 0)


def test_reserva_leer_serializa_una_reserva():
    reserva = Reserva(
        id=3, usuario_id=2, fecha=date(2030, 1, 15), hora_inicio=time(9), hora_fin=time(10)
    )
    salida = ReservaLeer.model_validate(reserva)
    assert (salida.id, salida.usuario_id, salida.fecha) == (3, 2, date(2030, 1, 15))
    assert set(ReservaLeer.model_fields) == {
        "id",
        "usuario_id",
        "fecha",
        "hora_inicio",
        "hora_fin",
    }
