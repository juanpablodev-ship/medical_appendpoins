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

    doctor_availability = relationship("DoctorAvailability", back_populates="doctor")
    appointments = relationship("Appointment", foreign_keys="[Appointment.patient_id]", back_populates="patient")


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
