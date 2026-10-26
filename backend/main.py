"""Optional HTTP API exposing the same saved hybrid inference artifacts."""
from __future__ import annotations

from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import os
import json
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path

import joblib
import numpy as np
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from src.predict import load_artifacts, predict
from src.report_extraction import MAX_REPORT_BYTES, ReportExtractionError, extract_report, validate_upload
from src.report import build_report
from src.risk_network import get_risk_network
from backend.patient_auth import current_user, patient_user, require_roles, staff_user, store as patient_store, verify_mutation
from backend.patient_store import REVIEW_ROLES, STAFF_ROLES, PatientStore

app = FastAPI(title="XAI-CVD Hybrid AI API", version="2.0.0",
              description="Academic/research prototype only; not a medical diagnosis system.")
ROOT = Path(__file__).resolve().parents[1]
allowed_origins = [origin.strip() for origin in os.getenv(
    "XAI_CVD_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8081,http://127.0.0.1:8081"
).split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins,
                   allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
                   allow_headers=["Content-Type", "X-CSRF-Token", "Authorization"])

# Uploads are parsed in a small in-process pool. Files are never written to disk;
# only extracted candidates/snippets stay in memory for a short review window.
report_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="report-extract")
report_jobs: dict[str, dict] = {}
report_jobs_lock = threading.Lock()
REPORT_JOB_TTL_SECONDS = 30 * 60

# Keep only the data needed to render a just-created assessment report. This
# short-lived process cache avoids re-running inference for an existing result.
assessment_records: dict[str, dict] = {}
assessment_records_lock = threading.Lock()
ASSESSMENT_RECORD_TTL_SECONDS = 60 * 60


def _prune_report_jobs() -> None:
    now = time.monotonic()
    expired = [key for key, value in report_jobs.items()
               if now - value.get("created_monotonic", now) > REPORT_JOB_TTL_SECONDS]
    for key in expired:
        report_jobs.pop(key, None)


def _expire_report_job(job_id: str) -> None:
    with report_jobs_lock:
        report_jobs.pop(job_id, None)


def _run_report_extraction(job_id: str, kind: str, content: bytes) -> None:
    def progress(percent: int, stage: str) -> None:
        with report_jobs_lock:
            job = report_jobs.get(job_id)
            if job:
                job.update(progress=max(0, min(99, percent)), stage=stage)
    try:
        result = extract_report(kind, content, progress)
        with report_jobs_lock:
            if job_id in report_jobs:
                report_jobs[job_id].update(status="completed", progress=100,
                                           stage="Ready for review", result=result)
    except ReportExtractionError as exc:
        with report_jobs_lock:
            if job_id in report_jobs:
                report_jobs[job_id].update(status="failed", progress=100,
                                           stage="Extraction failed", error=str(exc))
    except Exception:
        with report_jobs_lock:
            if job_id in report_jobs:
                report_jobs[job_id].update(status="failed", progress=100,
                                           stage="Extraction failed",
                                           error="The report could not be analyzed. Check the file and try again.")


def _public_report_job(job_id: str, job: dict) -> dict:
    return {"analysis_id": job_id, "status": job["status"], "progress": job["progress"],
            "stage": job["stage"], "result": job.get("result"), "error": job.get("error")}


def _prune_assessment_records(now: float | None = None) -> None:
    current = time.monotonic() if now is None else now
    expired = [key for key, value in assessment_records.items()
               if current - value["created_monotonic"] > ASSESSMENT_RECORD_TTL_SECONDS]
    for key in expired:
        assessment_records.pop(key, None)


def _expire_assessment_record(assessment_id: str) -> None:
    with assessment_records_lock:
        record = assessment_records.get(assessment_id)
        if record and time.monotonic() - record["created_monotonic"] >= ASSESSMENT_RECORD_TTL_SECONDS:
            assessment_records.pop(assessment_id, None)


class PatientInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    gender: float = Field(ge=0, le=1)
    age: float = Field(ge=18, le=120)
    education: float = Field(ge=1, le=4)
    currentSmoker: float = Field(ge=0, le=1)
    cigsPerDay: float = Field(ge=0, le=100)
    BPMeds: float = Field(ge=0, le=1)
    prevalentStroke: float = Field(ge=0, le=1)
    prevalentHyp: float = Field(ge=0, le=1)
    diabetes: float = Field(ge=0, le=1)
    totChol: float = Field(ge=50, le=700)
    sysBP: float = Field(ge=50, le=300)
    diaBP: float = Field(ge=30, le=200)
    BMI: float = Field(ge=10, le=100)
    heartRate: float = Field(ge=25, le=250)
    glucose: float = Field(ge=20, le=1000)


class AssessmentReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment_id: str = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$")


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class PortalActivationRequest(LoginRequest):
    token: str = Field(min_length=32, max_length=128)


class NotificationPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    portal_updates: bool = True
    email: bool = False
    sms: bool = False


class PortalPreferencesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferred_contact: str = Field(pattern=r"^(in_person|phone|email|portal)$")
    notification_preferences: NotificationPreferences


class PatientProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    date_of_birth: str | None = Field(default=None, max_length=10)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    preferred_contact: str = Field(default="in_person", pattern=r"^(in_person|phone|email|portal)$")
    consent_recorded: bool
    consent_note: str = Field(default="", max_length=500)


class PatientProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=160)
    date_of_birth: str | None = Field(default=None, max_length=10)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    preferred_contact: str | None = Field(default=None, pattern=r"^(in_person|phone|email|portal)$")
    consent_recorded: bool | None = None
    consent_note: str | None = Field(default=None, max_length=500)


def _patient_store() -> PatientStore:
    try:
        return patient_store()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


def _check_login_origin(request: Request) -> None:
    if request.headers.get("origin") not in set(allowed_origins):
        raise HTTPException(status_code=403, detail="Request origin is not allowed.")


def _set_auth_cookies(response: Response, request: Request, user_id: str) -> dict:
    token, csrf, expires = _patient_store().create_session(user_id)
    max_age = 60 * 60 * 8
    secure = request.url.scheme == "https"
    response.set_cookie("xai_session", token, max_age=max_age, httponly=True,
                        secure=secure, samesite="strict", path="/")
    response.set_cookie("xai_csrf", csrf, max_age=max_age, httponly=False,
                        secure=secure, samesite="strict", path="/")
    return {"expires_at": expires}


def _ensure_session_csrf(request: Request, user: dict) -> None:
    verify_mutation(request, user)


def _create_prediction(values: dict) -> tuple[dict, dict]:
    model, metadata = artifacts()
    result = predict(values, model, metadata)
    assessment_id = uuid4().hex
    assessed_at = datetime.now(timezone.utc).isoformat()
    result.update(assessment_id=assessment_id, assessed_at=assessed_at,
                  model_version=metadata.get("model_version", "unversioned"))
    with assessment_records_lock:
        _prune_assessment_records()
        assessment_records[assessment_id] = {
            "patient": values, "result": deepcopy(result), "metadata": deepcopy(metadata),
            "created_monotonic": time.monotonic(),
        }
    expiry = threading.Timer(ASSESSMENT_RECORD_TTL_SECONDS, _expire_assessment_record,
                            args=(assessment_id,))
    expiry.daemon = True
    expiry.start()
    return result, metadata


@lru_cache(maxsize=1)
def artifacts():
    return load_artifacts()


@app.get("/health")
def health():
    try:
        artifacts()
        return {"status": "ok", "model_ready": True}
    except FileNotFoundError:
        return {"status": "ok", "model_ready": False}


@app.get("/api/auth/status")
def patient_auth_status(request: Request):
    """Return the role for this browser session without disclosing account data."""
    token = request.cookies.get("xai_session", "")
    if not token:
        return {"authenticated": False, "user": None}
    try:
        session = _patient_store().session_user(token)
    except HTTPException:
        return {"authenticated": False, "user": None}
    return {"authenticated": bool(session), "user": session[0] if session else None}


@app.post("/api/auth/login")
def patient_auth_login(payload: LoginRequest, request: Request, response: Response):
    _check_login_origin(request)
    store = _patient_store()
    user = store.authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="The username or password is incorrect, or the account is temporarily locked.")
    expiry = _set_auth_cookies(response, request, user["id"])
    return {"user": user, **expiry}


@app.post("/api/auth/logout")
def patient_auth_logout(request: Request, response: Response,
                        user: dict = Depends(current_user)):
    _ensure_session_csrf(request, user)
    _patient_store().revoke_session(request.cookies.get("xai_session", ""))
    response.delete_cookie("xai_session", path="/", samesite="strict")
    response.delete_cookie("xai_csrf", path="/", samesite="strict")
    _patient_store().audit(user["id"], "auth.logout", "user", user["id"])
    return {"ok": True}


