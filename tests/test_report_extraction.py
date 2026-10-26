from __future__ import annotations

import unittest
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from reportlab.pdfgen import canvas
from src.report_extraction import ReportExtractionError, extract_report, validate_upload

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_labs.csv"


class ReportExtractionTests(unittest.TestCase):
    def test_synthetic_lab_csv_maps_values_and_converts_units(self):
        content = FIXTURE.read_bytes()
        kind = validate_upload("synthetic_labs.csv", content)
        result = extract_report(kind, content)
        fields = {field["feature"]: field for field in result["fields"]}
        self.assertEqual(fields["gender"]["value"], 1.0)
        self.assertEqual(fields["sysBP"]["value"], 130.0)
        self.assertEqual(fields["diaBP"]["value"], 85.0)
        self.assertAlmostEqual(fields["totChol"]["value"], 5.2 * 38.67)
        self.assertAlmostEqual(fields["glucose"]["value"], 6.1 * 18.018)
        self.assertEqual(fields["totChol"]["status"], "found")
        self.assertIn("5.2", fields["totChol"]["source_snippet"])
        self.assertTrue(result["requires_user_confirmation"])

    def test_absent_education_stays_missing_without_imputation(self):
        result = extract_report("csv", FIXTURE.read_bytes())
        fields = {field["feature"]: field for field in result["fields"]}
        self.assertIsNone(fields["education"]["value"])
        self.assertEqual(fields["education"]["status"], "missing")
        self.assertTrue(any("will not impute" in issue for issue in fields["education"]["issues"]))

    def test_conflicting_values_are_flagged_as_ambiguous(self):
        content = b"Test Name,Result,Unit\nAge,52,years\nAge,53,years\n"
        result = extract_report("csv", content)
        age = next(field for field in result["fields"] if field["feature"] == "age")
        self.assertIsNone(age["value"])
        self.assertEqual(age["status"], "ambiguous")
        self.assertLess(age["confidence"], .65)

    def test_out_of_range_value_is_preserved_and_flagged(self):
        content = b"Test Name,Result,Unit\nAge,5,years\n"
        result = extract_report("csv", content)
        age = next(field for field in result["fields"] if field["feature"] == "age")
        self.assertEqual(age["value"], 5.0)
        self.assertEqual(age["status"], "out_of_range")

    def test_reference_range_is_not_mistaken_for_a_patient_result(self):
        content = b"Test Name,Result,Unit\nTotal cholesterol,125-200,mg/dL\nHDL cholesterol,60,mg/dL\n"
        result = extract_report("csv", content)
        cholesterol = next(field for field in result["fields"] if field["feature"] == "totChol")
        self.assertIsNone(cholesterol["value"])
        self.assertEqual(cholesterol["status"], "missing")

    def test_unheaded_key_value_csv_is_supported(self):
        content = b"Age,57,years\nSex,Male,\nBlood pressure,130/85,mmHg\n"
        result = extract_report("csv", content)
        fields = {field["feature"]: field for field in result["fields"]}
        self.assertEqual(fields["age"]["value"], 57)
        self.assertEqual(fields["gender"]["value"], 1)
        self.assertEqual(fields["sysBP"]["value"], 130)
        self.assertEqual(fields["diaBP"]["value"], 85)

    def test_upload_type_and_size_validation(self):
        with self.assertRaises(ReportExtractionError):
            validate_upload("bad.exe", b"MZ\x00")
        with self.assertRaises(ReportExtractionError):
            validate_upload("too-large.csv", b"x" * (10 * 1024 * 1024 + 1))

    def test_text_pdf_extracts_with_page_provenance(self):
        output = BytesIO()
        pdf = canvas.Canvas(output)
        for index, line in enumerate(["Synthetic clinical report", "Age: 57 years", "Sex: Male",
                                      "Blood pressure: 130/85 mmHg", "Total cholesterol: 200 mg/dL"]):
            pdf.drawString(72, 750 - 20 * index, line)
        pdf.save()
        content = output.getvalue()
        self.assertEqual(validate_upload("synthetic_report.pdf", content), "pdf")
        result = extract_report("pdf", content)
        fields = {field["feature"]: field for field in result["fields"]}
        self.assertEqual(fields["age"]["value"], 57)
        self.assertEqual(fields["sysBP"]["value"], 130)
        self.assertEqual(fields["diaBP"]["value"], 85)
        self.assertEqual(fields["totChol"]["page"], 1)

    def test_xlsx_lab_table_is_parsed_locally(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Test Name", "Result", "Unit"])
        sheet.append(["Age", 57, "years"])
        sheet.append(["FBS", 100, "mg/dL"])
        output = BytesIO(); workbook.save(output)
        content = output.getvalue()
        self.assertEqual(validate_upload("synthetic_labs.xlsx", content), "xlsx")
        result = extract_report("xlsx", content)
        fields = {field["feature"]: field for field in result["fields"]}
        self.assertEqual(fields["age"]["value"], 57)
        self.assertEqual(fields["glucose"]["value"], 100)


if __name__ == "__main__":
    unittest.main()
