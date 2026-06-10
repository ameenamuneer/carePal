# Account Types & Access Control API

**Version:** 1.0
**Date:** 2026-06-10
**Base URL:** `http://localhost:8000`

---

## Overview

CarePal supports four account types:

| `user_type` | Description |
|---|---|
| `PATIENT` | The monitored individual. Owns all health data. |
| `FAMILY` | Family member or caregiver. Read-only access to linked patients. |
| `DOCTOR` | Clinical staff. Read + edit access based on per-relationship permissions. |
| `ADMIN` | Full access to all data. |

Permissions are **per-link**, not per account type globally. Each Doctor→Patient link (`ClinicalRelationship`) and each Family→Patient link (`FamilyMember`) has its own set of boolean permission flags that can be toggled independently.

---

## 1. Register an Account

All account types use the same endpoint. The `user_type` field determines the type.

**`POST /api/v1/auth/register/`**

### Request fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `username` | string | ✅ | Unique |
| `email` | string | ✅ | Unique |
| `phone_number` | string | ✅ | Format: `+923001234567` |
| `password` | string | ✅ | Must pass Django password validation |
| `password_confirm` | string | ✅ | Must match `password` |
| `user_type` | string | ✅ | `PATIENT`, `FAMILY`, `DOCTOR`, or `ADMIN` |
| `first_name` | string | ❌ | |
| `last_name` | string | ❌ | |
| `date_of_birth` | date | ❌ | Format: `YYYY-MM-DD` |

### Register a Family member
```json
{
  "username": "sara_family",
  "email": "sara@example.com",
  "phone_number": "+923001234567",
  "password": "StrongPass123!",
  "password_confirm": "StrongPass123!",
  "user_type": "FAMILY",
  "first_name": "Sara",
  "last_name": "Khan"
}
```

### Register a Doctor
```json
{
  "username": "dr_ahmed",
  "email": "ahmed@hospital.com",
  "phone_number": "+923009876543",
  "password": "StrongPass123!",
  "password_confirm": "StrongPass123!",
  "user_type": "DOCTOR",
  "first_name": "Ahmed",
  "last_name": "Malik"
}
```

### Register a Patient
```json
{
  "username": "john_patient",
  "email": "john@example.com",
  "phone_number": "+923001111111",
  "password": "StrongPass123!",
  "password_confirm": "StrongPass123!",
  "user_type": "PATIENT",
  "first_name": "John",
  "last_name": "Doe",
  "date_of_birth": "1980-05-15"
}
```

