"""Input validation and explanation for the saved hybrid inference bundle."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.data_processing import BOUNDS, FEATURES
from src.hybrid import component_probabilities, explain_hybrid, hybrid_predict

ROOT = Path(__file__).resolve().parents[1]


def validate_input(payload: dict) -> pd.DataFrame:
    missing = [f for f in FEATURES if f not in payload]
    extra = sorted(set(payload) - set(FEATURES))
    if missing:
        raise ValueError("Missing required inputs: " + ", ".join(missing))
    if extra:
        raise ValueError("Unexpected inputs: " + ", ".join(extra))
    clean = {}
    for name in FEATURES:
        value = payload[name]
        if isinstance(value, bool): value = int(value)
        try: number = float(value)
        except (TypeError, ValueError): raise ValueError(f"{name} must be a finite number.") from None
        if not np.isfinite(number): raise ValueError(f"{name} must be a finite number.")
        lo, hi = BOUNDS[name]
        if not lo <= number <= hi: raise ValueError(f"{name} must be between {lo} and {hi}.")
        if name in ["gender", "education", "currentSmoker", "BPMeds", "prevalentStroke", "prevalentHyp", "diabetes"] and not number.is_integer():
            raise ValueError(f"{name} must be a whole number.")
        clean[name] = number
    for name in ["gender", "currentSmoker", "BPMeds", "prevalentStroke", "prevalentHyp", "diabetes"]:
        if clean[name] not in (0, 1): raise ValueError(f"{name} must be 0 or 1.")
    if clean["education"] not in (1, 2, 3, 4): raise ValueError("education must be one of 1, 2, 3, or 4.")
    return pd.DataFrame([clean], columns=FEATURES)


def load_artifacts(models_dir: Path = ROOT / "models") -> tuple:
    bundle_path, metadata_path = models_dir / "hybrid_model.joblib", models_dir / "model_metadata.json"
    if not bundle_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError("Trained hybrid model artifacts not found. Add the dataset and run python -m src.train.")
    return joblib.load(bundle_path), json.loads(metadata_path.read_text(encoding="utf-8"))


def predict(payload: dict, model=None, metadata=None, models_dir: Path = ROOT / "models") -> dict:
    row = validate_input(payload)
    if model is None or metadata is None: model, metadata = load_artifacts(models_dir)
    outputs = component_probabilities(row, model)
    probability = float(hybrid_predict(row, model)[0])
    threshold = float(metadata.get("threshold", .5))
    bands = metadata.get("risk_thresholds", {"low_max_exclusive": .10, "moderate_max_exclusive": .20})
    category = "LOW" if probability < bands["low_max_exclusive"] else "MODERATE" if probability < bands["moderate_max_exclusive"] else "HIGH"
    factors, base_value = explain_hybrid(row, model, metadata)
    top = factors[:8]
    # Compare the two independent component models only. The hybrid is derived
    # from these components and must not be counted as a third independent vote.
    component_predictions = [outputs["tree"] >= threshold, outputs["dl"] >= threshold]
    positives = sum(component_predictions)
    consensus = component_predictions[0] == component_predictions[1]
    suggestions = []
    if row.at[0, "sysBP"] >= 130 or row.at[0, "diaBP"] >= 80:
        suggestions.append("Blood pressure contributed to the assessment inputs. Consider discussing blood pressure monitoring with a qualified healthcare professional.")
    if row.at[0, "totChol"] >= 200:
        suggestions.append("Cholesterol is one of the assessment inputs. Consider appropriate monitoring with a healthcare professional.")
    if row.at[0, "glucose"] >= 100 or row.at[0, "diabetes"] == 1:
        suggestions.append("Glucose or diabetes status is part of the assessment. Discuss monitoring with a qualified healthcare professional.")
    if row.at[0, "currentSmoker"] == 1:
        suggestions.append("Smoking status is part of the assessment. Smoking cessation support may be a cardiovascular health consideration.")
    if row.at[0, "BMI"] >= 25:
        suggestions.append("BMI is one of the assessment inputs. Consider discussing healthy activity and weight goals with a healthcare professional.")
    suggestions.append("Regular physical activity and consultation with a qualified healthcare professional may support cardiovascular health.")
    models = {**outputs["ml"], "Deep Neural Network": outputs["dl"], "Hybrid AI": probability}
    return {"prediction": int(probability >= threshold), "probability": probability,
            "risk_category": category, "binary_label": "Higher predicted risk" if probability >= threshold else "Lower predicted risk",
            "model_threshold": threshold, "alpha": float(model["alpha"]), "tree_component": model["tree_model_name"],
            "ml_probability": float(outputs["tree"]), "dl_probability": float(outputs["dl"]),
            "hybrid_probability": probability, "model_outputs": models,
            "model_consensus": consensus, "model_consensus_count": positives,
            "model_consensus_total": len(component_predictions),
            "model_agreement_note": "Component models agree" if consensus else "Component models disagree; interpret the model estimate cautiously.",
            "top_factors": top, "top_features": top, "shap_values": factors, "explanation": top,
            "shap_base_value": base_value,
            "feature_order": FEATURES,
            "decision_support": suggestions,
            "disclaimer": "Academic/research decision support only; not a diagnosis. SHAP contributions describe model behavior and do not establish medical causation."}