@app.post("/api/portal/activate")
def portal_activate(payload: PortalActivationRequest, request: Request, response: Response):
    """Redeem a staff-issued single-use code; no email/SMS is sent by this demo."""
    _check_login_origin(request)
    try:
        user = _patient_store().activate_invite(payload.token, payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=409, detail="The account could not be activated. Contact the staff member who issued the code.") from None
    expiry = _set_auth_cookies(response, request, user["id"])
    return {"user": user, **expiry}


def _mobile_session_result(user: dict) -> dict:
    access_token, _csrf, expires_at = _patient_store().create_session(user["id"])
    return {"user": user, "access_token": access_token, "token_type": "bearer", "expires_at": expires_at}


@app.post("/api/mobile/auth/login")
def mobile_login(payload: LoginRequest):
    """Issue a short-lived bearer token for the Expo app; never logs credentials."""
    user = _patient_store().authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="The username or password is incorrect, or the account is temporarily locked.")
    if user["role"] != "patient":
        raise HTTPException(status_code=403, detail="The mobile app is limited to patient accounts.")
    return _mobile_session_result(user)


@app.post("/api/mobile/auth/activate")
def mobile_activate(payload: PortalActivationRequest):
    try:
        user = _patient_store().activate_invite(payload.token, payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=409, detail="The account could not be activated. Contact the staff member who issued the code.") from None
    return _mobile_session_result(user)


@app.post("/api/mobile/auth/logout")
def mobile_logout(request: Request, user: dict = Depends(patient_user)):
    authorization = request.headers.get("authorization", "")
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    if not token:
        raise HTTPException(status_code=401, detail="A mobile bearer session is required.")
    _patient_store().revoke_session(token)
    _patient_store().audit(user["id"], "auth.logout", "user", user["id"])
    return {"ok": True}


@app.get("/dataset-audit")
def dataset_audit():
    audit_path = ROOT / "reports" / "dataset_report.json"
    if not audit_path.is_file():
        return {"available": False}
    try:
        report = json.loads(audit_path.read_text(encoding="utf-8"))
        return {"available": True, "rows_before_cleaning": report.get("rows_before_cleaning"),
                "rows_after_cleaning": report.get("rows_after_cleaning"), "columns": report.get("columns"),
                "duplicate_rows_removed": report.get("duplicate_rows_removed"),
                "class_distribution": report.get("class_distribution", {})}
    except (OSError, ValueError):
        raise HTTPException(status_code=503, detail="Dataset audit is temporarily unavailable.") from None


@app.get("/risk-factor-network")
def risk_factor_network():
    """Return cached dataset-level associations between the model predictors."""
    try:
        return get_risk_network()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="The source dataset is unavailable. No sample network is substituted.") from None
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=f"The source dataset cannot be used for the network: {exc}") from None
    except Exception:
        raise HTTPException(status_code=500, detail="Risk-factor associations are temporarily unavailable.") from None


@app.post("/predict")
def predict_endpoint(patient: PatientInput):
    try:
        values = patient.model_dump()
        result, _ = _create_prediction(values)
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Trained model artifacts are unavailable. Add the dataset and run the documented training pipeline.") from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="The assessment could not be completed. Check model readiness and try again.") from None


@app.get("/api/patients")
def list_patients(search: str = Query(default="", max_length=160),
                  limit: int = Query(default=25, ge=1, le=100),
                  offset: int = Query(default=0, ge=0),
                  user: dict = Depends(staff_user)):
    try:
        return _patient_store().list_patients(search, limit, offset, user)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="The encrypted patient store is unavailable.") from None


@app.post("/api/patients", status_code=201)
def create_patient(payload: PatientProfileInput, request: Request,
                   user: dict = Depends(staff_user)):
    _ensure_session_csrf(request, user)
    try:
        return _patient_store().create_patient(payload.model_dump(), user)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="The patient record could not be saved.") from None


@app.get("/api/patients/{patient_id}")
def get_patient(patient_id: str, user: dict = Depends(staff_user)):
    try:
        item = _patient_store().get_patient(patient_id, user)
    except Exception:
        raise HTTPException(status_code=503, detail="The patient record could not be loaded.") from None
    if not item:
        raise HTTPException(status_code=404, detail="Patient record not found.")
    return item


