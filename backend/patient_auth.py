"""Cookie-session authentication and request access checks for patient routes."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import hmac
import os

from fastapi import Depends, HTTPException, Request

from backend.patient_store import PatientStore, configured_store


@lru_cache(maxsize=1)
def store() -> PatientStore:
    return configured_store()


def current_user(request: Request) -> dict:
    authorization = request.headers.get("authorization", "")
    bearer = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    token = bearer or request.cookies.get("xai_session", "")
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to access patient records.")
    try:
        session = store().session_user(token)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    if session is None:
        raise HTTPException(status_code=401, detail="Your session has expired. Sign in again.")
    user, csrf_hash = session
    request.state.csrf_hash = csrf_hash
    request.state.auth_scheme = "bearer" if bearer else "cookie"
    return user


def staff_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] not in {"medical_assistant", "clinician", "administrator"}:
        raise HTTPException(status_code=403, detail="Staff access is required.")
    return user


def patient_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "patient" or not user.get("patient_id"):
        raise HTTPException(status_code=403, detail="Patient portal access is required.")
    return user


def require_roles(*roles: str):
    def check(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Your account role does not permit this action.")
        return user
    return check


def verify_mutation(request: Request, user: dict) -> None:
    # Native Expo calls use a high-entropy bearer session stored by the OS.
    # Unlike ambient cookies, bearer authorization is not a browser CSRF vector.
    if getattr(request.state, "auth_scheme", "cookie") == "bearer":
        return
    origin = request.headers.get("origin")
    allowed = {item.strip() for item in os.getenv(
        "XAI_CVD_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",") if item.strip()}
    if origin not in allowed:
        raise HTTPException(status_code=403, detail="Request origin is not allowed.")
    cookie_token = request.cookies.get("xai_csrf", "")
    header_token = request.headers.get("x-csrf-token", "")
    expected_hash = getattr(request.state, "csrf_hash", "")
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="A valid request-verification token is required.")
    if not hmac.compare_digest(hashlib.sha256(cookie_token.encode()).hexdigest(), expected_hash):
        raise HTTPException(status_code=403, detail="The request-verification token has expired.")
