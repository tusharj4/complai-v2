from uuid import uuid4
from app.models import Company


def test_create_company(test_db):
    company = Company(
        id=uuid4(),
        partner_id=uuid4(),
        name="Test Company Pvt Ltd",
        gst_id="27AABAA0000A1Z5",
    )
    test_db.add(company)
    test_db.commit()

    retrieved = test_db.query(Company).filter_by(gst_id="27AABAA0000A1Z5").first()
    assert retrieved is not None
    assert retrieved.name == "Test Company Pvt Ltd"


def test_company_duplicate_gst_raises(test_db):
    partner_id = uuid4()
    company1 = Company(id=uuid4(), partner_id=partner_id, name="Company A", gst_id="27AABAA0000A1Z5")
    test_db.add(company1)
    test_db.commit()

    company2 = Company(id=uuid4(), partner_id=partner_id, name="Company B", gst_id="27AABAA0000A1Z5")
    test_db.add(company2)
    try:
        test_db.commit()
        assert False, "Should have raised IntegrityError"
    except Exception:
        test_db.rollback()