@app.patch("/api/patients/{patient_id}")
def update_patient(patient_id: str, payload: PatientProfilePatch, request: Request,
                   user: dict = Depends(staff_user)):
    _ensure_session_csrf(request, user)
    try:
        item = _patient_store().update_patient(patient_id, payload.model_dump(exclude_unset=True), user)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=503, detail="The patient record could not be updated.") from None
    if not item:
        raise HTTPException(status_code=404, detail="Patient record not found.")
    return item


@app.get("/api/patients/{patient_id}/assessments")
def patient_assessment_history(patient_id: str, user: dict = Depends(staff_user)):
    store = _patient_store()
    if not store.get_patient(patient_id, user):
        raise HTTPException(status_code=404, detail="Patient record not found.")
    try:
        return {"items": store.list_assessments(patient_id, user)}
    except Exception:
        raise HTTPException(status_code=503, detail="Assessment history is unavailable.") from None


@app.post("/api/patients/{patient_id}/assessments")
def create_patient_assessment(patient_id: str, patient: PatientInput, request: Request,
                              user: dict = Depends(staff_user)):
    _ensure_session_csrf(request, user)
    db = _patient_store()
    if not db.get_patient(patient_id, user):
        raise HTTPException(status_code=404, detail="Patient record not found.")
    try:
        values = patient.model_dump()
        result, metadata = _create_prediction(values)
        saved = db.create_assessment(patient_id, values, result, metadata, user)
        return saved
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Trained model artifacts are unavailable.") from None
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'") ) from None
    except Exception:
        raise HTTPException(status_code=503, detail="The assessment could not be saved to the encrypted patient store.") from None


@app.get("/api/patients/{patient_id}/reports")
def patient_report_history(patient_id: str, user: dict = Depends(staff_user)):
    db = _patient_store()
    if not db.get_patient(patient_id, user):
        raise HTTPException(status_code=404, detail="Patient record not found.")
    return {"items": db.list_reports(patient_id, actor=user)}


@app.post("/api/patients/{patient_id}/portal-invite")
def invite_patient_portal(patient_id: str, request: Request,
                          user: dict = Depends(require_roles("medical_assistant", "clinician", "administrator"))):
    _ensure_session_csrf(request, user)
    try:
        token, details = _patient_store().create_invite(patient_id, user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Patient record not found.") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {**details, "activation_code": token,
            "notice": "Show this code only once, after verifying the patient in person. The app does not email or text it."}


@app.post("/api/patients/{patient_id}/portal-revoke")
def revoke_patient_portal(patient_id: str, request: Request,
                          user: dict = Depends(require_roles("clinician", "administrator"))):
    _ensure_session_csrf(request, user)
    if not _patient_store().revoke_portal_access(patient_id, user):
        raise HTTPException(status_code=404, detail="Patient record not found.")
    return {"patient_id": patient_id, "portal_active": False,
            "message": "Portal sessions and unused activation codes were revoked."}


@app.post("/api/assessments/{assessment_id}/report", status_code=201)
def create_persisted_report(assessment_id: str, request: Request,
                           user: dict = Depends(staff_user)):
    _ensure_session_csrf(request, user)
    db = _patient_store()
    record = db.get_assessment(assessment_id, user)
    if not record:
        raise HTTPException(status_code=404, detail="Assessment record not found.")
    try:
        pdf = build_report(record["patient"], record["result"], record["metadata"],
                           assessment_id=assessment_id, assessed_at=record["assessed_at"])
        return db.create_report(record["patient_id"], assessment_id, pdf, user,
                                review_required=os.getenv("XAI_CVD_REPORT_REVIEW_REQUIRED", "true").lower() not in {"0", "false", "no"})
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=500, detail="The report could not be generated and saved with its required patient graph.") from None


@app.get("/api/reports/review-queue")
def report_review_queue(status: str | None = Query(default=None),
                        user: dict = Depends(require_roles("clinician", "administrator"))):
    return {"items": _patient_store().list_review_queue(status)}


@app.post("/api/reports/{report_id}/review")
def review_patient_report(report_id: str, request: Request,
                         user: dict = Depends(require_roles("clinician", "administrator"))):
    _ensure_session_csrf(request, user)
    try:
        report = _patient_store().review_report(report_id, user, release=False)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


