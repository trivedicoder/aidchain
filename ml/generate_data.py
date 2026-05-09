"""
AidChain — Synthetic Disaster Aid Dataset Generator

Generates realistic disaster relief claim data with embedded patterns for:
1. Fraud detection (~8% of claims contain one of four fraud patterns)
2. Vulnerability scoring (continuous score based on demographics + circumstances)

Usage:
    python ml/generate_data.py --n 50000 --output ml/data/claims.csv
"""

import argparse
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)


def generate_claims(n=50000, fraud_rate=0.08, disaster_date=None):
    """Generate synthetic disaster aid claims with realistic patterns."""
    if disaster_date is None:
        disaster_date = datetime(2026, 5, 1)

    claims = []
    for i in range(n):
        # === Demographics ===
        age = int(np.clip(RNG.normal(45, 18), 18, 95))
        disability = bool(RNG.random() < 0.15)
        dependents = int(np.clip(RNG.poisson(1.2), 0, 8))
        income_proxy = float(RNG.lognormal(mean=10.0, sigma=0.6))  # ~$10k–$80k
        displaced = bool(RNG.random() < 0.40)  # post-disaster, many displaced
        in_affected_zone = bool(RNG.random() < 0.85)  # 85% legitimately in zone
        prior_claims_count = int(RNG.poisson(0.3))

        # === Disaster claim details ===
        days_since = float(np.clip(RNG.exponential(3.0), 0, 30))
        amount_requested = float(np.clip(RNG.lognormal(mean=7.5, sigma=0.7), 100, 50000))

        # === Fraud injection (one of four patterns) ===
        is_fraud = False
        if RNG.random() < fraud_rate:
            is_fraud = True
            fraud_type = RNG.choice(
                ['inflated', 'outside_zone', 'duplicate_identity', 'rapid_fire']
            )
            if fraud_type == 'inflated':
                amount_requested *= float(RNG.uniform(3, 8))
            elif fraud_type == 'outside_zone':
                in_affected_zone = False
            elif fraud_type == 'duplicate_identity':
                prior_claims_count = int(RNG.integers(3, 12))
            elif fraud_type == 'rapid_fire':
                days_since = float(RNG.uniform(0, 0.5))

        # === Vulnerability score (0–1, higher = more vulnerable) ===
        vuln = 0.0
        if age >= 65:
            vuln += 0.25
        if age <= 21:
            vuln += 0.10
        if disability:
            vuln += 0.30
        vuln += min(dependents * 0.05, 0.20)
        if income_proxy < 25000:
            vuln += 0.20
        if displaced:
            vuln += 0.15
        # Add small noise so the model has to actually learn
        vuln = float(np.clip(vuln + RNG.normal(0, 0.05), 0.0, 1.0))

        claim_timestamp = disaster_date + timedelta(days=days_since)

        claims.append({
            'claim_id': f'CLM{i:08d}',
            'age': age,
            'disability': int(disability),
            'dependents': dependents,
            'income_proxy': round(income_proxy, 2),
            'displaced': int(displaced),
            'in_affected_zone': int(in_affected_zone),
            'prior_claims_count': prior_claims_count,
            'amount_requested': round(amount_requested, 2),
            'days_since_disaster': round(days_since, 2),
            'claim_timestamp': claim_timestamp.isoformat(),
            'is_fraud': int(is_fraud),
            'vulnerability_score': round(vuln, 4),
        })

    return pd.DataFrame(claims)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=50000)
    parser.add_argument('--output', type=str, default='ml/data/claims.csv')
    parser.add_argument('--fraud-rate', type=float, default=0.08)
    args = parser.parse_args()

    print(f'Generating {args.n:,} synthetic disaster aid claims...')
    df = generate_claims(n=args.n, fraud_rate=args.fraud_rate)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df.to_csv(args.output, index=False)

    print(f'\nDataset saved to {args.output}')
    print(f'Total claims:        {len(df):,}')
    print(f'Fraud rate:          {df["is_fraud"].mean():.2%}')
    print(f'Mean vulnerability:  {df["vulnerability_score"].mean():.3f}')
    print(f'Mean claim amount:   ${df["amount_requested"].mean():,.0f}')
    print(f'\nSample:')
    print(df.head().to_string())


if __name__ == '__main__':
    main()
