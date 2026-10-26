"""A reproducible, class-balanced tabular neural network using scikit-learn."""
from __future__ import annotations

import numpy as np
from sklearn.neural_network import MLPClassifier


class TabularMLP:
    """Sklearn-style MLP with training-only random oversampling and early stopping."""

    def __init__(self, epochs: int = 100, patience: int = 12, batch_size: int = 128,
                 learning_rate: float = 1e-3, random_state: int = 42):
        self.epochs = epochs
        self.patience = patience
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.random_state = random_state
        self.model = None
        self.n_features_in_ = None
        self.best_epoch_ = None

    def fit(self, X, y):
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.int64).reshape(-1)
        if X.ndim != 2 or X.shape[0] != y.shape[0]:
            raise ValueError("MLP expects a 2D feature array aligned with the target.")
        self.n_features_in_ = X.shape[1]
        rng = np.random.default_rng(self.random_state)
        classes, counts = np.unique(y, return_counts=True)
        if len(classes) != 2:
            raise ValueError("MLP requires both target classes.")
        target_count = int(counts.max())
        sampled = [np.flatnonzero(y == label) for label in classes]
        indices = np.concatenate([
            np.concatenate([rows, rng.choice(rows, target_count - len(rows), replace=True)])
            if len(rows) < target_count else rows
            for rows in sampled
        ])
        rng.shuffle(indices)
        self.model = MLPClassifier(
            hidden_layer_sizes=(128, 64), activation="relu", solver="adam",
            alpha=1e-4, batch_size=self.batch_size, learning_rate_init=self.learning_rate,
            max_iter=self.epochs, early_stopping=True, validation_fraction=.15,
            n_iter_no_change=self.patience, random_state=self.random_state,
        ).fit(X[indices], y[indices])
        self.best_epoch_ = int(self.model.n_iter_)
        return self

    def predict_proba(self, X):
        if self.model is None:
            raise RuntimeError("The saved MLP is unavailable or has not been fitted.")
        return self.model.predict_proba(np.asarray(X, dtype=np.float64))
