"""Tests unitarios de `app/core/security.py` (hash bcrypt y JWT). Sin dobles de prueba de terceros."""

from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings
from app.core.security import (
    crear_token,
    decodificar_token,
    hashear_password,
    verificar_password,
)


def _token_con(carga: dict, clave: str | None = None) -> str:
    ajustes = get_settings()
    return jwt.encode(carga, clave or ajustes.SECRET_KEY, algorithm=ajustes.ALGORITHM)


def _en(minutos: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutos)


# --- hash de contraseñas -----------------------------------------------------------------


def test_el_hash_no_es_la_contrasena():
    assert hashear_password("clave-segura-1") != "clave-segura-1"


def test_verificar_password_correcta_e_incorrecta():
    hash_ = hashear_password("clave-segura-1")
    assert verificar_password("clave-segura-1", hash_) is True
    assert verificar_password("otra-clave", hash_) is False


def test_dos_hashes_de_la_misma_contrasena_difieren():
    assert hashear_password("clave-segura-1") != hashear_password("clave-segura-1")


def test_verificar_con_hash_mal_formado_devuelve_false():
    assert verificar_password("clave-segura-1", "esto-no-es-un-hash") is False


# --- JWT ---------------------------------------------------------------------------------


def test_token_ida_y_vuelta_devuelve_el_mismo_id():
    assert decodificar_token(crear_token("42")) == 42


def test_token_con_otra_firma_devuelve_none():
    token = _token_con({"sub": "1", "exp": _en(5)}, clave="otra-clave-distinta-de-32-caracteres-o-mas")
    assert decodificar_token(token) is None


def test_token_mal_formado_devuelve_none():
    assert decodificar_token("esto.no.es-un-jwt") is None
    assert decodificar_token("basura") is None


def test_cadena_vacia_devuelve_none():
    assert decodificar_token("") is None


def test_token_expirado_devuelve_none():
    token = _token_con({"sub": "1", "exp": _en(-5)})
    assert decodificar_token(token) is None


def test_sub_no_numerico_devuelve_none():
    token = _token_con({"sub": "no-es-un-numero", "exp": _en(5)})
    assert decodificar_token(token) is None


def test_token_sin_exp_o_sin_sub_devuelve_none():
    assert decodificar_token(_token_con({"sub": "1"})) is None
    assert decodificar_token(_token_con({"exp": _en(5)})) is None
