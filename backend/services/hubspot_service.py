"""
HubSpot CRM integration via the v3 REST API (httpx, no SDK needed).

Pipeline & stage constants:
  Pipeline      : Revenue Team SG  (2054237899)
  Refund Requested stage           : 3730777848
  Refunded stage                   : 3695886040

All functions are synchronous — called from FastAPI background tasks
or directly from route handlers.
"""
import os
import re
import httpx
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────
HS_TOKEN  = os.getenv("HUBSPOT_TOKEN", "")
BASE_URL  = "https://api.hubapi.com"

PIPELINE_ID            = "2054237899"
STAGE_REFUND_REQUESTED = "3730777848"
STAGE_REFUNDED         = "3695886040"

# Only deals in these stages are eligible for a refund request
# (payment must have been received before a refund can be initiated)
ELIGIBLE_STAGE_IDS = [
    "3243113153",  # Payment Collected
    "3263420111",  # Closed Won (Automated)
    "3243113154",  # Payment Verified
]

STAGE_LABELS = {
    "3243113153": "Payment Collected",
    "3263420111": "Closed Won (Automated)",
    "3243113154": "Payment Verified",
    STAGE_REFUND_REQUESTED: "Refund Requested",
    STAGE_REFUNDED:         "Refunded",
}


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {HS_TOKEN}",
        "Content-Type":  "application/json",
    }


def extract_deal_id_from_link(url: str) -> str:
    """
    Best-effort extraction of a HubSpot deal's numeric object ID from its URL.
    The BD now types the deal name freely, so this is the only reliable way
    to recover the real deal_id needed for stage/status automation.
    """
    match = re.search(r"/deal/(\d+)", url) or re.search(r"(\d{6,})", url)
    return match.group(1) if match else ""


# ── Deal search ───────────────────────────────────────────────────────────────

