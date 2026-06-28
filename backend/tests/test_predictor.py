"""Tests for training, persistence, and prediction mechanics."""
import random
from datetime import date, timedelta
from types import SimpleNamespace

from app import predictor


def make_matches(n=600, seed=0):
    """Synthetic matches with a latent strength signal (stronger team scores more)."""
    rng = random.Random(seed)
    strength = {f"T{i}": i for i in range(8)}  # 0..7
    names = list(strength)
    start = date(2000, 1, 1)
    out = []
    for k in range(n):
        h, a = rng.sample(names, 2)
        hs = rng.randint(0, 1 + strength[h] // 2)
        as_ = rng.randint(0, 1 + strength[a] // 2)
        out.append(
            SimpleNamespace(
                date=start + timedelta(days=k),
                home_team=h,
                away_team=a,
                home_score=hs,
                away_score=as_,
                tournament="Friendly",
                neutral=True,
            )
        )
    return out


def test_train_persist_predict(tmp_path, monkeypatch):
    monkeypatch.setattr(predictor, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(predictor, "MODEL_PATH", tmp_path / "model.joblib")
    monkeypatch.setattr(predictor, "METRICS_PATH", tmp_path / "metrics.json")
    predictor._MODEL = None

    metrics = predictor.train(make_matches(), min_history=3)
    assert {"accuracy", "log_loss", "n_samples", "classes", "features"} <= metrics.keys()
    assert (tmp_path / "model.joblib").exists()
    assert (tmp_path / "metrics.json").exists()

    # Reload from disk and predict.
    predictor._MODEL = None
    model = predictor.load_model(force_reload=True)
    feats = {name: 0.0 for name in predictor.FEATURE_NAMES}
    feats["elo_diff"] = 200.0
    feats["home_advantage"] = 1.0
    probs = predictor.predict_features(model, feats)

    assert set(probs) == {"home_win", "draw", "away_win"}
    assert abs(sum(probs.values()) - 1.0) < 0.02


def test_predict_favours_stronger_side(tmp_path, monkeypatch):
    monkeypatch.setattr(predictor, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(predictor, "MODEL_PATH", tmp_path / "model.joblib")
    monkeypatch.setattr(predictor, "METRICS_PATH", tmp_path / "metrics.json")
    predictor._MODEL = None
    predictor.train(make_matches(), min_history=3)
    model = predictor.load_model(force_reload=True)

    strong = {name: 0.0 for name in predictor.FEATURE_NAMES}
    strong["elo_diff"] = 400.0
    weak = dict(strong)
    weak["elo_diff"] = -400.0
    # A big positive Elo edge should give the home side a higher win prob.
    assert predictor.predict_features(model, strong)["home_win"] > \
        predictor.predict_features(model, weak)["home_win"]
