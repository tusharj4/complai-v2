import re
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from typing import Optional, Dict, List
from datetime import datetime


# --- Company Schemas ---

class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    gst_id: str = Field(..., min_length=15, max_length=15)
    filing_deadlines: Optional[Dict[str, str]] = None

    @field_validator("gst_id")
    @classmethod
    def validate_gst_id(cls, v):
        pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid GST ID format")
        return v


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    gst_id: str
    filing_deadlines: Optional[Dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Document Schemas ---

class DocumentCreate(BaseModel):
    company_id: UUID
    document_type: str = Field(..., pattern=r"^(gst_return|itr|mca_filing|bank_statement)$")
    file_path: Optional[str] = None
    metadata: Optional[Dict] = None


class DocumentResponse(BaseModel):
    id: UUID
    company_id: UUID
    document_type: str
    extraction_status: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Auth Schemas ---

class TokenRequest(BaseModel):
    partner_id: str
    user_id: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Manual Override ---

class ManualOverrideRequest(BaseModel):
    new_status: str = Field(..., pattern=r"^(compliant|non_compliant|review_required)$")
    reason: str = Field(..., min_length=5, max_length=1000)


# --- Webhook Schemas ---

class WebhookCreate(BaseModel):
    url: str = Field(..., min_length=10)
    event_types: List[str] = Field(..., min_length=1)
    company_id: Optional[UUID] = None


class WebhookResponse(BaseModel):
    id: UUID
    url: str
    event_types: List[str]
    company_id: Optional[UUID] = None
    is_active: bool = True
