"""Global and local SHAP utilities used by training and inference."""
from __future__ import annotations

import joblib
import numpy as np
import shap


def explain_global(model, transformed_training_data, feature_names, max_samples=1000):
    estimator = model.named_steps["model"]
    background = shap.sample(transformed_training_data, min(100, len(transformed_training_data)), random_state=42)
    explainer = shap.Explainer(estimator, background, feature_names=feature_names)
    values = explainer(transformed_training_data[:max_samples])
    matrix = values.values[..., 1] if values.values.ndim == 3 else values.values
    return explainer, matrix, np.abs(matrix).mean(axis=0)


def save_global_explanation(path, names, importance):
    joblib.dump(sorted(zip(names, importance), key=lambda item: item[1], reverse=True), path)
