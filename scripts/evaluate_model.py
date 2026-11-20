"""Reproduce synthetic training and export a real evaluation report."""

import json
import sys
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.intelligence import model_metrics, MODEL, TRAIN, MODEL_VERSION
import joblib

if __name__ == "__main__":
    output = ROOT / "data" / "model_artifacts"
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / (MODEL_VERSION + ".joblib")
    joblib.dump(MODEL, artifact)
    report = {
        **model_metrics(),
        "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "training_array_sha256": hashlib.sha256(TRAIN.tobytes()).hexdigest(),
        "evaluation_seed": 89,
        "split": "independently generated synthetic normal and synthetic abnormal holdout",
        "promotion_status": "demo_only",
        "real_equipment_validation": "not_performed",
    }
    (output / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
