"""Pydantic models for request/response validation."""
from datetime import date
from pydantic import BaseModel, EmailStr, field_validator
from typing import Literal


class RefundRequestIn(BaseModel):
    """Payload the frontend sends when BD submits the form."""
    sales_rep_name:         str
    sales_rep_id:           str
    sales_rep_email:        str
    deal_id:                str
    deal_name:              str
    original_payment_date:  str   # ISO date (YYYY-MM-DD); validated below
    original_payment_info:  str
    hubspot_link:            str
    customer:               str
    bank_name:              str
    account_no:              str
    refund_amount:            str   # keep as string; validated below
    refund_reason:           str
    refund_type:             Literal["full", "partial"]
    partial_products:        str = ""
    products:                 str   # comma-joined list of selected product categories
    invoice_numbers:          str   # e.g. "Invoice Number (PSG): INV-123; Invoice Number (Website): INV-456"
    is_psg_rejected:          str = ""   # "Yes" | "No" | "" (only applicable when PSG products involved)

    @field_validator("refund_amount")
    @classmethod
    def must_be_numeric(cls, v: str) -> str:
        cleaned = v.replace(",", "").strip()
        try:
            float(cleaned)
        except ValueError:
            raise ValueError("refund_amount must be a valid number")
        return v

    @field_validator("original_payment_date")
    @classmethod
    def must_be_valid_date(cls, v: str) -> str:
        try:
            date.fromisoformat(v.strip())
        except ValueError:
            raise ValueError("original_payment_date must be a valid date (YYYY-MM-DD)")
        return v

    @field_validator("hubspot_link")
    @classmethod
    def must_be_url(cls, v: str) -> str:
        if not v.strip().lower().startswith(("http://", "https://")):
            raise ValueError("hubspot_link must be a valid URL")
        return v

    @field_validator("sales_rep_name", "deal_id", "deal_name", "original_payment_info", "customer",
                     "bank_name", "account_no", "refund_reason", "products", "invoice_numbers")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be empty")
        return v


class RefundRequestOut(BaseModel):
    """Response after successful form submission."""
    success:    bool
    request_id: str
    message:    str


class RejectPayload(BaseModel):
    """Body sent when Director submits the rejection form."""
    reason: str

    @field_validator("reason")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Rejection reason is required")
        return v


class DealItem(BaseModel):
    """A HubSpot deal row returned to the frontend dropdown."""
    id:       str
    name:     str
    amount:   str
    stage:    str
    stage_id: str = ""   # raw HubSpot stage ID — used by frontend for card colour
