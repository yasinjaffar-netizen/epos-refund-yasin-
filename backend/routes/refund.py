"""
Refund routes:
  GET  /api/deals                    — fetch HubSpot deals for a sales rep
  GET  /api/deals/{deal_id}/products — fetch product line items for a deal
  POST /api/refund-request           — submit a new refund request
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

import database
from models import RefundRequestIn, RefundRequestOut, DealItem
from services import hubspot_service as hs
from services import email_service   as em

router = APIRouter()


# ── GET /api/deals ────────────────────────────────────────────────────────────

@router.get("/api/deals", response_model=list[DealItem])
def get_deals(owner_id: str = Query(..., description="HubSpot owner ID of the sales rep")):
    """Return deals for the given HubSpot owner from the Revenue Team SG pipeline."""
    deals = hs.get_deals_for_owner(owner_id)
    return deals


# ── GET /api/deals/{deal_id}/products ────────────────────────────────────────

# (original_prop, gst_prop, label)
# gst_prop is None for Website which has no GST-applied property in HubSpot.
PRODUCT_PROPS: list[tuple] = [
    ("pos",               "retail_pos_gst_applied",        "Retail POS (Software)"),
    ("fnb_pos",           "fnb_pos_gst_applied",           "FnB POS (Software)"),
    ("website",           None,                             "Website"),
    ("epos_rewards",      "website_gst_applied",           "EPOS Rewards"),
    ("digital_marketing", "digital_marketing_gst_applied", "Digital Marketing"),
    ("hardwarepwp",       "hardware_gst_applied",          "Hardware"),
]
# quantity_of_pos_sold is metadata — not a line-item, so kept separate
QUANTITY_PROP = "quantity_of_pos_sold"


@router.get("/api/deals/{deal_id}/products")
def get_deal_products(deal_id: str):
    """
    Fetch the product fields from a HubSpot deal and return only
    those with a non-zero value as [{name, amount}].
    Amounts shown are GST-applied (post-GST) values.
    Falls back to [] if HubSpot is unreachable (frontend shows free-text).
    """
    import os, httpx

    token = os.getenv("HUBSPOT_TOKEN", "")
    if not token or token.startswith("your_"):
        return []   # HubSpot not configured — frontend will fall back to free-text

    # Collect all prop keys needed (original + gst variants)
    all_props = [QUANTITY_PROP]
    for orig, gst, _ in PRODUCT_PROPS:
        all_props.append(orig)
        if gst:
            all_props.append(gst)

    url = f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}"
    try:
        resp = httpx.get(
            url,
            params={"properties": ",".join(all_props)},
            headers={"Authorization": f"Bearer {token}"},
            timeout=8,
        )
        resp.raise_for_status()
        deal_props = resp.json().get("properties", {})
    except Exception as exc:
        print(f"[HubSpot] get_deal_products error: {exc}")
        return []

    qty = deal_props.get(QUANTITY_PROP) or ""

    products = []
    for orig_key, gst_key, label in PRODUCT_PROPS:
        raw_orig = deal_props.get(orig_key)
        if not raw_orig:
            continue
        try:
            val_orig = float(str(raw_orig).replace(",", ""))
        except ValueError:
            continue
        if val_orig <= 0:
            continue

        # Use GST amount for display; fall back to original if GST prop absent
        raw_display = (deal_props.get(gst_key) if gst_key else None) or raw_orig
        try:
            amount_fmt = f"{float(str(raw_display).replace(',', '')):,.2f}"
        except (ValueError, TypeError):
            amount_fmt = str(raw_orig)

        display_label = label
        if orig_key in ("pos", "fnb_pos") and qty:
            display_label = f"{label} (Qty: {qty})"

        products.append({"name": display_label, "amount": amount_fmt})

    return products


# ── POST /api/refund-request ──────────────────────────────────────────────────

@router.post("/api/refund-request", response_model=RefundRequestOut)
def submit_refund_request(
    body: RefundRequestIn,
    background_tasks: BackgroundTasks,
):
    """
    1. Persist the request to SQLite.
    2. In the background: update HubSpot stage + email the Director.
    """
    now         = datetime.now(timezone.utc).isoformat()
    request_id  = str(uuid.uuid4())
    app_token   = str(uuid.uuid4())
    rej_token   = str(uuid.uuid4())

    row = {
        "id":                     request_id,
        "sales_rep_name":         body.sales_rep_name,
        "sales_rep_id":           body.sales_rep_id,
        "sales_rep_email":        body.sales_rep_email,
        "deal_id":                body.deal_id,
        "deal_name":              body.deal_name,
        "original_payment_date":  body.original_payment_date,
        "original_payment_info":  body.original_payment_info,
        "hubspot_link":           body.hubspot_link,
        "customer":               body.customer,
        "bank_name":              body.bank_name,
        "account_no":             body.account_no,
        "refund_amount":          body.refund_amount,
        "refund_reason":          body.refund_reason,
        "refund_type":            body.refund_type,
        "partial_products":       body.partial_products,
        "products":               body.products,
        "invoice_numbers":        body.invoice_numbers,
        "is_psg_rejected":        body.is_psg_rejected,
        "approve_token":          app_token,
        "reject_token":           rej_token,
        "hs_deal_id":             body.deal_id,   # may be overwritten for partial below
        "created_at":             now,
        "updated_at":             now,
    }

    database.insert_request(row)

    # Background: HubSpot + email (non-blocking for the BD's UX)
    background_tasks.add_task(
        _process_submission, row, body.refund_type, body.partial_products
    )

    return RefundRequestOut(
        success    = True,
        request_id = request_id,
        message    = (
            "Refund request submitted. "
            "The Sales Director has been notified for approval."
        ),
    )


# ── GET /api/my-requests ─────────────────────────────────────────────────────

@router.get("/api/my-requests")
def get_my_requests(sales_rep_name: str = Query(..., description="Sales rep's full name")):
    """
    Return all refund requests submitted by the given sales rep, newest first.
    Only safe fields are returned (no tokens).
    """
    return database.get_by_sales_rep_name(sales_rep_name)


# ── Background task ───────────────────────────────────────────────────────────

def _process_submission(row: dict, refund_type: str, partial_products: str):
    """
    Runs after the HTTP response is sent:
      - Update / create HubSpot deal (stage + all refund properties in one call)
      - Email the Director
    """
    deal_id = row["deal_id"]

    if refund_type == "full":
        # Single PATCH: stage + all refund properties
        hs.patch_deal(deal_id, {
            "dealstage":     hs.STAGE_REFUND_REQUESTED,
            "refund_reason": row["refund_reason"],
            "refund_type":   "Full",
            "refund_status": hs.STATUS_REQUESTED,
        })

    else:
        # Single POST creates the deal with all properties already set
        new_deal_id = hs.create_partial_refund_deal(
            original_deal_name = row["deal_name"],
            owner_id           = row["sales_rep_id"],
            refund_amount      = row["refund_amount"],
            refund_reason      = row["refund_reason"],
            partial_products   = partial_products,
        )
        if new_deal_id:
            import database as _db
            conn = _db.get_conn()
            conn.execute(
                "UPDATE refund_requests SET hs_deal_id = ? WHERE id = ?",
                (new_deal_id, row["id"])
            )
            conn.commit()
            conn.close()

    # Email Director
    try:
        em.send_director_approval_request(
            request       = row,
            approve_token = row["approve_token"],
            reject_token  = row["reject_token"],
        )
    except Exception as exc:
        print(f"[Email] Director notification failed: {exc}")
