from fastapi import FastAPI, Depends, HTTPException, status, Query, Path, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from database import get_db
from models import User, DoctorAvailability, Appointment
from schemas import (
    UserCreate, UserLogin, Token, UserOut, MessageOut,
    AvailabilityCreate, AvailabilityUpdate, AvailabilityOut,
    AppointmentCreate, AppointmentUpdate, AppointmentOut,
    DoctorPublicOut
)
from auth import (
    hash_password, authenticate_user, create_access_token, decode_token_claims,
    get_current_user, require_role, require_verified, oauth2_scheme,
    check_register_rate_limit, revoke_token, revoke_all_sessions,
    generate_verification_token, send_verification_email,
    SMTP_HOST,
)

# rango real de una columna INTEGER en SQLite (entero de 64 bits con signo);
# sin este límite, un id fuera de rango revienta con OverflowError -> 500
SQLITE_MAX_INT = 2**63 - 1

MAX_BODY_SIZE = 1_000_000  # 1 MB, generoso para el payload más grande que espera esta API

app = FastAPI(
    title="API Gestión de Citas Médicas",
    description="Sistema para coordinar disponibilidad de profesionales y reserva de citas",
    version="1.0.0",
    responses={
        404: {"description": "Recurso no encontrado"},
        400: {"description": "Solicitud inválida"},
        403: {"description": "Sin permisos"},
        409: {"description": "Conflicto - recurso ya existe o no disponible"},
    }
)


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_SIZE:
        return JSONResponse(status_code=413, content={"detail": "El cuerpo de la petición es demasiado grande"})
    return await call_next(request)


def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# =============================================
# AUTH
# =============================================
@app.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Autenticación"],
    summary="Registrar nuevo usuario",
    responses={
        400: {"description": "El email o el documento de identidad ya están registrados"},
        429: {"description": "Demasiados registros desde esta red, intenta más tarde"},
    }
)
def register(user: UserCreate, request: Request, db: Session = Depends(get_db)):
    check_register_rate_limit(db, get_client_ip(request))

    already_exists = db.query(User).filter(
        (User.email == user.email) | (User.document_id == user.document_id)
    ).first()
    if already_exists:
        # Mensaje genérico a propósito: no revela cuál de los dos campos
        # coincide, para no permitir enumerar emails/documentos registrados.
        raise HTTPException(status_code=400, detail="El email o el documento de identidad ya están registrados")

    db_user = User(
        email=user.email,
        hashed_password=hash_password(user.password),
        full_name=user.full_name,
        phone=user.phone,
        document_id=user.document_id,
        role=user.role,
        specialty=user.specialty,
        license_number=user.license_number
    )
    db.add(db_user)
    db.flush()
    token = generate_verification_token(db_user)
    db.commit()
    db.refresh(db_user)
    send_verification_email(db_user.email, token)
    return db_user


