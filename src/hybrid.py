"""Inference and model-agnostic explanation for the final ML + MLP ensemble."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data_processing import FEATURES


def component_probabilities(X, bundle):
    frame = X if isinstance(X, pd.DataFrame) else pd.DataFrame(X, columns=FEATURES)
    ml = {name: float(model.predict_proba(frame)[0, 1]) for name, model in bundle["models"].items()}
    tree_probability = float(bundle["tree_model"].predict_proba(frame)[0, 1])
    transformed = bundle["mlp_preprocessor"].transform(frame)
    dl_probability = float(bundle["mlp_model"].predict_proba(transformed)[0, 1])
    hybrid_probability = float(bundle["alpha"] * tree_probability + (1.0 - bundle["alpha"]) * dl_probability)
    return {"ml": ml, "tree": tree_probability, "dl": dl_probability, "hybrid": hybrid_probability}


def hybrid_predict(X, bundle):
    """Return positive class probabilities for raw feature rows, including single rows."""
    frame = X if isinstance(X, pd.DataFrame) else pd.DataFrame(X, columns=FEATURES)
    tree = bundle["tree_model"].predict_proba(frame)[:, 1]
    mlp_x = bundle["mlp_preprocessor"].transform(frame)
    deep = bundle["mlp_model"].predict_proba(mlp_x)[:, 1]
    return bundle["alpha"] * np.asarray(tree) + (1.0 - bundle["alpha"]) * np.asarray(deep)


def explain_hybrid(row, bundle, metadata, max_evals=None):
    import shap
    frame = row if isinstance(row, pd.DataFrame) else pd.DataFrame([row], columns=FEATURES)
    background = pd.DataFrame(bundle["shap_background"], columns=FEATURES)
    explainer = shap.Explainer(lambda values: hybrid_predict(pd.DataFrame(values, columns=FEATURES), bundle),
                               shap.maskers.Independent(background), feature_names=FEATURES,
                               algorithm="permutation")
    if max_evals is None:
        max_evals = 2 * len(FEATURES) + 1
    explanation = explainer(frame.to_numpy(dtype=float), max_evals=max_evals)
    values = np.asarray(explanation.values).reshape(-1)
    return [{"feature": name, "value": float(frame.iloc[0][name]),
             "contribution": float(value),
             "direction": "increased" if value > 0 else "decreased" if value < 0 else "neutral"}
            for name, value in sorted(zip(FEATURES, values), key=lambda pair: abs(pair[1]), reverse=True)], float(np.asarray(explanation.base_values).reshape(-1)[0])
