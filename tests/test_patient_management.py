from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from cryptography.fernet import Fernet
from starlette.requests import Request

import backend.patient_auth as auth
from backend.main import (LoginRequest, PortalPreferencesInput, app, mobile_login,
                          update_patient_portal_preferences)
from backend.patient_store import PatientStore
from backend.patient_auth import current_user, verify_mutation


class PatientStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "data")
        self.key = Fernet.generate_key()
        self.store = PatientStore(Path(self.temp.name) / "patients.sqlite3", self.key)
        self.staff = self.store.create_user("clinician-a", "a-strong-demo-password", "clinician")
        self.profile = {"name": "Synthetic Person Alpha", "date_of_birth": "1970-01-01",
                        "email": "alpha@example.invalid", "phone": "555-0100",
                        "preferred_contact": "in_person", "consent_recorded": True,
                        "consent_note": "Synthetic test fixture"}

    def tearDown(self):
        self.temp.cleanup()

    def create_patient(self, profile=None):
        return self.store.create_patient(profile or self.profile, self.staff)

    def test_patient_pii_is_encrypted_and_duplicate_check_is_stable(self):
        patient = self.create_patient()
        raw = Path(self.temp.name, "patients.sqlite3").read_bytes()
        self.assertNotIn(b"Synthetic Person Alpha", raw)
        self.assertNotIn(b"alpha@example.invalid", raw)
        self.assertEqual(self.store.get_patient(patient["id"], self.staff)["profile"]["name"], "Synthetic Person Alpha")
        with self.assertRaisesRegex(ValueError, "matching record already exists"):
            self.create_patient()

    def test_patient_search_supports_partial_name_and_pagination(self):
        first = self.create_patient()
        second = self.create_patient({**self.profile, "name": "Synthetic Person Beta",
                                      "date_of_birth": "1972-02-02", "email": "beta@example.invalid"})
        page_one = self.store.list_patients("synthetic person", 1, 0, self.staff)
        page_two = self.store.list_patients("synthetic person", 1, 1, self.staff)
        self.assertEqual(page_one["total"], 2)
        self.assertEqual(len(page_one["items"]), 1)
        self.assertEqual(len(page_two["items"]), 1)
        self.assertNotEqual(page_one["items"][0]["id"], page_two["items"][0]["id"])
        self.assertEqual({page_one["items"][0]["id"], page_two["items"][0]["id"]},
                         {first["id"], second["id"]})

    def test_portal_invite_is_single_use_and_access_can_be_revoked(self):
        patient = self.create_patient()
        token, _ = self.store.create_invite(patient["id"], self.staff)
        portal = self.store.activate_invite(token, "portal-alpha", "a-different-strong-password")
        self.assertEqual(portal["patient_id"], patient["id"])
        with self.assertRaisesRegex(ValueError, "invalid, expired, or already used"):
            self.store.activate_invite(token, "portal-second", "another-strong-password")
        self.assertTrue(self.store.revoke_portal_access(patient["id"], self.staff))
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT disabled FROM users WHERE id=?", (portal["id"],)).fetchone()[0], 1)

    def test_bearer_session_is_resolved_for_native_client(self):
        patient = self.create_patient()
        invite, _ = self.store.create_invite(patient["id"], self.staff)
        portal = self.store.activate_invite(invite, "portal-mobile", "mobile-strong-demo-password")
        token, _csrf, _expires = self.store.create_session(portal["id"])
        request = Request({"type": "http", "method": "PATCH", "path": "/api/portal/preferences",
                           "headers": [(b"authorization", f"Bearer {token}".encode())],
                           "query_string": b"", "server": ("localhost", 8000), "client": ("127.0.0.1", 50000),
                           "scheme": "http", "http_version": "1.1"})
        with patch("backend.patient_auth.store", return_value=self.store):
            user = current_user(request)
            self.assertEqual(user["patient_id"], patient["id"])
            self.assertEqual(request.state.auth_scheme, "bearer")
            verify_mutation(request, user)

    def test_mobile_login_is_patient_only_and_preferences_persist(self):
        patient = self.create_patient()
        invite, _ = self.store.create_invite(patient["id"], self.staff)
        portal = self.store.activate_invite(invite, "portal-mobile-login", "mobile-strong-demo-password")
        with patch("backend.main._patient_store", return_value=self.store):
            with self.assertRaises(HTTPException) as denied:
                mobile_login(LoginRequest(username=self.staff["username"], password="a-strong-demo-password"))
            self.assertEqual(denied.exception.status_code, 403)
            auth_result = mobile_login(LoginRequest(username=portal["username"], password="mobile-strong-demo-password"))
        self.assertEqual(auth_result["token_type"], "bearer")
        request = Request({"type": "http", "method": "PATCH", "path": "/api/portal/preferences",
                           "headers": [(b"authorization", f"Bearer {auth_result['access_token']}".encode())],
                           "query_string": b"", "server": ("localhost", 8000), "client": ("127.0.0.1", 50000),
                           "scheme": "http", "http_version": "1.1"})
        with patch("backend.patient_auth.store", return_value=self.store), patch("backend.main._patient_store", return_value=self.store):
            user = current_user(request)
            response = update_patient_portal_preferences(
                PortalPreferencesInput(preferred_contact="portal", notification_preferences={"portal_updates": True, "email": False, "sms": False}),
                request, user)
        self.assertEqual(response["preferred_contact"], "portal")
        self.assertTrue(response["notification_preferences"]["portal_updates"])

    def test_portal_only_sees_its_own_released_assessments(self):
        patient_a = self.create_patient()
        patient_b = self.create_patient({**self.profile, "name": "Synthetic Person Beta",
                                         "date_of_birth": "1972-02-02", "email": "beta@example.invalid"})
        token, _ = self.store.create_invite(patient_b["id"], self.staff)
        portal_b = self.store.activate_invite(token, "portal-beta", "beta-portal-strong-password")
        assessment = {"assessment_id": "a" * 32, "assessed_at": "2026-01-01T00:00:00+00:00",
                      "model_version": "synthetic-test", "probability": .25,
                      "risk_category": "MODERATE", "shap_values": [], "shap_base_value": .1,
                      "decision_support": [], "disclaimer": "Research only"}
        self.store.create_assessment(patient_a["id"], {"age": 55}, assessment,
                                     {"metrics": {}}, self.staff)
        report = self.store.create_report(patient_a["id"], assessment["assessment_id"],
                                          b"%PDF synthetic assessment A", self.staff, review_required=True)
        reviewed = self.store.review_report(report["report_id"], self.staff, release=False)
        self.assertEqual(reviewed["status"], "reviewed")
        self.assertEqual(self.store.patient_portal_summary(patient_b["id"], portal_b)["assessments"], [])
        self.assertIsNone(self.store.get_report_pdf(report["report_id"], portal_b,
                                                   patient_id=patient_b["id"], released_only=True))
        released = self.store.review_report(report["report_id"], self.staff, release=True)
        self.assertEqual(released["status"], "released")
        portal_a_token, _ = self.store.create_invite(patient_a["id"], self.staff)
        portal_a = self.store.activate_invite(portal_a_token, "portal-alpha", "alpha-portal-strong-password")
        home_a = self.store.patient_portal_summary(patient_a["id"], portal_a)
        self.assertEqual([item["assessment_id"] for item in home_a["assessments"]], [assessment["assessment_id"]])
        self.assertEqual(self.store.get_report_pdf(report["report_id"], portal_a,
                                                   patient_id=patient_a["id"], released_only=True),
                         b"%PDF synthetic assessment A")


