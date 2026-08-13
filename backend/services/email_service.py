"""
Gmail email service using SMTP_SSL + App Password (Google Workspace).

Email types:
  1. send_director_approval_request  — BD submits → Director gets approve/reject links
  2. send_admin_notification          — Director approves → Admin notified to upload doc
  3. send_document_ready_notification — Admin uploads → BD notified, doc ready to download
  4. send_finance_notification        — Admin uploads → Finance notified
  5. send_rejection_notification      — Director rejects → BD notified
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText

GMAIL_SENDER       = os.getenv("GMAIL_SENDER",       "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD",  "")
DIRECTOR_EMAIL     = os.getenv("DIRECTOR_EMAIL",      "")
DIRECTOR_NAME      = os.getenv("DIRECTOR_NAME",       "Sales Director")
FINANCE_EMAIL      = os.getenv("FINANCE_EMAIL",       "")
ADMIN_EMAIL        = os.getenv("ADMIN_EMAIL",         "")
BACKEND_URL        = os.getenv("BACKEND_URL",         "http://localhost:8000")
FRONTEND_URL       = os.getenv("FRONTEND_URL",        "http://localhost:5173")

_HEADER_STYLE = "background:#1a3c6e; color:#fff; padding:24px 32px;"
_WRAP_STYLE   = (
    "max-width:600px; margin:30px auto; background:#fff;"
    "border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.1);"
)
_TABLE_STYLE  = "width:100%; border-collapse:collapse; margin:16px 0;"
_TD_STYLE     = "padding:8px 12px; border:1px solid #e0e0e0; font-size:14px;"
_TDL_STYLE    = f"{_TD_STYLE} background:#f5f7fa; font-weight:bold; color:#444; width:40%;"
_FOOTER_STYLE = "background:#f5f5f5; padding:14px 32px; font-size:11px; color:#aaa; text-align:center;"


def _smtp():
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
    return server


def _send(to: list[str], subject: str, html: str):
    msg = MIMEMultipart("mixed")
    msg["From"]    = f"EPOS Refund System <{GMAIL_SENDER}>"
    msg["To"]      = ", ".join(to)
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))
    with _smtp() as server:
        server.sendmail(GMAIL_SENDER, to, msg.as_string())


def _refund_type_label(request: dict) -> str:
    if request["refund_type"] == "full":
        return "Full Refund"
    products = request.get("partial_products", "")
    return f"Partial Refund — {products}" if products else "Partial Refund"


# ── 1. Director approval request ──────────────────────────────────────────────

def send_director_approval_request(request: dict, approve_token: str, reject_token: str):
    approve_url = f"{BACKEND_URL}/api/approve/{approve_token}"
    reject_url  = f"{BACKEND_URL}/api/reject/{reject_token}"

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap');
  body {{ font-family:Arial,sans-serif; background:#f4f4f4; margin:0; padding:0; }}
  .wrap {{ {_WRAP_STYLE} }}
  .header {{ {_HEADER_STYLE} }}
  .header h2 {{ margin:0; font-size:18px; }}
  .header p  {{ margin:4px 0 0; font-size:13px; opacity:.85; }}
  .body {{ padding:28px 32px; }}
  .data-table {{ {_TABLE_STYLE} }}
  .data-table td {{ {_TD_STYLE} }}
  .data-table td:first-child {{ {_TDL_STYLE} }}
  .actions {{ text-align:center; margin:32px 0 10px; }}
  .btn-approve {{
    display:inline-table; text-decoration:none; margin:0 10px;
    background:#e8f8e8; border-radius:999px; overflow:hidden;
  }}
  .btn-approve td {{ border:none !important; background:transparent !important; padding:0 !important; vertical-align:middle; }}
  .btn-approve .icon {{ width:42px; height:42px; background:#59cc53; border-radius:50%; text-align:center; line-height:42px; font-size:20px; color:#fff; margin:6px 0 6px 6px; font-weight:900; }}
  .btn-approve .lbl  {{ padding:0 22px 0 12px; font-family:'Montserrat',Arial,sans-serif; font-weight:800; font-size:15px; letter-spacing:0.5px; color:#007af3; white-space:nowrap; text-transform:uppercase; }}
  .btn-reject {{
    display:inline-table; text-decoration:none; margin:0 10px;
    background:#fde8e8; border-radius:999px; overflow:hidden;
  }}
  .btn-reject td {{ border:none !important; background:transparent !important; padding:0 !important; vertical-align:middle; }}
  .btn-reject .icon {{ width:42px; height:42px; background:#ef4444; border-radius:50%; text-align:center; line-height:42px; font-size:20px; color:#fff; margin:6px 0 6px 6px; font-weight:900; }}
  .btn-reject .lbl  {{ padding:0 22px 0 12px; font-family:'Montserrat',Arial,sans-serif; font-weight:800; font-size:15px; letter-spacing:0.5px; color:#ef4444; white-space:nowrap; text-transform:uppercase; }}
  .note {{ font-size:12px; color:#888; text-align:center; margin-top:10px; }}
  .footer {{ {_FOOTER_STYLE} }}
</style></head>
<body><div class="wrap">
  <div class="header"><h2>Refund Approval Required</h2>
    <p>A Sales Representative has submitted a refund request for your review.</p></div>
  <div class="body">
    <p>Dear {DIRECTOR_NAME},</p>
    <p>Please review the following refund request and take action below.</p>
    <table class="data-table">
      <tr><td>Sales Rep</td><td>{request["sales_rep_name"]}</td></tr>
      <tr><td>Deal Name</td><td>{request["deal_name"]}</td></tr>
      <tr><td>Customer</td><td>{request.get("customer", "")}</td></tr>
      <tr><td>HubSpot Link</td><td><a href="{request.get("hubspot_link", "")}">{request.get("hubspot_link", "")}</a></td></tr>
      <tr><td>Original Payment Date</td><td>{request.get("original_payment_date", "")}</td></tr>
      <tr><td>Original Payment Info</td><td>{request.get("original_payment_info", "")}</td></tr>
      <tr><td>Product(s)</td><td>{request.get("products", "")}</td></tr>
      <tr><td>Invoice Number(s)</td><td>{request.get("invoice_numbers", "")}</td></tr>
      {f'<tr><td>Is PSG Rejected?</td><td>{request["is_psg_rejected"]}</td></tr>' if request.get("is_psg_rejected") else ""}
      <tr><td>Refund Type</td><td>{_refund_type_label(request)}</td></tr>
      <tr><td>Refund Amount</td><td><strong>SGD {request["refund_amount"]}</strong></td></tr>
      <tr><td>Reason</td><td>{request["refund_reason"]}</td></tr>
      <tr><td>Bank Name</td><td>{request["bank_name"]}</td></tr>
      <tr><td>Account / PayNow</td><td>{request["account_no"]}</td></tr>
      <tr><td>Request ID</td><td>{request["id"]}</td></tr>
    </table>
    <div class="actions">
      <a href="{approve_url}" class="btn-approve">
        <table cellpadding="0" cellspacing="0"><tr>
          <td><div class="icon">&#10003;</div></td>
          <td><span class="lbl">Approve</span></td>
        </tr></table>
      </a>
      <a href="{reject_url}" class="btn-reject">
        <table cellpadding="0" cellspacing="0"><tr>
          <td><div class="icon">&#10005;</div></td>
          <td><span class="lbl">Reject</span></td>
        </tr></table>
      </a>
    </div>
    <p class="note">Approving will notify the Admin team to prepare and upload
      the signed Return &amp; Deposit Agreement.</p>
  </div>
  <div class="footer">EPOS Now (Singapore) Pte Ltd — Refund Management System</div>
</div></body></html>"""

    _send(
        to      = [DIRECTOR_EMAIL],
        subject = f"[Action Required] Refund Request: {request['deal_name']} - SGD {request['refund_amount']}",
        html    = html,
    )


