"""Train and evaluate ML, tabular MLP, and a validation-weighted hybrid model."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score, roc_curve)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from src.data_processing import BINARY, FEATURES, NUMERIC, TARGET, load_and_clean, save_report
from src.deep_model import TabularMLP
from src.hybrid import hybrid_predict

ROOT = Path(__file__).resolve().parents[1]


def build_preprocessor(scale_numeric: bool = True) -> ColumnTransformer:
    numeric = [("imputer", SimpleImputer(strategy="median"))]
    if scale_numeric:
        numeric.append(("scaler", StandardScaler()))
    categorical = Pipeline([("imputer", SimpleImputer(strategy="most_frequent")),
                            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))])
    return ColumnTransformer([("numeric", Pipeline(numeric), NUMERIC), ("categorical", categorical, BINARY)])


def _models(y_train: pd.Series) -> dict:
    return {
        "Logistic Regression": Pipeline([("preprocess", build_preprocessor(True)),
            ("model", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42))]),
        "Random Forest": Pipeline([("preprocess", build_preprocessor(False)),
            ("model", RandomForestClassifier(n_estimators=350, min_samples_leaf=3,
                 class_weight="balanced_subsample",
                 max_features="sqrt", n_jobs=1, random_state=42))]),
        "XGBoost": Pipeline([("preprocess", build_preprocessor(False)),
            ("model", XGBClassifier(n_estimators=300, max_depth=3, learning_rate=.04,
                subsample=.85, colsample_bytree=.85, reg_lambda=2, objective="binary:logistic",
                eval_metric="logloss", scale_pos_weight=float((y_train == 0).sum() / max((y_train == 1).sum(), 1)),
                n_jobs=1, random_state=42))]),
    }


def _metrics(y_true, probability, threshold):
    prediction = (np.asarray(probability) >= threshold).astype(int)
    fpr, tpr, _ = roc_curve(y_true, probability)
    return {"accuracy": float(accuracy_score(y_true, prediction)),
            "precision": float(precision_score(y_true, prediction, zero_division=0)),
            "recall": float(recall_score(y_true, prediction, zero_division=0)),
            "f1": float(f1_score(y_true, prediction, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_true, probability)),
            "confusion_matrix": confusion_matrix(y_true, prediction, labels=[0, 1]).tolist(),
            "roc_curve": {"fpr": fpr.tolist(), "tpr": tpr.tolist()}}


def _selection_score(metrics):
    return .5 * metrics["roc_auc"] + .3 * metrics["recall"] + .2 * metrics["f1"]


def train(dataset: Path, threshold: float = .5, reports_dir: Path = ROOT / "reports",
          models_dir: Path = ROOT / "models") -> dict:
    frame, data_report = load_and_clean(dataset)
    reports_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    save_report(data_report, reports_dir / "dataset_report.json")
    X, y = frame[FEATURES], frame[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=.2, stratify=y, random_state=42)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scoring = {"roc_auc": "roc_auc", "recall": "recall", "f1": "f1", "accuracy": "accuracy", "precision": "precision"}
    pipelines, cv_results = {}, {}
    for name, pipeline in _models(y_train).items():
        print(f"Cross-validating {name}...")
        cv_result = cross_validate(pipeline, X_train, y_train, cv=cv, scoring=scoring, n_jobs=1)
        cv_results[name] = {"cv_mean": {metric: float(np.mean(cv_result[f"test_{metric}"])) for metric in scoring},
                            "cv_std": {metric: float(np.std(cv_result[f"test_{metric}"])) for metric in scoring}}
        pipeline.fit(X_train, y_train)
        pipelines[name] = pipeline

    # Select a tree model as the ML branch using only training CV results.
    tree_name = max(["Random Forest", "XGBoost"], key=lambda n: _selection_score(cv_results[n]["cv_mean"]))
    # Reserve part of the training partition to calibrate alpha. Never use the final test split here.
    X_fit, X_val, y_fit, y_val = train_test_split(X_train, y_train, test_size=.2, stratify=y_train, random_state=43)
    calibration_tree = _models(y_train)[tree_name]
    calibration_tree.fit(X_fit, y_fit)
    calibration_preprocessor = build_preprocessor(True).fit(X_fit)
    calibration_mlp = TabularMLP(random_state=42).fit(calibration_preprocessor.transform(X_fit), y_fit)
    p_ml_val = calibration_tree.predict_proba(X_val)[:, 1]
    p_dl_val = calibration_mlp.predict_proba(calibration_preprocessor.transform(X_val))[:, 1]
    alpha_candidates = np.linspace(0, 1, 21)
    alpha_scores = []
    for alpha in alpha_candidates:
        prob = alpha * p_ml_val + (1 - alpha) * p_dl_val
        alpha_scores.append(_selection_score(_metrics(y_val, prob, threshold)))
    alpha = float(alpha_candidates[int(np.argmax(alpha_scores))])
    calibration_score = float(max(alpha_scores))

    # Train final MLP on the complete training partition; its own validation split controls early stopping.
    mlp_preprocessor = build_preprocessor(True).fit(X_train)
    mlp_model = TabularMLP(random_state=42).fit(mlp_preprocessor.transform(X_train), y_train)
    bundle = {"models": pipelines, "tree_model": pipelines[tree_name], "tree_model_name": tree_name,
              "mlp_preprocessor": mlp_preprocessor, "mlp_model": mlp_model,
              "alpha": alpha, "shap_background": X_train.sample(min(40, len(X_train)), random_state=42).to_numpy().tolist()}
    p_test = {name: model.predict_proba(X_test)[:, 1] for name, model in pipelines.items()}
    p_dl = mlp_model.predict_proba(mlp_preprocessor.transform(X_test))[:, 1]
    p_hybrid = hybrid_predict(X_test, bundle)
    probabilities = {**p_test, "Deep Neural Network": p_dl, "Hybrid AI": p_hybrid}
    metrics = {name: _metrics(y_test, prob, threshold) for name, prob in probabilities.items()}
    best_model = max(metrics, key=lambda name: _selection_score(metrics[name]))
    metrics_comparison = {"hybrid_best_by_composite": best_model == "Hybrid AI",
                          "best_model_by_composite": best_model,
                          "hybrid_roc_auc_delta_vs_best_individual": float(metrics["Hybrid AI"]["roc_auc"] - max(metrics[n]["roc_auc"] for n in metrics if n != "Hybrid AI")),
                          "hybrid_f1_delta_vs_best_individual": float(metrics["Hybrid AI"]["f1"] - max(metrics[n]["f1"] for n in metrics if n != "Hybrid AI"))}
    # Model-agnostic Permutation SHAP explains the final weighted hybrid function over raw dataset predictors.
    try:
        background = pd.DataFrame(bundle["shap_background"], columns=FEATURES)
        explainer = shap.Explainer(lambda a: hybrid_predict(pd.DataFrame(a, columns=FEATURES), bundle),
                                   shap.maskers.Independent(background), feature_names=FEATURES, algorithm="permutation")
        explanation_rows = X_train.sample(min(120, len(X_train)), random_state=42)
        shap_values = explainer(explanation_rows.to_numpy(dtype=float), max_evals=2 * len(FEATURES) + 1)
        values = np.asarray(shap_values.values).reshape(len(explanation_rows), len(FEATURES))
        global_importance = np.abs(values).mean(axis=0)
        global_data = sorted([{"feature": f, "importance": float(v)} for f, v in zip(FEATURES, global_importance)],
                             key=lambda item: item["importance"], reverse=True)
        shap_data = {"values": values.tolist(), "feature_values": explanation_rows.to_numpy(dtype=float).tolist(),
                     "feature_names": FEATURES, "base_values": np.asarray(shap_values.base_values).reshape(-1).tolist(),
                     "global_importance": global_data}
        bundle["shap_background"] = background.to_numpy(dtype=float).tolist()
    except Exception as exc:
        raise RuntimeError(f"Hybrid SHAP generation failed; no explainability artifacts were saved: {exc}") from exc

    for name, model_metrics in metrics.items():
        print(f"{name}: AUC={model_metrics['roc_auc']:.3f}, recall={model_metrics['recall']:.3f}, F1={model_metrics['f1']:.3f}")
    print(f"Selected tree branch: {tree_name}; validation-calibrated alpha={alpha:.2f}; best overall: {best_model}")
    metadata = {
        "title": "Explainable AI Engine for Early Cardiovascular Disease Risk Detection and Clinical Decision Support",
        "selected_model": "Hybrid AI", "best_model_by_composite": best_model,
        "model_version": "2.0.0", "dataset_version": {"filename": Path(dataset).name, "rows_after_cleaning": len(frame)},
        "hybrid_strategy": "Validation-calibrated weighted ensemble: alpha × selected tree probability + (1-alpha) × MLP probability",
        "tree_component": tree_name, "alpha": alpha, "alpha_calibration_score": calibration_score,
        "component_selection_rule": "Tree branch selected by 5-fold training CV composite: 0.50 ROC-AUC + 0.30 recall + 0.20 F1",
        "alpha_selection_rule": "Grid search on a stratified calibration split from training data only, using the same composite metric",
        "threshold": threshold, "risk_thresholds": {"low_max_exclusive": .10, "moderate_max_exclusive": .20},
        "risk_threshold_note": "Configurable academic model-based categories; not clinically validated.",
        "random_seed": 42, "test_size": .2, "cv_folds": 5, "training_rows": len(X_train), "test_rows": len(X_test),
        "features": FEATURES, "target": TARGET, "metrics": metrics, "comparison": metrics_comparison,
        "cv_results": cv_results, "mlp_best_epoch": int(mlp_model.best_epoch_ or 0),
        "mlp_architecture": "Scikit-learn MLPClassifier with 128/64 hidden layers, ReLU, Adam, early stopping and training-only class oversampling",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(), "dataset_report": "reports/dataset_report.json",
        "global_shap": global_data, "xai_method": "SHAP PermutationExplainer applied to the final hybrid_predict function",
        "xai_note": "SHAP describes model contribution, not medical causation.",
    }
    # Persist individual components and the combined inference bundle.
    for name, filename in [("Logistic Regression", "logistic_model.joblib"), ("Random Forest", "random_forest_model.joblib"), ("XGBoost", "xgboost_model.joblib")]:
        joblib.dump(pipelines[name], models_dir / filename)
    joblib.dump(mlp_model, models_dir / "mlp_model.joblib")
    joblib.dump(bundle, models_dir / "hybrid_model.joblib")
    joblib.dump(mlp_preprocessor, models_dir / "preprocessing_pipeline.joblib")
    joblib.dump(shap_data, models_dir / "shap_config.joblib")
    # Compatibility alias for earlier UI versions; the hybrid app reads hybrid_model.joblib.
    joblib.dump(bundle, models_dir / "best_model.joblib")
    (models_dir / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Artifacts saved to {models_dir}")
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "data/raw/framingham.csv")
    parser.add_argument("--threshold", type=float, default=.5)
    args = parser.parse_args()
    train(args.data, args.threshold)


if __name__ == "__main__":
    main()
