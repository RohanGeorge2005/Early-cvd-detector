"""Dataset-level associations between the existing CVD model predictors."""
from __future__ import annotations

from functools import lru_cache
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

try:  # NetworkX enriches the graph object when installed; API payloads stay portable.
    import networkx as nx
except ImportError:  # Dependency installation can be unavailable in offline environments.
    nx = None

from src.data_processing import FEATURES, load_and_clean

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "raw" / "framingham.csv"
MIN_PAIRWISE_N = 100
METHOD = "Spearman rank correlation"
P_VALUE_METHOD = "SciPy Spearman asymptotic p-value approximation"
FDR_METHOD = "Benjamini–Hochberg false-discovery-rate correction (q ≤ 0.05)"

FEATURE_INFO: dict[str, dict[str, str]] = {
    "gender": {"label": "Gender", "short_label": "Gender", "category": "Demographics", "unit": "encoded category", "description": "Binary gender field in the source dataset (male is encoded 1; female is encoded 0)."},
    "age": {"label": "Age", "short_label": "Age", "category": "Demographics", "unit": "years", "description": "Age recorded in the source dataset, in years."},
    "education": {"label": "Education", "short_label": "Education", "category": "Demographics", "unit": "ordinal level", "description": "Education category encoded as levels 1 through 4; the values are treated as ordinal ranks."},
    "currentSmoker": {"label": "Current smoker", "short_label": "Smoker", "category": "Lifestyle", "unit": "yes/no", "description": "Whether the source dataset records the person as a current smoker."},
    "cigsPerDay": {"label": "Cigarettes per day", "short_label": "Cigarettes/day", "category": "Lifestyle", "unit": "cigarettes/day", "description": "Reported cigarettes smoked per day."},
    "BPMeds": {"label": "Blood pressure medication", "short_label": "BP medication", "category": "Medical history", "unit": "yes/no", "description": "Whether blood pressure medication use is recorded."},
    "prevalentStroke": {"label": "Previous stroke", "short_label": "Stroke", "category": "Medical history", "unit": "yes/no", "description": "Whether a prior stroke is recorded in the dataset."},
    "prevalentHyp": {"label": "Hypertension", "short_label": "Hypertension", "category": "Medical history", "unit": "yes/no", "description": "Whether prevalent hypertension is recorded."},
    "diabetes": {"label": "Diabetes", "short_label": "Diabetes", "category": "Medical history", "unit": "yes/no", "description": "Whether diabetes is recorded in the dataset."},
    "totChol": {"label": "Total cholesterol", "short_label": "Cholesterol", "category": "Clinical measures", "unit": "mg/dL", "description": "Total cholesterol measurement recorded in the source dataset."},
    "sysBP": {"label": "Systolic blood pressure", "short_label": "Systolic BP", "category": "Clinical measures", "unit": "mmHg", "description": "Systolic blood pressure measurement recorded in the source dataset."},
    "diaBP": {"label": "Diastolic blood pressure", "short_label": "Diastolic BP", "category": "Clinical measures", "unit": "mmHg", "description": "Diastolic blood pressure measurement recorded in the source dataset."},
    "BMI": {"label": "Body mass index", "short_label": "BMI", "category": "Clinical measures", "unit": "kg/m²", "description": "Body mass index measurement recorded in the source dataset."},
    "heartRate": {"label": "Resting heart rate", "short_label": "Heart rate", "category": "Clinical measures", "unit": "bpm", "description": "Resting heart rate recorded in beats per minute."},
    "glucose": {"label": "Fasting glucose", "short_label": "Glucose", "category": "Clinical measures", "unit": "mg/dL", "description": "Glucose measurement recorded in the source dataset."},
}
VALUE_ONE_LABEL = {
    "gender": "Male", "currentSmoker": "Current smoker", "BPMeds": "Medication recorded",
    "prevalentStroke": "Previous stroke recorded", "prevalentHyp": "Hypertension recorded",
    "diabetes": "Diabetes recorded",
}


def _fdr_bh(p_values: list[float]) -> list[float]:
    """Benjamini–Hochberg adjusted p-values, in original order."""
    count = len(p_values)
    if not count:
        return []
    ordered = sorted(range(count), key=p_values.__getitem__)
    adjusted = [1.0] * count
    running_min = 1.0
    for rank_index in range(count - 1, -1, -1):
        original_index = ordered[rank_index]
        rank = rank_index + 1
        running_min = min(running_min, p_values[original_index] * count / rank)
        adjusted[original_index] = min(1.0, running_min)
    return adjusted


