from __future__ import annotations

import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_labs.csv"


class ReportUploadApiTests(unittest.TestCase):
    def test_upload_returns_async_job_and_reviewable_fields(self):
        client = TestClient(app)
        response = client.post("/api/reports/upload", files={
            "file": ("synthetic_labs.csv", FIXTURE.read_bytes(), "text/csv")
        })
        self.assertEqual(response.status_code, 202)
        job_id = response.json()["analysis_id"]
        result = None
        for _ in range(40):
            status = client.get(f"/api/reports/{job_id}")
            self.assertEqual(status.status_code, 200)
            result = status.json()
            if result["status"] != "processing":
                break
            time.sleep(.025)
        self.assertEqual(result["status"], "completed")
        fields = {item["feature"]: item for item in result["result"]["fields"]}
        self.assertEqual(fields["sysBP"]["value"], 130)
        self.assertEqual(fields["diaBP"]["value"], 85)
        self.assertEqual(fields["education"]["status"], "missing")
        self.assertTrue(result["result"]["requires_user_confirmation"])

    def test_invalid_upload_is_rejected(self):
        client = TestClient(app)
        response = client.post("/api/reports/upload", files={
            "file": ("payload.exe", b"MZ\x00", "application/octet-stream")
        })
        self.assertEqual(response.status_code, 415)


if __name__ == "__main__":
    unittest.main()
