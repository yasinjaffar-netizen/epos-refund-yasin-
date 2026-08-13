import { useState, useEffect } from "react";
import "./shared.css";

// ── Constants ────────────────────────────────────────────────
// Vite proxy rewrites /api/* → http://localhost:8000/api/* in dev.
// In production, set VITE_API_BASE to your Railway backend URL.
const API_BASE = import.meta.env.VITE_API_BASE || "";

// Sales reps — name + HubSpot owner id + email
const SALES_REPS = [
  { name: "Alvin Seah",     id: "161621502", email: "alvin.seah@epos.com.sg" },
  { name: "Andy Chia",      id: "218061175", email: "andy.chia@epos.com.sg" },
  { name: "Arvinder Singh", id: "81514542",  email: "arvinder.singh@epos.com.sg" },
  { name: "Brandon Leong",  id: "326921814", email: "brandon.leong@epos.com.sg" },
  { name: "Belle Phia",     id: "162289152", email: "belle.phia@epos.com.sg" },
  { name: "Crystal Lee",    id: "253502246", email: "crystal.lee@epos.com.sg" },
  { name: "Dominic Chan",   id: "57274755",  email: "dominic.chan@epos.com.sg" },
  { name: "Fenny Wong",     id: "53224564",  email: "fenny.wong@epos.com.sg" },
  { name: "Glenn Wee",      id: "37676685",  email: "glenn.wee@epos.com.sg" },
  { name: "Hadi Sng",       id: "61019637",  email: "hadi.sng@epos.com.sg" },
  { name: "Harold Lim",     id: "344217702", email: "harold.lim@epos.com.sg" },
  { name: "Julie Chan",     id: "29349349",  email: "julie.chan@epos.com.sg" },
  { name: "Tasha Goh",      id: "81330493",  email: "tasha.goh@epos.com.sg" },
  { name: "Mervin Cai",     id: "83765548",  email: "mervin.cai@epos.com.sg" },
  { name: "Rachel Tai",     id: "163983329", email: "rachel.tai@epos.com.sg" },
  { name: "Ruth Han",       id: "16431507",  email: "ruth.han@epos.com.sg" },
  { name: "Winston Heng",   id: "83762739",  email: "winston.heng@epos.com.sg" },
  { name: "Zack Gaffar",    id: "488014670", email: "zack.gaffar@epos.com.sg" },
];

const SG_BANKS = [
  "DBS / POSB",
  "OCBC",
  "UOB",
  "Standard Chartered",
  "HSBC",
  "Citibank",
  "Maybank",
  "Bank of China",
  "RHB",
  "CIMB",
  "PayNow",
];

const initialFields = {
  sales_rep:              "",
  deal_id:                "",
  original_payment_date:  "",
  original_payment_info:  "",
  hubspot_link:            "",
  customer:               "",
  bank_name:              "",
  account_no:             "",
  refund_amount:          "",
  refund_reason:          "",
  refund_type:            "",
  partial_products:       "",
  is_psg_rejected:        "",
};

const REQUIRED = [
  "sales_rep", "deal_id", "original_payment_date", "original_payment_info", "hubspot_link",
  "customer", "bank_name", "account_no", "refund_amount", "refund_reason", "refund_type",
  "is_psg_rejected",
];
const FIELD_LABELS = {
  sales_rep:             "Deal Owner",
  deal_id:               "Deal",
  original_payment_date: "Original Payment Date",
  original_payment_info: "Original Payment Info",
  hubspot_link:          "HubSpot Link",
  customer:              "Customer",
  bank_name:             "Bank Name",
  account_no:            "Account No.",
  refund_amount:         "Refund Amount",
  refund_reason:         "Refund Reason",
  is_psg_rejected:       "Is PSG Approved?",
  refund_type:           "Refund Type",
};

// Fixed product list for the "Product" field — distinct from the
// HubSpot-driven partial-refund product checklist further down the form.
const PRODUCTS = [
  "Retail POS (Software)",
  "FnB POS (Software)",
  "Website",
  "EPOS Rewards",
  "Digital Marketing",
  "Hardware",
];

