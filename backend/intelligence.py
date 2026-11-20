"""Working local analytics and retrieval; all training data is synthetic.

The hash-vector retriever is deliberately dependency-light, not a semantic
embedding model. Replace it behind this interface after evaluated comparison.
"""

import hashlib
import math
import re
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score

MODEL_VERSION = "synthetic-isolation-forest-v1"
rng = np.random.default_rng(41)
TRAIN = rng.normal([2.15, 65, 5.2, 120], [0.38, 4, 0.35, 9], (1500, 4))
MODEL = IsolationForest(n_estimators=80, contamination=0.04, random_state=41, n_jobs=1).fit(TRAIN)
test_rng = np.random.default_rng(89)
TEST_NORMAL = test_rng.normal([2.15, 65, 5.2, 120], [0.38, 4, 0.35, 9], (300, 4))
TEST_FAULT = test_rng.normal([5.8, 88, 4.0, 88], [0.6, 5, 0.4, 12], (100, 4))
Y = np.r_[np.zeros(300), np.ones(100)]
PRED = (MODEL.predict(np.vstack([TEST_NORMAL, TEST_FAULT])) == -1).astype(int)


def model_metrics():
    return {
        "version": MODEL_VERSION,
        "algorithm": "Isolation Forest",
        "training_samples": 1500,
        "evaluation_samples": 400,
        "precision": round(float(precision_score(Y, PRED)), 3),
        "recall": round(float(recall_score(Y, PRED)), 3),
        "f1": round(float(f1_score(Y, PRED)), 3),
        "false_positives": int(((PRED == 1) & (Y == 0)).sum()),
        "normal_samples": 300,
        "data_type": "Synthetic held-out simulation",
        "seed": 41,
        "limitation": "Synthetic separation validates this demonstration only. It does not establish real equipment fault prediction or remaining useful life.",
    }


def condition(reading, threshold=4.5):
    if not reading or reading.quality != "good":
        return {"health": None, "status": "unknown", "anomaly": False, "anomaly_score": None}
    penalty = max(0, (reading.vibration - 1.6) * 10.8) + max(0, (reading.temperature - 70) * 0.65)
    health = max(8, min(99, round(100 - penalty)))
    status = "critical" if health < 45 else "warning" if health < 75 else "healthy"
    x = [[reading.vibration, reading.temperature, reading.pressure, reading.flow]]
    anomaly = bool(MODEL.predict(x)[0] == -1)
    return {
        "health": health,
        "status": status,
        "anomaly": anomaly,
        "anomaly_score": round(float(-MODEL.score_samples(x)[0]), 3),
        "model_version": MODEL_VERSION,
        "threshold_exceeded": reading.vibration > threshold,
    }


STOP = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "what",
    "how",
    "are",
    "from",
    "should",
    "asset",
    "equipment",
    "please",
    "does",
    "can",
    "you",
    "about",
    "have",
    "into",
    "when",
    "a",
    "to",
    "of",
    "in",
    "is",
    "on",
    "an",
    "it",
}


def tokens(text):
    return [x for x in re.findall(r"[a-z0-9]+", text.lower()) if len(x) > 2 and x not in STOP]


def hash_vector(text):
    vec = np.zeros(256)
    for word in tokens(text):
        h = hashlib.sha256(word.encode()).digest()
        vec[int.from_bytes(h[:2], "big") % 256] += 1 if h[2] % 2 else -1
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


def search_documents(documents, query, limit=5, kind=None):
    q = Counter(tokens(query))
    qv = hash_vector(query)
    results = []
    for doc in documents:
        if kind and doc.kind not in (kind, "All equipment"):
            continue
        for page_no, page in enumerate(doc.pages, 1):
            # Page-aware chunks; preserve the originating page for citations.
            words = page.split()
            for start in range(0, len(words), 150):
                text = " ".join(words[max(0, start - 25) : start + 190])
                terms = Counter(tokens(text))
                overlap = sum(min(n, terms.get(w, 0)) for w, n in q.items())
                if not overlap:
                    continue
                lexical = overlap / max(1, sum(q.values()))
                cosine = max(0, float(np.dot(qv, hash_vector(text))))
                score = lexical * 0.8 + cosine * 0.2
                results.append(
                    {
                        "id": f"{doc.id}:{page_no}:{start}",
                        "document_id": doc.id,
                        "title": doc.title,
                        "page": page_no,
                        "version": doc.version,
                        "text": text,
                        "score": round(score, 3),
                        "kind": doc.kind,
                        "checksum": doc.checksum,
                        "site": doc.site,
                    }
                )
    # Keep a small evidence set without repeated chunks from the same page.
    seen = set()
    out = []
    for row in sorted(results, key=lambda x: x["score"], reverse=True):
        key = (row["checksum"], row["page"])
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
        if len(out) == limit:
            break
    return out


def make_investigation(asset, reading, documents):
    c = condition(reading, asset.threshold)
    evidence = search_documents(
        documents,
        f"{asset.kind} vibration bearing temperature inspection lubrication alignment",
        3,
        asset.kind,
    )
    facts = [
        f"Vibration RMS is {reading.vibration:.2f} mm/s; the configured demonstration limit is {asset.threshold:.1f} mm/s.",
        f"Temperature is {reading.temperature:.1f} °C and discharge pressure is {reading.pressure:.2f} bar.",
        f'The transparent condition index is {c["health"]}/100. This is not a failure probability.',
    ]
    steps = [
        "Verify sensor mounting, data quality and current operating state before interpreting the alert."
    ]
    if evidence:
        steps += [
            "Review the cited demonstration procedure for equipment applicability.",
            "Prepare a qualified technician inspection of lubrication, alignment and bearing condition under the established site procedure.",
            "Record inspection findings before confirming a failure mode or changing the maintenance plan.",
        ]
    else:
        steps += [
            "Obtain an applicable reviewed manual before preparing equipment-specific maintenance steps."
        ]
    return {
        "observations": facts,
        "possible_causes": [
            "Changed operating conditions",
            "Sensor or mounting issue",
            "Mechanical condition requiring inspection",
        ],
        "recommendation": (
            f"Review {asset.tag} condition and prepare a controlled inspection."
            if evidence
            else "Insufficient applicable evidence. A domain reviewer must supply an appropriate procedure."
        ),
        "checklist": steps,
        "evidence": evidence,
        "data_gaps": [
            "No confirmed fault labels or inspection findings are available.",
            "Seed manuals are synthetic demonstration procedures.",
        ],
        "engine": "Evidence workflow · local deterministic mode",
        "model_version": MODEL_VERSION,
        "requires_approval": True,
        "priority": "High" if c["status"] == "critical" else "Medium",
    }