class PatientRouteAuthorizationTests(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32" and sys.version_info >= (3, 14),
                     "This sandbox's Python 3.14 Windows event loop stalls while bootstrapping socketpair; run in Linux CI.")
    def test_http_routes_deny_anonymous_users_and_cross_patient_report_access(self):
        async def scenario():
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "data") as directory:
                env = patch.dict(os.environ, {
                    "XAI_CVD_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                    "XAI_CVD_PATIENT_DB": str(Path(directory) / "patients.sqlite3"),
                    "XAI_CVD_CORS_ORIGINS": "http://localhost:3000",
                })
                env.start()
                auth.store.cache_clear()
                db = auth.store()
                clinician = db.create_user("clinician", "clinical-demo-password", "clinician")
                patient_a = db.create_patient({"name": "Test One", "date_of_birth": "1970-01-01",
                    "email": "one@example.invalid", "phone": "", "preferred_contact": "in_person",
                    "consent_recorded": True, "consent_note": "Synthetic"}, clinician)
                patient_b = db.create_patient({"name": "Test Two", "date_of_birth": "1972-02-02",
                    "email": "two@example.invalid", "phone": "", "preferred_contact": "in_person",
                    "consent_recorded": True, "consent_note": "Synthetic"}, clinician)
                invite_a, _ = db.create_invite(patient_a["id"], clinician)
                invite_b, _ = db.create_invite(patient_b["id"], clinician)
                portal_a = db.activate_invite(invite_a, "one", "patient-one-strong-password")
                db.activate_invite(invite_b, "two", "patient-two-strong-password")
                assessment = {"assessment_id": "b" * 32, "assessed_at": "2026-02-01T00:00:00+00:00",
                              "model_version": "test", "probability": .3, "risk_category": "MODERATE",
                              "binary_label": "Lower predicted risk", "shap_values": [],
                              "shap_base_value": .1, "decision_support": [], "disclaimer": "Research only"}
                db.create_assessment(patient_a["id"], {"age": 55}, assessment, {"metrics": {}}, clinician)
                report = db.create_report(patient_a["id"], assessment["assessment_id"], b"%PDF test", clinician, True)
                db.review_report(report["report_id"], clinician, False)
                db.review_report(report["report_id"], clinician, True)

                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8000") as anonymous:
                    denied = await anonymous.get("/api/patients")
                    self.assertEqual(denied.status_code, 401)
                async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8000") as portal:
                    login = await portal.post("/api/auth/login", headers={"Origin": "http://localhost:3000"},
                        json={"username": "two", "password": "patient-two-strong-password"})
                    self.assertEqual(login.status_code, 200)
                    csrf = portal.cookies.get("xai_csrf")
                    other_assessment = await portal.get(f"/api/portal/assessments/{assessment['assessment_id']}")
                    other_report = await portal.get(f"/api/portal/reports/{report['report_id']}/pdf")
                    home = await portal.get("/api/portal/me")
                    self.assertEqual(other_assessment.status_code, 404)
                    self.assertEqual(other_report.status_code, 404)
                    self.assertEqual(home.json()["assessments"], [])
                    forbidden_staff = await portal.get("/api/patients")
                    self.assertEqual(forbidden_staff.status_code, 403)
                    logout = await portal.post("/api/auth/logout", headers={
                        "Origin": "http://localhost:3000", "X-CSRF-Token": csrf})
                    self.assertEqual(logout.status_code, 200)
                auth.store.cache_clear()
                env.stop()
        # The Windows Proactor loop's socketpair bootstrap can stall in some
        # Python 3.14 builds; this ASGI-only test does not need Proactor APIs.
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            runner.run(scenario())


if __name__ == "__main__":
    unittest.main()
