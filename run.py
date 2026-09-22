"""
Punto de entrada recomendado para levantar el servidor en desarrollo.

Usar esto en vez de `uvicorn main:app --reload` a secas evita dos errores
comunes:
1. Olvidar --no-proxy-headers: sin él, uvicorn confía por defecto en el
   header X-Forwarded-For para conexiones locales, lo que permite evadir
   el rate limiting por IP (ver sección 10.13 del README).
2. Olvidar correr "alembic upgrade head" antes de arrancar: sin las tablas
   creadas, cualquier endpoint que toque la base de datos revienta con 500.

Uso:
    python3 run.py   (macOS/Linux)
    python run.py    (Windows)
"""
import uvicorn
from alembic.config import Config
from alembic import command


def run_migrations():
    command.upgrade(Config("alembic.ini"), "head")


if __name__ == "__main__":
    run_migrations()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, proxy_headers=False)
