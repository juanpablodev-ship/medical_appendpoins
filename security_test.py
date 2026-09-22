"""
Script de PENTEST automatizado para la API de Gestión de Citas Médicas.

A diferencia de test_all.py (que verifica que la API funcione), este script
ataca la API a propósito y confirma que cada defensa responda como debería
(401/403/422/429), no que el ataque tenga éxito.

Requisitos:
    - El servidor debe estar corriendo: uvicorn main:app --reload --no-proxy-headers
    - Recomendado correrlo SIN SMTP configurado (modo dev), para poder
      verificar emails automáticamente vía /_dev/verification-token.
    - pip install requests

Uso:
    python3 security_test.py

⚠️  ADVERTENCIA: este script agota a propósito los límites de rate limiting
por IP (login y registro). Después de correrlo, tu propia IP puede quedar
bloqueada para hacer login (~5 min) o registrar cuentas (~1 hora) en esa
misma base de datos. Es el comportamiento esperado, no un bug del script.
Se recomienda correrlo contra una base de datos de prueba, no la real.
"""
import sys
import uuid
import json
import base64
from datetime import date, timedelta

import requests

BASE = "http://localhost:8000"
SUFFIX = uuid.uuid4().hex[:6]

passed = 0
failed = 0


def section(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def check(label, response, expected_statuses):
    global passed, failed
    if isinstance(expected_statuses, int):
        expected_statuses = [expected_statuses]
    ok = response.status_code in expected_statuses
    icon = "✅" if ok else "🚨"
    esperado = " o ".join(str(s) for s in expected_statuses)
    print(f"{icon} {label} -> esperado {esperado}, obtuvo {response.status_code}")
    if not ok:
        try:
            print(f"    ⚠️  POSIBLE VULNERABILIDAD - detalle: {response.json()}")
        except Exception:
            print(f"    ⚠️  POSIBLE VULNERABILIDAD - detalle: {response.text[:200]}")
        failed += 1
    else:
        passed += 1
    return response


def check_bool(label, condition_ok, detail_on_fail=""):
    global passed, failed
    icon = "✅" if condition_ok else "🚨"
    print(f"{icon} {label}")
    if not condition_ok:
        print(f"    ⚠️  POSIBLE VULNERABILIDAD - {detail_on_fail}")
        failed += 1
    else:
        passed += 1


def b64url(data: dict) -> str:
    raw = json.dumps(data).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def verify_user(email):
    r = requests.get(f"{BASE}/_dev/verification-token", params={"email": email})
    if r.status_code != 200:
        return None
    token = r.json()["token"]
    return requests.get(f"{BASE}/verify-email", params={"token": token})


def register_and_verify(email, password, full_name, phone, doc_id, role, **extra):
    payload = {"email": email, "password": password, "full_name": full_name,
               "phone": phone, "document_id": doc_id, "role": role, **extra}
    r = requests.post(f"{BASE}/register", json=payload)
    if r.status_code != 201:
        return None, None
    verify_user(email)
    login_r = requests.post(f"{BASE}/login", json={"email": email, "password": password})
    token = login_r.json().get("access_token") if login_r.status_code == 200 else None
    return r.json()["id"], token


def trigger_rate_limit(request_fn, max_attempts):
    """Llama request_fn() hasta max_attempts veces o hasta ver un 429."""
    for i in range(1, max_attempts + 1):
        r = request_fn(i)
        if r.status_code == 429:
            return i, True
    return max_attempts, False


# ==========================================
section("0. VERIFICAR QUE EL SERVIDOR ESTÉ CORRIENDO")
# ==========================================
try:
    requests.get(f"{BASE}/docs", timeout=3)
    print(f"✅ Servidor accesible en {BASE}")
except requests.exceptions.ConnectionError:
    print(f"❌ No se pudo conectar a {BASE}")
    print("   Levanta el servidor primero con: python3 run.py")
    sys.exit(1)

r_db_check = requests.get(f"{BASE}/doctors")
if r_db_check.status_code >= 500:
    print("❌ La base de datos no tiene las tablas creadas (¿corriste 'alembic upgrade head'?)")
    print(f"   detalle: {r_db_check.text[:200]}")
    sys.exit(1)
print("✅ Base de datos con el esquema esperado")

_probe = requests.get(f"{BASE}/_dev/verification-token", params={"email": "x@x.com"})
# Si la ruta no existe, FastAPI responde {"detail": "Not Found"} (genérico del framework);
# si existe pero el usuario no, responde nuestro mensaje propio ("No encontrado").
DEV_MODE = _probe.status_code == 404 and _probe.json().get("detail") != "Not Found"
if not DEV_MODE:
    print("⚠️  El endpoint /_dev/verification-token no está disponible (¿SMTP configurado?).")
    print("   Este script necesita modo dev para verificar cuentas automáticamente. Abortando.")
    sys.exit(1)

# ==========================================
section("1. SETUP: usuarios de prueba (verificados)")
# ==========================================
p1_id, token_p1 = register_and_verify(
    f"atkp1.{SUFFIX}@test.com", "Segura123", "Attack Patient 1", "+111", f"ATKP1{SUFFIX}", "patient")
p2_id, token_p2 = register_and_verify(
    f"atkp2.{SUFFIX}@test.com", "Segura123", "Attack Patient 2", "+222", f"ATKP2{SUFFIX}", "patient")
m1_id, token_m1 = register_and_verify(
    f"atkm1.{SUFFIX}@test.com", "Segura123", "Attack Doctor 1", "+333", f"ATKM1{SUFFIX}", "doctor",
    specialty="General", license_number=f"LIC{SUFFIX}")
m2_id, token_m2 = register_and_verify(
    f"atkm2.{SUFFIX}@test.com", "Segura123", "Attack Doctor 2", "+444", f"ATKM2{SUFFIX}", "doctor",
    specialty="General", license_number=f"LIC2{SUFFIX}")

if not all([token_p1, token_p2, token_m1, token_m2]):
    print("❌ No se pudo preparar el entorno de prueba (revisa que el servidor esté limpio). Abortando.")
    sys.exit(1)

headers_p1 = {"Authorization": f"Bearer {token_p1}"}
headers_p2 = {"Authorization": f"Bearer {token_p2}"}
headers_m1 = {"Authorization": f"Bearer {token_m1}"}
headers_m2 = {"Authorization": f"Bearer {token_m2}"}

requests.post(f"{BASE}/availability", json={"day_of_week": 0, "start_time": "08:00", "end_time": "18:00"}, headers=headers_m1)
next_monday = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)
cita = requests.post(f"{BASE}/appointments",
                      json={"doctor_id": m1_id, "date": next_monday.isoformat(), "time": "09:00", "reason": "test"},
                      headers=headers_p1).json()
