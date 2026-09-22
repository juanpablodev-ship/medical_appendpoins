"""
Punto de entrada recomendado para levantar el servidor en desarrollo.

Usar esto en vez de `uvicorn main:app --reload` a secas evita tener que
acordarse del flag --no-proxy-headers cada vez: sin él, uvicorn confía por
defecto en el header X-Forwarded-For para conexiones locales, lo que permite
evadir el rate limiting por IP (ver sección 10.13 del README).

Uso:
    python3 run.py   (macOS/Linux)
    python run.py    (Windows)
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, proxy_headers=False)