// Which invoice-number field a product maps to.
// Retail POS and FnB POS share the same "PSG" invoice number.
const INVOICE_GROUP_MAP = {
  "Retail POS (Software)": "PSG",
  "FnB POS (Software)":    "PSG",
  "Website":                "Website",
  "EPOS Rewards":           "EPOS Rewards",
  "Digital Marketing":      "Digital Marketing",
  "Hardware":                "Hardware",
};

const INVOICE_GROUP_ORDER = ["PSG", "Website", "EPOS Rewards", "Digital Marketing", "Hardware"];
const INVOICE_GROUP_LABELS = {
  "PSG":               "Invoice Number (PSG)",
  "Website":           "Invoice Number (Website)",
  "EPOS Rewards":      "Invoice Number (EPOS Rewards)",
  "Digital Marketing": "Invoice Number (Digital Marketing)",
  "Hardware":          "Invoice Number (Hardware)",
};

// ── Reusable components ──────────────────────────────────────

function FieldGroup({ label, sublabel, required, error, children }) {
  return (
    <div className="field-group">
      <label>{label}{required && <span className="req"> *</span>}</label>
      {sublabel && <div className="field-sublabel">{sublabel}</div>}
      {children}
      {error && <div className="error-msg">{error}</div>}
    </div>
  );
}