@app.post(
    "/login",
    response_model=Token,
    tags=["Autenticación"],
    summary="Iniciar sesión",
    responses={
        401: {"description": "Email o contraseña incorrectos"},
        429: {"description": "Demasiados intentos fallidos, intenta más tarde"},
    }
)
def login(user_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_data.email, user_data.password, get_client_ip(request))
    token = create_access_token(data={"sub": user.id, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


@app.post(
    "/token",
    response_model=Token,
    include_in_schema=False,
)
def login_for_swagger(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Usado internamente por el botón "Authorize" de Swagger (form OAuth2 estándar, no expuesto en /docs)
    user = authenticate_user(db, form_data.username, form_data.password, get_client_ip(request))
    token = create_access_token(data={"sub": user.id, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


@app.post(
    "/logout",
    response_model=MessageOut,
    tags=["Autenticación"],
    summary="Cerrar sesión (solo el token actual)",
)
def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    payload = decode_token_claims(token)
    jti, exp = payload.get("jti"), payload.get("exp")
    if jti and exp:
        revoke_token(db, jti, datetime.utcfromtimestamp(exp))
    return {"detail": "Sesión cerrada. Este token ya no es válido."}


@app.post(
    "/logout-all",
    response_model=MessageOut,
    tags=["Autenticación"],
    summary="Cerrar sesión en todos los dispositivos",
)
def logout_all(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    revoke_all_sessions(db, current_user)
    return {"detail": "Todas tus sesiones fueron cerradas. Ningún token emitido antes de ahora es válido."}


@app.get(
    "/verify-email",
    response_model=MessageOut,
    tags=["Autenticación"],
    summary="Verificar el email a partir del enlace enviado al registrarse",
    responses={
        400: {"description": "Token de verificación inválido o expirado"},
    }
)
def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == token).first()
    if not user or not user.verification_token_expires or user.verification_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token de verificación inválido o expirado")

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    db.commit()
    return {"detail": "Email verificado correctamente. Ya puedes usar todas las funciones de la plataforma."}


@app.post(
    "/resend-verification",
    response_model=MessageOut,
    tags=["Autenticación"],
    summary="Reenviar el email de verificación",
)
def resend_verification(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.is_verified:
        return {"detail": "Tu email ya estaba verificado."}

    token = generate_verification_token(current_user)
    db.commit()
    send_verification_email(current_user.email, token)
    return {"detail": "Te reenviamos el enlace de verificación."}


if not SMTP_HOST:
    @app.get("/_dev/verification-token", include_in_schema=False)
    def dev_get_verification_token(email: str, db: Session = Depends(get_db)):
        # Solo existe cuando no hay SMTP configurado (modo desarrollo): permite
        # a test_all.py obtener el token sin una bandeja de correo real.
        user = db.query(User).filter(User.email == email.lower()).first()
        if not user or not user.verification_token:
            raise HTTPException(status_code=404, detail="No encontrado")
        return {"token": user.verification_token}


# =============================================
# PACIENTES
# =============================================
@app.get(
    "/patients/me",
    response_model=UserOut,
    tags=["Pacientes"],
    summary="Ver mi perfil"
)
def get_my_profile(current_user: User = Depends(require_role("patient"))):
    return current_user


@app.get(
    "/patients/me/history",
    response_model=List[AppointmentOut],
    tags=["Pacientes"],
    summary="Ver historial de mis citas"
)
def get_my_history(
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db)
):
    return db.query(Appointment).filter(
        Appointment.patient_id == current_user.id
    ).all()


# =============================================
# DOCTORES - Disponibilidad
# =============================================
@app.post(
    "/availability",
    response_model=AvailabilityOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Disponibilidad"],
    summary="Agregar horario de disponibilidad",
    responses={
        403: {"description": "Debes verificar tu email antes de agregar disponibilidad"},
    }
)
def create_availability(
    avail: AvailabilityCreate,
    current_user: User = Depends(require_role("doctor")),
    _verified: User = Depends(require_verified),
    db: Session = Depends(get_db)
):
    if avail.start_time >= avail.end_time:
        raise HTTPException(status_code=400, detail="La hora de inicio debe ser menor a la de fin")

    db_avail = DoctorAvailability(
        doctor_id=current_user.id,
        day_of_week=avail.day_of_week,
        start_time=avail.start_time,
        end_time=avail.end_time
    )
    db.add(db_avail)
    db.commit()
    db.refresh(db_avail)
    return db_avail


@app.patch(
    "/availability/{availability_id}",
    response_model=AvailabilityOut,
    tags=["Disponibilidad"],
    summary="Actualizar un horario de disponibilidad",
    responses={
        404: {"description": "Horario de disponibilidad no encontrado"},
    }
)
def update_availability(
    update: AvailabilityUpdate,
    availability_id: int = Path(..., gt=0, le=SQLITE_MAX_INT),
    current_user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db)
):
    avail = db.query(DoctorAvailability).filter(
        DoctorAvailability.id == availability_id,
        DoctorAvailability.doctor_id == current_user.id
    ).first()
    if not avail:
        raise HTTPException(status_code=404, detail="Horario de disponibilidad no encontrado")

    new_start = update.start_time if update.start_time is not None else avail.start_time
    new_end = update.end_time if update.end_time is not None else avail.end_time
    if new_start >= new_end:
        raise HTTPException(status_code=400, detail="La hora de inicio debe ser menor a la de fin")

    if update.day_of_week is not None:
        avail.day_of_week = update.day_of_week
    avail.start_time = new_start
    avail.end_time = new_end

    db.commit()
    db.refresh(avail)
    return avail


@app.delete(
    "/availability/{availability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Disponibilidad"],
    summary="Eliminar un horario de disponibilidad",
    responses={
        404: {"description": "Horario de disponibilidad no encontrado"},
    }
)
def delete_availability(
    availability_id: int = Path(..., gt=0, le=SQLITE_MAX_INT),
    current_user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db)
):
    avail = db.query(DoctorAvailability).filter(
        DoctorAvailability.id == availability_id,
        DoctorAvailability.doctor_id == current_user.id
    ).first()
    if not avail:
        raise HTTPException(status_code=404, detail="Horario de disponibilidad no encontrado")

    db.delete(avail)
    db.commit()
    return None


@app.get(
    "/availability/me",
    response_model=List[AvailabilityOut],
    tags=["Disponibilidad"],
    summary="Ver mis horarios de disponibilidad"
)
def get_my_availability(
    current_user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db)
):
    return db.query(DoctorAvailability).filter(
        DoctorAvailability.doctor_id == current_user.id
    ).all()


@app.get(
    "/doctors",
    response_model=List[DoctorPublicOut],
    tags=["Disponibilidad"],
    summary="Listar todos los médicos"
)
def list_doctors(db: Session = Depends(get_db)):
    return db.query(User).filter(User.role == "doctor").all()


# =============================================
# DOCTORES - Agenda
# =============================================
@app.get(
    "/doctors/me/appointments",
    response_model=List[AppointmentOut],
    tags=["Citas"],
    summary="Ver agenda completa del médico"
)
def get_doctor_appointments(
    date: str = Query(None, description="Filtrar por fecha YYYY-MM-DD"),
    current_user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db)
):
    query = db.query(Appointment).filter(Appointment.doctor_id == current_user.id)
    if date:
        query = query.filter(Appointment.date == date)
    return query.all()