cita_id = cita.get("id")
print(f"Setup listo. cita_id={cita_id}, doctor m1_id={m1_id}")

# ==========================================
section("2. MANIPULACIÓN DE JWT")
# ==========================================
check("Token con firma alterada", requests.get(f"{BASE}/patients/me", headers={"Authorization": f"Bearer {token_p1[:-1]}X"}), 401)

none_token = b64url({"alg": "none", "typ": "JWT"}) + "." + b64url({"sub": "1", "role": "doctor"}) + "."
check("Ataque alg=none (token sin firma)", requests.get(f"{BASE}/patients/me", headers={"Authorization": f"Bearer {none_token}"}), 401)

parts = token_p1.split(".")
payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
payload["sub"] = "999999"
tampered = parts[0] + "." + b64url(payload) + "." + parts[2]
check("Payload modificado (sub falsificado) sin re-firmar", requests.get(f"{BASE}/patients/me", headers={"Authorization": f"Bearer {tampered}"}), 401)

check("Sin token", requests.get(f"{BASE}/patients/me"), 401)
check("Esquema de auth incorrecto (Basic en vez de Bearer)", requests.get(f"{BASE}/patients/me", headers={"Authorization": "Basic YWRtaW46YWRtaW4="}), 401)

# ==========================================
section("3. INYECCIÓN SQL")
# ==========================================
check("SQLi clásica en email de login", requests.post(f"{BASE}/login", json={"email": "' OR '1'='1", "password": "x"}), 422)
check("SQLi UNION-based en email de registro",
      requests.post(f"{BASE}/register", json={"email": "x@test.com'; DROP TABLE users;--", "password": "Segura123",
                                                "full_name": "X", "phone": "+111", "document_id": "SQLI11111", "role": "patient"}),
      422)
r = requests.get(f"{BASE}/doctors")
check("La tabla users sigue intacta tras los intentos de SQLi", r, 200)

# ==========================================
section("4. IDOR (acceso a recursos de otro usuario)")
# ==========================================
check("Paciente2 intenta cancelar cita de Paciente1", requests.patch(f"{BASE}/appointments/{cita_id}/cancel", headers=headers_p2), 404)
check("Paciente2 intenta eliminar cita de Paciente1", requests.delete(f"{BASE}/appointments/{cita_id}", headers=headers_p2), 403)
check("Médico2 intenta eliminar cita de Médico1", requests.delete(f"{BASE}/appointments/{cita_id}", headers=headers_m2), 403)
check("Médico2 intenta editar disponibilidad de Médico1",
      requests.patch(f"{BASE}/availability/1", json={"start_time": "07:00"}, headers=headers_m2), [403, 404])