def get_deals_for_owner(owner_id: str) -> list[dict]:
    """
    Return deals owned by `owner_id` in the Revenue Team SG pipeline,
    filtered to payment-received stages only (refund only valid after payment).
    Returns a list of {id, name, amount, stage, stage_id} dicts.
    """
    url  = f"{BASE_URL}/crm/v3/objects/deals/search"
    body = {
        "filterGroups": [{
            "filters": [
                {
                    "propertyName": "hubspot_owner_id",
                    "operator":     "EQ",
                    "value":        owner_id,
                },
                {
                    "propertyName": "pipeline",
                    "operator":     "EQ",
                    "value":        PIPELINE_ID,
                },
                {
                    "propertyName": "dealstage",
                    "operator":     "IN",
                    "values":       ELIGIBLE_STAGE_IDS,
                },
            ]
        }],
        "properties": ["dealname", "amount", "total_amount_automated_gst_applied", "dealstage", "hubspot_owner_id"],
        "limit": 100,
        "sorts": [{"propertyName": "createdate", "direction": "DESCENDING"}],
    }

    try:
        resp = httpx.post(url, json=body, headers=_headers(), timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception as exc:
        print(f"[HubSpot] get_deals_for_owner error: {exc}")
        return []

    deals = []
    for r in results:
        props    = r.get("properties", {})
        stage_id = props.get("dealstage") or ""
        # Use GST-applied total if available, fall back to raw amount
        amount_raw = props.get("total_amount_automated_gst_applied") or props.get("amount") or "0"
        try:
            amount_fmt = f"{float(amount_raw):,.2f}"
        except (ValueError, TypeError):
            amount_fmt = amount_raw

        deals.append({
            "id":       r["id"],
            "name":     props.get("dealname") or "(Unnamed Deal)",
            "amount":   amount_fmt,
            "stage":    STAGE_LABELS.get(stage_id, stage_id),
            "stage_id": stage_id,
        })

    return deals


# ── Deal mutations ────────────────────────────────────────────────────────────

# refund_status internal values
STATUS_REQUESTED   = "Requested"
STATUS_UNDER_REVIEW = "Under Review"
STATUS_REJECTED    = "Rejected"


def patch_deal(deal_id: str, properties: dict) -> bool:
    """
    PATCH any set of properties onto an existing deal in one API call.
    Use this for all deal updates — stage changes, refund info, status, etc.
    """
    url = f"{BASE_URL}/crm/v3/objects/deals/{deal_id}"
    try:
        resp = httpx.patch(
            url,
            json={"properties": properties},
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        print(f"[HubSpot] patch_deal error: {exc}")
        return False


def create_partial_refund_deal(
    original_deal_name: str,
    owner_id: str,
    refund_amount: str,
    refund_reason: str,
    partial_products: str,
) -> Optional[str]:
    """
    Create a new deal for a partial refund with all refund properties
    set in a single POST. Returns the new deal's HubSpot ID, or None.
    """
    url  = f"{BASE_URL}/crm/v3/objects/deals"
    name = f"{original_deal_name} - Partial Refund"
    try:
        amount_val = float(refund_amount.replace(",", ""))
    except (ValueError, TypeError):
        amount_val = 0

    body = {
        "properties": {
            "dealname":          name,
            "pipeline":          PIPELINE_ID,
            "dealstage":         STAGE_REFUND_REQUESTED,
            "amount":            str(amount_val),
            "hubspot_owner_id":  owner_id,
            "refund_reason":     refund_reason,
            "refund_type":       "Partial",
            "products_refunded": partial_products,
            "refund_status":     STATUS_REQUESTED,
        }
    }
    try:
        resp = httpx.post(url, json=body, headers=_headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()["id"]
    except Exception as exc:
        print(f"[HubSpot] create_partial_refund_deal error: {exc}")
        return None


# ── File / note attachment ────────────────────────────────────────────────────

def attach_pdf_to_deal(deal_id: str, pdf_path: str, request_id: str) -> bool:
    """
    Upload the signed PDF to HubSpot Files and create a Note engagement
    associated with the deal so the file appears in the deal timeline.
    """
    # Step 1 — upload file
    file_id = _upload_file(pdf_path, request_id)
    if not file_id:
        return False

    # Step 2 — get public URL
    file_url = _get_file_url(file_id)

    # Step 3 — create a note on the deal
    note_body = (
        f"✅ Refund approved. Signed Return & Deposit Agreement attached.\n"
        f"Request ID: {request_id}\n"
        f"File URL: {file_url or '(see HubSpot Files)'}"
    )
    return _create_note(deal_id, note_body)


def _upload_file(pdf_path: str, request_id: str) -> Optional[str]:
    """Upload PDF to HubSpot Files API v3. Returns file ID."""
    url = f"{BASE_URL}/files/v3/files"
    headers = {"Authorization": f"Bearer {HS_TOKEN}"}
    try:
        with open(pdf_path, "rb") as f:
            resp = httpx.post(
                url,
                headers=headers,
                data={
                    "folderPath": "/refund-agreements",
                    "options":    '{"access":"PRIVATE","overwrite":false}',
                },
                files={"file": (f"RDA_{request_id}.pdf", f, "application/pdf")},
                timeout=30,
            )
        resp.raise_for_status()
        return resp.json().get("id")
    except Exception as exc:
        print(f"[HubSpot] _upload_file error: {exc}")
        return None


def _get_file_url(file_id: str) -> Optional[str]:
    url = f"{BASE_URL}/files/v3/files/{file_id}/signed-url"
    try:
        resp = httpx.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        return resp.json().get("url")
    except Exception:
        return None


def _create_note(deal_id: str, body_text: str) -> bool:
    """Create a Note CRM object and associate it with a deal."""
    # 1. Create note
    url  = f"{BASE_URL}/crm/v3/objects/notes"
    note_body = {
        "properties": {
            "hs_note_body":      body_text,
            "hs_timestamp":      _now_ms(),
        }
    }
    try:
        resp = httpx.post(url, json=note_body, headers=_headers(), timeout=10)
        resp.raise_for_status()
        note_id = resp.json()["id"]
    except Exception as exc:
        print(f"[HubSpot] _create_note error: {exc}")
        return False

    # 2. Associate note → deal
    assoc_url = (
        f"{BASE_URL}/crm/v4/objects/notes/{note_id}"
        f"/associations/deals/{deal_id}"
    )
    assoc_body = [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}]
    try:
        resp = httpx.put(assoc_url, json=assoc_body, headers=_headers(), timeout=10)
        resp.raise_for_status()
        return True
    except Exception as exc:
        print(f"[HubSpot] associate note error: {exc}")
        return False


def _now_ms() -> str:
    from datetime import datetime, timezone
    return str(int(datetime.now(timezone.utc).timestamp() * 1000))
