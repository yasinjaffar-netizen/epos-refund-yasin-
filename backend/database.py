"""
SQLite database layer.
For production on Railway, swap to PostgreSQL by replacing the connection
logic with asyncpg or SQLAlchemy + psycopg2.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "refund_requests.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # rows behave like dicts
    return conn


def init_db() -> None:
    """Create tables on first startup; migrate new columns for existing DBs."""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS refund_requests (
            id                  TEXT PRIMARY KEY,
            sales_rep_name      TEXT NOT NULL,
            sales_rep_id        TEXT NOT NULL,
            sales_rep_email     TEXT NOT NULL,
            deal_id             TEXT NOT NULL,
            deal_name           TEXT NOT NULL,
            original_payment_date TEXT DEFAULT '',
            original_payment_info TEXT DEFAULT '',
            hubspot_link        TEXT DEFAULT '',
            customer            TEXT DEFAULT '',
            bank_name           TEXT NOT NULL,
            account_no          TEXT NOT NULL,
            refund_amount       TEXT NOT NULL,
            refund_reason       TEXT NOT NULL,
            refund_type         TEXT NOT NULL,   -- 'full' | 'partial'
            partial_products    TEXT DEFAULT '',
            products            TEXT DEFAULT '',
            invoice_numbers     TEXT DEFAULT '',
            is_psg_rejected     TEXT DEFAULT '',
            status              TEXT DEFAULT 'pending',
            -- pending | director_approved | document_ready | rejected
            approve_token       TEXT UNIQUE NOT NULL,
            reject_token        TEXT UNIQUE NOT NULL,
            rejection_reason    TEXT DEFAULT '',
            pdf_path            TEXT DEFAULT '',  -- unused, kept for schema compat
            hs_deal_id          TEXT DEFAULT '',  -- HubSpot deal ID
            uploaded_doc_path   TEXT DEFAULT '',  -- path to admin-uploaded document
            uploaded_at         TEXT DEFAULT '',  -- timestamp of admin upload
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL
        )
    """)
    conn.commit()

    # Migrate existing databases that pre-date these columns
    for col, definition in [
        ("uploaded_doc_path",      "TEXT DEFAULT ''"),
        ("uploaded_at",            "TEXT DEFAULT ''"),
        ("original_payment_date",  "TEXT DEFAULT ''"),
        ("original_payment_info",  "TEXT DEFAULT ''"),
        ("hubspot_link",           "TEXT DEFAULT ''"),
        ("customer",               "TEXT DEFAULT ''"),
        ("products",               "TEXT DEFAULT ''"),
        ("invoice_numbers",        "TEXT DEFAULT ''"),
        ("is_psg_rejected",        "TEXT DEFAULT ''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE refund_requests ADD COLUMN {col} {definition}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists

    conn.close()


# ── CRUD helpers ──────────────────────────────────────────────────────────────

def insert_request(row: dict) -> None:
    conn = get_conn()
    conn.execute("""
        INSERT INTO refund_requests
            (id, sales_rep_name, sales_rep_id, sales_rep_email,
             deal_id, deal_name, original_payment_date, original_payment_info,
             hubspot_link, customer,
             bank_name, account_no,
             refund_amount, refund_reason, refund_type, partial_products,
             products, invoice_numbers, is_psg_rejected,
             status, approve_token, reject_token,
             hs_deal_id, created_at, updated_at)
        VALUES
            (:id, :sales_rep_name, :sales_rep_id, :sales_rep_email,
             :deal_id, :deal_name, :original_payment_date, :original_payment_info,
             :hubspot_link, :customer,
             :bank_name, :account_no,
             :refund_amount, :refund_reason, :refund_type, :partial_products,
             :products, :invoice_numbers, :is_psg_rejected,
             'pending', :approve_token, :reject_token,
             :hs_deal_id, :created_at, :updated_at)
    """, row)
    conn.commit()
    conn.close()


def get_by_approve_token(token: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM refund_requests WHERE approve_token = ?", (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_by_reject_token(token: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM refund_requests WHERE reject_token = ?", (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_by_id(request_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM refund_requests WHERE id = ?", (request_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending_uploads() -> list[dict]:
    """Return all requests awaiting admin document upload (Director approved)."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM refund_requests
        WHERE status = 'director_approved'
        ORDER BY updated_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_by_sales_rep_name(name: str) -> list[dict]:
    """Return all requests for a given sales rep, newest first."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, deal_name, deal_id, refund_amount, refund_type,
               partial_products, status, created_at, updated_at,
               rejection_reason, uploaded_at
        FROM refund_requests
        WHERE sales_rep_name = ?
        ORDER BY created_at DESC
    """, (name,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_director_approved(request_id: str, updated_at: str) -> None:
    """Director approved — awaiting admin document upload."""
    conn = get_conn()
    conn.execute("""
        UPDATE refund_requests
        SET status = 'director_approved', updated_at = ?
        WHERE id = ?
    """, (updated_at, request_id))
    conn.commit()
    conn.close()


def mark_document_uploaded(request_id: str, doc_path: str, uploaded_at: str) -> None:
    """Admin uploaded the signed document — document is ready for BD download."""
    conn = get_conn()
    conn.execute("""
        UPDATE refund_requests
        SET status = 'document_ready',
            uploaded_doc_path = ?,
            uploaded_at = ?,
            updated_at = ?
        WHERE id = ?
    """, (doc_path, uploaded_at, uploaded_at, request_id))
    conn.commit()
    conn.close()


def mark_rejected(request_id: str, reason: str, updated_at: str) -> None:
    conn = get_conn()
    conn.execute("""
        UPDATE refund_requests
        SET status = 'rejected', rejection_reason = ?, updated_at = ?
        WHERE id = ?
    """, (reason, updated_at, request_id))
    conn.commit()
    conn.close()