# ==========================================
section("5. ESCALACIÓN DE PRIVILEGIOS / ROLES")
# ==========================================
check("Paciente intenta ver agenda de médico", requests.get(f"{BASE}/doctors/me/appointments", headers=headers_p1), 403)
check("Paciente intenta cambiar estado de una cita (acción de médico)",
      requests.patch(f"{BASE}/appointments/{cita_id}/status", json={"status": "confirmed"}, headers=headers_p1), 403)
check("Paciente intenta crear disponibilidad", requests.post(f"{BASE}/availability", json={"day_of_week": 0, "start_time": "08:00", "end_time": "12:00"}, headers=headers_p1), 403)
check("Médico intenta ver perfil de paciente", requests.get(f"{BASE}/patients/me", headers=headers_m1), 403)

# ==========================================
section("6. MASS ASSIGNMENT / CAMPOS INESPERADOS")
# ==========================================
check("Intentar inyectar id/hashed_password en el registro",
      requests.post(f"{BASE}/register", json={"email": f"mass.{SUFFIX}@test.com", "password": "Segura123", "full_name": "M",
                                                "phone": "+111", "document_id": f"MASS{SUFFIX}", "role": "patient",
                                                "id": 9999, "hashed_password": "pwned", "is_verified": True}),
      422)
check("Campo extra no documentado en creación de cita",
      requests.post(f"{BASE}/appointments", json={"doctor_id": m1_id, "date": next_monday.isoformat(), "time": "09:00", "status": "confirmed"}, headers=headers_p1),
      422)

# ==========================================
section("7. OVERFLOW DE ENTEROS EN IDs DE RUTA")
# ==========================================
check("appointment_id gigante", requests.delete(f"{BASE}/appointments/999999999999999999999999999999", headers=headers_p1), 422)
check("availability_id gigante", requests.delete(f"{BASE}/availability/999999999999999999999999999999", headers=headers_m1), 422)
check("appointment_id negativo", requests.delete(f"{BASE}/appointments/-1", headers=headers_p1), 422)
check("appointment_id no numérico", requests.delete(f"{BASE}/appointments/abc", headers=headers_p1), 422)

# ==========================================
section("8. EXPOSICIÓN DE DATOS PERSONALES")
# ==========================================
doctores = requests.get(f"{BASE}/doctors").json()
campos_sensibles = {"email", "phone", "document_id"}
expuestos = campos_sensibles & set(doctores[0].keys()) if doctores else set()
check_bool(f"/doctors no expone {campos_sensibles}", not expuestos, f"campos expuestos de más: {expuestos}")

# ==========================================
section("9. DUPLICADOS POR MAYÚSCULAS Y ENUMERACIÓN")
# ==========================================
dup_email = f"CaseTest.{SUFFIX}@Test.com"
requests.post(f"{BASE}/register", json={"email": dup_email.lower(), "password": "Segura123", "full_name": "C",
                                          "phone": "+111", "document_id": f"CASE{SUFFIX}", "role": "patient"})
check("Registrar el mismo email con mayúsculas distintas", requests.post(f"{BASE}/register",
      json={"email": dup_email.upper(), "password": "Segura123", "full_name": "C2", "phone": "+111",
            "document_id": f"CASEB{SUFFIX}", "role": "patient"}), 400)

r_email_dup = requests.post(f"{BASE}/register", json={"email": dup_email.lower(), "password": "Segura123", "full_name": "C3",
                                                        "phone": "+111", "document_id": f"OTRO{SUFFIX}", "role": "patient"})
r_doc_dup = requests.post(f"{BASE}/register", json={"email": f"otro.{SUFFIX}@test.com", "password": "Segura123", "full_name": "C4",
                                                      "phone": "+111", "document_id": f"CASE{SUFFIX}", "role": "patient"})
check_bool("Mensaje de duplicado no distingue email vs. documento (anti-enumeración)",
           r_email_dup.json() == r_doc_dup.json(),
           f"mensajes distintos: {r_email_dup.json()} vs {r_doc_dup.json()}")

# ==========================================
section("10. VERIFICACIÓN DE EMAIL OBLIGATORIA")
# ==========================================
r_nv = requests.post(f"{BASE}/register", json={"email": f"noverif.{SUFFIX}@test.com", "password": "Segura123",
                                                 "full_name": "No Verificado", "phone": "+111",
                                                 "document_id": f"NOVER{SUFFIX}", "role": "patient"})
