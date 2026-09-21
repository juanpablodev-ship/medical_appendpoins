"""
Script de pruebas end-to-end para la API de Gestión de Citas Médicas.

Requisitos:
    - El servidor debe estar corriendo: uvicorn main:app --reload
    - pip install requests

Uso:
    python3 test_all.py

Este script es IDEMPOTENTE: genera emails/documentos únicos en cada
ejecución (usando un sufijo aleatorio), por lo que puede correrse las
veces que quieras sin necesidad de borrar medical_appointments.db.
Las fechas de las citas se calculan en relación a "hoy", así que nunca
quedan obsoletas.
"""
import sys
import uuid
from datetime import date, datetime, timedelta

import requests

BASE = "http://localhost:8000"
SUFFIX = uuid.uuid4().hex[:6]  # hace única cada ejecución

passed = 0
failed = 0


def section(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def check(label, response, expected_status):
    global passed, failed
    ok = response.status_code == expected_status
    icon = "✅" if ok else "❌"
    print(f"{icon} {label} -> esperado {expected_status}, obtuvo {response.status_code}")
    if not ok:
        try:
            print(f"    detalle: {response.json()}")
        except Exception:
            print(f"    detalle: {response.text}")
        failed += 1
    else:
        passed += 1
    return response


def verify_user(email):
    # Solo funciona si el servidor corre sin SMTP configurado (modo dev):
    # /_dev/verification-token expone el token en vez de mandarlo por correo.
    r = requests.get(f"{BASE}/_dev/verification-token", params={"email": email})
    r.raise_for_status()
    token = r.json()["token"]
    return requests.get(f"{BASE}/verify-email", params={"token": token})


# ==========================================
section("0. VERIFICAR QUE EL SERVIDOR ESTÉ CORRIENDO")
# ==========================================
try:
    requests.get(f"{BASE}/docs", timeout=3)
    print(f"✅ Servidor accesible en {BASE}")
except requests.exceptions.ConnectionError:
    print(f"❌ No se pudo conectar a {BASE}")
    print("   Levanta el servidor primero con: uvicorn main:app --reload")
    sys.exit(1)


# ==========================================
# Fechas dinámicas: tomamos los próximos 7 días (offsets 1..7),
# que cubren cada día de la semana exactamente una vez.
# ==========================================
today = date.today()
dates = {offset: today + timedelta(days=offset) for offset in range(1, 8)}

# El Dr. López trabajará en estos offsets (dejamos fuera el offset 2
# a propósito para probar "médico no disponible ese día").
LOPEZ_WORK_OFFSETS = [1, 3, 4, 5, 6]
LOPEZ_NO_WORK_OFFSET = 2

# ==========================================
section("1. REGISTRAR 3 PACIENTES")
# ==========================================
pacientes = [
    {"email": f"carlos.{SUFFIX}@email.com", "password": "Segura123", "full_name": "Carlos García",
     "phone": "+573001112233", "document_id": f"CG{SUFFIX}1", "role": "patient"},
    {"email": f"maria.{SUFFIX}@email.com", "password": "Segura123", "full_name": "María López",
     "phone": "+573002223344", "document_id": f"ML{SUFFIX}2", "role": "patient"},
    {"email": f"pedro.{SUFFIX}@email.com", "password": "Segura123", "full_name": "Pedro Ramírez",
     "phone": "+573003334455", "document_id": f"PR{SUFFIX}3", "role": "patient"},
]
for p in pacientes:
    check(f"Registrar paciente {p['full_name']}", requests.post(f"{BASE}/register", json=p), 201)
    check(f"Verificar email de {p['full_name']}", verify_user(p["email"]), 200)

# ==========================================
section("2. REGISTRAR 3 MÉDICOS")
# ==========================================
medicos = [
    {"email": f"dr.lopez.{SUFFIX}@email.com", "password": "Segura123", "full_name": "Dr. Carlos López",
     "phone": "+573009876543", "document_id": f"DL{SUFFIX}4", "role": "doctor",
     "specialty": "Medicina General", "license_number": f"MG-{SUFFIX}-1"},
    {"email": f"dra.martinez.{SUFFIX}@email.com", "password": "Segura123", "full_name": "Dra. Ana Martínez",
     "phone": "+573005551234", "document_id": f"AM{SUFFIX}5", "role": "doctor",
     "specialty": "Pediatría", "license_number": f"MG-{SUFFIX}-2"},
    {"email": f"dr.garcia.{SUFFIX}@email.com", "password": "Segura123", "full_name": "Dr. Luis García",
     "phone": "+573006667788", "document_id": f"LG{SUFFIX}6", "role": "doctor",
     "specialty": "Cardiología", "license_number": f"MG-{SUFFIX}-3"},
]
doctor_ids = {}
for m in medicos:
    r = check(f"Registrar médico {m['full_name']}", requests.post(f"{BASE}/register", json=m), 201)
    if r.status_code == 201:
        doctor_ids[m["email"]] = r.json()["id"]
    check(f"Verificar email de {m['full_name']}", verify_user(m["email"]), 200)

# ==========================================
section("3. LOGIN - TODOS LOS USUARIOS")
# ==========================================
tokens = {}
for user in pacientes + medicos:
    r = check(f"Login {user['full_name']}",
              requests.post(f"{BASE}/login", json={"email": user["email"], "password": user["password"]}),
              200)
    tokens[user["email"]] = r.json()["access_token"]

headers_p1 = {"Authorization": f"Bearer {tokens[pacientes[0]['email']]}"}
headers_p2 = {"Authorization": f"Bearer {tokens[pacientes[1]['email']]}"}
headers_p3 = {"Authorization": f"Bearer {tokens[pacientes[2]['email']]}"}
headers_m1 = {"Authorization": f"Bearer {tokens[medicos[0]['email']]}"}  # Dr. López
headers_m2 = {"Authorization": f"Bearer {tokens[medicos[1]['email']]}"}  # Dra. Martínez
headers_m3 = {"Authorization": f"Bearer {tokens[medicos[2]['email']]}"}  # Dr. García

# ==========================================
section("4. VER PERFIL Y LISTAR MÉDICOS")
# ==========================================
check("Ver mi perfil (paciente 1)", requests.get(f"{BASE}/patients/me", headers=headers_p1), 200)
check("Ver historial vacío (paciente 1)", requests.get(f"{BASE}/patients/me/history", headers=headers_p1), 200)
check("Listar médicos", requests.get(f"{BASE}/doctors"), 200)

# ==========================================
section("5. MÉDICOS AGREGAN DISPONIBILIDAD")
# ==========================================
avail_ids_lopez = []
for offset in LOPEZ_WORK_OFFSETS:
    day_of_week = dates[offset].weekday()
    r = check(f"Dr. López disponibilidad día_semana={day_of_week} (offset +{offset})",
              requests.post(f"{BASE}/availability",
                             json={"day_of_week": day_of_week, "start_time": "08:00", "end_time": "12:00"},
                             headers=headers_m1),
              201)
    if r.status_code == 201:
        avail_ids_lopez.append(r.json()["id"])

for offset in [1, 3]:
    check(f"Dra. Martínez disponibilidad día_semana={dates[offset].weekday()}",
          requests.post(f"{BASE}/availability",
                         json={"day_of_week": dates[offset].weekday(), "start_time": "09:00", "end_time": "15:00"},
                         headers=headers_m2),
          201)

for offset in [4]:
    check(f"Dr. García disponibilidad día_semana={dates[offset].weekday()}",
          requests.post(f"{BASE}/availability",
                         json={"day_of_week": dates[offset].weekday(), "start_time": "14:00", "end_time": "18:00"},
                         headers=headers_m3),
          201)

check("Ver mis horarios (Dr. López)", requests.get(f"{BASE}/availability/me", headers=headers_m1), 200)

# ==========================================
section("6. ACTUALIZAR Y ELIMINAR DISPONIBILIDAD")
# ==========================================
if avail_ids_lopez:
    first_id = avail_ids_lopez[0]
    check("Dr. López actualiza su primer horario (09:00-13:00)",
          requests.patch(f"{BASE}/availability/{first_id}",
                          json={"start_time": "09:00", "end_time": "13:00"}, headers=headers_m1),
          200)
    check("Dra. Martínez intenta actualizar horario del Dr. López (debe fallar)",
          requests.patch(f"{BASE}/availability/{first_id}",
                          json={"start_time": "07:00"}, headers=headers_m2),
          404)

if len(avail_ids_lopez) > 1:
    last_id = avail_ids_lopez[-1]
    check("Dr. López elimina su último horario",
          requests.delete(f"{BASE}/availability/{last_id}", headers=headers_m1),
          204)

# ==========================================
section("7. CREAR CITAS VÁLIDAS")
# ==========================================
d_ok1 = dates[LOPEZ_WORK_OFFSETS[1]].isoformat()  # un día que López sí trabaja
d_ok2 = dates[LOPEZ_WORK_OFFSETS[2]].isoformat()

id_lopez = doctor_ids[medicos[0]["email"]]
id_martinez = doctor_ids[medicos[1]["email"]]

r = requests.post(f"{BASE}/appointments",
                   json={"doctor_id": id_lopez, "date": d_ok1, "time": "09:30", "reason": "Dolor de cabeza"},
                   headers=headers_p1)
check("Carlos agenda cita con Dr. López (id correcto)", r, 201)
cita_carlos_1 = r.json()["id"] if r.status_code == 201 else None

r = requests.post(f"{BASE}/appointments",
                   json={"doctor_id": id_lopez, "date": d_ok2, "time": "10:00", "reason": "Revisión"},
                   headers=headers_p1)
check("Carlos agenda segunda cita con Dr. López", r, 201)
cita_carlos_2 = r.json()["id"] if r.status_code == 201 else None

r = requests.post(f"{BASE}/appointments",
                   json={"doctor_id": id_lopez, "date": d_ok1, "time": "10:00", "reason": "Control"},
                   headers=headers_p2)
check("María agenda cita con Dr. López (misma fecha, otra hora)", r, 201)
cita_maria = r.json()["id"] if r.status_code == 201 else None

# ==========================================
section("8. VALIDACIONES - ERRORES ESPERADOS")
# ==========================================
check("Doble reserva (misma fecha/hora que Carlos)",
      requests.post(f"{BASE}/appointments",
                     json={"doctor_id": id_lopez, "date": d_ok1, "time": "09:30", "reason": "Duplicado"},
                     headers=headers_p3),
      409)

d_no_disponible = dates[LOPEZ_NO_WORK_OFFSET].isoformat()
check("Cita en día que Dr. López no atiende",
      requests.post(f"{BASE}/appointments",
                     json={"doctor_id": id_lopez, "date": d_no_disponible, "time": "10:00", "reason": "Error día"},
                     headers=headers_p3),
      409)

check("Cita fuera del horario de atención (20:00)",
      requests.post(f"{BASE}/appointments",
                     json={"doctor_id": id_lopez, "date": d_ok1, "time": "20:00", "reason": "Error hora"},
                     headers=headers_p3),
      409)

fecha_pasada = (today - timedelta(days=1)).isoformat()
check("Cita en el pasado",
      requests.post(f"{BASE}/appointments",
                     json={"doctor_id": id_lopez, "date": fecha_pasada, "time": "10:00", "reason": "Error fecha"},
                     headers=headers_p3),
      400)

check("Formato de fecha inválido",
      requests.post(f"{BASE}/appointments",
                     json={"doctor_id": id_lopez, "date": "21-09-2026", "time": "10:00", "reason": "x"},
                     headers=headers_p3),
      422)

# ==========================================
section("9. AGENDA Y ESTADOS")
# ==========================================
check("Ver agenda completa del Dr. López", requests.get(f"{BASE}/doctors/me/appointments", headers=headers_m1), 200)
check("Ver agenda filtrada por fecha", requests.get(f"{BASE}/doctors/me/appointments?date={d_ok1}", headers=headers_m1), 200)

if cita_carlos_1:
    check("Dr. López confirma cita de Carlos",
          requests.patch(f"{BASE}/appointments/{cita_carlos_1}/status", json={"status": "confirmed"}, headers=headers_m1),
          200)

check("Estado inválido rechazado",
      requests.patch(f"{BASE}/appointments/{cita_carlos_1}/status", json={"status": "en_camino"}, headers=headers_m1) if cita_carlos_1
      else requests.get(f"{BASE}/doctors"),
      422 if cita_carlos_1 else 200)

if cita_carlos_2:
    check("Carlos cancela su segunda cita",
          requests.patch(f"{BASE}/appointments/{cita_carlos_2}/cancel", headers=headers_p1),
          200)
    check("Cancelar una cita ya cancelada",
          requests.patch(f"{BASE}/appointments/{cita_carlos_2}/cancel", headers=headers_p1),
          400)

# ==========================================
section("10. CONTROL DE ACCESO POR ROLES")
# ==========================================
check("Paciente intenta ver agenda de médico (prohibido)",
      requests.get(f"{BASE}/doctors/me/appointments", headers=headers_p1), 403)
check("Médico intenta ver perfil de paciente (prohibido)",
      requests.get(f"{BASE}/patients/me", headers=headers_m1), 403)

if cita_maria:
    check("Carlos intenta borrar la cita de María (no es suya, prohibido)",
          requests.delete(f"{BASE}/appointments/{cita_maria}", headers=headers_p1), 403)
    check("Dra. Martínez intenta borrar cita de otro médico (prohibido)",
          requests.delete(f"{BASE}/appointments/{cita_maria}", headers=headers_m2), 403)
    check("María elimina su propia cita",
          requests.delete(f"{BASE}/appointments/{cita_maria}", headers=headers_p2), 204)

check("Eliminar cita inexistente", requests.delete(f"{BASE}/appointments/999999", headers=headers_p1), 404)

# ==========================================
section("11. VALIDACIONES DE REGISTRO")
# ==========================================
check("Email duplicado",
      requests.post(f"{BASE}/register", json={**pacientes[0], "document_id": "OTRO12345"}), 400)
check("Documento duplicado",
      requests.post(f"{BASE}/register",
                     json={**pacientes[0], "email": f"nuevo.{SUFFIX}@email.com"}), 400)
check("Contraseña incorrecta al login",
      requests.post(f"{BASE}/login", json={"email": pacientes[0]["email"], "password": "wrongpassword"}), 401)
check("Rol inválido",
      requests.post(f"{BASE}/register",
                     json={**pacientes[0], "email": f"bad.{SUFFIX}@email.com",
                           "document_id": f"BAD{SUFFIX}9", "role": "admin"}),
      422)
check("Médico sin especialidad (campo requerido por rol)",
      requests.post(f"{BASE}/register",
                     json={"email": f"docsin.{SUFFIX}@email.com", "password": "Segura123", "full_name": "Doc Incompleto",
                           "phone": "+573000000000", "document_id": f"DOCX{SUFFIX}", "role": "doctor"}),
      422)
check("Documento con formato inválido",
      requests.post(f"{BASE}/register",
                     json={"email": f"docformato.{SUFFIX}@email.com", "password": "Segura123", "full_name": "X",
                           "phone": "+573000000000", "document_id": "a b", "role": "patient"}),
      422)

# ==========================================
section("12. VERIFICACIÓN DE EMAIL OBLIGATORIA PARA AGENDAR")
# ==========================================
sin_verificar = {"email": f"sinverificar.{SUFFIX}@email.com", "password": "Segura123", "full_name": "Sin Verificar",
                  "phone": "+573000000099", "document_id": f"NV{SUFFIX}9", "role": "patient"}
check("Registrar paciente sin verificar", requests.post(f"{BASE}/register", json=sin_verificar), 201)
token_nv = requests.post(f"{BASE}/login", json={"email": sin_verificar["email"], "password": sin_verificar["password"]}).json()["access_token"]
headers_nv = {"Authorization": f"Bearer {token_nv}"}
check("Paciente sin verificar intenta agendar cita (prohibido)",
      requests.post(f"{BASE}/appointments", json={"doctor_id": id_lopez, "date": d_ok1, "time": "09:30"}, headers=headers_nv),
      403)
check("Reenviar verificación", requests.post(f"{BASE}/resend-verification", headers=headers_nv), 200)
check("Verificar email tras reenvío", verify_user(sin_verificar["email"]), 200)
check("Ahora sí puede agendar (mismo horario que ya usó Carlos, debe dar 409 no 403)",
      requests.post(f"{BASE}/appointments", json={"doctor_id": id_lopez, "date": d_ok1, "time": "09:30"}, headers=headers_nv),
      409)

# ==========================================
section("13. REVOCACIÓN DE SESIÓN (/logout Y /logout-all)")
# ==========================================
token_a = requests.post(f"{BASE}/login", json={"email": pacientes[0]["email"], "password": pacientes[0]["password"]}).json()["access_token"]
token_b = requests.post(f"{BASE}/login", json={"email": pacientes[0]["email"], "password": pacientes[0]["password"]}).json()["access_token"]
check("Token A funciona antes de logout", requests.get(f"{BASE}/patients/me", headers={"Authorization": f"Bearer {token_a}"}), 200)
check("Logout revoca solo el token A", requests.post(f"{BASE}/logout", headers={"Authorization": f"Bearer {token_a}"}), 200)
check("Token A ya no funciona", requests.get(f"{BASE}/patients/me", headers={"Authorization": f"Bearer {token_a}"}), 401)
check("Token B (otra sesión) sigue funcionando", requests.get(f"{BASE}/patients/me", headers={"Authorization": f"Bearer {token_b}"}), 200)
check("Logout-all revoca TODAS las sesiones", requests.post(f"{BASE}/logout-all", headers={"Authorization": f"Bearer {token_b}"}), 200)
check("Token B ya no funciona tras logout-all", requests.get(f"{BASE}/patients/me", headers={"Authorization": f"Bearer {token_b}"}), 401)

# ==========================================
section("RESUMEN FINAL")
# ==========================================
total = passed + failed
print(f"\n✅ Pasaron: {passed}/{total}")
print(f"❌ Fallaron: {failed}/{total}")
sys.exit(1 if failed else 0)
