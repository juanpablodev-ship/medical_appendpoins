from pydantic import BaseModel, EmailStr, field_validator, model_validator
from typing import Optional
from datetime import datetime


# ===== AUTH =====
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: str
    document_id: str
    role: str  # "patient" o "doctor"
    specialty: Optional[str] = None       # requerido si role == "doctor"
    license_number: Optional[str] = None  # requerido si role == "doctor"

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if not v.replace("+", "").replace("-", "").replace(" ", "").isdigit():
            raise ValueError("Formato de teléfono inválido")
        return v

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, v):
        if not v.isalnum() or not (5 <= len(v) <= 20):
            raise ValueError("El documento de identidad debe ser alfanumérico y tener entre 5 y 20 caracteres")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in ["patient", "doctor"]:
            raise ValueError("El rol debe ser 'patient' o 'doctor'")
        return v

    @model_validator(mode="after")
    def validate_required_by_role(self):
        if self.role == "doctor":
            if not self.specialty or not self.specialty.strip():
                raise ValueError("La especialidad es requerida para médicos")
            if not self.license_number or not self.license_number.strip():
                raise ValueError("El número de licencia/tarjeta profesional es requerido para médicos")
        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


# ===== USERS =====
class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    phone: str
    document_id: str
    role: str
    specialty: Optional[str] = None
    license_number: Optional[str] = None

    class Config:
        from_attributes = True


# ===== AVAILABILITY =====
class AvailabilityCreate(BaseModel):
    day_of_week: int
    start_time: str
    end_time: str

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v):
        if not 0 <= v <= 6:
            raise ValueError("day_of_week debe ser 0 (lunes) a 6 (domingo)")
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, v):
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError:
            raise ValueError("Formato de hora inválido. Usa HH:MM")
        return v


class AvailabilityUpdate(BaseModel):
    day_of_week: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v):
        if v is not None and not 0 <= v <= 6:
            raise ValueError("day_of_week debe ser 0 (lunes) a 6 (domingo)")
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, v):
        if v is None:
            return v
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError:
            raise ValueError("Formato de hora inválido. Usa HH:MM")
        return v

    @model_validator(mode="after")
    def validate_at_least_one_field(self):
        if self.day_of_week is None and self.start_time is None and self.end_time is None:
            raise ValueError("Debes enviar al menos un campo para actualizar")
        return self


class AvailabilityOut(BaseModel):
    id: int
    doctor_id: int
    day_of_week: int
    start_time: str
    end_time: str

    class Config:
        from_attributes = True


# ===== APPOINTMENTS =====
class AppointmentCreate(BaseModel):
    doctor_id: int
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    reason: Optional[str] = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Formato de fecha inválido. Usa YYYY-MM-DD")
        return v

    @field_validator("time")
    @classmethod
    def validate_time(cls, v):
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError:
            raise ValueError("Formato de hora inválido. Usa HH:MM")
        return v


class AppointmentUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in ["pending", "confirmed", "cancelled"]:
            raise ValueError("El estado debe ser: pending, confirmed o cancelled")
        return v


class AppointmentOut(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    date: str
    time: str
    status: str
    reason: Optional[str]

    class Config:
        from_attributes = True
