"""Local, conservative extraction of supported values from synthetic or user reports.

This module only proposes field values. It never imputes missing values or makes
predictions; the frontend must present every proposal for confirmation first.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path
from typing import Any

from src.data_processing import BOUNDS, FEATURES

MAX_REPORT_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 30
MAX_SCANNED_PDF_PAGES = 10

FIELD_LABELS = {
    "gender": "Sex", "age": "Age", "education": "Education level",
    "currentSmoker": "Current smoker", "cigsPerDay": "Cigarettes per day",
    "BPMeds": "Blood pressure medication", "prevalentStroke": "Previous stroke",
    "prevalentHyp": "Hypertension history", "diabetes": "Diabetes",
    "totChol": "Total cholesterol", "sysBP": "Systolic blood pressure",
    "diaBP": "Diastolic blood pressure", "BMI": "Body mass index",
    "heartRate": "Resting heart rate", "glucose": "Glucose",
}
FIELD_UNITS = {
    "gender": None, "age": "years", "education": "level (1–4)",
    "currentSmoker": None, "cigsPerDay": "cigarettes/day", "BPMeds": None,
    "prevalentStroke": None, "prevalentHyp": None, "diabetes": None,
    "totChol": "mg/dL", "sysBP": "mmHg", "diaBP": "mmHg",
    "BMI": "kg/m²", "heartRate": "bpm", "glucose": "mg/dL",
}

LABELS: dict[str, tuple[str, ...]] = {
    "gender": (r"sex", r"gender"),
    "age": (r"age",),
    "education": (r"education(?:\s+level)?",),
    "currentSmoker": (r"current\s+smoker", r"smoking\s+status", r"smoker", r"tobacco\s+use"),
    "cigsPerDay": (r"cigarettes?(?:\s+per\s+day|/day|\s+daily)", r"cigs?(?:\s+per\s+day|/day)"),
    "BPMeds": (r"(?:bp|blood\s+pressure|hypertension)\s+med(?:ication|ications|s)?", r"on\s+(?:bp|blood\s+pressure)\s+medication"),
    "prevalentStroke": (r"(?:history\s+of\s+)?(?:prior|previous|prevalent)?\s*stroke",),
    "prevalentHyp": (r"(?:history\s+of\s+)?(?:prevalent\s+)?hypertension", r"hypertension\s+history", r"htn\s+history"),
    "diabetes": (r"diabetes(?:\s+status|\s+history)?", r"diabetic"),
    "totChol": (r"total\s+cholesterol", r"total\s+chol", r"cholesterol\s*,?\s*total", r"\bchol\b"),
    "sysBP": (r"systolic(?:\s+blood\s+pressure|\s+bp)?", r"sys\s*bp"),
    "diaBP": (r"diastolic(?:\s+blood\s+pressure|\s+bp)?", r"dia\s*bp"),
    "BMI": (r"body\s+mass\s+index", r"\bbmi\b"),
    "heartRate": (r"resting\s+heart\s+rate", r"heart\s+rate", r"\bpulse\b", r"\bhr\b"),
    "glucose": (r"fasting\s+blood\s+glucose", r"fasting\s+glucose", r"\bfbs\b", r"\bglucose\b"),
}

YES = {"yes", "y", "true", "positive", "present", "1", "current", "smoker", "diabetic"}
NO = {"no", "n", "false", "negative", "absent", "0", "never", "former", "non-smoker", "nonsmoker"}


class ReportExtractionError(ValueError):
    """A safe, user-displayable extraction error."""


def validate_upload(filename: str | None, content: bytes) -> str:
    """Validate size, extension and file signature, then return the format."""
    if not content:
        raise ReportExtractionError("The selected file is empty.")
    if len(content) > MAX_REPORT_BYTES:
        raise ReportExtractionError("Files must be 10 MB or smaller.")
    extension = Path(filename or "").suffix.lower()
    formats = {".pdf": "pdf", ".jpg": "image", ".jpeg": "image", ".png": "image",
               ".csv": "csv", ".xlsx": "xlsx"}
    if extension not in formats:
        raise ReportExtractionError("Supported file types are PDF, JPG, PNG, CSV and XLSX.")
    kind = formats[extension]
    if kind == "pdf" and not content.startswith(b"%PDF-"):
        raise ReportExtractionError("The file extension says PDF but its contents are not a valid PDF.")
    if kind == "image" and not (content.startswith(b"\x89PNG\r\n\x1a\n") or content.startswith(b"\xff\xd8\xff")):
        raise ReportExtractionError("The image file is not a valid PNG or JPEG.")
    if kind == "xlsx" and not content.startswith(b"PK\x03\x04"):
        raise ReportExtractionError("The XLSX file does not have a valid workbook signature.")
    if kind == "csv":
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ReportExtractionError("CSV files must use UTF-8 text encoding.") from None
    return kind


def _source_lines(kind: str, content: bytes, progress=None) -> list[tuple[int | None, str, bool]]:
    if kind == "pdf":
        try:
            import pymupdf
        except ImportError:
            raise ReportExtractionError("PDF parsing is unavailable. Install the project requirements and retry.") from None
        pages: list[tuple[int | None, str, bool]] = []
        try:
            document = pymupdf.open(stream=content, filetype="pdf")
        except Exception:
            raise ReportExtractionError("The PDF could not be opened. It may be damaged or password protected.") from None
        if document.page_count > MAX_PDF_PAGES:
            raise ReportExtractionError(f"PDF reports are limited to {MAX_PDF_PAGES} pages.")
        total_text = ""
        for index, page in enumerate(document):
            text = page.get_text("text") or ""
            total_text += text
            page_lines = [line.strip() for line in text.splitlines() if line.strip()]
            pages.extend((index + 1, line, False) for line in page_lines)
            # PDF table extractors often put a label and its value on adjacent
            # text lines. Preserve the page and label/value source together.
            for pos in range(len(page_lines) - 1):
                label_line, value_line = page_lines[pos], page_lines[pos + 1]
                if re.search(r"\d", label_line) or not re.search(r"\d", value_line):
                    continue
                if any(re.search(_aliases_pattern(feature), label_line, re.I) for feature in FEATURES):
                    pages.append((index + 1, f"{label_line}: {value_line}", False))
            if progress:
                progress(15 + int(25 * (index + 1) / max(1, document.page_count)), "Reading PDF text")
        if len(total_text.strip()) < 20:
            pages = _ocr_pdf(document, progress)
        document.close()
        return pages
    if kind == "image":
        return _ocr_image(content, progress)
    if kind == "csv":
        try:
            text = content.decode("utf-8-sig")
            rows = list(csv.reader(io.StringIO(text)))
        except (UnicodeDecodeError, csv.Error):
            raise ReportExtractionError("The CSV could not be read. Check that it is a valid UTF-8 CSV file.") from None
        if not rows:
            return []
        header = [cell.strip() for cell in rows[0]]
        if len(header) >= 2 and any(re.search(_aliases_pattern(feature), header[0], re.I) for feature in FEATURES) \
                and re.fullmatch(r"\s*\d+(?:\.\d+)?\s*", header[1]):
            return [(None, f"{row[0].strip()}: {row[1].strip()} {row[2].strip() if len(row) > 2 else ''}".strip(), False)
                    for row in rows if len(row) >= 2 and row[0].strip() and row[1].strip()]
        label_column = next((i for i, name in enumerate(header)
                             if name.lower() in {"test", "test name", "label", "field", "feature", "measurement", "analyte", "name"}), None)
        if label_column is None and len(header) > 1 and header[1].lower() in {"value", "result", "reading", "measurement value"} \
                and any(re.search(_aliases_pattern(feature), header[0], re.I) for feature in FEATURES):
            label_column = 0
        if label_column is not None and len(header) > 1:
            value_column = next((i for i, name in enumerate(header)
                                 if name.lower() in {"value", "result", "reading", "measurement value"}), None)
            unit_column = next((i for i, name in enumerate(header) if name.lower() in {"unit", "units"}), None)
            if value_column is not None:
                out = []
                for row in rows[1:]:
                    if len(row) <= max(label_column, value_column) or not row[label_column].strip():
                        continue
                    unit = row[unit_column].strip() if unit_column is not None and len(row) > unit_column else ""
                    out.append((None, f"{row[label_column].strip()}: {row[value_column].strip()} {unit}".strip(), False))
                return out
        feature_header_count = sum(any(re.search(_aliases_pattern(feature), cell, re.I) for feature in FEATURES)
                                   for cell in header)
        if len(rows) > 1 and len(header) > 1 and feature_header_count >= 2:
            headers = rows[0]
            return [(None, " | ".join(f"{h.strip()}: {v.strip()}" for h, v in zip(headers, row)
                                       if h.strip() and v.strip()), False) for row in rows[1:]]
        if len(header) > 1 and any(re.search(_aliases_pattern(feature), header[0], re.I) for feature in FEATURES) \
                and not any(re.search(_aliases_pattern(feature), header[1], re.I) for feature in FEATURES) \
                and header[1].lower() not in {"value", "result", "reading", "unit", "units"}:
            return [(None, f"{row[0].strip()}: {row[1].strip()} {row[2].strip() if len(row) > 2 else ''}".strip(), False)
                    for row in rows if len(row) >= 2 and row[0].strip() and row[1].strip()]
        return [(None, " | ".join(cell.strip() for cell in row if cell.strip()), False)
                for row in rows if any(cell.strip() for cell in row)]
    if kind == "xlsx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as workbook_zip:
                members = workbook_zip.infolist()
                if len(members) > 300 or sum(member.file_size for member in members) > 50 * 1024 * 1024:
                    raise ReportExtractionError("The XLSX workbook expands beyond the safe parsing limit.")
                if any(member.compress_size and member.file_size / member.compress_size > 1000 for member in members):
                    raise ReportExtractionError("The XLSX workbook has an unsafe compression ratio.")
            import pandas as pd
            frame = pd.read_excel(io.BytesIO(content), engine="openpyxl", dtype=object)
        except ReportExtractionError:
            raise
        except ImportError:
            raise ReportExtractionError("XLSX parsing is unavailable. Install the project requirements and retry.") from None
        except Exception:
            raise ReportExtractionError("The spreadsheet could not be read. Check that it is a valid XLSX file.") from None
        if frame.size > 100_000:
            raise ReportExtractionError("Spreadsheet reports are limited to 100,000 cells.")
        headers = [str(column).strip() for column in frame.columns]
        header_lower = [h.lower() for h in headers]
        label_column = next((i for i, name in enumerate(header_lower)
                             if name in {"test", "test name", "label", "field", "feature", "measurement", "analyte", "name"}), None)
        value_column = next((i for i, name in enumerate(header_lower)
                             if name in {"value", "result", "reading", "measurement value"}), None)
        unit_column = next((i for i, name in enumerate(header_lower) if name in {"unit", "units"}), None)
        lines = []
        for _, row in frame.iterrows():
            if label_column is not None and value_column is not None and pd.notna(row.iloc[label_column]) and pd.notna(row.iloc[value_column]):
                unit = row.iloc[unit_column] if unit_column is not None and pd.notna(row.iloc[unit_column]) else ""
                lines.append((None, f"{row.iloc[label_column]}: {row.iloc[value_column]} {unit}".strip(), False))
                continue
            parts = [f"{column}: {value}" for column, value in row.items()
                     if pd.notna(value) and str(value).strip()]
            if parts:
                lines.append((None, " | ".join(parts), False))
        return lines
    raise ReportExtractionError("This file type is not supported.")


def _ocr_image(content: bytes, progress=None) -> list[tuple[int | None, str, bool]]:
    try:
        from PIL import Image
        import pytesseract
        image = Image.open(io.BytesIO(content))
        if image.width * image.height > 40_000_000:
            raise ReportExtractionError("Image dimensions are too large to process safely.")
        image = image.convert("RGB")
        if progress:
            progress(25, "Running local OCR")
        text = pytesseract.image_to_string(image, timeout=25)
        return [(1, line.strip(), True) for line in text.splitlines() if line.strip()]
    except ReportExtractionError:
        raise
    except ImportError:
        raise ReportExtractionError("Image OCR is unavailable. Install the project requirements and local Tesseract OCR, then retry.") from None
    except Exception as exc:
        if "tesseract" in str(exc).lower():
            raise ReportExtractionError("Local Tesseract OCR was not found. Install Tesseract or upload a text-based PDF/CSV/XLSX.") from None
        raise ReportExtractionError("The image could not be read by local OCR.") from None


def _ocr_pdf(document, progress=None) -> list[tuple[int | None, str, bool]]:
    try:
        from PIL import Image
        import pymupdf
        import pytesseract
    except ImportError:
        raise ReportExtractionError("This PDF appears scanned. Install project requirements and local Tesseract OCR, then retry.") from None
    if document.page_count > MAX_SCANNED_PDF_PAGES:
        raise ReportExtractionError(f"Scanned PDF OCR is limited to {MAX_SCANNED_PDF_PAGES} pages per upload.")
    lines: list[tuple[int | None, str, bool]] = []
    for index, page in enumerate(document):
        rect = page.rect
        if rect.width * rect.height * 1.6 * 1.6 > 40_000_000:
            raise ReportExtractionError("A scanned PDF page has dimensions too large to process safely.")
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
        try:
            text = pytesseract.image_to_string(image, timeout=25)
        except Exception:
            raise ReportExtractionError("Local Tesseract OCR was not found. Install Tesseract or upload a text-based report.") from None
        lines.extend((index + 1, line.strip(), True) for line in text.splitlines() if line.strip())
        if progress:
            progress(40 + int(35 * (index + 1) / max(1, document.page_count)), "Running local OCR")
    return lines


def _aliases_pattern(feature: str) -> str:
    return "(?:" + "|".join(LABELS[feature]) + ")"


def _value_match(line: str, feature: str) -> tuple[float, str, str | None] | None:
    """Return raw value, minimal source text, and nearby explicit unit."""
    label = _aliases_pattern(feature)
    if feature == "totChol" and re.search(r"\b(?:hdl|ldl|non[- ]?hdl)\b", line, re.I) \
            and not re.search(r"total\s+(?:cholesterol|chol)|cholesterol\s*,?\s*total", line, re.I):
        return None
    if feature == "gender":
        pattern = rf"{label}\s*[:=]?\s*(male|female|m\b|f\b)"
        match = re.search(pattern, line, re.I)
        if not match:
            return None
        value = 1.0 if match.group(1).lower() in ("male", "m") else 0.0
        return value, match.group(0)[:120], None
    if feature in {"currentSmoker", "BPMeds", "prevalentStroke", "prevalentHyp", "diabetes"}:
        # Smoking statuses carry distinct meanings; former/never are both not current smokers.
        pattern = rf"{label}\s*[:=]?\s*(yes|no|y\b|n\b|true|false|positive|negative|present|absent|current|former|never|non[- ]?smoker|smoker|diabetic|0|1)\b"
        match = re.search(pattern, line, re.I)
        if not match:
            return None
        token = match.group(1).lower().replace(" ", "-")
        if feature == "currentSmoker" and token in {"former", "never", "non-smoker", "nonsmoker"}:
            value = 0.0
        elif token in YES:
            value = 1.0
        elif token in NO:
            value = 0.0
        else:
            return None
        return value, match.group(0)[:120], None
    if feature in {"sysBP", "diaBP"}:
        # A labeled 130/85 reading proposes both values and records the same source snippet.
        bp = re.search(r"(?:blood\s+pressure|\bbp\b)\s*[:=]?\s*(\d{2,3}(?:\.\d+)?)\s*/\s*(\d{2,3}(?:\.\d+)?)\s*(mmhg|kpa)?", line, re.I)
        if bp:
            raw = float(bp.group(1 if feature == "sysBP" else 2))
            unit = (bp.group(3) or "mmHg").lower()
            if unit == "kpa":
                raw *= 7.50062
            return raw, bp.group(0)[:120], unit
    if feature == "cigsPerDay":
        match = re.search(rf"{label}\s*[:=]?\s*(\d{{1,3}}(?:\.\d+)?)\s*(cigarettes?|cigs?)?", line, re.I)
    else:
        match = re.search(rf"{label}\s*[:=]?\s*(\d{{1,4}}(?:\.\d+)?)\s*([a-zA-Z%²/]+(?:\s*/\s*[a-zA-Z]+)?)?", line, re.I)
    if not match:
        return None
    if re.match(r"\s*[-–]\s*\d", line[match.end(1):]):
        # A range is not a measured patient value; leave it for manual review.
        return None
    value = float(match.group(1))
    unit = (match.group(2) or "").strip().lower() or None
    snippet = match.group(0)[:120]
    if feature == "totChol" and unit and ("mmol" in unit):
        value *= 38.67
    elif feature == "glucose" and unit and ("mmol" in unit):
        value *= 18.018
    elif feature in {"sysBP", "diaBP"} and unit == "kpa":
        value *= 7.50062
    return value, snippet, unit


def extract_report(kind: str, content: bytes, progress=None) -> dict[str, Any]:
    """Extract conservative feature candidates with provenance and confidence."""
    lines = _source_lines(kind, content, progress)
    if progress:
        progress(78, "Mapping report values")
    by_feature: dict[str, list[dict[str, Any]]] = {feature: [] for feature in FEATURES}
    for page, line, is_ocr in lines:
        for feature in FEATURES:
            match = _value_match(line, feature)
            if not match:
                continue
            value, snippet, unit = match
            # A clinical label with an explicit value is relatively reliable. Generic HR/Chol
            # shorthand is slightly less certain; OCR results are never marked high certainty.
            confidence = .96 if unit or feature in {"gender", "currentSmoker", "BPMeds", "prevalentStroke", "prevalentHyp", "diabetes"} else .88
            if feature in {"heartRate", "totChol"} and len(snippet.split()) <= 2:
                confidence = .78
            if is_ocr:
                confidence = max(.4, confidence - .18)
            by_feature[feature].append({"value": value, "confidence": confidence,
                                        "source_snippet": snippet, "page": page, "source_unit": unit})
    fields = []
    for feature in FEATURES:
        candidates = by_feature[feature]
        status = "missing"
        value, confidence, snippet, page, source_unit = None, 0.0, None, None, None
        issues: list[str] = []
        if candidates:
            unique = {round(item["value"], 5) for item in candidates}
            if len(unique) > 1:
                status = "ambiguous"
                issues.append("The report contains conflicting values; enter the correct value manually.")
                confidence = .35
                snippets = [item["source_snippet"] for item in candidates[:3]]
                snippet = " | ".join(snippets)[:240]
                page = candidates[0]["page"]
            else:
                candidate = candidates[0]
                value, confidence = candidate["value"], candidate["confidence"]
                snippet, page, source_unit = candidate["source_snippet"], candidate["page"], candidate["source_unit"]
                lo, hi = BOUNDS[feature]
                if value < lo or value > hi:
                    status = "out_of_range"
                    issues.append(f"Extracted value is outside the accepted input range ({lo}–{hi}).")
                elif confidence < .65:
                    status = "low_confidence"
                    issues.append("Please verify this value against the source report.")
                else:
                    status = "found"
        if not candidates:
            issues.append("No value was found. Enter it manually if known; the app will not impute it.")
        fields.append({"feature": feature, "label": FIELD_LABELS[feature], "value": value,
                       "unit": FIELD_UNITS[feature], "source_unit": source_unit,
                       "confidence": confidence, "status": status,
                       "source_snippet": snippet, "page": page, "issues": issues})
    if progress:
        progress(95, "Preparing review")
    return {"fields": fields, "requires_user_confirmation": True,
            "extraction_note": "Extracted values are suggestions, not verified facts. Confidence scores are heuristic extraction estimates, not probabilities. No prediction was run and no missing value was imputed."}