# ── 2. Admin notification (Director approved → admin must upload) ─────────────

def send_admin_notification(request: dict):
    upload_url = f"{BACKEND_URL}/admin/upload/{request['id']}"

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/>
<style>
  body {{ font-family:Arial,sans-serif; background:#f4f4f4; margin:0; padding:0; }}
  .wrap {{ {_WRAP_STYLE} }}
  .header {{ background:#59cc53; color:#fff; padding:24px 32px; }}
  .header h2 {{ margin:0; font-size:18px; }}
  .header p  {{ margin:4px 0 0; font-size:13px; opacity:.9; }}
  .body {{ padding:28px 32px; }}
  .data-table {{ {_TABLE_STYLE} }}
  .data-table td {{ {_TD_STYLE} }}
  .data-table td:first-child {{ {_TDL_STYLE} }}
  .upload-btn {{
    display:inline-block; margin-top:22px; padding:13px 34px;
    background:#59cc53; color:#fff; text-decoration:none;
    border-radius:999px; font-weight:bold; font-size:14px;
    letter-spacing:0.3px;
  }}
  .footer {{ {_FOOTER_STYLE} }}
</style></head>
<body><div class="wrap">
  <div class="header">
    <h2>Action Required: Upload Return &amp; Deposit Agreement</h2>
    <p>A refund request has been approved by the Sales Director.</p>
  </div>
  <div class="body">
    <p>Dear Admin Team,</p>
    <p>The following refund request has been <strong>approved by the Director</strong>.
       Please prepare the signed Return &amp; Deposit Agreement and upload it via the
       admin portal.</p>
    <table class="data-table">
      <tr><td>Deal Name</td><td>{request["deal_name"]}</td></tr>
      <tr><td>Sales Rep</td><td>{request["sales_rep_name"]}</td></tr>
      <tr><td>Customer</td><td>{request.get("customer", "")}</td></tr>
      <tr><td>HubSpot Link</td><td><a href="{request.get("hubspot_link", "")}">{request.get("hubspot_link", "")}</a></td></tr>
      <tr><td>Original Payment Date</td><td>{request.get("original_payment_date", "")}</td></tr>
      <tr><td>Original Payment Info</td><td>{request.get("original_payment_info", "")}</td></tr>
      <tr><td>Product(s)</td><td>{request.get("products", "")}</td></tr>
      <tr><td>Invoice Number(s)</td><td>{request.get("invoice_numbers", "")}</td></tr>
      {f'<tr><td>Is PSG Rejected?</td><td>{request["is_psg_rejected"]}</td></tr>' if request.get("is_psg_rejected") else ""}
      <tr><td>Refund Type</td><td>{_refund_type_label(request)}</td></tr>
      <tr><td>Refund Amount</td><td><strong>SGD {request["refund_amount"]}</strong></td></tr>
      <tr><td>Reason</td><td>{request["refund_reason"]}</td></tr>
      <tr><td>Bank Name</td><td>{request["bank_name"]}</td></tr>
      <tr><td>Account / PayNow</td><td>{request["account_no"]}</td></tr>
      <tr><td>Request ID</td><td>{request["id"]}</td></tr>
    </table>
    <p style="text-align:center;">
      <a href="{upload_url}" class="upload-btn">&#8679; Upload Document</a>
    </p>
    <p style="font-size:12px; color:#888; margin-top:16px; text-align:center;">
      Or visit the admin portal: <a href="{BACKEND_URL}/admin">{BACKEND_URL}/admin</a>
    </p>
  </div>
  <div class="footer">EPOS Now (Singapore) Pte Ltd — Refund Management System</div>
</div></body></html>"""

    _send(
        to      = [ADMIN_EMAIL],
        subject = f"[Upload Required] Return & Deposit Agreement: {request['deal_name']}",
        html    = html,
    )


# ── 3. BD notification — document ready to download ───────────────────────────

def send_document_ready_notification(request: dict, download_url: str):
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap');
  body {{ font-family:Arial,sans-serif; background:#f4f4f4; margin:0; padding:0; }}
  .wrap {{ {_WRAP_STYLE} }}
  .header {{ {_HEADER_STYLE} }}
  .header h2 {{ margin:0; font-size:18px; }}
  .header p  {{ margin:4px 0 0; font-size:13px; opacity:.85; }}
  .body {{ padding:28px 32px; }}
  .data-table {{ {_TABLE_STYLE} }}
  .data-table td {{ {_TD_STYLE} }}
  .data-table td:first-child {{ {_TDL_STYLE} }}
  .dl-btn {{
    display:inline-block; margin-top:20px; padding:13px 34px;
    background:#59cc53; color:#fff; text-decoration:none;
    border-radius:999px; font-weight:bold; font-size:14px;
  }}
  .footer {{ {_FOOTER_STYLE} }}
</style></head>
<body><div class="wrap">
  <div class="header">
    <h2>Refund Approved — Document Ready</h2>
    <p>Your Return &amp; Deposit Agreement is ready to download.</p>
  </div>
  <div class="body">
    <p style="margin-bottom:20px;">Hi {request["sales_rep_name"]},</p>
    <table cellpadding="0" cellspacing="0" style="width:100%;border:2px solid #0a21ab;border-radius:12px;overflow:hidden;margin-bottom:20px;">
      <tr>
        <td style="width:54px;padding:10px 0 10px 12px;border:none;">
          <div style="width:38px;height:38px;background:#e8f8e8;border-radius:50%;text-align:center;line-height:38px;font-size:20px;color:#59cc53;font-weight:900;">&#10003;</div>
        </td>
        <td style="padding:10px 16px;border:none;font-family:'Montserrat',Arial,sans-serif;font-weight:800;font-size:15px;letter-spacing:0.4px;color:#111827;text-transform:uppercase;">
          Document Ready for Download
        </td>
      </tr>
    </table>
    <table class="data-table">
      <tr><td>Deal Name</td><td>{request["deal_name"]}</td></tr>
      <tr><td>Refund Type</td><td>{_refund_type_label(request)}</td></tr>
      <tr><td>Refund Amount</td><td><strong>SGD {request["refund_amount"]}</strong></td></tr>
    </table>
    <p>Your signed <strong>Return &amp; Deposit Agreement</strong> has been uploaded
       and is ready for download. You can also access it anytime via the
       <strong>My Requests</strong> tab in the refund portal.</p>
    <p style="text-align:center;">
      <a href="{download_url}" class="dl-btn">&#8681; Download Agreement</a>
    </p>
    <p style="font-size:13px; color:#666; margin-top:16px;">
      Finance has been notified and will process the refund within 7–14 business days.
    </p>
  </div>
  <div class="footer">EPOS (Singapore) Pte Ltd Refund Management System</div>
</div></body></html>"""

    _send(
        to      = [request["sales_rep_email"]],
        subject = f"Document Ready: {request['deal_name']} — SGD {request['refund_amount']}",
        html    = html,
    )


# ── 4. Finance notification — document uploaded, process refund ───────────────

def send_finance_notification(request: dict, download_url: str):
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/>
<style>
  body {{ font-family:Arial,sans-serif; background:#f4f4f4; margin:0; padding:0; }}
  .wrap {{ {_WRAP_STYLE} }}
  .header {{ {_HEADER_STYLE} }}
  .header h2 {{ margin:0; font-size:18px; }}
  .header p  {{ margin:4px 0 0; font-size:13px; opacity:.85; }}
  .body {{ padding:28px 32px; }}
  .data-table {{ {_TABLE_STYLE} }}
  .data-table td {{ {_TD_STYLE} }}
  .data-table td:first-child {{ {_TDL_STYLE} }}
  .badge {{ display:inline-block; background:#fef9c3; color:#854d0e;
            padding:4px 14px; border-radius:20px; font-weight:bold; font-size:13px; }}
  .dl-btn {{
    display:inline-block; margin-top:16px; padding:11px 28px;
    background:#1a3c6e; color:#fff; text-decoration:none;
    border-radius:6px; font-weight:bold; font-size:14px;
  }}
  .footer {{ {_FOOTER_STYLE} }}
</style></head>
<body><div class="wrap">
  <div class="header">
    <h2>Action Required: Process Refund</h2>
    <p>A signed Return &amp; Deposit Agreement has been uploaded and is ready.</p>
  </div>
  <div class="body">
    <p>Dear Finance Team,</p>
    <p>The following refund has been <span class="badge">Approved</span> and the signed
       agreement is ready. Please process the refund accordingly.</p>
    <table class="data-table">
      <tr><td>Deal Name</td><td>{request["deal_name"]}</td></tr>
      <tr><td>Sales Rep</td><td>{request["sales_rep_name"]}</td></tr>
      <tr><td>Customer</td><td>{request.get("customer", "")}</td></tr>
      <tr><td>HubSpot Link</td><td><a href="{request.get("hubspot_link", "")}">{request.get("hubspot_link", "")}</a></td></tr>
      <tr><td>Original Payment Date</td><td>{request.get("original_payment_date", "")}</td></tr>
      <tr><td>Original Payment Info</td><td>{request.get("original_payment_info", "")}</td></tr>
      <tr><td>Product(s)</td><td>{request.get("products", "")}</td></tr>
      <tr><td>Invoice Number(s)</td><td>{request.get("invoice_numbers", "")}</td></tr>
      {f'<tr><td>Is PSG Rejected?</td><td>{request["is_psg_rejected"]}</td></tr>' if request.get("is_psg_rejected") else ""}
      <tr><td>Refund Type</td><td>{_refund_type_label(request)}</td></tr>
      <tr><td>Refund Amount</td><td><strong>SGD {request["refund_amount"]}</strong></td></tr>
      <tr><td>Reason</td><td>{request["refund_reason"]}</td></tr>
      <tr><td>Bank Name</td><td>{request["bank_name"]}</td></tr>
      <tr><td>Account / PayNow</td><td>{request["account_no"]}</td></tr>
      <tr><td>Request ID</td><td>{request["id"]}</td></tr>
    </table>
    <p style="text-align:center;">
      <a href="{download_url}" class="dl-btn">&#8681; Download Agreement</a>
    </p>
  </div>
  <div class="footer">EPOS Now (Singapore) Pte Ltd — Refund Management System</div>
</div></body></html>"""

    _send(
        to      = [FINANCE_EMAIL],
        subject = f"[Finance] Process Refund: {request['deal_name']} — SGD {request['refund_amount']}",
        html    = html,
    )


# ── 5. Rejection notification ─────────────────────────────────────────────────

def send_rejection_notification(request: dict, reason: str):
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap');
  body {{ font-family:Arial,sans-serif; background:#f4f4f4; margin:0; padding:0; }}
  .wrap {{ {_WRAP_STYLE} }}
  .header {{ {_HEADER_STYLE} }}
  .header h2 {{ margin:0; font-size:18px; }}
  .header p  {{ margin:4px 0 0; font-size:13px; opacity:.85; }}
  .body {{ padding:28px 32px; }}
  .reason-box {{ background:#fef2f2; border-left:4px solid #ef4444;
                 padding:14px 18px; border-radius:4px; margin:16px 0; font-size:14px; color:#333; }}
  .data-table {{ {_TABLE_STYLE} }}
  .data-table td {{ {_TD_STYLE} }}
  .data-table td:first-child {{ {_TDL_STYLE} }}
  .footer {{ {_FOOTER_STYLE} }}
</style></head>
<body><div class="wrap">
  <div class="header">
    <h2>Refund Request Not Approved</h2>
    <p>Your refund request has been reviewed by the Sales Director.</p>
  </div>
  <div class="body">
    <p style="margin-bottom:20px;">Hi {request["sales_rep_name"]},</p>
    <table cellpadding="0" cellspacing="0" style="width:100%;border:2px solid #0a21ab;border-radius:12px;overflow:hidden;margin-bottom:20px;">
      <tr>
        <td style="width:54px;padding:10px 0 10px 12px;border:none;">
          <div style="width:38px;height:38px;background:#fde8e8;border-radius:50%;text-align:center;line-height:38px;font-size:20px;color:#ef4444;font-weight:900;">&#10005;</div>
        </td>
        <td style="padding:10px 16px;border:none;font-family:'Montserrat',Arial,sans-serif;font-weight:800;font-size:15px;letter-spacing:0.4px;color:#111827;text-transform:uppercase;">
          Refund Request Rejected
        </td>
      </tr>
    </table>
    <p><strong>Reason for rejection:</strong></p>
    <div class="reason-box">{reason}</div>
    <table class="data-table">
      <tr><td>Deal Name</td><td>{request["deal_name"]}</td></tr>
      <tr><td>Refund Amount</td><td>SGD {request["refund_amount"]}</td></tr>
      <tr><td>Request ID</td><td>{request["id"]}</td></tr>
    </table>
    <p style="font-size:13px; color:#666;">
      If you believe this was rejected in error, please discuss with your
      Sales Director before resubmitting a new request.
    </p>
  </div>
  <div class="footer">EPOS (Singapore) Pte Ltd Refund Management System</div>
</div></body></html>"""

    _send(
        to      = [request["sales_rep_email"]],
        subject = f"Refund Request Not Approved: {request['deal_name']}",
        html    = html,
    )
