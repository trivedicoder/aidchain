"""
AidChain — Two-AI inference pipeline.

This is the core of AidChain. Every claim runs through both AIs simultaneously:
- FraudGuard:    blocks fraudulent claims
- PriorityCare:  prioritizes vulnerable claimants

In production on IBM Z, both inferences happen on the Telum on-chip AI
accelerator, inside the transaction path, in <2ms. Here we mimic that flow
with sklearn models — same pipeline shape, same decision structure.
"""

import os
import time
from typing import Dict

import joblib
import numpy as np

FRAUD_MODEL_PATH = os.environ.get(
    'AIDCHAIN_FRAUD_MODEL', 'ml/models/fraud_model.pkl'
)
VULN_MODEL_PATH = os.environ.get(
    'AIDCHAIN_VULN_MODEL', 'ml/models/vulnerability_model.pkl'
)

# Decision thresholds (tunable)
FRAUD_BLOCK_THRESHOLD = 0.70
VULNERABILITY_PRIORITY_THRESHOLD = 0.60

_fraud_bundle = None
_vuln_bundle = None


def _load_models():
    global _fraud_bundle, _vuln_bundle
    if _fraud_bundle is None:
        if not os.path.exists(FRAUD_MODEL_PATH):
            raise FileNotFoundError(
                f'Fraud model not found at {FRAUD_MODEL_PATH}. '
                'Run: python ml/train_fraud.py'
            )
        _fraud_bundle = joblib.load(FRAUD_MODEL_PATH)
    if _vuln_bundle is None:
        if not os.path.exists(VULN_MODEL_PATH):
            raise FileNotFoundError(
                f'Vulnerability model not found at {VULN_MODEL_PATH}. '
                'Run: python ml/train_vulnerability.py'
            )
        _vuln_bundle = joblib.load(VULN_MODEL_PATH)


def _features_array(claim: Dict, feature_names: list) -> np.ndarray:
    return np.array([[claim[f] for f in feature_names]])


def score(claim: Dict) -> Dict:
    """Run both AIs against a single claim. Returns the full decision."""
    _load_models()
    t0 = time.perf_counter()

    fraud_features = _features_array(claim, _fraud_bundle['features'])
    vuln_features = _features_array(claim, _vuln_bundle['features'])

    fraud_score = float(_fraud_bundle['model'].predict_proba(fraud_features)[0, 1])
    vulnerability_score = float(_vuln_bundle['model'].predict(vuln_features)[0])
    vulnerability_score = max(0.0, min(1.0, vulnerability_score))

    inference_ms = (time.perf_counter() - t0) * 1000

    # Decision logic
    if fraud_score >= FRAUD_BLOCK_THRESHOLD:
        decision = 'rejected'
        reasoning = f'Fraud risk too high ({fraud_score:.2f}). Flagged for review.'
        amount_approved = 0.0
    elif vulnerability_score >= VULNERABILITY_PRIORITY_THRESHOLD:
        decision = 'prioritized'
        reasoning = (f'High vulnerability ({vulnerability_score:.2f}). '
                     f'Priority routing — funds dispatched immediately.')
        amount_approved = float(claim.get('amount_requested', 0))
    else:
        decision = 'approved'
        reasoning = (f'Approved. Fraud risk: {fraud_score:.2f}, '
                     f'Vulnerability: {vulnerability_score:.2f}.')
        amount_approved = float(claim.get('amount_requested', 0))

    return {
        'fraud_score': round(fraud_score, 4),
        'vulnerability_score': round(vulnerability_score, 4),
        'decision': decision,
        'reasoning': reasoning,
        'amount_approved': round(amount_approved, 2),
        'inference_time_ms': round(inference_ms, 3),
    }
