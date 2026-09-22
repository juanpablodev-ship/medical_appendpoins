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
9. [Migraciones con Alembic](#9-migraciones-con-alembic)
10. [Seguridad](#10-seguridad)

---

## 1. Requisitos Previos

Necesitas tener instalado en tu computadora:
- **Python 3.10 o superior**
- **pip** (gestor de paquetes de Python, viene incluido con Python)
- **Git** (para clonar el repositorio)

Las instrucciones de instalación difieren entre macOS y Windows — sigue la que corresponda a tu sistema.

### 1.1 macOS

**Verificar si ya tienes Python:**
```bash
python3 --version
```
Si aparece `Python 3.10` o superior, ya lo tienes y puedes saltar al siguiente paso. Si no, instálalo con [Homebrew](https://brew.sh):
```bash
# Instalar Homebrew (si no lo tienes)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Instalar Python
brew install python@3.12

# Instalar Git (normalmente ya viene con macOS)
brew install git
```

### 1.2 Windows

**Verificar si ya tienes Python:** abre **PowerShell** (búscalo en el menú Inicio) y corre:
```powershell
python --version
```
Si aparece `Python 3.10` o superior, ya lo tienes. Si da error o una versión vieja:

1. Ve a [python.org/downloads](https://www.python.org/downloads/) y descarga la última versión de Python 3 para Windows.
2. Ejecuta el instalador. **Muy importante**: en la primera pantalla, marca la casilla **"Add python.exe to PATH"** antes de darle a "Install Now" — si no la marcas, los comandos `python`/`pip` no van a funcionar en la terminal.
3. Cierra y vuelve a abrir PowerShell, y verifica de nuevo con `python --version`.

**Instalar Git:** descarga el instalador desde [git-scm.com/downloads](https://git-scm.com/downloads) y déjalo con las opciones por defecto. Verifica con:
```powershell
git --version
```

**Habilitar la ejecución de scripts en PowerShell** (necesario más adelante para activar el entorno virtual). Abre PowerShell **como administrador** (clic derecho → "Ejecutar como administrador") y corre una sola vez:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
Confirma con "S" o "Y" si te lo pregunta. Ya puedes usar una terminal normal para todo lo demás.

---

## 2. Instalación

### 2.1 Clonar el repositorio

**macOS** (Terminal):
```bash
cd ~/Desktop
git clone https://github.com/juanpablodev-ship/medical_appendpoins.git medical-appointments
cd medical-appointments
```

**Windows** (PowerShell):
```powershell
cd ~\Desktop
git clone https://github.com/juanpablodev-ship/medical_appendpoins.git medical-appointments
cd medical-appointments
```

### 2.2 Crear y activar un entorno virtual
Un entorno virtual mantiene las dependencias de este proyecto separadas del resto de tu sistema. Es opcional pero muy recomendado.

**macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**Windows (cmd.exe, si no usas PowerShell):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

Sabrás que quedó activado porque el prompt de la terminal empieza con `(venv)`. A partir de aquí, **todos los comandos de este README asumen que el entorno virtual está activado** — si cierras la terminal, tienes que volver a activarlo (`source venv/bin/activate` o `venv\Scripts\Activate.ps1`) antes de seguir trabajando.

### 2.3 Instalar las dependencias

**macOS:**
```bash
pip3 install -r requirements.txt
```

**Windows:**
```powershell
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
| `alembic` | Migraciones de base de datos |
| `requests` | Usado por `test_all.py` y `security_test.py` (no por la API en sí) |

Si algún paquete falla, instálalo por separado (mismo comando en macOS/Windows, cambiando `pip3` por `pip` según corresponda):
```bash
pip install fastapi uvicorn sqlalchemy alembic requests
pip install "python-jose[cryptography]" "passlib[bcrypt]"
pip install python-multipart "pydantic[email]"
```
> En Windows, si `passlib[bcrypt]` falla por no encontrar un compilador, instala primero el wheel precompilado: `pip install --only-binary :all: bcrypt`, y luego vuelve a correr `pip install -r requirements.txt`.

### 2.4 (Opcional) Instalar un visor de base de datos
Útil para inspeccionar `medical_appointments.db` visualmente en vez de usar la terminal.

**macOS:**
```bash
brew install --cask db-browser-for-sqlite
```

**Windows:** descarga el instalador ("DB Browser for SQLite - Windows") desde [sqlitebrowser.org](https://sqlitebrowser.org/dl/) y ejecútalo.

---

## 3. Ejecución

Los comandos de esta sección son **iguales en macOS y Windows** salvo que se indique lo contrario (asumiendo que ya activaste el entorno virtual del paso 2.2).

### 3.1 Iniciar el servidor

**Forma recomendada** (igual en macOS y Windows, no requiere acordarse de ningún flag ni paso extra):
```bash
python3 run.py   # macOS/Linux
python run.py     # Windows
```
`run.py` corre `alembic upgrade head` automáticamente antes de levantar uvicorn — no hace falta correrlo aparte, ni siquiera la primera vez. Ver la sección [9. Migraciones con Alembic](#9-migraciones-con-alembic) para más detalle sobre qué hace esa migración.

**Alternativa manual** (si por lo que sea no quieres usar `run.py`): con esta forma **sí** tienes que acordarte de correr la migración tú mismo, y de incluir `--no-proxy-headers` — si olvidas cualquiera de las dos, la API responde con 500 en cualquier endpoint que use la base de datos (falta la migración), o el rate limiting por IP queda evadible con un header `X-Forwarded-For` falso (falta el flag, ver [10.13](#1013-el-servidor-no-confía-en-x-forwarded-for)):
```bash
alembic upgrade head
uvicorn main:app --reload --port 8000 --no-proxy-headers
```
> Si el comando `uvicorn` no se reconoce (típico en Windows si el entorno virtual no quedó activado), usa `python -m uvicorn main:app --reload --port 8000 --no-proxy-headers` (o `python3 -m uvicorn ...` en macOS).

Verás en la terminal:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```
Deja esta terminal abierta corriendo el servidor, y usa **una segunda terminal** (con el mismo entorno virtual activado) para todo lo demás (correr `test_all.py`, `alembic revision`, `curl`, etc.).

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
En la terminal donde corre uvicorn, presiona `Ctrl + C`.

### 3.5 Correr los scripts de prueba
Con el servidor del paso 3.1 corriendo, en la **segunda terminal** (mismo entorno virtual activado):
```bash
python3 test_all.py        # macOS: prueba que todo funcione (70+ checks)
python3 security_test.py   # macOS: pentest, ataca la API a propósito

python test_all.py         # Windows: equivalente
python security_test.py    # Windows: equivalente
```

---

## 4. Estructura del Proyecto

```
medical-appointments/
│
├── main.py              # Archivo principal - todos los endpoints
├── run.py               # Punto de entrada recomendado para levantar el servidor
├── database.py          # Configuración de la base de datos SQLite
├── models.py            # Modelos de tablas (User, Availability, Appointment)
├── schemas.py           # Validaciones con Pydantic
├── auth.py              # Autenticación JWT y control de roles
├── requirements.txt     # Lista de dependencias
├── test_all.py          # Script de pruebas end-to-end contra el servidor
├── security_test.py     # Script de pentest: ataca la API y verifica que cada defensa responda
├── alembic.ini          # Configuración de Alembic (migraciones)
├── alembic/
│   ├── env.py           # Conecta Alembic con Base.metadata y DATABASE_URL
│   └── versions/        # Cada archivo es una migración del esquema
└── medical_appointments.db  # Base de datos (se crea con `alembic upgrade head`)
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
  "password": "Segura123",
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
  "password": "Segura123",
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
  "password": "Segura123"
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
| POST | `/logout` | Cerrar sesión (revoca solo el token actual) | JWT |
| POST | `/logout-all` | Cerrar sesión en todos los dispositivos | JWT |
| GET | `/verify-email` | Verificar el email con el token recibido al registrarse | No |
| POST | `/resend-verification` | Reenviar el enlace de verificación | JWT |

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
| 429 | Demasiados intentos de login fallidos |

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
    "password": "Segura123",
    "full_name": "Dr. Carlos López",
    "phone": "+573009876543",
    "document_id": "87654321",
    "role": "doctor",
    "specialty": "Medicina General",
    "license_number": "MG-001"
  }'
```
> Recuerda verificar también este email (mismo procedimiento del Paso 2.1) antes del Paso 4 — si no, `/availability` te devolverá 403.

### Paso 2: Registrar paciente
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "juan@email.com",
    "password": "Segura123",
    "full_name": "Juan Pérez",
    "phone": "+573001234567",
    "document_id": "12345678",
    "role": "patient"
  }'
```

### Paso 2.1: Verificar el email (requerido antes de poder agendar)
Si no configuraste `SMTP_HOST`, el enlace de verificación se imprime en la **consola donde corre el servidor**, con este formato:
```
[VERIFICACIÓN DE EMAIL] SMTP no configurado. Enlace para juan@email.com:
  http://localhost:8000/verify-email?token=<TOKEN>
```
Ábrelo en el navegador, o con curl:
```bash
curl "http://localhost:8000/verify-email?token=<TOKEN>"
```
Repite esto también para el médico registrado en el Paso 1 — sin verificar, tampoco podrá agregar disponibilidad en el Paso 4.

### Paso 3: Login del médico
```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dr.lopez@email.com",
    "password": "Segura123"
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
    "password": "Segura123"
  }'
```

### Paso 6: Paciente crea una cita
```bash
curl -X POST http://localhost:8000/appointments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_DEL_PACIENTE>" \
  -d '{
    "doctor_id": 1,
    "date": "2026-09-28",
    "time": "10:00",
    "reason": "Dolor de cabeza persistente"
  }'
```
> La fecha debe caer en un día en que el médico tenga disponibilidad (en el Paso 4 configuramos `day_of_week: 0` = lunes) y debe ser una fecha futura respecto a hoy. Ajusta `"2026-09-28"` por la fecha del próximo lunes cuando lo pruebes.

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

## 9. Migraciones con Alembic

El esquema de la base de datos (tablas y columnas) se gestiona con [Alembic](https://alembic.sqlalchemy.org/), no con `Base.metadata.create_all()`. Esto evita el problema de que agregar un campo nuevo a `models.py` no se refleje en una base de datos que ya existía (justo el bug que tuvimos al agregar `specialty`/`license_number`).

### 9.1 Cómo está configurado
- `alembic.ini`: configuración general. La URL de conexión **no** está aquí — se toma de `database.DATABASE_URL` dentro de `alembic/env.py` para no duplicar esa configuración en dos lugares.
- `alembic/env.py`: importa `Base` (de `database.py`) y los modelos (de `models.py`) para que Alembic sepa comparar el esquema real contra lo definido en `models.py`.
- `alembic/versions/`: cada archivo aquí es una migración (una versión del esquema). **Sí se suben al repo** — son código, no datos.

### 9.2 Comandos que vas a usar

**Crear/actualizar la base de datos** (correr después de clonar el repo, o después de traer cambios de otra persona):
```bash
alembic upgrade head
```

**Después de modificar `models.py`** (agregar/quitar una columna, una tabla, etc.), generar la migración automáticamente:
```bash
alembic revision --autogenerate -m "descripción corta del cambio"
```
Alembic compara `models.py` contra el estado real de la base de datos y genera el archivo en `alembic/versions/`. **Revisa siempre el archivo generado** antes de aplicarlo — el autogenerate no detecta todo perfectamente (por ejemplo, renombrar una columna lo interpreta como "borrar una y crear otra nueva", perdiendo esos datos).

**Aplicar la migración que acabas de generar:**
```bash
alembic upgrade head
```

**Deshacer la última migración** (por si algo salió mal):
```bash
alembic downgrade -1
```

**Ver el historial de migraciones:**
```bash
alembic history
```

**Ver en qué versión está la base de datos actual:**
```bash
alembic current
```

### 9.3 Si ya tenías una base de datos de antes de usar Alembic
Si tu `medical_appointments.db` ya tenía las tablas creadas por el viejo `create_all()` y coinciden con `models.py` actual, no corras `alembic upgrade head` directamente (fallaría con "la tabla ya existe"). En su lugar, márcala como ya actualizada:
```bash
alembic stamp head
```

---

## 10. Seguridad

Todo lo de esta sección está verificado con `security_test.py` (ver más abajo), un script de pentest que ataca la API a propósito y confirma que cada defensa responda como debe.

### 10.1 Política de contraseñas
Al registrarse, la contraseña debe tener **mínimo 8 caracteres** y contener **al menos una letra y un número**. El límite real de bcrypt es **72 bytes**, no 72 caracteres — con tildes, `ñ` o emojis, una contraseña de 72 caracteres puede pesar más de 72 bytes en UTF-8, así que la validación cuenta bytes, no caracteres.

> **Nota de compatibilidad**: según la versión de `bcrypt` instalada (no está fijada en `requirements.txt`), pasarle una contraseña de más de 72 bytes directamente a la librería puede lanzar `ValueError` en vez de simplemente rechazarla — el comportamiento cambió entre versiones y no es igual en todas las máquinas. Por eso `auth.py` valida el largo en bytes **antes** de llamar a bcrypt en `verify_password()`/`hash_password()`, sin depender de qué versión tenga cada quien instalada. `/login` y `/register` además lo rechazan con 422 a nivel de schema; `/token` (usado por el botón "Authorize" de Swagger) no pasa por ese schema, así que el guardado en `auth.py` es el que realmente evita el crash ahí.

### 10.2 Rate limiting en login
`/login` y `/token` bloquean con **429 Too Many Requests** tras **5 intentos fallidos** en **5 minutos** para el mismo email — incluso si el 6.º intento usa la contraseña correcta. El contador se reinicia tras un login exitoso o al pasar la ventana de 5 minutos.

### 10.3 Rechazo de campos desconocidos
Todos los endpoints que reciben datos (`/register`, `/login`, `/availability`, `/appointments`, etc.) rechazan con **422** cualquier campo que no esté definido en el schema — protege contra intentos de colar campos inesperados en el body.

### 10.4 Clave secreta del JWT (`SECRET_KEY`)
`auth.py` lee la clave de firma de los tokens desde la variable de entorno `SECRET_KEY`. Si no la defines, el servidor genera una aleatoria en cada arranque (verás un aviso en la consola) — útil para desarrollo, pero significa que los tokens dejan de ser válidos al reiniciar. Para un entorno estable o de producción, defínela antes de levantar el servidor:

```bash
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
uvicorn main:app --reload --no-proxy-headers
```
En Windows (PowerShell):
```powershell
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
uvicorn main:app --reload --no-proxy-headers
```
> **Nunca** subas el valor de `SECRET_KEY` al repositorio ni lo hardcodees en el código.

### 10.5 Emails normalizados a minúsculas
El email se guarda y se compara siempre en minúsculas (`Juan@Mail.com` y `juan@mail.com` son la misma cuenta). Evita registros duplicados y bypass del rate limiting jugando con mayúsculas/minúsculas.

### 10.6 IDs de ruta acotados a rango válido
`appointment_id` y `availability_id` en la URL solo aceptan enteros positivos hasta el máximo de un `INTEGER` de SQLite (2⁶³-1). Un ID fuera de rango devuelve **422** en vez de un 500 (antes, SQLite lanzaba `OverflowError` sin capturar).

### 10.7 `/doctors` no expone datos personales
El listado público de médicos (sin login) solo devuelve `id`, `full_name`, `specialty` y `license_number`. Email, teléfono y documento de identidad **no** se exponen ahí — solo son visibles para el propio médico vía `/patients/me`-equivalente autenticado.

### 10.8 Mensaje genérico en registros duplicados
`/register` devuelve el mismo mensaje ("El email o el documento de identidad ya están registrados") sin importar cuál de los dos coincide, para no permitir enumerar qué emails ya están registrados en el sistema probando uno por uno.

### 10.9 Límite de tamaño del body
Cualquier request con `Content-Length` mayor a 1 MB se rechaza con **413** antes de procesarse. Nota: esto depende de que el cliente envíe el header `Content-Length` (no cubre uploads con `Transfer-Encoding: chunked`); en producción, este límite debería reforzarse también a nivel de proxy/servidor (nginx, etc.).

### 10.10 Rate limiting también por IP (password spraying)
Además del límite por email ([10.2](#102-rate-limiting-en-login)), `/login` y `/token` bloquean con **429** una IP que acumule **20 intentos fallidos en 5 minutos**, sin importar contra cuántas cuentas distintas — protege contra "password spraying" (probar una misma contraseña contra muchos emails desde el mismo origen, donde cada cuenta individual nunca llega a su propio límite).

### 10.11 Límite de registros por IP
`/register` bloquea con **429** una IP que cree más de **30 cuentas en una hora**. No reemplaza un CAPTCHA real, pero frena la creación automatizada de cuentas en volumen.

### 10.12 Revocación de sesión individual (`/logout`) y global (`/logout-all`)
Cada token incluye un identificador único (`jti`) y cuándo fue emitido (`iat`).
- **`POST /logout`**: revoca **solo el token usado en esa petición** (guarda su `jti` en la tabla `revoked_tokens`). Otras sesiones del mismo usuario (otro dispositivo, otra pestaña) siguen funcionando.
- **`POST /logout-all`**: revoca **todas** las sesiones del usuario de una vez, marcando en `users.tokens_valid_after` el momento del cierre — cualquier token emitido antes queda inválido de inmediato, sin importar su `jti`.

### 10.13 El servidor no confía en `X-Forwarded-For`
Por defecto, uvicorn confía en el header `X-Forwarded-For` cuando la conexión viene de `127.0.0.1` — sin desactivar esto, cualquiera podía mandar ese header con un valor distinto en cada request y evadir por completo el rate limiting por IP ([10.10](#1010-rate-limiting-también-por-ip-password-spraying) y [10.11](#1011-límite-de-registros-por-ip)), ya que cada request parecía venir de una IP "nueva". `security_test.py` prueba esto exactamente y lo marca como 🚨 si el servidor no está bien configurado.

La primera versión de este fix dependía de que corrieras `uvicorn` con el flag `--no-proxy-headers` **a mano, cada vez** — fácil de olvidar, y de hecho `security_test.py` detectó justo eso en una corrida sin el flag. Por eso ahora existe **`run.py`**: levanta uvicorn con `proxy_headers=False` ya fijado en el código, así no depende de que nadie se acuerde de un flag. **Usa `python run.py` / `python3 run.py` en vez del comando `uvicorn` a secas** (ver [3.1](#31-iniciar-el-servidor)).

`main.py` también fija `proxy_headers=False` en su propio bloque `if __name__ == "__main__":`, por si alguna vez lo corres con `python main.py` directamente.

**Si en algún momento pones esta API detrás de un reverse proxy real** (nginx, un load balancer), vas a necesitar reactivar la confianza en el header (`proxy_headers=True` y `forwarded_allow_ips` con la IP exacta de ese proxy) — nunca dejarlo abierto a `*`.

### 10.14 Rate limiting persistido en base de datos
Los intentos fallidos de login/registro se guardan en la tabla `rate_limit_attempts` (no en un diccionario en memoria del proceso). Esto significa:
- **Sobrevive reinicios**: reiniciar el servidor ya no resetea el contador de intentos fallidos de un atacante.
- **Se comparte entre workers/instancias**: si corres `uvicorn --workers 4` o varias instancias apuntando a la misma base de datos, todas ven el mismo contador (con un dict en memoria, cada worker tenía el suyo, multiplicando el límite real por el número de workers).
- Las filas vencidas se borran en cada consulta, así la tabla no crece sin límite.

Para escalar a múltiples servidores con bases de datos separadas, o para mayor performance en tráfico muy alto, el siguiente paso natural sería mover esto a un store compartido como Redis — pero para el volumen de esta app, SQLite es suficiente y evita sumar una dependencia de infraestructura nueva.

### 10.15 Verificación de email (sustituto de CAPTCHA)
Un CAPTCHA tradicional no aplica bien a una API JSON pura sin frontend (no hay dónde renderizar el widget). En su lugar, `/register` exige verificar el email antes de poder usar las funciones que realmente generan valor en el sistema:
- Al registrarse, el usuario queda con `is_verified: false` y se genera un enlace de un solo uso (`GET /verify-email?token=...`), válido por 24 horas.
- **`POST /appointments`** (agendar cita) y **`POST /availability`** (agregar disponibilidad) devuelven **403** si el usuario no verificó su email. El resto de acciones (login, ver perfil, ver historial) siguen funcionando sin verificar.
- **`POST /resend-verification`** (autenticado) reenvía el enlace si el original expiró o se perdió.
- El envío real de correos usa `smtplib` (nada de dependencias nuevas). Si no configuras SMTP, el enlace se imprime en la consola del servidor — útil para desarrollo, pero en producción **debes** configurar estas variables de entorno:
  ```bash
  export SMTP_HOST=smtp.tu-proveedor.com
  export SMTP_PORT=587
  export SMTP_USER=tu-usuario
  export SMTP_PASSWORD=tu-contraseña
  export APP_BASE_URL=https://tu-dominio.com
  ```
- Mientras `SMTP_HOST` no esté configurado, existe además `GET /_dev/verification-token?email=...` (oculto de `/docs`) que expone el token directamente — así `test_all.py` puede verificar cuentas sin una bandeja de correo real. **Este endpoint deja de existir automáticamente en cuanto configuras `SMTP_HOST`.**

### 10.16 Limitaciones conocidas (no corregidas)
- No es un CAPTCHA real: alguien con acceso a muchos emails desechables (temp-mail) todavía podría verificar cuentas automatizadas una por una — pero ya no puede hacerlo con solo un script contra `/register`, necesita resolver la verificación de cada email.
- `/logout` y `/logout-all` no muestran al usuario una lista de "sesiones activas" (IP, dispositivo, fecha) para elegir cuál cerrar — solo existe "esta" o "todas".

### 10.17 Script de pentest (`security_test.py`)
A diferencia de `test_all.py` (que verifica que la API *funcione*), este script la **ataca a propósito** y confirma que cada defensa responda con el código esperado (401/403/422/429) en vez de dejar pasar el ataque — manipulación de JWT, inyección SQL, IDOR, escalación de privilegios, mass assignment, overflow de enteros, exposición de PII, duplicados por mayúsculas, payload gigante, verificación de email, revocación de sesión, fuerza bruta, password spraying con spoofing de `X-Forwarded-For`, y creación masiva de cuentas.

```bash
python3 run.py             # en una terminal
python3 security_test.py   # en otra
```

Requiere correr **sin `SMTP_HOST` configurado** (modo dev), ya que usa `/_dev/verification-token` para verificar cuentas de prueba automáticamente.

> ⚠️ El script agota a propósito los límites de rate limiting por IP (login y registro). Después de correrlo, tu propia IP queda bloqueada para login (~5 min) o registro (~1 hora) en esa base de datos — es el comportamiento esperado, no un bug. Córrelo contra una base de datos de prueba, no la real, y no dos veces seguidas esperando que ambas pasen limpio.

Cada línea marcada con 🚨 en la salida indica un ataque que tuvo más éxito del esperado — es decir, una vulnerabilidad real que hay que investigar.

### 10.18 `run.py` corre las migraciones automáticamente
Desde que se introdujo Alembic, el servidor dejó de crear las tablas solo al arrancar — si alguien levanta el servidor sin haber corrido `alembic upgrade head` antes (por ejemplo, con una base de datos nueva o recién borrada), **todo** endpoint que toque la base de datos responde con **500 Internal Server Error** en vez de un error controlado, porque las tablas simplemente no existen. `run.py` llama a `alembic upgrade head` por su cuenta antes de levantar uvicorn, así que este error deja de ser posible siguiendo el flujo recomendado. `test_all.py` y `security_test.py` además revisan esto al arrancar (`GET /doctors`) y avisan con un mensaje claro en vez de un traceback si detectan una base de datos sin migrar.

---

## Notas

- La base de datos `medical_appointments.db` se crea/actualiza corriendo `alembic upgrade head` (ver [sección 9](#9-migraciones-con-alembic)) — ya no se crea sola al levantar el servidor.
- Los tokens JWT duran **60 minutos** antes de expirar.
- Las contraseñas se almacenan hasheadas con **bcrypt** (nunca en texto plano).
- La fecha y hora de las citas se almacenan como strings para mayor compatibilidad con SQLite.
- Un usuario recién registrado **no puede** agendar citas ni agregar disponibilidad hasta verificar su email (ver [10.15](#1015-verificación-de-email-sustituto-de-captcha)). Sí puede iniciar sesión y ver su perfil sin verificar.
