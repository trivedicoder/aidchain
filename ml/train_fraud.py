"""
AidChain — FraudGuard model training.

Trains a Random Forest classifier to flag fraudulent disaster aid claims.
Goal: catch most fraudsters while keeping false positives low (we never
want a real victim wrongly rejected).

Usage:
    python ml/train_fraud.py --data ml/data/claims.csv --output ml/models/fraud_model.pkl
"""

import argparse
import os

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (classification_report, confusion_matrix,
                             roc_auc_score)
from sklearn.model_selection import train_test_split

FEATURES = [
    'age', 'disability', 'dependents', 'income_proxy', 'displaced',
    'in_affected_zone', 'prior_claims_count', 'amount_requested',
    'days_since_disaster',
]


def train(data_path, model_path):
    print(f'Loading data from {data_path}...')
    df = pd.read_csv(data_path)

    X = df[FEATURES]
    y = df['is_fraud']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    print(f'Training Random Forest on {len(X_train):,} claims...')
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=20,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    print('\n=== FraudGuard Evaluation ===')
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    print(classification_report(y_test, y_pred,
                                target_names=['Legitimate', 'Fraud']))
    print(f'ROC-AUC: {roc_auc_score(y_test, y_prob):.4f}')
    print(f'Confusion matrix:\n{confusion_matrix(y_test, y_pred)}')

    print('\n=== Feature Importance ===')
    importance = pd.DataFrame({
        'feature': FEATURES,
        'importance': model.feature_importances_,
    }).sort_values('importance', ascending=False)
    print(importance.to_string(index=False))

    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump({'model': model, 'features': FEATURES}, model_path)
    print(f'\nModel saved to {model_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default='ml/data/claims.csv')
    parser.add_argument('--output', default='ml/models/fraud_model.pkl')
    args = parser.parse_args()
    train(args.data, args.output)
