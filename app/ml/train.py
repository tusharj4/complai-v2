"""
XGBoost Classifier Training Pipeline for CompLai compliance documents.

Usage:
    python -m app.ml.train --data training-data/labeled_documents.csv --output models/

Requires: xgboost, scikit-learn, pandas, joblib
"""

import re
import os
import logging
import numpy as np
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, f1_score, precision_score, recall_score

logger = logging.getLogger(__name__)


def extract_features(text: str, metadata: dict = None) -> dict:
    """Extract domain-specific features from compliance document text."""
    metadata = metadata or {}
    return {
        "length": len(text),
        "has_gstin": bool(re.search(r"\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}", text)),
        "has_invoice_numbers": len(re.findall(r"INV-\d+", text, re.I)),
        "has_amount_fields": len(re.findall(r"₹|INR|\$", text)),
        "has_date_fields": len(re.findall(r"\d{2}/\d{2}/\d{4}", text)),
        "filing_period_mentioned": 1 if metadata.get("filing_period", "") in text else 0,
        "has_penalty_keywords": len(re.findall(r"penalty|late|overdue|notice", text, re.I)),
        "has_compliance_keywords": len(re.findall(r"filed|compliant|submitted|approved", text, re.I)),
    }


def generate_synthetic_training_data(n_samples: int = 200) -> tuple:
    """Generate synthetic training data for initial model training."""
    np.random.seed(42)
    texts = []
    labels = []

    # Compliant documents
    compliant_templates = [
        "GSTR-1 for period {period} filed on time. All invoices matched. Total taxable value INR {amount}.",
        "Annual return filed successfully. No discrepancies found. All attachments present.",
        "GST return submitted before due date. GSTIN {gstin} verified. Reconciliation complete.",
        "Filing status: Submitted. Period: {period}. All sections complete. No penalties applicable.",
        "Return accepted by portal. Reference number generated. Filing date within deadline.",
    ]

    # Non-compliant documents
    non_compliant_templates = [
        "NOTICE: Late filing penalty of INR {amount} imposed. Filing overdue by {days} days.",
        "DISCREPANCY: Mismatch between GSTR-1 and GSTR-3B. Reconciliation needed urgently.",
        "WARNING: Missing attachment - Annexure B not submitted. Show cause notice issued.",
        "Return filing delayed. Penalty notice received. Amount due: INR {amount}. Overdue {days} days.",
        "Non-compliant status. Multiple discrepancies found. Late filing. Missing documents.",
    ]

    periods = ["Q1_2024", "Q2_2024", "Q3_2024", "Q4_2024", "Jan_2024", "Feb_2024"]
    gstins = ["27AABAA0000A1Z5", "29BBBBB1111B2Z3", "07CCCCC2222C3Z1"]

    for i in range(n_samples):
        if i < n_samples // 2:
            template = np.random.choice(compliant_templates)
            label = 0  # compliant
        else:
            template = np.random.choice(non_compliant_templates)
            label = 1  # non-compliant

        text = template.format(
            period=np.random.choice(periods),
            amount=np.random.randint(1000, 500000),
            gstin=np.random.choice(gstins),
            days=np.random.randint(1, 90),
        )
        # Add some noise
        text += " " + " ".join(np.random.choice(
            ["invoice", "tax", "GST", "return", "filing", "amount", "period", "status", "date"],
            size=np.random.randint(3, 10),
        ))

        texts.append(text)
        labels.append(label)

    return texts, labels


def train_classifier(csv_path: str = None, output_dir: str = "models") -> bool:
    """
    Train XGBoost classifier on labeled compliance documents.
    If no CSV provided, uses synthetic data for initial training.
    """
    os.makedirs(output_dir, exist_ok=True)

    if csv_path and os.path.exists(csv_path):
        logger.info(f"Loading training data from {csv_path}")
        df = pd.read_csv(csv_path)
        texts = df["text"].tolist()
        labels = [1 if label == "non_compliant" else 0 for label in df["label"]]
    else:
        logger.info("No training data CSV found. Generating synthetic data...")
        texts, labels = generate_synthetic_training_data(200)

    logger.info(f"Training with {len(texts)} samples")

    # Vectorize text
    vectorizer = TfidfVectorizer(
        max_features=500,
        ngram_range=(1, 2),
        lowercase=True,
        stop_words="english",
    )
    X = vectorizer.fit_transform(texts)
    y = np.array(labels)

    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Train XGBoost
    import xgboost as xgb

    model = xgb.XGBClassifier(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="logloss",
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=10,
    )

    # Evaluate
    y_pred = model.predict(X_test)

    report = classification_report(y_test, y_pred)
    logger.info(f"\n{report}")

    f1 = f1_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)

    logger.info(f"F1: {f1:.4f} | Precision: {precision:.4f} | Recall: {recall:.4f}")

    # Save model
    model_path = os.path.join(output_dir, "xgboost_classifier_v1.pkl")
    vectorizer_path = os.path.join(output_dir, "tfidf_vectorizer_v1.pkl")

    joblib.dump(model, model_path)
    joblib.dump(vectorizer, vectorizer_path)
    logger.info(f"Model saved to {output_dir}")

    return f1 > 0.90


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    parser = argparse.ArgumentParser(description="Train CompLai compliance classifier")
    parser.add_argument("--data", default=None, help="Path to labeled CSV")
    parser.add_argument("--output", default="models", help="Output directory")
    args = parser.parse_args()

    success = train_classifier(args.data, args.output)
    print(f"\nTraining {'succeeded' if success else 'completed (F1 below threshold)'}")
