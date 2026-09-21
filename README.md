# 🏥 API Gestión de Citas Médicas

Sistema backend para coordinar la disponibilidad de profesionales médicos y la reserva de citas por parte de pacientes. Construido con **FastAPI**, **SQLAlchemy** y **SQLite**.

---

## 📋 Índice

1. [Requisitos Previos](#1-requisitos-previos)
2. [Instalación](#2-instalación)
3. [Ejecución](#3-ejecución)
4. [Estructura del Proyecto](#4-estructura-del-proyecto)
5. [Uso de la API](#5-uso-de-la-api)
6. [Endpoints Disponibles](#6-endpoints-disponibles)
7. [Base de Datos](#7-base-de-datos)
8. [Flujo de Ejemplo Completo](#8-flujo-de-ejemplo-completo)

---

## 1. Requisitos Previos

Necesitas tener instalado en tu computadora:

- **Python 3.8 o superior**
- **pip** (gestor de paquetes de Python, viene con Python)
- **Homebrew** (solo macOS, para instalar el visor de BD)

Para verificar que tienes Python:
```bash
python3 --version
```

---

## 2. Instalación

### 2.1 Navegar a la carpeta del proyecto
```bash
cd ~/Desktop/medical-appointments
```

### 2.2 Instalar las dependencias
```bash
pip install -r requirements.txt
```

Esto instalará automáticamente:
| Paquete | Para qué sirve |
|---------|----------------|
| `fastapi` | Framework web para crear la API |
| `uvicorn` | Servidor HTTP para ejecutar la app |
| `sqlalchemy` | ORM para conectarse a la base de datos |
| `python-jose` | Crear y verificar tokens JWT |
| `passlib` | Hashear contraseñas con bcrypt |
| `python-multipart` | Soporte para formularios en FastAPI |
| `pydantic` | Validación de datos de entrada |
| `email-validator` | Validación de formato de email |

Si algún paquete falla, instálalo por separado:
```bash
pip install fastapi uvicorn sqlalchemy
pip install 'python-jose[cryptography]' 'passlib[bcrypt]'
pip install python-multipart pydantic[email]
```

### 2.3 (Opcional) Instalar visor de base de datos
```bash
brew install --cask db-browser-for-sqlite
```

---

## 3. Ejecución

### 3.1 Iniciar el servidor
```bash
cd ~/Desktop/medical-appointments
python3 -m uvicorn main:app --reload --port 8000
```

Verás en la terminal:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### 3.2 Abrir Swagger (documentación interactiva)
Abre tu navegador y ve a:
```
http://localhost:8000/docs
```

Ahí puedes probar todos los endpoints directamente desde el navegador.

### 3.3 Abrir ReDoc (documentación alternativa)
```
http://localhost:8000/redoc
```

### 3.4 Detener el servidor
En la terminal presiona `Ctrl + C`.

---

## 4. Estructura del Proyecto

```
medical-appointments/
│
├── main.py              # Archivo principal - todos los endpoints
├── database.py          # Configuración de la base de datos SQLite
├── models.py            # Modelos de tablas (User, Availability, Appointment)
├── schemas.py           # Validaciones con Pydantic
├── auth.py              # Autenticación JWT y control de roles
├── requirements.txt     # Lista de dependencias
├── test_all.py          # Script de pruebas end-to-end contra el servidor
└── medical_appointments.db  # Base de datos (se crea automáticamente)
```

### Explicación de cada archivo:

**`database.py`** - Conexión a la BD
- Crea la conexión SQLite
- `get_db()` abre y cierra la conexión automáticamente en cada petición

**`models.py`** - Estructura de las tablas
- `users`: Almacena pacientes y médicos (diferenciados por el campo `role`). Los médicos además guardan `specialty` y `license_number`
- `doctor_availability`: Horarios que cada médico tiene disponibles
- `appointments`: Citas agendadas entre paciente y médico

**`schemas.py`** - Validaciones
- Define qué datos se aceptan en cada endpoint
- Valida formatos de email, teléfono, fechas, horas, roles

**`auth.py`** - Seguridad
- Hashea contraseñas con bcrypt
- Crea tokens JWT con expiración de 60 minutos
- `get_current_user()`: extrae el usuario del token
- `require_role()`: restringe endpoints por rol (patient/doctor)
- El `tokenUrl` del esquema OAuth2 apunta a `/token` (endpoint interno usado solo por el botón "Authorize" de Swagger, ver [5.4](#54-usar-el-token-en-endpoints-protegidos))

**`main.py`** - Lógica de negocio
- Contiene todos los endpoints
- Implementa la lógica de validación al crear citas

---

## 5. Uso de la API

### 5.1 Registrar un paciente
```
POST /register
```
```json
{
  "email": "juan@email.com",
  "password": "123456",
  "full_name": "Juan Pérez",
  "phone": "+573001234567",
  "document_id": "12345678",
  "role": "patient"
}
```

### 5.2 Registrar un médico
```
POST /register
```
```json
{
  "email": "dr.lopez@email.com",
  "password": "123456",
  "full_name": "Dr. Carlos López",
  "phone": "+573009876543",
  "document_id": "87654321",
  "role": "doctor",
  "specialty": "Medicina General",
  "license_number": "MG-001"
}
```
> `specialty` y `license_number` son **requeridos únicamente para el rol `doctor`**.

### 5.3 Iniciar sesión
```
POST /login
```
```json
{
  "email": "juan@email.com",
  "password": "123456"
}
```
Respuesta:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### 5.4 Usar el token en endpoints protegidos

**Desde Swagger** (`/docs`): haz clic en el botón **"Authorize"** (candado, arriba a la derecha) e ingresa el **email** en el campo `username` y la contraseña en `password` (deja `client_id`/`client_secret`/`scopes` vacíos). Swagger obtiene el token por su cuenta usando el endpoint interno `/token` — no necesitas pegar nada manualmente.

**Desde curl/Postman**: haz login en `/login` (JSON), copia el `access_token` de la respuesta, y mándalo en cada petición protegida como header:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

---

## 6. Endpoints Disponibles

### Autenticación
| Método | Ruta | Descripción | Autenticación |
|--------|------|-------------|---------------|
| POST | `/register` | Registrar usuario nuevo | No |
| POST | `/login` | Iniciar sesión | No |

### Pacientes
| Método | Ruta | Descripción | Autenticación |
|--------|------|-------------|---------------|
| GET | `/patients/me` | Ver mi perfil | JWT (patient) |
| GET | `/patients/me/history` | Ver historial de mis citas | JWT (patient) |

### Disponibilidad
| Método | Ruta | Descripción | Autenticación |
|--------|------|-------------|---------------|
| POST | `/availability` | Agregar horario de atención | JWT (doctor) |
| PATCH | `/availability/{id}` | Actualizar un horario propio | JWT (doctor) |
| DELETE | `/availability/{id}` | Eliminar un horario propio | JWT (doctor) |
| GET | `/availability/me` | Ver mis horarios | JWT (doctor) |
| GET | `/doctors` | Listar todos los médicos | No |

### Citas
| Método | Ruta | Descripción | Autenticación |
|--------|------|-------------|---------------|
| POST | `/appointments` | Crear una cita | JWT (patient) |
| PATCH | `/appointments/{id}/cancel` | Cancelar mi cita | JWT (patient) |
| PATCH | `/appointments/{id}/status` | Cambiar estado de cita | JWT (doctor) |
| DELETE | `/appointments/{id}` | Eliminar cita propia | JWT (patient/doctor dueño) |
| GET | `/doctors/me/appointments` | Ver agenda completa | JWT (doctor) |

### Errores personalizados
| Código | Significado |
|--------|-------------|
| 400 | Solicitud inválida (fecha en el pasado, email duplicado) |
| 401 | Credenciales incorrectas |
| 403 | Sin permisos para esta acción |
| 404 | Recurso no encontrado (cita, médico) |
| 409 | Conflicto (horario no disponible, doble reserva) |
| 422 | Error de validación en los datos |

---

## 7. Base de Datos

### Ver las tablas con SQLite (terminal)
```bash
sqlite3 ~/Desktop/medical-appointments/medical_appointments.db
```
Dentro de sqlite3:
```sql
.tables                              -- ver tablas
.schema users                        -- ver estructura de users
.schema doctor_availability          -- ver estructura de disponibilidad
.schema appointments                 -- ver estructura de citas
SELECT * FROM users;                 -- ver todos los usuarios
SELECT * FROM doctor_availability;   -- ver horarios
SELECT * FROM appointments;          -- ver citas
.quit                                -- salir
```

### Ver las tablas con DB Browser
1. Abrir "DB Browser for SQLite"
2. Click en "Open Database"
3. Navegar a `~/Desktop/medical-appointments/medical_appointments.db`
4. Seleccionar y abrir

---

## 8. Flujo de Ejemplo Completo

### Paso 1: Registrar médico
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dr.lopez@email.com",
    "password": "123456",
    "full_name": "Dr. Carlos López",
    "phone": "+573009876543",
    "document_id": "87654321",
    "role": "doctor",
    "specialty": "Medicina General",
    "license_number": "MG-001"
  }'
```

### Paso 2: Registrar paciente
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "juan@email.com",
    "password": "123456",
    "full_name": "Juan Pérez",
    "phone": "+573001234567",
    "document_id": "12345678",
    "role": "patient"
  }'
```

### Paso 3: Login del médico
```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dr.lopez@email.com",
    "password": "123456"
  }'
```
Copia el `access_token` de la respuesta.

### Paso 4: Médico agrega disponibilidad
```bash
curl -X POST http://localhost:8000/availability \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_DEL_MEDICO>" \
  -d '{
    "day_of_week": 0,
    "start_time": "09:00",
    "end_time": "17:00"
  }'
```
(day_of_week: 0=Lunes, 1=Martes, ..., 6=Domingo)

### Paso 5: Login del paciente
```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "juan@email.com",
    "password": "123456"
  }'
```

### Paso 6: Paciente crea una cita
```bash
curl -X POST http://localhost:8000/appointments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_DEL_PACIENTE>" \
  -d '{
    "doctor_id": 1,
    "date": "2026-09-21",
    "time": "10:00",
    "reason": "Dolor de cabeza persistente"
  }'
```
> La fecha debe caer en un día en que el médico tenga disponibilidad (en el Paso 4 configuramos `day_of_week: 0` = lunes) y debe ser una fecha futura respecto a hoy.

### Paso 7: Médico confirma la cita
```bash
curl -X PATCH http://localhost:8000/appointments/1/status \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_DEL_MEDICO>" \
  -d '{
    "status": "confirmed"
  }'
```

### Paso 8: Paciente cancela la cita
```bash
curl -X PATCH http://localhost:8000/appointments/1/cancel \
  -H "Authorization: Bearer <TOKEN_DEL_PACIENTE>"
```

---

## Notas

- La base de datos `medical_appointments.db` se crea automáticamente al ejecutar el servidor por primera vez.
- Los tokens JWT duran **60 minutos** antes de expirar.
- Las contraseñas se almacenan hasheadas con **bcrypt** (nunca en texto plano).
- La fecha y hora de las citas se almacenan como strings para mayor compatibilidad con SQLite.
