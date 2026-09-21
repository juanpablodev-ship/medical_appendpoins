import os
import secrets
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from models import User, RevokedToken, RateLimitAttempt

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    print(
        "\n[AVISO DE SEGURIDAD] No se definió la variable de entorno SECRET_KEY.\n"
        "Se generó una clave aleatoria válida solo para esta ejecución: los tokens\n"
        "emitidos ahora dejarán de ser válidos si reinicias el servidor.\n"
        "Define SECRET_KEY en tu entorno para producción, ej:\n"
        "  export SECRET_KEY=$(python3 -c \"import secrets; print(secrets.token_hex(32))\")\n"
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
VERIFICATION_TOKEN_EXPIRE_HOURS = 24

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER or "no-reply@medical-appointments.local")
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8000")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Hash "señuelo" usado cuando el email no existe, para que el tiempo de
# respuesta de un login fallido no delate si el email está registrado.
_DUMMY_HASH = pwd_context.hash("dummy-password-para-tiempo-constante")

LOGIN_ATTEMPTS_LIMIT = 5              # intentos fallidos por email
LOGIN_ATTEMPTS_WINDOW_SECONDS = 300
LOGIN_IP_ATTEMPTS_LIMIT = 20          # intentos fallidos por IP, cubre varias cuentas (password spraying)
LOGIN_IP_ATTEMPTS_WINDOW_SECONDS = 300
REGISTER_IP_LIMIT = 30                # registros por IP por hora
REGISTER_IP_WINDOW_SECONDS = 3600


# =============================================
# Rate limiting persistido en BD (sobrevive reinicios y se comparte
# entre varios workers/instancias, a diferencia de un dict en memoria)
# =============================================
def _check_rate_limit(db: Session, scope: str, key: str, limit: int, window_seconds: int, detail: str):
    cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
    db.query(RateLimitAttempt).filter(
        RateLimitAttempt.scope == scope,
        RateLimitAttempt.key == key,
        RateLimitAttempt.created_at < cutoff
    ).delete()
    count = db.query(RateLimitAttempt).filter(
        RateLimitAttempt.scope == scope,
        RateLimitAttempt.key == key
    ).count()
    if count >= limit:
        db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


def _record_attempt(db: Session, scope: str, key: str):
    db.add(RateLimitAttempt(scope=scope, key=key, created_at=datetime.utcnow()))
    db.commit()


def _clear_attempts(db: Session, scope: str, key: str):
    db.query(RateLimitAttempt).filter(RateLimitAttempt.scope == scope, RateLimitAttempt.key == key).delete()
    db.commit()


def check_register_rate_limit(db: Session, client_ip: str):
    _check_rate_limit(
        db, "register_ip", client_ip, REGISTER_IP_LIMIT, REGISTER_IP_WINDOW_SECONDS,
        "Demasiados registros desde esta red. Intenta de nuevo más tarde."
    )
    _record_attempt(db, "register_ip", client_ip)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password):
    return pwd_context.hash(password)


def create_access_token(data: dict):
    to_encode = data.copy()
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    now = datetime.utcnow()
    to_encode.update({
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": now,
        "jti": secrets.token_hex(16),
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token_claims(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def authenticate_user(db: Session, email: str, password: str, client_ip: str = "unknown") -> User:
    """Valida credenciales con rate limiting (por email y por IP) y tiempo constante."""
    email = email.lower()

    _check_rate_limit(
        db, "login_email", email, LOGIN_ATTEMPTS_LIMIT, LOGIN_ATTEMPTS_WINDOW_SECONDS,
        "Demasiados intentos fallidos para este email. Intenta de nuevo en unos minutos."
    )
    _check_rate_limit(
        db, "login_ip", client_ip, LOGIN_IP_ATTEMPTS_LIMIT, LOGIN_IP_ATTEMPTS_WINDOW_SECONDS,
        "Demasiados intentos fallidos desde tu red. Intenta de nuevo en unos minutos."
    )

    user = db.query(User).filter(User.email == email).first()
    hashed = user.hashed_password if user else _DUMMY_HASH
    password_ok = verify_password(password, hashed)

    if not user or not password_ok:
        _record_attempt(db, "login_email", email)
        _record_attempt(db, "login_ip", client_ip)
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    _clear_attempts(db, "login_email", email)
    # El contador por IP NO se limpia en un login exitoso a propósito: si se
    # limpiara, un atacante podría intercalar logins válidos propios para
    # resetear su cupo de intentos contra otras cuentas desde la misma IP.
    return user


# =============================================
# Revocación de sesiones
# =============================================
def revoke_token(db: Session, jti: str, expires_at: datetime):
    """Revoca un único token (el de la sesión actual) vía su jti."""
    if not db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        db.add(RevokedToken(jti=jti, expires_at=expires_at))
    # de paso, purga entradas ya vencidas (su token original ya expiró solo)
    db.query(RevokedToken).filter(RevokedToken.expires_at < datetime.utcnow()).delete()
    db.commit()


def revoke_all_sessions(db: Session, user: User):
    """Revoca TODAS las sesiones del usuario (todos los dispositivos)."""
    user.tokens_valid_after = datetime.utcnow().replace(microsecond=0)
    db.commit()
    db.refresh(user)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token_claims(token)
        sub = payload.get("sub")
        iat = payload.get("iat")
        jti = payload.get("jti")
        if sub is None or iat is None:
            raise credentials_exception
        user_id = int(sub)
    except JWTError:
        raise credentials_exception

    if jti and db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    if user.tokens_valid_after is not None:
        token_issued_at = datetime.utcfromtimestamp(iat)
        # "<=" a propósito: con precisión de segundos, un token emitido en el
        # mismo segundo que la revocación no se puede distinguir de forma
        # confiable, así que ante la duda se trata como revocado (fail-closed).
        if token_issued_at <= user.tokens_valid_after:
            raise credentials_exception

    return user


def require_role(role: str):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para realizar esta acción"
            )
        return current_user
    return role_checker


def require_verified(current_user: User = Depends(get_current_user)):
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes verificar tu email antes de realizar esta acción"
        )
    return current_user


# =============================================
# Verificación de email (sustituto de CAPTCHA para una API sin frontend)
# =============================================
def generate_verification_token(user: User):
    user.verification_token = secrets.token_urlsafe(32)
    user.verification_token_expires = datetime.utcnow() + timedelta(hours=VERIFICATION_TOKEN_EXPIRE_HOURS)
    return user.verification_token


def send_verification_email(to_email: str, token: str):
    verify_url = f"{APP_BASE_URL}/verify-email?token={token}"
    if not SMTP_HOST:
        print(f"\n[VERIFICACIÓN DE EMAIL] SMTP no configurado. Enlace para {to_email}:\n  {verify_url}\n")
        return

    msg = MIMEText(f"Verifica tu cuenta en la Plataforma de Citas Médicas visitando:\n{verify_url}")
    msg["Subject"] = "Verifica tu cuenta"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        if SMTP_USER and SMTP_PASSWORD:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
