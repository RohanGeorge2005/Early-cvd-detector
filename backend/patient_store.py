"""Encrypted local patient store for the explicitly demo-only portal.

Patient names, contact details, assessment payloads, and PDF bytes are encrypted
with an operator-supplied Fernet key. The key is never generated or persisted by
the application. This is a local research foundation, not a clinic deployment.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from hashlib import sha256, scrypt
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import uuid

from cryptography.fernet import Fernet, InvalidToken


ROLES = {"medical_assistant", "clinician", "administrator", "patient"}
STAFF_ROLES = {"medical_assistant", "clinician", "administrator"}
REVIEW_ROLES = {"clinician", "administrator"}
SESSION_HOURS = 8
INVITE_HOURS = 24


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat()


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


class PatientStore:
    def __init__(self, path: str | Path, encryption_key: str | bytes):
        key = encryption_key.encode() if isinstance(encryption_key, str) else encryption_key
        self.fernet = Fernet(key)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._search_key = sha256(key + b"xai-cvd-patient-search-v1").digest()
        self.initialize()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
                INSERT INTO schema_version(version) SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_version);
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, role TEXT NOT NULL,
                    password_salt BLOB NOT NULL, password_hash BLOB NOT NULL,
                    patient_id TEXT, created_at TEXT NOT NULL, disabled INTEGER NOT NULL DEFAULT 0,
                    failed_logins INTEGER NOT NULL DEFAULT 0, locked_until TEXT,
                    FOREIGN KEY(patient_id) REFERENCES patients(id)
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, csrf_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
                CREATE TABLE IF NOT EXISTS patients (
                    id TEXT PRIMARY KEY, patient_ref TEXT NOT NULL UNIQUE,
                    encrypted_profile BLOB NOT NULL, name_digest TEXT NOT NULL,
                    dob_digest TEXT, email_digest TEXT, created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_patient_name_digest ON patients(name_digest);
                CREATE INDEX IF NOT EXISTS idx_patient_dob_digest ON patients(dob_digest);
                CREATE INDEX IF NOT EXISTS idx_patient_email_digest ON patients(email_digest);
                CREATE TABLE IF NOT EXISTS assessments (
                    id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, created_at TEXT NOT NULL,
                    model_version TEXT NOT NULL, encrypted_payload BLOB NOT NULL,
                    FOREIGN KEY(patient_id) REFERENCES patients(id)
                );
                CREATE INDEX IF NOT EXISTS idx_assessments_patient_date ON assessments(patient_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, assessment_id TEXT NOT NULL,
                    version INTEGER NOT NULL, status TEXT NOT NULL, encrypted_pdf BLOB NOT NULL,
                    created_at TEXT NOT NULL, created_by TEXT NOT NULL,
                    reviewed_by TEXT, reviewed_at TEXT, released_by TEXT, released_at TEXT,
                    UNIQUE(assessment_id, version),
                    FOREIGN KEY(patient_id) REFERENCES patients(id),
                    FOREIGN KEY(assessment_id) REFERENCES assessments(id)
                );
                CREATE INDEX IF NOT EXISTS idx_reports_patient_date ON reports(patient_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS portal_invites (
                    token_hash TEXT PRIMARY KEY, patient_id TEXT NOT NULL, created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT,
                    FOREIGN KEY(patient_id) REFERENCES patients(id)
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY, actor_id TEXT, action TEXT NOT NULL,
                    resource_type TEXT NOT NULL, resource_id TEXT, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_events(resource_type, resource_id, created_at);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_active_patient_portal_user
                    ON users(patient_id) WHERE role='patient' AND disabled=0;
            """)

    def encrypt(self, value: object) -> bytes:
        return self.fernet.encrypt(_json_bytes(value))

    def decrypt(self, value: bytes) -> object:
        return json.loads(self.fernet.decrypt(value).decode("utf-8"))

    def encrypt_bytes(self, value: bytes) -> bytes:
        return self.fernet.encrypt(value)

    def decrypt_bytes(self, value: bytes) -> bytes:
        return self.fernet.decrypt(value)

    def digest(self, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = " ".join(value.casefold().strip().split())
        return hmac.new(self._search_key, normalized.encode("utf-8"), sha256).hexdigest()

    @staticmethod
    def _password_hash(password: str, salt: bytes) -> bytes:
        if len(password) < 12 or len(password) > 256:
            raise ValueError("Password must be 12–256 characters.")
        return scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)

    def create_user(self, username: str, password: str, role: str,
                    patient_id: str | None = None) -> dict:
        normalized = username.casefold().strip()
        if not normalized or len(normalized) > 120 or "@" in normalized:
            raise ValueError("Username must be a non-empty local account name (maximum 120 characters).")
        if role not in ROLES:
            raise ValueError("Unknown account role.")
        if role == "patient" and not patient_id:
            raise ValueError("Patient accounts must be linked to a patient record.")
        salt = secrets.token_bytes(16)
        hashed = self._password_hash(password, salt)
        user_id = uuid.uuid4().hex
        try:
            with self.connect() as db:
                db.execute("INSERT INTO users(id,username,role,password_salt,password_hash,patient_id,created_at) VALUES(?,?,?,?,?,?,?)",
                           (user_id, normalized, role, salt, hashed, patient_id, iso()))
                self._audit(db, user_id, "user.created", "user", user_id)
        except sqlite3.IntegrityError as exc:
            raise ValueError("Username already exists or linked patient does not exist.") from exc
        return {"id": user_id, "username": normalized, "role": role, "patient_id": patient_id}

    def authenticate(self, username: str, password: str) -> dict | None:
        normalized = username.casefold().strip()
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (normalized,)).fetchone()
            if row is None:
                # Perform a password hash to reduce username-enumeration timing differences.
                self._password_hash(password if 12 <= len(password) <= 256 else "invalid-password-placeholder", b"0" * 16)
                return None
            if row["disabled"]:
                return None
            locked_until = row["locked_until"]
            if locked_until and datetime.fromisoformat(locked_until) > utc_now():
                return None
            try:
                candidate = self._password_hash(password, row["password_salt"])
            except ValueError:
                candidate = b""
            if not hmac.compare_digest(candidate, row["password_hash"]):
                attempts = row["failed_logins"] + 1
                lock = iso(utc_now() + timedelta(minutes=15)) if attempts >= 5 else None
                db.execute("UPDATE users SET failed_logins=?, locked_until=? WHERE id=?",
                           (0 if lock else attempts, lock, row["id"]))
                return None
            db.execute("UPDATE users SET failed_logins=0, locked_until=NULL WHERE id=?", (row["id"],))
            self._audit(db, row["id"], "auth.login", "user", row["id"])
            return self._user_dict(row)

    @staticmethod
    def _user_dict(row: sqlite3.Row) -> dict:
        return {"id": row["id"], "username": row["username"], "role": row["role"], "patient_id": row["patient_id"]}

    def create_session(self, user_id: str) -> tuple[str, str, str]:
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        expires = utc_now() + timedelta(hours=SESSION_HOURS)
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires_at < ?", (iso(),))
            db.execute("INSERT INTO sessions(token_hash,user_id,csrf_hash,created_at,expires_at) VALUES(?,?,?,?,?)",
                       (sha256(token.encode()).hexdigest(), user_id, sha256(csrf.encode()).hexdigest(), iso(), iso(expires)))
        return token, csrf, iso(expires)

    def session_user(self, token: str) -> tuple[dict, str] | None:
        if not token:
            return None
        with self.connect() as db:
            row = db.execute("SELECT u.*,s.csrf_hash,s.expires_at FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?",
                             (sha256(token.encode()).hexdigest(),)).fetchone()
            if not row or row["disabled"] or datetime.fromisoformat(row["expires_at"]) <= utc_now():
                return None
            return self._user_dict(row), row["csrf_hash"]

    def revoke_session(self, token: str) -> None:
        if not token:
            return
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (sha256(token.encode()).hexdigest(),))

    @staticmethod
    def _audit(db: sqlite3.Connection, actor: str | None, action: str,
               resource_type: str, resource_id: str | None) -> None:
        db.execute("INSERT INTO audit_events VALUES(?,?,?,?,?,?)",
                   (uuid.uuid4().hex, actor, action, resource_type, resource_id, iso()))

    def audit(self, actor: str | None, action: str, resource_type: str, resource_id: str | None) -> None:
        with self.connect() as db:
            self._audit(db, actor, action, resource_type, resource_id)

    def create_patient(self, profile: dict, actor: dict) -> dict:
        name = str(profile.get("name", "")).strip()
        if not name or len(name) > 160:
            raise ValueError("Patient name is required and must be 160 characters or fewer.")
        email = str(profile.get("email", "")).strip()
        phone = str(profile.get("phone", "")).strip()
        if len(email) > 254 or len(phone) > 40:
            raise ValueError("Contact details exceed the allowed length.")
        dob = str(profile.get("date_of_birth", "")).strip() or None
        if dob:
            try:
                datetime.strptime(dob, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Date of birth must use YYYY-MM-DD.") from None
        if not profile.get("consent_recorded"):
            raise ValueError("Record the patient's consent before creating their portal-ready record.")
        patient_id = uuid.uuid4().hex
        patient_ref = f"PT-{patient_id[:10].upper()}"
        safe_profile = {"name": name, "email": email, "phone": phone,
                        "date_of_birth": dob,
                        "preferred_contact": profile.get("preferred_contact", "in_person"),
                        "notification_preferences": {"portal_updates": True, "email": False, "sms": False},
                        "consent_recorded": True, "consent_at": iso(),
                        "consent_note": str(profile.get("consent_note", ""))[:500]}
        name_digest = self.digest(name)
        dob_digest = self.digest(dob)
        email_digest = self.digest(email)
        with self.connect() as db:
            if dob_digest:
                duplicate = db.execute("SELECT patient_ref FROM patients WHERE name_digest=? AND dob_digest=? LIMIT 1",
                                       (name_digest, dob_digest)).fetchone()
            elif email_digest:
                duplicate = db.execute("SELECT patient_ref FROM patients WHERE name_digest=? AND email_digest=? LIMIT 1",
                                       (name_digest, email_digest)).fetchone()
            else:
                duplicate = None
            if duplicate:
                raise ValueError(f"A matching record already exists ({duplicate['patient_ref']}). Review it instead of creating a duplicate.")
            db.execute("INSERT INTO patients VALUES(?,?,?,?,?,?,?,?)",
                       (patient_id, patient_ref, self.encrypt(safe_profile), name_digest,
                        dob_digest, email_digest, iso(), actor["id"]))
            self._audit(db, actor["id"], "patient.created", "patient", patient_id)
        return {"id": patient_id, "patient_ref": patient_ref, "profile": safe_profile, "created_at": iso()}

    def update_patient(self, patient_id: str, changes: dict, actor: dict) -> dict | None:
        current = self.get_patient(patient_id, actor=actor, record_access=False)
        if current is None:
            return None
        profile = {**current["profile"], **changes}
        if not profile.get("consent_recorded"):
            raise ValueError("Patient consent must remain recorded for this research demo.")
        name = str(profile.get("name", "")).strip()
        email = str(profile.get("email", "")).strip()
        dob = str(profile.get("date_of_birth", "")).strip() or None
        if not name or len(name) > 160 or len(email) > 254:
            raise ValueError("Patient name or email is invalid.")
        with self.connect() as db:
            db.execute("UPDATE patients SET encrypted_profile=?,name_digest=?,dob_digest=?,email_digest=? WHERE id=?",
                       (self.encrypt(profile), self.digest(name), self.digest(dob), self.digest(email), patient_id))
            self._audit(db, actor["id"], "patient.updated", "patient", patient_id)
        return self.get_patient(patient_id, actor=actor, record_access=False)

    def _patient_row(self, db: sqlite3.Connection, patient_id: str):
        return db.execute("""SELECT p.*, (SELECT COUNT(*) FROM assessments a WHERE a.patient_id=p.id) assessment_count,
            (SELECT MAX(created_at) FROM assessments a WHERE a.patient_id=p.id) latest_assessment,
            (SELECT status FROM reports r WHERE r.patient_id=p.id ORDER BY created_at DESC LIMIT 1) latest_report_status,
            EXISTS(SELECT 1 FROM users u WHERE u.patient_id=p.id AND u.role='patient' AND u.disabled=0) portal_active
            FROM patients p WHERE p.id=?""", (patient_id,)).fetchone()

    def _patient_public(self, row: sqlite3.Row) -> dict:
        return {"id": row["id"], "patient_ref": row["patient_ref"],
                "profile": self.decrypt(row["encrypted_profile"]), "created_at": row["created_at"],
                "assessment_count": row["assessment_count"], "latest_assessment": row["latest_assessment"],
                "latest_report_status": row["latest_report_status"], "portal_active": bool(row["portal_active"])}

    def get_patient(self, patient_id: str, actor: dict, record_access: bool = True) -> dict | None:
        with self.connect() as db:
            row = self._patient_row(db, patient_id)
            if row is None:
                return None
            if record_access:
                self._audit(db, actor["id"], "patient.viewed", "patient", patient_id)
            return self._patient_public(row)

    def list_patients(self, search: str, limit: int, offset: int, actor: dict) -> dict:
        term = search.strip().casefold()
        with self.connect() as db:
            rows = db.execute("""SELECT p.*, (SELECT COUNT(*) FROM assessments a WHERE a.patient_id=p.id) assessment_count,
                (SELECT MAX(created_at) FROM assessments a WHERE a.patient_id=p.id) latest_assessment,
                (SELECT status FROM reports r WHERE r.patient_id=p.id ORDER BY created_at DESC LIMIT 1) latest_report_status,
                EXISTS(SELECT 1 FROM users u WHERE u.patient_id=p.id AND u.role='patient' AND u.disabled=0) portal_active
                FROM patients p ORDER BY p.created_at DESC""").fetchall()
            matching = []
            for row in rows:
                profile = self.decrypt(row["encrypted_profile"])
                if not term or term in row["patient_ref"].casefold() or term in row["id"].casefold() or term in profile.get("name", "").casefold() or term in profile.get("email", "").casefold():
                    matching.append(row)
            selected = matching[offset:offset + limit]
            self._audit(db, actor["id"], "patients.listed", "patient_collection", None)
            return {"items": [self._patient_public(row) for row in selected], "total": len(matching),
                    "limit": limit, "offset": offset}

    def create_assessment(self, patient_id: str, patient: dict, result: dict,
                          metadata: dict, actor: dict) -> dict:
        assessment_id = result["assessment_id"]
        payload = {"patient": patient, "result": result, "metadata": metadata}
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM patients WHERE id=?", (patient_id,)).fetchone():
                raise KeyError("Patient record was not found.")
            db.execute("INSERT INTO assessments VALUES(?,?,?,?,?)",
                       (assessment_id, patient_id, result["assessed_at"], result.get("model_version", "unversioned"), self.encrypt(payload)))
            self._audit(db, actor["id"], "assessment.created", "assessment", assessment_id)
        return {"assessment_id": assessment_id, "patient_id": patient_id,
                "assessed_at": result["assessed_at"], "model_version": result.get("model_version", "unversioned"),
                "result": result}

    def get_assessment(self, assessment_id: str, actor: dict | None = None) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM assessments WHERE id=?", (assessment_id,)).fetchone()
            if not row:
                return None
            if actor:
                self._audit(db, actor["id"], "assessment.viewed", "assessment", assessment_id)
            return {"assessment_id": row["id"], "patient_id": row["patient_id"],
                    "assessed_at": row["created_at"], "model_version": row["model_version"],
                    **self.decrypt(row["encrypted_payload"])}

    def list_assessments(self, patient_id: str, actor: dict | None = None) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT id FROM assessments WHERE patient_id=? ORDER BY created_at DESC", (patient_id,)).fetchall()
            if actor:
                self._audit(db, actor["id"], "assessment_history.viewed", "patient", patient_id)
        return [self.get_assessment(row["id"]) for row in rows]

    def create_report(self, patient_id: str, assessment_id: str, pdf: bytes,
                      creator: dict, review_required: bool) -> dict:
        with self.connect() as db:
            assessment = db.execute("SELECT patient_id FROM assessments WHERE id=?", (assessment_id,)).fetchone()
            if not assessment or assessment["patient_id"] != patient_id:
                raise KeyError("Assessment is not associated with this patient.")
            version = db.execute("SELECT COALESCE(MAX(version),0)+1 FROM reports WHERE assessment_id=?", (assessment_id,)).fetchone()[0]
            report_id = uuid.uuid4().hex
            status = "pending_review" if review_required else "generated"
            db.execute("INSERT INTO reports(id,patient_id,assessment_id,version,status,encrypted_pdf,created_at,created_by) VALUES(?,?,?,?,?,?,?,?)",
                       (report_id, patient_id, assessment_id, version, status, self.encrypt_bytes(pdf), iso(), creator["id"]))
            self._audit(db, creator["id"], "report.generated", "report", report_id)
        return {"report_id": report_id, "patient_id": patient_id, "assessment_id": assessment_id,
                "version": version, "status": status, "created_at": iso()}

    def review_report(self, report_id: str, actor: dict, release: bool = False) -> dict | None:
        if actor["role"] not in REVIEW_ROLES:
            raise PermissionError("Only a clinician or administrator may review or release a report.")
        now = iso()
        with self.connect() as db:
            row = db.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
            if not row:
                return None
            if release:
                if row["status"] != "reviewed" and row["status"] != "generated":
                    raise ValueError("A report must be reviewed before release.")
                db.execute("UPDATE reports SET status='released',released_by=?,released_at=? WHERE id=?",
                           (actor["id"], now, report_id))
                action = "report.released"
            else:
                if row["status"] not in {"pending_review", "generated"}:
                    raise ValueError("Only a generated report can be reviewed.")
                db.execute("UPDATE reports SET status='reviewed',reviewed_by=?,reviewed_at=? WHERE id=?",
                           (actor["id"], now, report_id))
                action = "report.reviewed"
            self._audit(db, actor["id"], action, "report", report_id)
            updated = db.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
            return self._report_summary(updated)

    @staticmethod
    def _report_summary(row: sqlite3.Row) -> dict:
        return {"report_id": row["id"], "patient_id": row["patient_id"],
                "assessment_id": row["assessment_id"], "version": row["version"],
                "status": row["status"], "created_at": row["created_at"],
                "reviewed_at": row["reviewed_at"], "released_at": row["released_at"]}

    def list_reports(self, patient_id: str, released_only: bool = False, actor: dict | None = None) -> list[dict]:
        query = "SELECT * FROM reports WHERE patient_id=?"
        if released_only:
            query += " AND status='released'"
        query += " ORDER BY created_at DESC"
        with self.connect() as db:
            rows = db.execute(query, (patient_id,)).fetchall()
            if actor:
                self._audit(db, actor["id"], "report_history.viewed", "patient", patient_id)
            return [self._report_summary(row) for row in rows]

    def list_review_queue(self, status: str | None = None) -> list[dict]:
        with self.connect() as db:
            if status in {"generated", "pending_review", "reviewed", "released"}:
                rows = db.execute("SELECT * FROM reports WHERE status=? ORDER BY created_at", (status,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM reports WHERE status IN ('generated','pending_review','reviewed') ORDER BY created_at").fetchall()
            return [self._report_summary(row) for row in rows]

    def get_report_pdf(self, report_id: str, actor: dict, patient_id: str | None = None,
                       released_only: bool = False) -> bytes | None:
        query, params = "SELECT * FROM reports WHERE id=?", [report_id]
        if patient_id:
            query += " AND patient_id=?"
            params.append(patient_id)
        if released_only:
            query += " AND status='released'"
        with self.connect() as db:
            row = db.execute(query, params).fetchone()
            if not row:
                self._audit(db, actor["id"], "report.access_denied_or_missing", "report", report_id)
                return None
            self._audit(db, actor["id"], "report.downloaded", "report", report_id)
            return self.decrypt_bytes(row["encrypted_pdf"])

    def create_invite(self, patient_id: str, actor: dict) -> tuple[str, dict]:
        token = secrets.token_urlsafe(32)
        token_hash = sha256(token.encode()).hexdigest()
        expires = iso(utc_now() + timedelta(hours=INVITE_HOURS))
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM patients WHERE id=?", (patient_id,)).fetchone():
                raise KeyError("Patient record was not found.")
            if db.execute("SELECT 1 FROM users WHERE patient_id=? AND role='patient' AND disabled=0", (patient_id,)).fetchone():
                raise ValueError("This patient already has an active portal account. Revoke that account before issuing another invitation.")
            db.execute("UPDATE portal_invites SET used_at=? WHERE patient_id=? AND used_at IS NULL", (iso(), patient_id))
            db.execute("INSERT INTO portal_invites(token_hash,patient_id,created_by,created_at,expires_at) VALUES(?,?,?,?,?)",
                       (token_hash, patient_id, actor["id"], iso(), expires))
            self._audit(db, actor["id"], "portal_invite.created", "patient", patient_id)
        return token, {"patient_id": patient_id, "expires_at": expires, "delivery": "manual_after_identity_check"}

    def revoke_portal_access(self, patient_id: str, actor: dict) -> bool:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM patients WHERE id=?", (patient_id,)).fetchone():
                return False
            accounts = db.execute("SELECT id FROM users WHERE patient_id=? AND role='patient' AND disabled=0", (patient_id,)).fetchall()
            for account in accounts:
                db.execute("UPDATE users SET disabled=1 WHERE id=?", (account["id"],))
                db.execute("DELETE FROM sessions WHERE user_id=?", (account["id"],))
            db.execute("UPDATE portal_invites SET used_at=? WHERE patient_id=? AND used_at IS NULL", (iso(), patient_id))
            self._audit(db, actor["id"], "portal.access_revoked", "patient", patient_id)
            return True

    def activate_invite(self, token: str, username: str, password: str) -> dict:
        token_hash = sha256(token.encode()).hexdigest()
        # Serialize validation, account creation, and token consumption.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            invite = db.execute("SELECT * FROM portal_invites WHERE token_hash=? AND used_at IS NULL", (token_hash,)).fetchone()
            if not invite or datetime.fromisoformat(invite["expires_at"]) <= utc_now():
                raise ValueError("This activation code is invalid, expired, or already used.")
            normalized = username.casefold().strip()
            if not normalized or len(normalized) > 120 or "@" in normalized:
                raise ValueError("Choose a local username with no contact details.")
            salt = secrets.token_bytes(16)
            hashed = self._password_hash(password, salt)
            user_id = uuid.uuid4().hex
            db.execute("INSERT INTO users(id,username,role,password_salt,password_hash,patient_id,created_at) VALUES(?,?,?,?,?,?,?)",
                       (user_id, normalized, "patient", salt, hashed, invite["patient_id"], iso()))
            db.execute("UPDATE portal_invites SET used_at=? WHERE token_hash=?", (iso(), token_hash))
            self._audit(db, user_id, "portal.activated", "patient", invite["patient_id"])
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return self._user_dict(row)

    def patient_portal_summary(self, patient_id: str, actor: dict) -> dict | None:
        patient = self.get_patient(patient_id, actor, record_access=True)
        if not patient:
            return None
        reports = self.list_reports(patient_id, released_only=True, actor=actor)
        released_ids = {item["assessment_id"] for item in reports}
        assessments = [item for item in self.list_assessments(patient_id, actor)
                       if item["assessment_id"] in released_ids]
        # Only source-recorded measurements are returned; no interpolation is performed.
        measurements = []
        for item in reversed(assessments):
            values = item["patient"]
            measurements.append({"assessment_id": item["assessment_id"], "date": item["assessed_at"],
                                  **{name: values.get(name) for name in
                                     ("totChol", "sysBP", "diaBP", "BMI", "heartRate", "glucose")}})
        released_by_assessment = {item["assessment_id"]: item for item in reports}
        history = [{"assessment_id": item["assessment_id"], "assessed_at": item["assessed_at"],
                    "model_version": item["model_version"], "risk_category": item["result"]["risk_category"],
                    "probability": item["result"]["probability"],
                    "released_report": released_by_assessment.get(item["assessment_id"])}
                   for item in assessments]
        return {"patient": {"id": patient["id"], "patient_ref": patient["patient_ref"],
                            "name": patient["profile"]["name"]},
                "assessments": history, "reports": reports, "measurements": measurements}

    def report_detail(self, report_id: str, patient_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM reports WHERE id=? AND patient_id=?", (report_id, patient_id)).fetchone()
            return self._report_summary(row) if row else None


def configured_store() -> PatientStore:
    key = os.getenv("XAI_CVD_ENCRYPTION_KEY", "").strip()
    if not key:
        raise RuntimeError("Patient management is disabled. Configure XAI_CVD_ENCRYPTION_KEY before enabling the local demo store.")
    path = os.getenv("XAI_CVD_PATIENT_DB", str(Path(__file__).resolve().parents[1] / "data" / "patient-demo.sqlite3"))
    try:
        return PatientStore(path, key)
    except (ValueError, InvalidToken) as exc:
        raise RuntimeError("Patient management encryption configuration is invalid.") from exc