function ProductCheckboxes({ products, selected, onToggle, loading, error }) {
  if (loading) {
    return (
      <div className="product-loading">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round"
          style={{ animation: "spin 1s linear infinite" }}>
          <path d="M21 12a9 9 0 1 1-6.219-8.56" />
        </svg>
        Loading products from deal…
      </div>
    );
  }

  return (
    <div className="product-list">
      {products.map((p) => {
        const isSelected = selected.includes(p.name);
        return (
          <div
            key={p.name}
            className={`product-item${isSelected ? " selected" : ""}${error ? " has-error" : ""}`}
            onClick={() => onToggle(p.name)}
            role="checkbox"
            aria-checked={isSelected}
            tabIndex={0}
            onKeyDown={(e) => e.key === " " && onToggle(p.name)}
          >
            <div className="product-checkbox">
              <svg
                className="product-check-icon"
                width="11" height="11" viewBox="0 0 12 12"
                fill="none" stroke="white" strokeWidth="2.2"
                strokeLinecap="round" strokeLinejoin="round"
              >
                <polyline points="2 6 5 9 10 3" />
              </svg>
            </div>
            <span className="product-name">{p.name}</span>
            {p.amount && (
              <span className="product-amount">SGD {p.amount}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ThankYou({ onReset }) {
  return (
    <div className="form-card">
      <div className="form-body" style={{ paddingTop: 48, paddingBottom: 52 }}>
        <div className="thankyou-icon">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none"
            stroke="#22c55e" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </div>
        <h2 className="thankyou-title">Refund request submitted!</h2>
        <p className="thankyou-note">
          Your refund request has been sent to the Sales Director for approval.
          You'll receive an email with the signed Return &amp; Deposit Agreement once it's approved.
          The deal has been moved to the <strong>Refund Requested</strong> stage in HubSpot.
        </p>
        <button className="submit-btn" onClick={onReset}>
          Submit Another Request
        </button>
      </div>
    </div>
  );
}

// ── Status config for My Requests ────────────────────────────
const STATUS_CONFIG = {
  pending:          { label: "Awaiting Director",  color: "#6b7280", bg: "#f3f4f6", border: "#e5e7eb", dot: "#9ca3af" },
  director_approved: { label: "Awaiting Document", color: "#b45309", bg: "#fffbeb", border: "#fde68a", dot: "#f59e0b" },
  document_ready:   { label: "Document Ready",     color: "#15803d", bg: "#f0fdf4", border: "#bbf7d0", dot: "#22c55e" },
  rejected:         { label: "Rejected",           color: "#b91c1c", bg: "#fef2f2", border: "#fecaca", dot: "#ef4444" },
};

function RequestCard({ req }) {
  const cfg = STATUS_CONFIG[req.status] || STATUS_CONFIG.pending;
  const fmtDate = (d) => {
    try { return new Date(d).toLocaleDateString("en-SG", { day: "numeric", month: "short", year: "numeric" }); }
    catch { return d; }
  };

  return (
    <div className="request-card fade-in">
      <div className="request-card-top">
        <div className="request-card-name">{req.deal_name}</div>
        <span className="request-status-badge"
          style={{ color: cfg.color, background: cfg.bg, borderColor: cfg.border }}>
          <span className="request-status-dot" style={{ background: cfg.dot }} />
          {cfg.label}
        </span>
      </div>
      <div className="request-card-meta">
        <span>SGD {req.refund_amount}</span>
        <span>{req.refund_type === "full" ? "Full Refund" : "Partial Refund"}</span>
        <span>Submitted {fmtDate(req.created_at)}</span>
      </div>
      {req.status === "rejected" && req.rejection_reason && (
        <div className="request-rejection">
          <strong>Rejection reason:</strong> {req.rejection_reason}
        </div>
      )}
      {req.status === "document_ready" && (
        <a
          href={`${API_BASE}/api/download/${req.id}`}
          className="request-download-btn"
          target="_blank"
          rel="noreferrer"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          Download Agreement
        </a>
      )}
    </div>
  );
}

function MyRequests() {
  const [selectedRep, setSelectedRep] = useState("");
  const [requests, setRequests]       = useState([]);
  const [loading, setLoading]         = useState(false);

  useEffect(() => {
    if (!selectedRep) { setRequests([]); return; }
    setLoading(true);
    fetch(`${API_BASE}/api/my-requests?sales_rep_name=${encodeURIComponent(selectedRep)}`)
      .then((r) => r.ok ? r.json() : [])
      .then((data) => setRequests(Array.isArray(data) ? data : []))
      .catch(() => setRequests([]))
      .finally(() => setLoading(false));
  }, [selectedRep]);

  return (
    <div className="my-requests-body">
      <FieldGroup label="Select Your Name" sublabel="View all refund requests you have submitted.">
        <div className="select-wrap">
          <select
            value={selectedRep}
            onChange={(e) => setSelectedRep(e.target.value)}
            className={selectedRep ? "has-value" : ""}
          >
            <option value="">Select your name</option>
            {SALES_REPS.map((r) => (
              <option key={r.id} value={r.name}>{r.name}</option>
            ))}
          </select>
        </div>
      </FieldGroup>

      {loading && (
        <div className="requests-loading">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round"
            style={{ animation: "spin 1s linear infinite" }}>
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
          Loading requests…
        </div>
      )}

      {!loading && selectedRep && requests.length === 0 && (
        <div className="requests-empty">
          No refund requests found for <strong>{selectedRep}</strong>.
        </div>
      )}

      {!loading && requests.map((req) => (
        <RequestCard key={req.id} req={req} />
      ))}
    </div>
  );
}

// ── Main App ─────────────────────────────────────────────────
export default function App() {
  const [page, setPage]             = useState("form");
  const [activeTab, setActiveTab]   = useState("submit");
  const [fields, setFields]         = useState(initialFields);
  const [errors, setErrors]         = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError]     = useState("");

  const [selectedProductCategories, setSelectedProductCategories] = useState([]);   // fixed "Product" field selections
  const [invoiceNumbers, setInvoiceNumbers]                       = useState({});   // { PSG: "...", Website: "...", ... }

  const isPayNow = fields.bank_name === "PayNow";

  // Invoice-number field(s) to show, derived from the selected product(s)
  const activeInvoiceGroups = INVOICE_GROUP_ORDER.filter((group) =>
    selectedProductCategories.some((p) => INVOICE_GROUP_MAP[p] === group)
  );

  // ── Handlers ──────────────────────────────────────────────
  function handleChange(e) {
    const { name, value } = e.target;
    setFields((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: "" }));
  }

  function handleRepChange(e) {
    setFields((prev) => ({ ...prev, sales_rep: e.target.value }));
    if (errors.sales_rep) setErrors((prev) => ({ ...prev, sales_rep: "" }));
  }

  function handleTypeSelect(type) {
    setFields((prev) => ({ ...prev, refund_type: type }));
    if (errors.refund_type) setErrors((prev) => ({ ...prev, refund_type: "" }));
  }

  function handleProductCategoryToggle(productName) {
    const next = selectedProductCategories.includes(productName)
      ? selectedProductCategories.filter((p) => p !== productName)
      : [...selectedProductCategories, productName];
    setSelectedProductCategories(next);
    if (errors.product_categories) setErrors((prev) => ({ ...prev, product_categories: "" }));
  }

  function handlePsgRejectedSelect(value) {
    setFields((prev) => ({ ...prev, is_psg_rejected: value }));
    if (errors.is_psg_rejected) setErrors((prev) => ({ ...prev, is_psg_rejected: "" }));
  }

  function handleInvoiceNumberChange(group, value) {
    setInvoiceNumbers((prev) => ({ ...prev, [group]: value }));
    const key = `invoice_${group}`;
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: "" }));
  }

  function handleBankChange(e) {
    const bank = e.target.value;
    setFields((prev) => ({ ...prev, bank_name: bank, account_no: "" }));
    if (errors.bank_name)  setErrors((prev) => ({ ...prev, bank_name: "" }));
    if (errors.account_no) setErrors((prev) => ({ ...prev, account_no: "" }));
  }

  // ── Validation ─────────────────────────────────────────────
  function validate() {
    const newErrors = {};

    REQUIRED.forEach((key) => {
      if (!fields[key] || fields[key].toString().trim() === "")
        newErrors[key] = `${FIELD_LABELS[key]} is required.`;
    });

    if (fields.refund_amount &&
        isNaN(Number(fields.refund_amount.toString().replace(/,/g, "")))) {
      newErrors.refund_amount = "Please enter a valid amount.";
    }

    if (selectedProductCategories.length === 0) {
      newErrors.product_categories = "Please select at least one product.";
    }

    activeInvoiceGroups.forEach((group) => {
      if (!(invoiceNumbers[group] || "").trim())
        newErrors[`invoice_${group}`] = `${INVOICE_GROUP_LABELS[group]} is required.`;
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }

  // ── Submit ─────────────────────────────────────────────────
  async function handleSubmit(e) {
    e.preventDefault();
    if (!validate()) return;

    const rep = SALES_REPS.find((r) => r.name === fields.sales_rep);

    const invoiceNumbersValue = activeInvoiceGroups
      .map((group) => `${INVOICE_GROUP_LABELS[group]}: ${invoiceNumbers[group]}`)
      .join("; ");

    const payload = {
      sales_rep_name:         fields.sales_rep,
      sales_rep_id:           rep?.id || "",
      sales_rep_email:        rep?.email || "",
      deal_id:                fields.deal_id,
      deal_name:              fields.deal_id,
      original_payment_date:  fields.original_payment_date,
      original_payment_info:  fields.original_payment_info,
      hubspot_link:           fields.hubspot_link,
      customer:               fields.customer,
      bank_name:              fields.bank_name,
      account_no:             fields.account_no,
      refund_amount:          fields.refund_amount,
      refund_reason:          fields.refund_reason,
      refund_type:            fields.refund_type,
      partial_products:       fields.partial_products,
      products:                selectedProductCategories.join(", "),
      invoice_numbers:         invoiceNumbersValue,
      is_psg_rejected:         fields.is_psg_rejected,
    };

    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/refund-request`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(payload),
      });
      if (!res.ok) throw new Error();
      setPage("thankyou");
    } catch {
      setApiError("Submission failed. Please try again or check your connection.");
    } finally {
      setSubmitting(false);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  function handleReset() {
    setPage("form");
    setFields(initialFields);
    setErrors({});
    setApiError("");
    setSelectedProductCategories([]);
    setInvoiceNumbers({});
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  if (page === "thankyou") return <ThankYou onReset={handleReset} />;

  return (
    <div className="form-card">
      <div className="form-header">
        <div className="form-logo"><img src="/logo.webp" alt="EPOS Logo" /></div>
        <h1 className="form-title">Refund Request Form</h1>
        <p className="form-subtitle">
          Submit a refund request for a closed deal, or check the status of an existing request.
        </p>
      </div>

      {/* Tab bar */}
      <div className="tab-bar">
        <button
          className={`tab-btn${activeTab === "submit" ? " active" : ""}`}
          onClick={() => setActiveTab("submit")}
          type="button"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
          Submit Request
        </button>
        <button
          className={`tab-btn${activeTab === "my-requests" ? " active" : ""}`}
          onClick={() => setActiveTab("my-requests")}
          type="button"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
          My Requests
        </button>
      </div>

      {activeTab === "my-requests" && <MyRequests />}

      {activeTab === "submit" && (
      <div className="form-body">
        <form onSubmit={handleSubmit} noValidate>

          {/* 1. Deal Owner */}
          <FieldGroup label="1. Deal Owner" required error={errors.sales_rep}
            sublabel="Select your name from the list.">
            <div className="select-wrap">
              <select
                name="sales_rep"
                value={fields.sales_rep}
                onChange={handleRepChange}
                className={[errors.sales_rep ? "has-error" : "", fields.sales_rep ? "has-value" : ""].join(" ").trim()}
              >
                <option value="">Select your name</option>
                {SALES_REPS.map((r) => (
                  <option key={r.id} value={r.name}>{r.name} ({r.email})</option>
                ))}
              </select>
            </div>
          </FieldGroup>

          {/* 2. Deal */}
          <FieldGroup label="2. Deal" required error={errors.deal_id}
            sublabel="Please enter the exact deal name as it appears in HubSpot.">
            <input
              type="text"
              name="deal_id"
              value={fields.deal_id}
              onChange={handleChange}
              className={errors.deal_id ? "has-error" : ""}
              placeholder="Deal name"
            />
          </FieldGroup>

          {/* 3. Original Payment Date */}
          <FieldGroup label="3. Original Payment Date" required error={errors.original_payment_date}>
            <input
              type="date"
              name="original_payment_date"
              value={fields.original_payment_date}
              onChange={handleChange}
              className={errors.original_payment_date ? "has-error" : ""}
            />
          </FieldGroup>

          {/* 4. Original Payment Info */}
          <FieldGroup label="4. Original Payment Info" required error={errors.original_payment_info}>
            <input
              type="text"
              name="original_payment_info"
              value={fields.original_payment_info}
              onChange={handleChange}
              className={errors.original_payment_info ? "has-error" : ""}
              placeholder="e.g. Bank - Company Name on DD/MM/YY (Inv 00000 - $0.00)"
            />
          </FieldGroup>

          {/* 5. HubSpot Link */}
          <FieldGroup label="5. HubSpot Link" required error={errors.hubspot_link}>
            <input
              type="text"
              name="hubspot_link"
              value={fields.hubspot_link}
              onChange={handleChange}
              className={errors.hubspot_link ? "has-error" : ""}
              placeholder="https://app.hubspot.com/contacts/.../deal/..."
            />
          </FieldGroup>

          <hr className="section-divider" />

          {/* 6. Refund type */}
          <FieldGroup label="6. Refund Type" required error={errors.refund_type}>
            <div className="toggle-buttons">
              {[["full", "Full Refund"], ["partial", "Partial Refund"]].map(([val, lbl]) => (
                <button key={val} type="button"
                  className={`toggle-btn${fields.refund_type === val ? " active" : ""}`}
                  onClick={() => handleTypeSelect(val)}>
                  <span className="toggle-radio"><span className="toggle-radio-dot" /></span>
                  {lbl}
                </button>
              ))}
            </div>
          </FieldGroup>

          {/* 6a. Products (partial refund only) */}
          {fields.refund_type === "partial" && (
            <FieldGroup
              label="Since it is Partial refund, Notify Quantity of Hardware if any:"
              error={errors.partial_products}
            >
              <textarea
                name="partial_products"
                value={fields.partial_products}
                onChange={handleChange}
                className={errors.partial_products ? "has-error" : ""}
                placeholder="e.g. Soundbox x1, Payment Terminal x2"
              />
            </FieldGroup>
          )}

          {/* 7. Product(s) */}
          <FieldGroup
            label="7. Product(s)"
            required
            error={errors.product_categories}
            sublabel="Select the product(s) this refund relates to."
          >
            <ProductCheckboxes
              products={PRODUCTS.map((name) => ({ name }))}
              selected={selectedProductCategories}
              onToggle={handleProductCategoryToggle}
              loading={false}
              error={!!errors.product_categories}
            />
          </FieldGroup>

          {/* 7a. Invoice Number(s) — shown per selected product category */}
          {activeInvoiceGroups.map((group) => (
            <FieldGroup
              key={group}
              label={INVOICE_GROUP_LABELS[group]}
              required
              error={errors[`invoice_${group}`]}
            >
              <input
                type="text"
                value={invoiceNumbers[group] || ""}
                onChange={(e) => handleInvoiceNumberChange(group, e.target.value)}
                className={errors[`invoice_${group}`] ? "has-error" : ""}
                placeholder="e.g. INV-000123"
              />
            </FieldGroup>
          ))}

          {/* 8. Is PSG Approved? */}
          <FieldGroup label="8. Is PSG Approved?" required error={errors.is_psg_rejected}>
            <div className="toggle-buttons">
              {[["Yes", "Yes"], ["No", "No"]].map(([val, lbl]) => (
                <button key={val} type="button"
                  className={`toggle-btn${fields.is_psg_rejected === val ? " active" : ""}`}
                  onClick={() => handlePsgRejectedSelect(val)}>
                  <span className="toggle-radio"><span className="toggle-radio-dot" /></span>
                  {lbl}
                </button>
              ))}
            </div>
          </FieldGroup>

          {/* 9. Refund amount */}
          <FieldGroup label="9. Refund Amount" required error={errors.refund_amount}>
            <div className="amount-wrap">
              <span className="amount-prefix">SGD</span>
              <input
                type="text"
                name="refund_amount"
                value={fields.refund_amount}
                onChange={handleChange}
                className={errors.refund_amount ? "has-error" : ""}
                placeholder="Enter refund amount"
              />
            </div>
          </FieldGroup>

          {/* 10. Customer */}
          <FieldGroup label="10. Customer" required error={errors.customer}
            sublabel="Account Name (for Company Name if different from account name)">
            <input
              type="text"
              name="customer"
              value={fields.customer}
              onChange={handleChange}
              className={errors.customer ? "has-error" : ""}
              placeholder="Customer / company name"
            />
          </FieldGroup>

          {/* 11. Bank Name */}
          <FieldGroup label="11. Bank Name" required error={errors.bank_name}>
            <div className="select-wrap">
              <select
                name="bank_name"
                value={fields.bank_name}
                onChange={handleBankChange}
                className={[errors.bank_name ? "has-error" : "", fields.bank_name ? "has-value" : ""].join(" ").trim()}
              >
                <option value="">Select a bank</option>
                {SG_BANKS.map((b) => (
                  <option key={b} value={b}>{b}</option>
                ))}
              </select>
            </div>
          </FieldGroup>

          {/* 12. Account No. or PayNow */}
          <FieldGroup
            label={isPayNow ? "12. PayNow No." : "12. Account No."}
            required
            error={errors.account_no}
          >
            <input
              type="text"
              name="account_no"
              value={fields.account_no}
              onChange={handleChange}
              className={errors.account_no ? "has-error" : ""}
              placeholder={isPayNow ? "Mobile number or UEN" : "Bank account number"}
            />
          </FieldGroup>

          {/* 13. Refund reason */}
          <FieldGroup label="13. Refund Reason" required error={errors.refund_reason}>
            <textarea name="refund_reason" value={fields.refund_reason}
              onChange={handleChange} className={errors.refund_reason ? "has-error" : ""}
              placeholder="Explain the reason for this refund request" />
          </FieldGroup>

          {apiError && <div className="error-msg" style={{ marginBottom: 14 }}>{apiError}</div>}

          <hr className="section-divider" />
          <button type="submit" className="submit-btn" disabled={submitting}>
            {submitting ? "Submitting…" : "Submit Refund Request"}
          </button>

        </form>
      </div>
      )}
    </div>
  );
}