@app.patch(
    "/appointments/{appointment_id}/status",
    response_model=AppointmentOut,
    tags=["Citas"],
    summary="Actualizar estado de una cita (médico)",
    responses={
        404: {"description": "Cita no encontrada"},
    }
)
def update_appointment_status(
    update: AppointmentUpdate,
    appointment_id: int = Path(..., gt=0, le=SQLITE_MAX_INT),
    current_user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.doctor_id == current_user.id
    ).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada o no pertenece a este médico")

    appointment.status = update.status
    db.commit()
    db.refresh(appointment)
    return appointment


# =============================================
# CITAS - Crear y gestionar
# =============================================
@app.post(
    "/appointments",
    response_model=AppointmentOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Citas"],
    summary="Crear una nueva cita",
    responses={
        403: {"description": "Debes verificar tu email antes de agendar una cita"},
        409: {"description": "Horario no disponible o médico no disponible en ese día"},
    }
)
def create_appointment(
    appt: AppointmentCreate,
    current_user: User = Depends(require_role("patient")),
    _verified: User = Depends(require_verified),
    db: Session = Depends(get_db)
):
    # Verificar que la fecha no sea en el pasado
    appt_datetime = datetime.strptime(f"{appt.date} {appt.time}", "%Y-%m-%d %H:%M")
    if appt_datetime < datetime.now():
        raise HTTPException(status_code=400, detail="No se pueden agendar citas en el pasado")

    # Verificar que el médico exista
    doctor = db.query(User).filter(
        User.id == appt.doctor_id,
        User.role == "doctor"
    ).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Médico no encontrado")

    # Verificar que el médico tenga disponibilidad ese día de la semana
    appointment_date = datetime.strptime(appt.date, "%Y-%m-%d")
    day_of_week = appointment_date.weekday()  # 0=lunes, 6=domingo

    availability = db.query(DoctorAvailability).filter(
        DoctorAvailability.doctor_id == appt.doctor_id,
        DoctorAvailability.day_of_week == day_of_week
    ).first()

    if not availability:
        raise HTTPException(status_code=409, detail="Horario no disponible - el médico no atiende este día")

    # Verificar que la hora esté dentro del horario de disponibilidad
    if appt.time < availability.start_time or appt.time >= availability.end_time:
        raise HTTPException(status_code=409, detail="Horario no disponible - hora fuera del rango de atención")

    # Verificar que no haya otra cita a la misma hora para el mismo médico
    existing = db.query(Appointment).filter(
        Appointment.doctor_id == appt.doctor_id,
        Appointment.date == appt.date,
        Appointment.time == appt.time,
        Appointment.status != "cancelled"
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail="Horario no disponible - el médico ya tiene una cita a esta hora")

    db_appt = Appointment(
        patient_id=current_user.id,
        doctor_id=appt.doctor_id,
        date=appt.date,
        time=appt.time,
        status="pending",
        reason=appt.reason
    )
    db.add(db_appt)
    db.commit()
    db.refresh(db_appt)
    return db_appt


@app.patch(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentOut,
    tags=["Citas"],
    summary="Cancelar mi cita (paciente)",
    responses={
        404: {"description": "Cita no encontrada"},
    }
)
def cancel_appointment(
    appointment_id: int = Path(..., gt=0, le=SQLITE_MAX_INT),
    current_user: User = Depends(require_role("patient")),
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.patient_id == current_user.id
    ).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    if appointment.status == "cancelled":
        raise HTTPException(status_code=400, detail="La cita ya está cancelada")

    appointment.status = "cancelled"
    db.commit()
    db.refresh(appointment)
    return appointment


@app.delete(
    "/appointments/{appointment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Citas"],
    summary="Eliminar una cita",
    responses={
        404: {"description": "Cita no encontrada"},
    }
)
def delete_appointment(
    appointment_id: int = Path(..., gt=0, le=SQLITE_MAX_INT),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    # Pacientes y médicos solo pueden eliminar sus propias citas
    is_owner = (
        (current_user.role == "patient" and appointment.patient_id == current_user.id) or
        (current_user.role == "doctor" and appointment.doctor_id == current_user.id)
    )
    if not is_owner:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar esta cita")

    db.delete(appointment)
    db.commit()
    return None


if __name__ == "__main__":
    import uvicorn
    # proxy_headers=False: esta app no corre detrás de un reverse proxy, así
    # que no hay que confiar en X-Forwarded-For (cualquiera podría spoofearlo
    # para evadir el rate limiting por IP en auth.py).
    uvicorn.run(app, host="0.0.0.0", port=8000, proxy_headers=False)
