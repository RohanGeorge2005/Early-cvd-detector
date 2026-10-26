"""Dataset validation, cleaning, and research report generation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

FEATURES = [
    "gender", "age", "education", "currentSmoker", "cigsPerDay", "BPMeds",
    "prevalentStroke", "prevalentHyp", "diabetes", "totChol", "sysBP",
    "diaBP", "BMI", "heartRate", "glucose",
]
TARGET = "TenYearCHD"
NUMERIC = ["age", "education", "cigsPerDay", "totChol", "sysBP", "diaBP", "BMI", "heartRate", "glucose"]
BINARY = ["gender", "currentSmoker", "BPMeds", "prevalentStroke", "prevalentHyp", "diabetes"]
BOUNDS = {
    "gender": (0, 1), "age": (18, 120), "education": (1, 4), "currentSmoker": (0, 1),
    "cigsPerDay": (0, 100), "BPMeds": (0, 1), "prevalentStroke": (0, 1),
    "prevalentHyp": (0, 1), "diabetes": (0, 1), "totChol": (50, 700),
    "sysBP": (50, 300), "diaBP": (30, 200), "BMI": (10, 100),
    "heartRate": (25, 250), "glucose": (20, 1000), TARGET: (0, 1),
}


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_value(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if pd.isna(value):
        return None
    return value


def load_and_clean(path: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Validate schema, coerce numeric data, remove duplicates and impossible values."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")
    raw = pd.read_csv(path)
    raw.columns = [str(c).strip() for c in raw.columns]
    # The commonly distributed Framingham CSV labels the same 0/1 input "male".
    if "gender" not in raw.columns and "male" in raw.columns:
        raw = raw.rename(columns={"male": "gender"})
    missing_columns = sorted(set(FEATURES + [TARGET]) - set(raw.columns))
    if missing_columns:
        raise ValueError("Dataset is missing required columns: " + ", ".join(missing_columns))
    raw = raw[FEATURES + [TARGET]].copy()
    raw_rows = len(raw)
    missing_before = raw.isna().sum().to_dict()
    for col in FEATURES + [TARGET]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    duplicates = int(raw.duplicated().sum())
    raw = raw.drop_duplicates().reset_index(drop=True)
    invalid_counts = {}
    for col, (lo, hi) in BOUNDS.items():
        invalid = raw[col].notna() & ~raw[col].between(lo, hi)
        invalid_counts[col] = int(invalid.sum())
        raw.loc[invalid, col] = np.nan
    invalid_target = raw[TARGET].notna() & ~raw[TARGET].isin([0, 1])
    invalid_counts[TARGET] += int(invalid_target.sum())
    raw.loc[invalid_target, TARGET] = np.nan
    raw = raw.dropna(subset=[TARGET]).copy()
    raw[TARGET] = raw[TARGET].astype(int)
    if raw[TARGET].nunique() != 2:
        raise ValueError("TenYearCHD must contain both classes 0 and 1 after cleaning.")
    summary = raw.describe(include="all").replace({np.nan: None}).to_dict()
    outliers = {}
    for col in NUMERIC:
        series = raw[col].dropna()
        if len(series):
            q1, q3 = series.quantile([.25, .75])
            iqr = q3 - q1
            outliers[col] = int(((series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)).sum())
    report = {
        "source_file": path.name, "rows_before_cleaning": raw_rows, "rows_after_cleaning": len(raw),
        "columns": len(FEATURES) + 1, "feature_columns": FEATURES, "target": TARGET,
        "duplicate_rows_removed": duplicates, "missing_values_before_cleaning": missing_before,
        "missing_values_after_cleaning": raw.isna().sum().to_dict(), "invalid_values_replaced_with_missing": invalid_counts,
        "data_types": raw.dtypes.astype(str).to_dict(),
        "class_distribution": raw[TARGET].value_counts().sort_index().to_dict(),
        "class_proportion": raw[TARGET].value_counts(normalize=True).sort_index().to_dict(),
        "statistical_summary": summary, "iqr_outlier_counts": outliers,
        "feature_distributions": {col: raw[col].value_counts(dropna=False).to_dict() for col in BINARY},
    }
    return raw, _json_value(report)


def save_report(report: dict[str, Any], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(_json_value(report), indent=2), encoding="utf-8")
