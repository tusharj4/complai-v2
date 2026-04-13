import re
import logging

logger = logging.getLogger(__name__)

# Model state - loaded lazily
_model = None
_vectorizer = None
_model_version = None


def _load_model():
    """Lazy-load the ML model and vectorizer."""
    global _model, _vectorizer, _model_version
    if _model is not None:
        return

    try:
        import joblib
        _model = joblib.load("models/xgboost_classifier_v1.pkl")
        _vectorizer = joblib.load("models/tfidf_vectorizer_v1.pkl")
        _model_version = "v1"
        logger.info("Classifier model loaded successfully")
    except FileNotFoundError:
        logger.warning("Classifier model not found - using rule-based fallback")
    except Exception as e:
        logger.error(f"Failed to load classifier model: {e}")


def find_flags(text: str, document_type: str = None) -> list:
    """Extract compliance flags from document text using rule-based patterns."""
    flags = []

    if re.search(r"late|overdue|penalty|delayed", text, re.I):
        flags.append("late_filing")

    if re.search(r"attachment|annexure.*pending|missing|to be attached", text, re.I):
        flags.append("missing_attachment")

    if re.search(r"discrepancy|mismatch|variance|reconcil", text, re.I):
        flags.append("reconciliation_needed")

    if re.search(r"nil\s+return|zero\s+return", text, re.I):
        flags.append("nil_return")

    if re.search(r"notice|demand|show\s+cause", text, re.I):
        flags.append("notice_received")

    if re.search(r"revise|amendment|correction", text, re.I):
        flags.append("revision_filed")

    return flags


def classify_document_text(text: str, metadata: dict = None) -> dict:
    """
    Classify extracted text as compliant/non-compliant.
    Uses ML model if available, otherwise falls back to rule-based classification.
    Returns dict with status, confidence, flags.
    """
    metadata = metadata or {}
    flags = find_flags(text, metadata.get("document_type"))

    _load_model()

    if _model is not None and _vectorizer is not None:
        # ML-based classification
        X = _vectorizer.transform([text])
        prediction = _model.predict(X)[0]
        probabilities = _model.predict_proba(X)[0]
        confidence = float(max(probabilities))

        if confidence < 0.70:
            status = "review_required"
        elif prediction == 0:
            status = "compliant"
        else:
            status = "non_compliant"

        return {
            "status": status,
            "confidence": confidence,
            "flags": flags,
            "model_version": _model_version,
            "method": "ml",
        }
    else:
        # Rule-based fallback
        return _rule_based_classify(text, flags, metadata)


def _rule_based_classify(text: str, flags: list, metadata: dict) -> dict:
    """Rule-based classification when ML model is not available."""
    risk_score = 0.0

    # High-risk flags
    if "late_filing" in flags:
        risk_score += 0.3
    if "notice_received" in flags:
        risk_score += 0.4
    if "missing_attachment" in flags:
        risk_score += 0.2
    if "reconciliation_needed" in flags:
        risk_score += 0.2

    # Status keywords
    text_lower = text.lower()
    if "filed" in text_lower and "late" not in text_lower:
        risk_score -= 0.2
    if "compliant" in text_lower:
        risk_score -= 0.3
    if "non-compliant" in text_lower or "non compliant" in text_lower:
        risk_score += 0.4

    # Clamp to [0, 1]
    risk_score = max(0.0, min(1.0, risk_score))
    confidence = 1.0 - abs(risk_score - 0.5) * 2  # Higher near extremes

    if risk_score > 0.5:
        status = "non_compliant"
        confidence = 0.5 + risk_score * 0.4
    elif risk_score > 0.3:
        status = "review_required"
        confidence = 0.5
    else:
        status = "compliant"
        confidence = 0.7 + (0.3 - risk_score)

    return {
        "status": status,
        "confidence": round(min(confidence, 0.99), 4),
        "flags": flags,
        "model_version": "rule_based_v1",
        "method": "rule_based",
    }