token_nv = requests.post(f"{BASE}/login", json={"email": f"noverif.{SUFFIX}@test.com", "password": "Segura123"}).json().get("access_token")
headers_nv = {"Authorization": f"Bearer {token_nv}"}
check("Usuario sin verificar intenta agendar cita",
      requests.post(f"{BASE}/appointments", json={"doctor_id": m1_id, "date": next_monday.isoformat(), "time": "11:00"}, headers=headers_nv),
      403)

# ==========================================
section("11. PAYLOAD GIGANTE (DoS)")
# ==========================================
giant = {"email": f"giant.{SUFFIX}@test.com", "password": "Segura123", "full_name": "G", "phone": "+111",
         "document_id": "A" * 2_000_000, "role": "patient"}
check("Payload de ~2MB", requests.post(f"{BASE}/register", data=json.dumps(giant), headers={"Content-Type": "application/json"}), [413, 422])

# ==========================================
section("12. REVOCACIÓN DE SESIÓN")
# ==========================================
token_a = requests.post(f"{BASE}/login", json={"email": f"atkp1.{SUFFIX}@test.com", "password": "Segura123"}).json()["access_token"]
token_b = requests.post(f"{BASE}/login", json={"email": f"atkp1.{SUFFIX}@test.com", "password": "Segura123"}).json()["access_token"]
requests.post(f"{BASE}/logout", headers={"Authorization": f"Bearer {token_a}"})
check("Token revocado individualmente (logout) deja de funcionar", requests.get(f"{BASE}/patients/me", headers={"Authorization": f"Bearer {token_a}"}), 401)
check("Otra sesión del mismo usuario sigue viva", requests.get(f"{BASE}/patients/me", headers={"Authorization": f"Bearer {token_b}"}), 200)
requests.post(f"{BASE}/logout-all", headers={"Authorization": f"Bearer {token_b}"})
check("logout-all revoca también la otra sesión", requests.get(f"{BASE}/patients/me", headers={"Authorization": f"Bearer {token_b}"}), 401)

# ==========================================
# A PARTIR DE AQUÍ los ataques agotan a propósito los límites de IP.
# Van al final porque una vez activados, login/registro desde esta IP
# quedan bloqueados por un rato (ver advertencia al inicio del archivo).
# ==========================================

# ==========================================
section("13. FUERZA BRUTA CONTRA UNA CUENTA (rate limit por email)")
# ==========================================
brute_email = f"atkp2.{SUFFIX}@test.com"
attempts, blocked = trigger_rate_limit(
    lambda i: requests.post(f"{BASE}/login", json={"email": brute_email, "password": f"malaClave{i}"}),
    max_attempts=8
)
check_bool(f"Bloqueo tras fuerza bruta contra una cuenta (activado en intento {attempts})", blocked,
           f"no se activó el 429 en {attempts} intentos")

# ==========================================
section("14. PASSWORD SPRAYING + SPOOFING DE X-Forwarded-For")
# ==========================================
def spray_attempt(i):
    return requests.post(f"{BASE}/login",
                          json={"email": f"spray{i}.{SUFFIX}@test.com", "password": "malaClaveUnica"},
                          headers={"X-Forwarded-For": f"10.0.{i}.{i}"})

attempts, blocked = trigger_rate_limit(spray_attempt, max_attempts=30)
check_bool(f"Bloqueo por IP pese a usar cuentas y X-Forwarded-For distintos en cada intento (activado en intento {attempts})",
           blocked, "el servidor podría estar confiando en X-Forwarded-For (¿corriste con --no-proxy-headers?)")

# ==========================================
section("15. CREACIÓN MASIVA DE CUENTAS (rate limit de /register)")
# ==========================================
def register_attempt(i):
    return requests.post(f"{BASE}/register", json={
        "email": f"flood{i}.{SUFFIX}@test.com", "password": "Segura123", "full_name": f"Flood {i}",
        "phone": "+111", "document_id": f"FLOOD{SUFFIX}{i}", "role": "patient"
    })

attempts, blocked = trigger_rate_limit(register_attempt, max_attempts=35)
check_bool(f"Bloqueo tras registrar cuentas en volumen (activado en intento {attempts})", blocked,
           f"no se activó el 429 en {attempts} intentos")

# ==========================================
section("RESUMEN FINAL")
# ==========================================
total = passed + failed
print(f"\n✅ Defensas correctas: {passed}/{total}")
print(f"🚨 Posibles vulnerabilidades: {failed}/{total}")
if failed:
    print("\nRevisa arriba cada línea marcada con 🚨 — indica que un ataque tuvo más éxito del esperado.")
sys.exit(1 if failed else 0)