### Response `201 Created`
```json
{
  "message": "User registered successfully",
  "user": {
    "id": 3,
    "username": "dr_ahmed",
    "email": "ahmed@hospital.com",
    "phone_number": "+923009876543",
    "user_type": "DOCTOR",
    "first_name": "Ahmed",
    "last_name": "Malik",
    "date_of_birth": null,
    "age": null,
    "profile_picture": null,
    "is_active": true,
    "created_at": "2026-06-10T10:00:00Z",
    "updated_at": "2026-06-10T10:00:00Z",
    "patient_profile": null
  },
  "tokens": {
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

---

## 2. Login

**`POST /api/v1/auth/login/`**

The `username` field accepts **username, email, or phone number**.

```json
{
  "username": "dr_ahmed",
  "password": "StrongPass123!"
}
```

### Response `200 OK`
```json
{
  "message": "Login successful",
  "user": {
    "id": 3,
    "username": "dr_ahmed",
    "email": "ahmed@hospital.com",
    "phone_number": "+923009876543",
    "user_type": "DOCTOR",
    "first_name": "Ahmed",
    "last_name": "Malik",
    "date_of_birth": null,
    "age": null,
    "profile_picture": null,
    "is_active": true,
    "created_at": "2026-06-10T10:00:00Z",
    "updated_at": "2026-06-10T10:00:00Z",
    "patient_profile": null
  },
  "tokens": {
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

> **Note:** For a Patient login, `patient_profile` is populated:
> ```json
> "patient_profile": {
>   "id": 1,
>   "gender": "MALE",
>   "blood_group": "O+"
> }
> ```
> For Family and Doctor accounts it will always be `null`.

All subsequent requests must include the access token in the header:
```
Authorization: Bearer <access_token>
```

---

## 3. Link a Doctor to a Patient (`ClinicalRelationship`)

Once both the doctor and patient accounts exist, create a link using the **doctor's token**.

**`POST /api/v1/auth/clinical-relationships/`**
`Authorization: Bearer <doctor_access_token>`

### Request fields

| Field | Type | Default | Description |
|---|---|---|---|
| `patient` | integer | ✅ required | Patient profile ID |
| `role` | string | `PRIMARY` | `PRIMARY`, `SPECIALIST`, `NURSE`, `CONSULTANT` |
| `can_view_vitals` | bool | `true` | |
| `can_view_activity_log` | bool | `true` | |
| `can_view_medications` | bool | `true` | |
| `can_edit_medications` | bool | `true` | |
| `can_view_alerts` | bool | `true` | |
| `can_view_appointments` | bool | `true` | |
| `can_edit_appointments` | bool | `true` | |
| `notes` | string | `""` | Internal notes about the relationship |

> The `doctor` field is **automatically set** to the logged-in user. Admins can pass a `doctor` ID to create links on behalf of others.

```json
{
  "patient": 1,
  "role": "PRIMARY",
  "can_view_vitals": true,
  "can_view_activity_log": true,
  "can_view_medications": true,
  "can_edit_medications": true,
  "can_view_alerts": true,
  "can_view_appointments": true,
  "can_edit_appointments": false
}
```

### Response `201 Created`
```json
{
  "id": 1,
  "doctor": 3,
  "doctor_name": "Ahmed Malik",
  "patient": 1,
  "patient_name": "John Doe",
  "role": "PRIMARY",
  "is_active": true,
  "notes": "",
  "can_view_vitals": true,
  "can_view_activity_log": true,
  "can_view_medications": true,
  "can_edit_medications": true,
  "can_view_alerts": true,
  "can_view_appointments": true,
  "can_edit_appointments": false,
  "created_at": "2026-06-10T10:05:00Z",
  "updated_at": "2026-06-10T10:05:00Z"
}
```

### Other clinical relationship endpoints

| Method | URL | Description |
|---|---|---|
| `GET` | `/api/v1/auth/clinical-relationships/` | Doctor lists all their patient links |
| `GET` | `/api/v1/auth/clinical-relationships/{id}/` | Get a single link |
| `PATCH` | `/api/v1/auth/clinical-relationships/{id}/` | Update permissions on a link |
| `DELETE` | `/api/v1/auth/clinical-relationships/{id}/` | Remove a link |
| `GET` | `/api/v1/auth/clinical-relationships/my-patients/` | Doctor: list all linked patients |
| `GET` | `/api/v1/auth/clinical-relationships/my-doctors/` | Patient: list all linked doctors |

---

## 4. Link a Family Member to a Patient

**`POST /api/v1/family/members/`**
`Authorization: Bearer <any_authenticated_token>`

### Request fields

| Field | Type | Default | Description |
|---|---|---|---|
| `user` | integer | ✅ required | User ID of the family member |
| `patient` | integer | ✅ required | Patient profile ID |
| `relationship` | string | ✅ required | See relationship choices below |
| `can_view_vitals` | bool | `true` | |
| `can_view_medications` | bool | `true` | View medication schedule |
| `can_view_activity_log` | bool | `true` | |
| `can_view_alerts` | bool | `true` | |
| `can_acknowledge_alerts` | bool | `true` | |
| `can_add_notes` | bool | `true` | |
| `can_manage_medications` | bool | `false` | Edit medications — off by default for family |
| `can_view_medical_history` | bool | `false` | |
| `can_invite_others` | bool | `false` | |
| `is_primary_caregiver` | bool | `false` | |
| `is_emergency_contact` | bool | `false` | |

**Relationship choices:** `SPOUSE`, `CHILD`, `PARENT`, `SIBLING`, `GRANDCHILD`, `GRANDPARENT`, `OTHER_RELATIVE`, `FRIEND`, `CAREGIVER`, `GUARDIAN`

```json
{
  "user": 2,
  "patient": 1,
  "relationship": "CHILD",
  "can_view_vitals": true,
  "can_view_medications": true,
  "can_view_activity_log": true,
  "can_view_alerts": true,
  "can_acknowledge_alerts": true,
  "can_add_notes": true,
  "can_manage_medications": false
}
```

---

## 5. Permission Summary by Account Type

### Family — what they can access

| Feature | Permission flag on `FamilyMember` | Default |
|---|---|---|
| View vitals | `can_view_vitals` | ✅ |
| View activity log | `can_view_activity_log` | ✅ |
| View medication schedule | `can_view_medications` | ✅ |
| View alerts | `can_view_alerts` | ✅ |
| Acknowledge alerts | `can_acknowledge_alerts` | ✅ |
| Add notes | `can_add_notes` | ✅ |
| View medical history | `can_view_medical_history` | ❌ |
| Edit medications | `can_manage_medications` | ❌ |
| Invite others | `can_invite_others` | ❌ |

> Family members **cannot** create, edit, or delete medications regardless of flags — this is enforced at the API layer.

### Doctor — what they can access

| Feature | Permission flag on `ClinicalRelationship` | Default |
|---|---|---|
| View vitals | `can_view_vitals` | ✅ |
| View activity log | `can_view_activity_log` | ✅ |
| View medications | `can_view_medications` | ✅ |
| Edit / add medications | `can_edit_medications` | ✅ |
| View alerts | `can_view_alerts` | ✅ |
| View appointments | `can_view_appointments` | ✅ |
| Edit appointments | `can_edit_appointments` | ✅ |

---

## 6. Quick Test with curl

```bash
# 1. Register a doctor
curl -s -X POST http://localhost:8000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "dr_test",
    "email": "dr@test.com",
    "phone_number": "+923000000001",
    "password": "Test1234!",
    "password_confirm": "Test1234!",
    "user_type": "DOCTOR",
    "first_name": "Test",
    "last_name": "Doctor"
  }'

# 2. Register a family member
curl -s -X POST http://localhost:8000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "sara_family",
    "email": "sara@test.com",
    "phone_number": "+923000000002",
    "password": "Test1234!",
    "password_confirm": "Test1234!",
    "user_type": "FAMILY",
    "first_name": "Sara",
    "last_name": "Khan"
  }'

# 3. Login as doctor — save the access token
curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "dr_test", "password": "Test1234!"}'

# 4. Link doctor to patient (replace DOCTOR_TOKEN and patient id)
curl -s -X POST http://localhost:8000/api/v1/auth/clinical-relationships/ \
  -H "Authorization: Bearer DOCTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"patient": 1, "role": "PRIMARY"}'

# 5. Doctor views their linked patients
curl -s http://localhost:8000/api/v1/auth/clinical-relationships/my-patients/ \
  -H "Authorization: Bearer DOCTOR_TOKEN"

# 6. Link family member to patient (replace TOKEN, user id, patient id)
curl -s -X POST http://localhost:8000/api/v1/family/members/ \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user": 2, "patient": 1, "relationship": "CHILD"}'

# 7. Patient views their linked doctors (replace PATIENT_TOKEN)
curl -s http://localhost:8000/api/v1/auth/clinical-relationships/my-doctors/ \
  -H "Authorization: Bearer PATIENT_TOKEN"
```
