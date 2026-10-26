"""Convenience entry point to print recorded holdout and cross-validation metrics."""
import json
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "models/model_metadata.json"
if not path.exists():
    raise SystemExit("No evaluation results yet. Train using python -m src.train --data data/raw/framingham.csv")
meta = json.loads(path.read_text(encoding="utf-8"))
print(json.dumps({"selected_model": meta["selected_model"], "metrics": meta["metrics"]}, indent=2))