@app.post("/api/reports/{report_id}/release")
def release_patient_report(report_id: str, request: Request,
                           user: dict = Depends(require_roles("clinician", "administrator"))):
    _ensure_session_csrf(request, user)
    try:
        report = _patient_store().review_report(report_id, user, release=True)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


@app.get("/api/patients/{patient_id}/reports/{report_id}/pdf")
def download_staff_report(patient_id: str, report_id: str,
                          user: dict = Depends(staff_user)):
    pdf = _patient_store().get_report_pdf(report_id, user, patient_id=patient_id)
    if pdf is None:
        raise HTTPException(status_code=404, detail="Report not found for this patient.")
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename=xai-cvd-report-{report_id[:8]}.pdf",
                             "Cache-Control": "private, no-store"})


@app.get("/api/portal/me")
def patient_portal_home(user: dict = Depends(patient_user)):
    result = _patient_store().patient_portal_summary(user["patient_id"], user)
    if not result:
        raise HTTPException(status_code=404, detail="The linked patient record is no longer available.")
    return result


def _portal_profile_payload(record: dict) -> dict:
    profile = record["profile"]
    return {"patient_ref": record["patient_ref"], "name": profile.get("name", ""),
            "email": profile.get("email", ""), "phone": profile.get("phone", ""),
            "preferred_contact": profile.get("preferred_contact", "in_person"),
            "notification_preferences": profile.get("notification_preferences",
                {"portal_updates": True, "email": False, "sms": False})}


@app.get("/api/portal/profile")
def patient_portal_profile(user: dict = Depends(patient_user)):
    record = _patient_store().get_patient(user["patient_id"], user)
    if not record:
        raise HTTPException(status_code=404, detail="Linked patient profile not found.")
    return _portal_profile_payload(record)


@app.patch("/api/portal/preferences")
def update_patient_portal_preferences(payload: PortalPreferencesInput,
                                      request: Request,
                                      user: dict = Depends(patient_user)):
    verify_mutation(request, user)
    store = _patient_store()
    changes = payload.model_dump()
    record = store.update_patient(user["patient_id"], changes, user)
    if not record:
        raise HTTPException(status_code=404, detail="Linked patient profile not found.")
    store.audit(user["id"], "portal.preferences.updated", "patient", user["patient_id"])
    return _portal_profile_payload(record)


@app.get("/api/portal/assessments/{assessment_id}")
def patient_portal_assessment(assessment_id: str, user: dict = Depends(patient_user)):
    db = _patient_store()
    record = db.get_assessment(assessment_id, user)
    if not record or record["patient_id"] != user["patient_id"]:
        raise HTTPException(status_code=404, detail="Released assessment not found.")
    if not any(item["assessment_id"] == assessment_id for item in db.list_reports(user["patient_id"], released_only=True)):
        raise HTTPException(status_code=404, detail="Released assessment not found.")
    result = record["result"]
    return {"assessment_id": assessment_id, "assessed_at": record["assessed_at"],
            "model_version": record["model_version"], "patient": record["patient"],
            "probability": result["probability"], "risk_category": result["risk_category"],
            "binary_label": result["binary_label"], "shap_values": result["shap_values"],
            "shap_base_value": result["shap_base_value"], "decision_support": result["decision_support"],
            "disclaimer": result["disclaimer"]}


@app.get("/api/portal/reports/{report_id}")
def patient_portal_report_detail(report_id: str, user: dict = Depends(patient_user)):
    report = _patient_store().report_detail(report_id, user["patient_id"])
    if not report or report["status"] != "released":
        raise HTTPException(status_code=404, detail="Released report not found.")
    return report


@app.get("/api/portal/reports/{report_id}/pdf")
def patient_portal_report_pdf(report_id: str, user: dict = Depends(patient_user)):
    pdf = _patient_store().get_report_pdf(report_id, user, patient_id=user["patient_id"], released_only=True)
    if pdf is None:
        raise HTTPException(status_code=404, detail="Released report not found.")
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename=xai-cvd-report-{report_id[:8]}.pdf",
                             "Cache-Control": "private, no-store"})


