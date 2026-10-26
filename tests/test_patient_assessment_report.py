from __future__ import annotations

import time
import unittest
from unittest.mock import patch

import pymupdf
from fastapi.testclient import TestClient

import backend.main as api
from src.patient_graph import patient_graph_data, render_patient_graph


def sample_patient(age: int, systolic: int) -> dict:
    return {"gender": 0, "age": age, "education": 2, "currentSmoker": 0,
            "cigsPerDay": 0, "BPMeds": 0, "prevalentStroke": 0, "prevalentHyp": 0,
            "diabetes": 0, "totChol": 200, "sysBP": systolic, "diaBP": 80,
            "BMI": 25, "heartRate": 70, "glucose": 100}


def sample_result(patient: dict, probability: float) -> dict:
    features = ["age", "sysBP", "totChol", "diabetes", "currentSmoker", "BMI", "glucose", "heartRate"]
    factors = [{"feature": name, "value": patient[name], "contribution": (i + 1) * probability / 100,
               "direction": "increases risk"} for i, name in enumerate(features)]
    return {"probability": probability, "risk_category": "HIGH", "binary_label": "Higher predicted risk",
            "tree_component": "XGBoost", "model_threshold": .5, "alpha": .6,
            "top_factors": factors, "shap_values": factors, "model_outputs": {"XGBoost": probability},
            "model_consensus_count": 1, "model_consensus_total": 2,
            "model_agreement_note": "Components differ", "decision_support": ["Discuss monitoring."],
            "shap_base_value": .1}


METADATA = {"metrics": {"XGBoost": {"roc_auc": .7, "f1": .4, "recall": .5, "accuracy": .8}},
            "risk_thresholds": {"low_max_exclusive": .1, "moderate_max_exclusive": .2},
            "xai_method": "SHAP", "model_version": "test", "best_model_by_composite": "XGBoost",
            "comparison": {}}


class PatientAssessmentReportTests(unittest.TestCase):
    def test_two_assessment_ids_produce_their_own_pdf_graph_and_values(self):
        client = TestClient(api.app)
        cases = [("a" * 32, sample_patient(50, 120), .24),
                 ("b" * 32, sample_patient(70, 170), .81)]
        with api.assessment_records_lock:
            for assessment_id, patient, probability in cases:
                api.assessment_records[assessment_id] = {
                    "patient": patient, "result": sample_result(patient, probability),
                    "metadata": METADATA, "created_monotonic": time.monotonic()}
        try:
            outputs = []
            for assessment_id, patient, probability in cases:
                response = client.post("/generate-assessment-report", json={"assessment_id": assessment_id})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.content.startswith(b"%PDF"))
                document = pymupdf.open(stream=response.content, filetype="pdf")
                text = "\n".join(page.get_text() for page in document)
                self.assertIn(assessment_id, text)
                self.assertIn(f"{probability:.1%}", text)
                images = [xref for page in document for xref, *_ in page.get_images(full=True)]
                self.assertTrue(images, "PDF is missing the required patient graph image")
                outputs.append((document, text, patient, sample_result(patient, probability)))
            embedded = []
            for document, *_ in outputs:
                xref = next(xref for page in document for xref, *_ in page.get_images(full=True))
                embedded.append(document.extract_image(xref)["image"])
            self.assertNotEqual(embedded[0], embedded[1])
            self.assertNotIn("b" * 32, outputs[0][1])
            self.assertNotIn("a" * 32, outputs[1][1])
            self.assertEqual(patient_graph_data(outputs[0][2], outputs[0][3])[0]["value"], 50)
            self.assertEqual(patient_graph_data(outputs[1][2], outputs[1][3])[0]["value"], 70)
        finally:
            with api.assessment_records_lock:
                for assessment_id, *_ in cases:
                    api.assessment_records.pop(assessment_id, None)

    def test_graph_changes_with_patient_data_and_contributions(self):
        first = sample_patient(50, 120)
        second = sample_patient(70, 170)
        first_image = render_patient_graph(first, sample_result(first, .24))
        second_image = render_patient_graph(second, sample_result(second, .81))
        self.assertTrue(first_image.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertNotEqual(first_image, second_image)

    def test_missing_explanation_and_unknown_assessment_fail_clearly(self):
        client = TestClient(api.app)
        patient = sample_patient(50, 120)
        with api.assessment_records_lock:
            api.assessment_records["c" * 32] = {
                "patient": patient, "result": {**sample_result(patient, .24), "shap_values": []},
                "metadata": METADATA, "created_monotonic": time.monotonic()}
        try:
            missing_xai = client.post("/generate-assessment-report", json={"assessment_id": "c" * 32})
            self.assertEqual(missing_xai.status_code, 422)
            expired = client.post("/generate-assessment-report", json={"assessment_id": "d" * 32})
            self.assertEqual(expired.status_code, 410)
            invalid = client.post("/predict", json={})
            self.assertEqual(invalid.status_code, 422)
        finally:
            with api.assessment_records_lock:
                api.assessment_records.pop("c" * 32, None)

    def test_legacy_report_endpoint_still_returns_a_pdf_with_the_graph(self):
        patient = sample_patient(56, 132)
        with patch("backend.main.artifacts", return_value=(object(), METADATA)), \
             patch("backend.main.predict", return_value=sample_result(patient, .42)):
            response = TestClient(api.app).post("/generate-report", json=patient)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))
        document = pymupdf.open(stream=response.content, filetype="pdf")
        self.assertTrue(any(page.get_images(full=True) for page in document))


if __name__ == "__main__":
    unittest.main()