def _stats(series: pd.Series, feature: str) -> dict[str, Any]:
    values = series.dropna().astype(float)
    result: dict[str, Any] = {
        "observations": int(values.size), "missing": int(series.isna().sum()),
        "mean": float(values.mean()) if len(values) else None,
        "median": float(values.median()) if len(values) else None,
        "minimum": float(values.min()) if len(values) else None,
        "maximum": float(values.max()) if len(values) else None,
    }
    if feature in VALUE_ONE_LABEL and len(values):
        result["value_one_label"] = VALUE_ONE_LABEL[feature]
        result["value_one_count"] = int((values == 1).sum())
        result["value_one_percent"] = float((values == 1).mean() * 100)
    return result


def build_risk_network(frame: pd.DataFrame, dataset_name: str = "framingham.csv") -> dict[str, Any]:
    """Build a graph from predictors only; pairwise rows with missing values are omitted."""
    missing = sorted(set(FEATURES) - set(frame.columns))
    if missing:
        raise ValueError("Dataset is missing required predictor columns: " + ", ".join(missing))

    predictors = frame.loc[:, FEATURES].apply(pd.to_numeric, errors="coerce")
    graph = nx.Graph() if nx is not None else None
    node_payload: dict[str, dict[str, Any]] = {}
    edge_payload: list[dict[str, Any]] = []
    for feature in FEATURES:
        info = FEATURE_INFO[feature]
        attrs = {**info, "statistics": _stats(predictors[feature], feature)}
        node_payload[feature] = attrs
        if graph is not None:
            graph.add_node(feature, **attrs)

    tested: list[tuple[str, str, float, float, int]] = []
    for first, second in combinations(FEATURES, 2):
        pair = predictors[[first, second]].dropna()
        n = len(pair)
        if n < MIN_PAIRWISE_N:
            continue
        if pair[first].nunique(dropna=True) < 2 or pair[second].nunique(dropna=True) < 2:
            continue
        correlation, p_value = spearmanr(pair[first].to_numpy(), pair[second].to_numpy())
        if not np.isfinite(correlation) or not np.isfinite(p_value):
            continue
        tested.append((first, second, float(correlation), float(p_value), n))

    q_values = _fdr_bh([item[3] for item in tested])
    for (first, second, correlation, p_value, n), q_value in zip(tested, q_values):
        if q_value > 0.05:
            continue
        attrs = {"correlation": correlation, "strength": abs(correlation),
                 "p_value": p_value, "q_value": q_value, "sample_size": n, "method": METHOD}
        edge_payload.append({"source": first, "target": second, **attrs})
        if graph is not None:
            graph.add_edge(first, second, **attrs)

    if graph is None:
        nodes = [{"id": node, **attrs} for node, attrs in node_payload.items()]
        edges = edge_payload
    else:
        nodes = [{"id": node, **attrs} for node, attrs in graph.nodes(data=True)]
        edges = [{"source": source, "target": target, **attrs}
                 for source, target, attrs in graph.edges(data=True)]
    edges.sort(key=lambda edge: edge["strength"], reverse=True)
    cleaned_rows = len(predictors)
    return {
        "source_file": dataset_name, "rows": cleaned_rows,
        "feature_count": len(nodes), "target_excluded": True,
        "minimum_pairwise_observations": MIN_PAIRWISE_N,
        "association_method": METHOD, "p_value_method": P_VALUE_METHOD,
        "multiple_testing": FDR_METHOD,
        "tested_pair_count": len(tested), "edge_count": len(edges),
        "nodes": nodes, "edges": edges,
    }


@lru_cache(maxsize=2)
def _build_cached(dataset_path: str, modified_ns: int) -> dict[str, Any]:
    path = Path(dataset_path)
    frame, _ = load_and_clean(path)
    return build_risk_network(frame, path.name)


def get_risk_network() -> dict[str, Any]:
    """Read the configured dataset and cache associations until its file changes."""
    if not DATASET.is_file():
        raise FileNotFoundError(f"Dataset not found: {DATASET.name}")
    stat = DATASET.stat()
    return _build_cached(str(DATASET), stat.st_mtime_ns)
