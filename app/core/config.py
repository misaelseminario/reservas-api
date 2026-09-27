"""Configuración de la aplicación, leída del entorno / `.env` con pydantic-settings.

Ningún valor tiene un valor por defecto: los secretos y parámetros viven solo en `.env`
(Art. IV.3). Si falta alguna variable, la aplicación no arranca.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    DATABASE_URL: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
