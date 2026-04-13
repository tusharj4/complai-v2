from app.utils.validators import validate_gst_id, validate_pan


def test_validate_gst_id_valid():
    assert validate_gst_id("27AABAA0000A1Z5") is True


def test_validate_gst_id_invalid():
    assert validate_gst_id("INVALID") is False
    assert validate_gst_id("") is False
    assert validate_gst_id("12345678901234X") is False


def test_validate_pan_valid():
    assert validate_pan("ABCDE1234F") is True


def test_validate_pan_invalid():
    assert validate_pan("INVALID") is False
    assert validate_pan("12345ABCDE") is False
