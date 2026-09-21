from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Time
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    phone = Column(String)
    document_id = Column(String, unique=True)
    role = Column(String)  # "patient" o "doctor"
    specialty = Column(String, nullable=True)  # solo médicos
    license_number = Column(String, nullable=True)  # solo médicos
    tokens_valid_after = Column(DateTime, nullable=True)  # tokens con iat anterior a esto quedan revocados
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True, index=True)
    verification_token_expires = Column(DateTime, nullable=True)

    doctor_availability = relationship("DoctorAvailability", back_populates="doctor")
    appointments = relationship("Appointment", foreign_keys="[Appointment.patient_id]", back_populates="patient")


# Tokens revocados individualmente vía /logout (no todas las sesiones del usuario)
class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti = Column(String, primary_key=True)
    expires_at = Column(DateTime, index=True)  # se puede borrar la fila pasada esta fecha


class RateLimitAttempt(Base):
    __tablename__ = "rate_limit_attempts"

    id = Column(Integer, primary_key=True, index=True)
    scope = Column(String, index=True)   # "login_email", "login_ip", "register_ip"
    key = Column(String, index=True)     # el email o la IP según el scope
    created_at = Column(DateTime, index=True)


class DoctorAvailability(Base):
    __tablename__ = "doctor_availability"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"))
    day_of_week = Column(Integer)  # 0=lunes, 6=domingo
    start_time = Column(String)  # "09:00"
    end_time = Column(String)  # "17:00"

    doctor = relationship("User", back_populates="doctor_availability")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"))
    doctor_id = Column(Integer, ForeignKey("users.id"))
    date = Column(String)  # "YYYY-MM-DD"
    time = Column(String)  # "HH:MM"
    status = Column(String, default="pending")  # pending, confirmed, cancelled
    reason = Column(String)

    patient = relationship("User", foreign_keys=[patient_id])
    doctor = relationship("User", foreign_keys=[doctor_id])
