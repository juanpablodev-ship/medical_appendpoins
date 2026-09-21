from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from typing import List

from database import engine, get_db, Base
from models import User, DoctorAvailability, Appointment
from schemas import (
    UserCreate, UserLogin, Token, UserOut,
    AvailabilityCreate, AvailabilityUpdate, AvailabilityOut,
    AppointmentCreate, AppointmentUpdate, AppointmentOut
)
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_role
)

Base.metadata.create_all(bind=engine)

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
        400: {"description": "El email ya está registrado"},
    }
)
def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    if db.query(User).filter(User.document_id == user.document_id).first():
        raise HTTPException(status_code=400, detail="El documento de identidad ya está registrado")

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
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post(
    "/login",
    response_model=Token,
    tags=["Autenticación"],
    summary="Iniciar sesión",
    responses={
        401: {"description": "Email o contraseña incorrectos"},
    }
)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    token = create_access_token(data={"sub": user.id, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


@app.post(
    "/token",
    response_model=Token,
    include_in_schema=False,
)
def login_for_swagger(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Usado internamente por el botón "Authorize" de Swagger (form OAuth2 estándar, no expuesto en /docs)
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    token = create_access_token(data={"sub": user.id, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


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
    summary="Agregar horario de disponibilidad"
)
def create_availability(
    avail: AvailabilityCreate,
    current_user: User = Depends(require_role("doctor")),
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
    availability_id: int,
    update: AvailabilityUpdate,
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
    availability_id: int,
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
    response_model=List[UserOut],
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
    appointment_id: int,
    update: AppointmentUpdate,
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
        409: {"description": "Horario no disponible o médico no disponible en ese día"},
    }
)
def create_appointment(
    appt: AppointmentCreate,
    current_user: User = Depends(require_role("patient")),
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
    appointment_id: int,
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
    appointment_id: int,
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
