"""Tests unitarios de `autenticar_usuario` y `obtener_usuario_actual`. Repository falso, sin BD."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import crear_token
from app.services.auth import autenticar_usuario, obtener_usuario_actual, registrar_usuario
from app.services.excepciones import NoAutenticadoError
from tests.unit.fakes import FakeUsuarioRepository

PASSWORD = "clave-segura-1"


@pytest.fixture
def repo() -> FakeUsuarioRepository:
    return FakeUsuarioRepository()


def _token_con(carga: dict) -> str:
    ajustes = get_settings()
    return jwt.encode(carga, ajustes.SECRET_KEY, algorithm=ajustes.ALGORITHM)


def _en(minutos: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutos)


# --- login -------------------------------------------------------------------------------


def test_login_correcto_devuelve_un_token_que_resuelve_al_mismo_usuario(repo):
    usuario = registrar_usuario(None, "ana@example.com", PASSWORD, repo=repo)

    token = autenticar_usuario(None, "ana@example.com", PASSWORD, repo=repo)

    assert obtener_usuario_actual(None, token, repo=repo) is usuario


@pytest.mark.parametrize("email_de_login", ["usuario@x.com", "USUARIO@X.COM", "Usuario@X.com"])
def test_rn5_login_no_distingue_mayusculas_del_email(repo, email_de_login):
    usuario = registrar_usuario(None, "Usuario@X.com", PASSWORD, repo=repo)

    token = autenticar_usuario(None, email_de_login, PASSWORD, repo=repo)

    assert obtener_usuario_actual(None, token, repo=repo) is usuario


def test_contrasena_incorrecta_lanza_no_autenticado(repo):
    registrar_usuario(None, "ana@example.com", PASSWORD, repo=repo)

    with pytest.raises(NoAutenticadoError, match="Credenciales incorrectas"):
        autenticar_usuario(None, "ana@example.com", "otra-clave-9", repo=repo)


def test_email_inexistente_lanza_no_autenticado(repo):
    with pytest.raises(NoAutenticadoError, match="Credenciales incorrectas"):
        autenticar_usuario(None, "nadie@example.com", PASSWORD, repo=repo)


def test_email_inexistente_y_contrasena_incorrecta_dan_el_mismo_mensaje(repo):
    registrar_usuario(None, "ana@example.com", PASSWORD, repo=repo)

    with pytest.raises(NoAutenticadoError) as por_password:
        autenticar_usuario(None, "ana@example.com", "otra-clave-9", repo=repo)
    with pytest.raises(NoAutenticadoError) as por_email:
        autenticar_usuario(None, "nadie@example.com", PASSWORD, repo=repo)

    assert str(por_password.value) == str(por_email.value)


# --- validación del token ----------------------------------------------------------------


@pytest.mark.parametrize("token", [None, "", "basura", "esto.no.es-un-jwt"])
def test_token_ausente_vacio_o_basura_lanza_no_autenticado(repo, token):
    registrar_usuario(None, "ana@example.com", PASSWORD, repo=repo)

    with pytest.raises(NoAutenticadoError, match="^No autenticado$"):
        obtener_usuario_actual(None, token, repo=repo)


def test_token_expirado_lanza_no_autenticado(repo):
    usuario = registrar_usuario(None, "ana@example.com", PASSWORD, repo=repo)
    expirado = _token_con({"sub": str(usuario.id), "exp": _en(-5)})

    with pytest.raises(NoAutenticadoError, match="^No autenticado$"):
        obtener_usuario_actual(None, expirado, repo=repo)


def test_token_de_un_usuario_que_ya_no_existe_lanza_no_autenticado(repo):
    usuario = registrar_usuario(None, "ana@example.com", PASSWORD, repo=repo)
    token = crear_token(str(usuario.id))
    repo.usuarios.clear()  # el usuario desaparece después de emitirse el token

    with pytest.raises(NoAutenticadoError, match="^No autenticado$"):
        obtener_usuario_actual(None, token, repo=repo)


def test_token_valido_resuelve_al_usuario_que_lleva_en_sub(repo):
    registrar_usuario(None, "ana@example.com", PASSWORD, repo=repo)
    luis = registrar_usuario(None, "luis@example.com", PASSWORD, repo=repo)

    assert obtener_usuario_actual(None, crear_token(str(luis.id)), repo=repo) is luis
