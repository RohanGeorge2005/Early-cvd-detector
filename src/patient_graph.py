"""Shared patient-specific SHAP graph data and static PDF renderer."""
from __future__ import annotations

from io import BytesIO
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


FEATURE_LABELS = {
    "gender": "Gender", "age": "Age", "education": "Education",
    "currentSmoker": "Current smoker", "cigsPerDay": "Cigarettes/day",
    "BPMeds": "BP medication", "prevalentStroke": "Previous stroke",
    "prevalentHyp": "Hypertension", "diabetes": "Diabetes",
    "totChol": "Total cholesterol", "sysBP": "Systolic BP",
    "diaBP": "Diastolic BP", "BMI": "BMI", "heartRate": "Heart rate",
    "glucose": "Fasting glucose",
}


def patient_graph_data(patient: dict, result: dict) -> list[dict]:
    """Return the same ordered top-eight SHAP values used by the result view."""
    probability = float(result["probability"])
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("The assessment probability is invalid; its graph cannot be rendered.")
    factors = result.get("shap_values")
    if not isinstance(factors, list) or not factors:
        raise ValueError("Patient-specific explanation values are unavailable; the report graph cannot be rendered.")
    data = []
    seen = set()
    for factor in factors[:8]:
        feature = factor.get("feature")
        if feature not in FEATURE_LABELS or feature in seen or feature not in patient:
            raise ValueError("Patient-specific graph data contains an unknown or duplicated feature.")
        contribution = float(factor["contribution"])
        value = float(patient[feature])
        if not math.isfinite(contribution) or not math.isfinite(value):
            raise ValueError("Patient-specific graph data contains a non-finite value.")
        seen.add(feature)
        data.append({"feature": feature, "label": FEATURE_LABELS[feature], "value": value,
                     "contribution": contribution,
                     "direction": "raises" if contribution > 0 else "lowers" if contribution < 0 else "neutral"})
    if not data:
        raise ValueError("No patient-specific explanation values are available for the graph.")
    return data


def _display_value(feature: str, value: float) -> str:
    if feature == "gender": return "Male" if value else "Female"
    if feature in {"currentSmoker", "BPMeds", "prevalentStroke", "prevalentHyp", "diabetes"}:
        return "Yes" if value else "No"
    if feature == "education": return f"Level {value:g}"
    units = {"age": "y", "cigsPerDay": "/day", "totChol": "mg/dL", "sysBP": "mmHg",
             "diaBP": "mmHg", "BMI": "kg/m²", "heartRate": "bpm", "glucose": "mg/dL"}
    return f"{value:g} {units.get(feature, '')}".strip()


def render_patient_graph(patient: dict, result: dict) -> bytes:
    """Render the result-page graph as a standalone PNG suitable for PDF."""
    data = patient_graph_data(patient, result)
    probability = float(result["probability"])
    count = len(data)
    fig, ax = plt.subplots(figsize=(8.2, 5.4), dpi=180)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(-1.55, 1.55)
    ax.set_ylim(-1.3, 1.3)
    ax.set_aspect("equal")
    ax.axis("off")
    center = (0.0, 0.0)
    radius = 1.0
    angles = [math.pi / 2 + (2 * math.pi * i / count) for i in range(count)]
    positions = [(radius * math.cos(a), radius * math.sin(a)) for a in angles]
    for item, (x, y) in zip(data, positions):
        color = "#C64C52" if item["contribution"] > 0 else "#168A86" if item["contribution"] < 0 else "#758391"
        ax.annotate("", xy=center, xytext=(x * .68, y * .68),
                    arrowprops={"arrowstyle": "->", "color": color, "lw": 1.5, "alpha": .55,
                                "shrinkA": 6, "shrinkB": 20})
        ax.text(x * .52, y * .52, f"{item['contribution']:+.3f}", ha="center", va="center",
                fontsize=7.5, color=color, fontweight="bold",
                bbox={"boxstyle": "round,pad=.16", "facecolor": "white", "edgecolor": "none", "alpha": .95})
    ax.scatter([0], [0], s=2400, c="#173B4D", edgecolors="#0C2735", linewidths=1.2, zorder=4)
    ax.text(0, .12, "MODEL OUTPUT", color="white", fontsize=8.5, fontweight="bold", ha="center", va="center", zorder=5)
    ax.text(0, -.12, f"{probability:.1%}", color="white", fontsize=16, fontweight="bold", ha="center", va="center", zorder=5)
    for item, (x, y) in zip(data, positions):
        color = "#C64C52" if item["contribution"] > 0 else "#168A86" if item["contribution"] < 0 else "#758391"
        ax.scatter([x], [y], s=1120, c="#F5F7F8", edgecolors=color, linewidths=2.0, zorder=3)
        ax.text(x, y + .10, item["label"], ha="center", va="center", fontsize=7.5,
                color="#18313D", fontweight="bold", wrap=True, zorder=4)
        ax.text(x, y - .10, _display_value(item["feature"], item["value"]), ha="center", va="center",
                fontsize=7, color="#536570", zorder=4)
    ax.text(-1.48, -1.22, "Red: raises model output", color="#A63E45", fontsize=8, ha="left")
    ax.text(1.48, -1.22, "Teal: lowers model output", color="#14726F", fontsize=8, ha="right")
    ax.set_title("Patient-specific model contributions", fontsize=13, color="#173B4D", pad=12, fontweight="bold")
    image = BytesIO()
    fig.savefig(image, format="png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return image.getvalue()
