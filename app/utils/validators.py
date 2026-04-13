import re


def validate_gst_id(gst_id: str) -> bool:
    """Validate Indian GST ID format (15 characters)."""
    pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
    return bool(re.match(pattern, gst_id))


def validate_pan(pan: str) -> bool:
    """Validate Indian PAN format (10 characters)."""
    pattern = r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$"
    return bool(re.match(pattern, pan))
