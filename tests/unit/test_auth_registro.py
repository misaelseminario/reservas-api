"""Tests unitarios de `registrar_usuario` (RN-5). Repository falso, sin BD y sin dobles de terceros."""

import pytest

from app.core.security import verificar_password
from app.schemas.usuario import UsuarioLeer
from app.services.auth import registrar_usuario
from app.services.excepciones import EmailYaRegistradoError
from tests.unit.fakes import FakeUsuarioRepository

PASSWORD = "clave-segura-1"


def test_registro_nuevo_guarda_el_usuario_con_el_hash_y_no_la_contrasena():
    repo = FakeUsuarioRepository()

    usuario = registrar_usuario(None, "ana@example.com", PASSWORD, repo=repo)

    assert usuario.id is not None
    assert usuario.email == "ana@example.com"
    assert usuario.password_hash != PASSWORD
    assert verificar_password(PASSWORD, usuario.password_hash) is True
    assert repo.usuarios == [usuario]


def test_rn5_email_duplicado_lanza_email_ya_registrado():
    repo = FakeUsuarioRepository()
    registrar_usuario(None, "ana@example.com", PASSWORD, repo=repo)

    with pytest.raises(EmailYaRegistradoError, match="El email ya está registrado"):
        registrar_usuario(None, "ana@example.com", "otra-clave-9", repo=repo)

    assert len(repo.usuarios) == 1


def test_rn5_el_email_se_compara_sin_distinguir_mayusculas():
    repo = FakeUsuarioRepository()
    registrar_usuario(None, "Usuario@X.com", PASSWORD, repo=repo)

    with pytest.raises(EmailYaRegistradoError):
        registrar_usuario(None, "usuario@x.com", PASSWORD, repo=repo)

    assert len(repo.usuarios) == 1


def test_rn5_el_email_se_guarda_en_minusculas():
    repo = FakeUsuarioRepository()

    usuario = registrar_usuario(None, "Usuario@X.com", PASSWORD, repo=repo)

    assert usuario.email == "usuario@x.com"
    assert repo.usuarios[0].email == "usuario@x.com"


def test_emails_distintos_se_registran_como_usuarios_distintos():
    repo = FakeUsuarioRepository()

    ana = registrar_usuario(None, "ana@example.com", PASSWORD, repo=repo)
    luis = registrar_usuario(None, "luis@example.com", PASSWORD, repo=repo)

    assert ana.id != luis.id
    assert len(repo.usuarios) == 2


def test_el_usuario_devuelto_no_expone_la_contrasena():
    repo = FakeUsuarioRepository()

    usuario = registrar_usuario(None, "ana@example.com", PASSWORD, repo=repo)

    assert not hasattr(usuario, "password")
    assert PASSWORD not in {str(valor) for valor in vars(usuario).values()}
    # El schema de salida (lo que ve el cliente) solo lleva id y email.
    assert UsuarioLeer.model_validate(usuario).model_dump() == {
        "id": usuario.id,
        "email": "ana@example.com",
    }
