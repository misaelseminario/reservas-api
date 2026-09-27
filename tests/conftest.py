"""Configuración común de los tests.

Las variables de entorno se fijan ANTES de importar nada de `app`, para que los tests no
dependan del `.env` real (que contiene el secreto de desarrollo). Los valores de aquí son
solo de prueba. Los fixtures de BD y de cliente se añaden en la tarea T042.
"""

import os

os.environ.setdefault("SECRET_KEY", "clave-solo-para-tests-0123456789abcdef0123456789abcdef")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_placeholder.db")
