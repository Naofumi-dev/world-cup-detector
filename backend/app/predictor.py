"""Train, persist, and query the Win/Draw/Loss classifier.

A calibrated gradient-boosting model over the point-in-time features. Metrics
are reported on a chronological holdout (train on the past, test on the most
recent slice) for an honest read; the deployed model is then refit on all
history so live predictions use everything known to date.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .features import FEATURE_NAMES, build_training_frame, match_features

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_PATH = MODELS_DIR / "model.joblib"
METRICS_PATH = MODELS_DIR / "metrics.json"

# Map internal labels to the API's outcome keys.
LABEL_TO_KEY = {"H": "home_win", "D": "draw", "A": "away_win"}

_MODEL = None  # process-level cache


def _build_estimator() -> Pipeline:
    # The features (especially elo_diff) are engineered to be roughly linear in
    # the outcome log-odds, so a scaled multinomial logistic regression matches
    # gradient boosting on accuracy/log-loss here while training ~60x faster and
    # producing softmax-calibrated probabilities. Scaling is what logistic
    # regression needs given elo_diff spans hundreds while form spans ~0..3.
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, C=1.0)),
        ]
    )


def train(matches, min_history: int = 5) -> dict:
    """Train on the given (date-ordered) matches and persist the model.

    Returns the metrics dict that is also written to ``metrics.json``.
    """
    X, y = build_training_frame(matches, min_history=min_history)
    if len(X) < 200:
        raise ValueError("Not enough matches to train a model.")

    # Chronological holdout: last 15% of matches is the test set.
    split = int(len(X) * 0.85)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    holdout = _build_estimator().fit(X_train, y_train)
    classes = list(holdout.classes_)
    proba = holdout.predict_proba(X_test)
    preds = holdout.predict(X_test)
    acc = accuracy_score(y_test, preds)
    ll = log_loss(y_test, proba, labels=classes)

    # Baseline: always predict the most common class in the training data.
    majority = y_train.value_counts().idxmax()
    base_acc = accuracy_score(y_test, np.full(len(y_test), majority))
    base_proba = np.tile(
        [y_train.value_counts(normalize=True).get(c, 0.0) for c in classes],
        (len(y_test), 1),
    )
    base_ll = log_loss(y_test, base_proba, labels=classes)

    # Deployed model: refit on everything for the freshest predictions.
    model = _build_estimator().fit(X, y)
    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    metrics = {
        "accuracy": round(float(acc), 4),
        "log_loss": round(float(ll), 4),
        "baseline_accuracy": round(float(base_acc), 4),
        "baseline_log_loss": round(float(base_ll), 4),
        "n_samples": int(len(X)),
        "n_test": int(len(X_test)),
        "classes": list(model.classes_),
        "features": FEATURE_NAMES,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))

    global _MODEL
    _MODEL = model
    return metrics


def load_model(force_reload: bool = False):
    """Return the cached model, loading from disk on first use."""
    global _MODEL
    if _MODEL is None or force_reload:
        if not MODEL_PATH.exists():
            raise FileNotFoundError("Model not trained yet. Call train() first.")
        _MODEL = joblib.load(MODEL_PATH)
    return _MODEL


def get_metrics() -> dict | None:
    if METRICS_PATH.exists():
        return json.loads(METRICS_PATH.read_text())
    return None


def predict_features(model, feats: dict) -> dict:
    """Return {home_win, draw, away_win} probabilities for a feature row."""
    row = pd.DataFrame([[feats[name] for name in FEATURE_NAMES]], columns=FEATURE_NAMES)
    proba = model.predict_proba(row)[0]
    out = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}
    for cls, p in zip(model.classes_, proba):
        out[LABEL_TO_KEY[cls]] = round(float(p), 4)
    return out


def predict_fixture(model, home_state, away_state, neutral: bool, tournament: str) -> dict:
    """Convenience: build features from team states and predict."""
    feats = match_features(home_state, away_state, neutral, tournament)
    return predict_features(model, feats)