@app.post("/api/reports/upload", status_code=202)
async def upload_report(file: UploadFile = File(...)):
    """Accept a bounded upload and extract it asynchronously without disk storage."""
    try:
        content = await file.read(MAX_REPORT_BYTES + 1)
        kind = validate_upload(file.filename, content)
    except ReportExtractionError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from None
    finally:
        await file.close()
    job_id = uuid4().hex
    with report_jobs_lock:
        _prune_report_jobs()
        if len(report_jobs) >= 100:
            raise HTTPException(status_code=429, detail="Too many report analyses are active. Try again shortly.")
        report_jobs[job_id] = {"status": "processing", "progress": 5,
                               "stage": "Queued for local extraction",
                               "created_monotonic": time.monotonic()}
    try:
        report_executor.submit(_run_report_extraction, job_id, kind, content)
    except RuntimeError:
        with report_jobs_lock:
            report_jobs.pop(job_id, None)
        raise HTTPException(status_code=503, detail="Report extraction is temporarily unavailable.") from None
    expiry = threading.Timer(REPORT_JOB_TTL_SECONDS, _expire_report_job, args=(job_id,))
    expiry.daemon = True
    expiry.start()
    return {"analysis_id": job_id, "status": "processing", "progress": 5,
            "stage": "Queued for local extraction"}


@app.get("/api/reports/{analysis_id}")
def get_report_extraction(analysis_id: str):
    with report_jobs_lock:
        _prune_report_jobs()
        job = report_jobs.get(analysis_id)
        if not job:
            raise HTTPException(status_code=404, detail="This report analysis expired or was not found. Upload the file again.")
        return _public_report_job(analysis_id, job)


@app.post("/generate-report")
def generate_report(patient: PatientInput):
    try:
        model, metadata = artifacts()
        values = patient.model_dump()
        result = predict(values, model, metadata)
        data = build_report(values, result, metadata)
        return Response(content=data, media_type="application/pdf",
                        headers={"Content-Disposition": "attachment; filename=xai-cvd-assessment.pdf"})
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Trained model artifacts are unavailable. Add the dataset and run the documented training pipeline.") from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="The report could not be generated. Check model readiness and try again.") from None


@app.post("/generate-assessment-report")
def generate_assessment_report(request: AssessmentReportRequest):
    """Render the exact prediction and explanation previously returned by /predict."""
    with assessment_records_lock:
        _prune_assessment_records()
        record = assessment_records.get(request.assessment_id)
        if record:
            record = deepcopy(record)
    if record is None:
        raise HTTPException(status_code=410, detail="This assessment has expired from temporary report storage. Run the assessment again to generate its matching report.")
    try:
        if not record["result"].get("shap_values"):
            raise ValueError("This assessment has no patient-specific explanation values.")
        data = build_report(record["patient"], record["result"], record["metadata"],
                            assessment_id=request.assessment_id,
                            assessed_at=record["result"].get("assessed_at"))
        return Response(content=data, media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename=xai-cvd-{request.assessment_id[:8]}.pdf"})
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="The assessment report, including its personalized graph, could not be generated. Please retry.") from None


@app.get("/model-performance")
def model_performance():
    try:
        _, metadata = artifacts()
        return {"selected_model": metadata["selected_model"], "selected_tree_model": metadata.get("tree_component"),
                "best_model_by_composite": metadata["best_model_by_composite"],
                "comparison": metadata["comparison"], "metrics": metadata["metrics"]}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Trained model performance is unavailable. Run the documented training pipeline.") from exc
    except Exception:
        raise HTTPException(status_code=500, detail="Model performance is temporarily unavailable.") from None


@app.get("/xai/global")
def global_xai():
    try:
        _, metadata = artifacts()
        distribution = []
        shap_path = ROOT / "models" / "shap_config.joblib"
        if shap_path.is_file():
            saved = joblib.load(shap_path)
            values = np.asarray(saved.get("values", []), dtype=float)
            names = saved.get("feature_names", [])
            if values.ndim == 2 and len(names) == values.shape[1] and values.shape[0]:
                quantiles = np.quantile(values, [.05, .25, .5, .75, .95], axis=0)
                distribution = [{"feature": name, "q05": float(quantiles[0, i]),
                                 "q25": float(quantiles[1, i]), "median": float(quantiles[2, i]),
                                 "q75": float(quantiles[3, i]), "q95": float(quantiles[4, i])}
                                for i, name in enumerate(names)]
        return {"method": metadata.get("xai_method"), "feature_importance": metadata.get("global_shap", []),
                "feature_distributions": distribution, "causation_note": metadata.get("xai_note")}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Global SHAP artifacts are unavailable. Run the documented training pipeline.") from exc
    except Exception:
        raise HTTPException(status_code=500, detail="Global SHAP information is temporarily unavailable.") from None
