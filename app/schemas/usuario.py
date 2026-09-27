"""Schemas Pydantic de usuario, separados del modelo ORM (Art. III.2).

Solo validan formato. La normalización del email (RN-5) es regla de negocio y vive en
`services/auth.py`. La contraseña NUNCA aparece en un schema de salida.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

PASSWORD_LONGITUD_MINIMA = 8
# bcrypt solo admite contraseñas de hasta 72 bytes (bcrypt 5 lanza ValueError por encima).
PASSWORD_BYTES_MAXIMOS = 72


class UsuarioCrear(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def _validar_password(cls, valor: str) -> str:
        if len(valor) < PASSWORD_LONGITUD_MINIMA:
            raise ValueError(
                f"La contraseña debe tener al menos {PASSWORD_LONGITUD_MINIMA} caracteres"
            )
        if len(valor.encode("utf-8")) > PASSWORD_BYTES_MAXIMOS:
            raise ValueError(
                f"La contraseña no puede superar {PASSWORD_BYTES_MAXIMOS} bytes en UTF-8"
            )
        return valor


class UsuarioLeer(BaseModel):
    """Salida de usuario: sin `password` ni `password_hash`."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str
