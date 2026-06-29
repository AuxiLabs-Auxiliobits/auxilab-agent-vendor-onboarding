# SDD — Component 3: Reviewer App
**Product:** VendorGate  
**Entry Point:** `ReviewerApp.py`  
**Version:** 1.0  
**Date:** 2026-06-28  

---

## Table of Contents
1. [Overview](#1-overview)
2. [Page Structure](#2-page-structure)
3. [Authentication Gate](#3-authentication-gate)
4. [Page 1 — Admin Dashboard](#4-page-1--admin-dashboard)
5. [Review Queue Table](#5-review-queue-table)
6. [Vendor Detail Panel](#6-vendor-detail-panel)
7. [AI Analysis Viewer](#7-ai-analysis-viewer)
8. [Action System (Approve / Reject / Request Info)](#8-action-system-approve--reject--request-info)
9. [ERP Key Generation](#9-erp-key-generation)
10. [Email Notifications from Actions](#10-email-notifications-from-actions)
11. [Page 2 — Vendor Master Ledger](#11-page-2--vendor-master-ledger)
12. [COI Expiry Monitoring](#12-coi-expiry-monitoring)
13. [Audit Trail Integration](#13-audit-trail-integration)
14. [Security Design](#14-security-design)
15. [Data Flow Diagram](#15-data-flow-diagram)

---

## 1. Overview

The **Reviewer App** is the internal-facing application used by the procurement team and senior auditors to:
1. Review AI-analyzed vendor submissions
2. Inspect cross-document consistency check results
3. Take final decisions: Approve / Request More Info / Reject
4. View the permanent approved vendor ledger
5. Monitor COI expiry dates across all approved vendors

**Access control:** Username/password authentication gate.  
**Desktop only:** Mobile browser access is intercepted by a CSS-based overlay.

---

## 2. Page Structure

```
ReviewerApp.py
└── st.navigation()
    ├── views/3_Dashboard.py    📊 Admin Dashboard
    └── views/4_Vendor_Master.py 📋 Vendor Master
```

---

## 3. Authentication Gate

**File:** `views/3_Dashboard.py` (top of file)

### Login Screen
If `st.session_state["reviewer_authenticated"] == False`, a full-screen login form is rendered in a centered column (columns `[1, 1.5, 1]`).

```
🔐
Reviewer Portal Login

[ Username         ]
[ Password         ] (masked)
[ Authenticate     ]
```

### Credential Validation
```python
from utils.data_manager import authenticate_user
if authenticate_user(username, password):
    st.session_state["reviewer_authenticated"] = True
    st.session_state["reviewer_username"] = username
```

Credentials are stored in `data_manager.py` (hashed comparison or direct match depending on implementation). The reviewer username is carried in session state and used in all audit log entries.

### Session Persistence
Authentication persists for the duration of the browser session. Refreshing the page maintains the session (Streamlit session state behavior).

---

## 4. Page 1 — Admin Dashboard

**File:** `views/3_Dashboard.py`

### Layout
```
┌──────────────────────────────────────────────────────────────┐
│  📊 VendorGate Reviewer Dashboard                            │
│  Logged in as: {reviewer_username}           [Logout]        │
├────────────────────────────────────┬─────────────────────────┤
│  Review Queue (left/main)          │  Vendor Detail (right)  │
│                                    │                         │
│  Filters: Status | Score | Date    │  Selected vendor info   │
│  ┌────────────────────────────┐    │  AI analysis results    │
│  │ Submission table           │    │  Action buttons         │
│  │ (selectable rows)          │    │                         │
│  └────────────────────────────┘    │                         │
└────────────────────────────────────┴─────────────────────────┘
```

### Dashboard Header
- Page title and icon
- "Logged in as: {username}" label
- Logout button → clears `reviewer_authenticated` + `reviewer_username`, triggers `st.rerun()`
- Summary KPI metrics: Total submissions | Pending | Approved | Action Required

---

## 5. Review Queue Table

### Data Source
`read_submissions()` → all records from `data/submissions.csv`

### Columns Displayed
| Column | Source | Notes |
|---|---|---|
| Reference | `submission_id` | Monospace styled |
| Company | `legal_name` | — |
| Status | `status` | Coloured badge |
| Score | `overall_score` | Rounded to 1dp |
| Recommendation | `risk_recommendation` | approve / request_info / escalate |
| Risk Flags | `risk_flags` (parsed) | Count of high/medium |
| Submitted | `created_at` | Date only |
| Last Updated | `updated_at` | Datetime |

### Filtering
Filters available via `st.selectbox` / `st.slider`:
- Status filter: All / Processing / Awaiting human review / Action Required / Approved / Rejected
- Score filter: Slider 0–100
- Date range: Date picker

### Row Selection
Clicking a row (or selecting via radio button) loads the vendor into the right-side detail panel.

---

## 6. Vendor Detail Panel

Rendered in the right column when a submission is selected.

### Sections

#### Company Header
- Legal name, DBA, reference code, website
- Submission and last-update timestamps
- Current status badge

#### Contact Information
- Primary contact name, email, phone
- AP contact name, email, phone

#### Document Status
For each of the 5 required documents:
- Filename if uploaded + ✅
- "Not uploaded" + ❌ if missing

#### Questionnaire Summary
Key-value display of all questionnaire fields:
- Legal Name, DBA, Website, DUNS, FEIN
- Tax classification, State of Incorporation
- Addresses (HQ and billing)
- Business profile (years, revenue, employees)
- Bank beneficiary, SWIFT/BIC

---

## 7. AI Analysis Viewer

### Document Completeness Scores
Rendered as a 5-column metric grid:

| Doc | Score | Visual |
|---|---|---|
| W-9 | 95.0% | Green progress bar |
| COI | 80.0% | Amber/green bar |
| Bank | 60.0% | Amber bar |
| Questionnaire | 88.0% | Green bar |
| Company Reg | 40.0% | Red bar |
| **Overall** | **72.6%** | Bold combined |

### 10 Cross-Document Consistency Rules

Each rule displayed as a card with:
- Rule number and name
- **✓ VERIFIED** (green badge) or **❌ DISCREPANCY** (red badge)
- Detail string (e.g., "Similarity: 85% ('Alpha Ventures LLC' vs 'Alpha Ventures')")
- Left border colour-coded (green/red)

Rules displayed:
1. W-9 Legal Name vs COI Insured Name
2. W-9 Legal Name vs Bank Account Name
3. COI Expiration Check
4. COI Liability Limit Check (≥ $1M)
5. Cyber Liability Presence
6. COI Expiry Within 30 Days
7. Questionnaire Beneficiary vs Bank Account Name
8. Contact Email Domain vs Website Domain
9. FEIN Match (W-9 vs Questionnaire)
10. State of Incorporation Consistency

### Risk Flags Section

**High Risk** (red banner):
- Invalid EIN format
- PO Box only address
- Missing mandatory document

**Medium Risk** (amber banner):
- Business age < 2 years
- No cyber liability
- Any failed consistency rule

### Auto-Recommendation Banner

| Recommendation | Colour | Meaning |
|---|---|---|
| `approve` | Green | ≥1 high risk flag absent; score ≥80%; ≤2 medium risks |
| `request_info` | Amber | Score < 80% or > 2 medium risks |
| `escalate` | Red | ≥1 high risk flag present |

---

## 8. Action System (Approve / Reject / Request Info)

### Action Buttons
Three buttons rendered below the AI analysis section:

```
[ ✅ Approve ]   [ ⚠️ Request Info ]   [ ❌ Reject ]
```

### Confirmation Overlay
Clicking any button opens a confirmation section (inline, not a modal):
- Summary of action
- For "Request Info": text area for action items (one per line)
- Confirm / Cancel buttons

### Approve Action
On confirmation:
1. `sub["status"]` → `"Approved"`
2. `sub["erp_vendor_key"]` → generated ERP key (e.g., `ERP-ALPHA-001`)
3. `save_single_submission(sub)`
4. `send_approved_email(vendor_email, ref, company_name, erp_key)`
5. `write_audit_log("human.approved", reviewer_username, ref, "ERP key: {erp_key}")`
6. `st.success()` toast
7. `st.rerun()`

### Request Info Action
On confirmation:
1. `sub["status"]` → `"Action Required"`
2. `sub["reviewer_comments"]` → entered action items text
3. `save_single_submission(sub)`
4. `send_action_required_email(vendor_email, ref, company_name, items_list)`
5. `write_audit_log("human.action_required", reviewer_username, ref, items_text)`
6. `st.warning()` toast

### Reject Action
On confirmation:
1. `sub["status"]` → `"Rejected"`
2. Optional rejection reason saved to `reviewer_comments`
3. `save_single_submission(sub)`
4. `write_audit_log("human.rejected", reviewer_username, ref, reason)`
5. `st.error()` toast

---

## 9. ERP Key Generation

Generated at approval time:

```python
def generate_erp_key(company_name: str, submission_id: str) -> str:
    # Takes first word of company name (uppercase, alphanumeric only)
    # Appends sequential suffix from submission_id
    prefix = re.sub(r'[^A-Z0-9]', '', company_name.split()[0].upper())[:8]
    seq = submission_id.split('-')[-1]  # e.g., "00001"
    return f"ERP-{prefix}-{seq}"
    # Example: "ERP-ALPHA-00001"
```

---

## 10. Email Notifications from Actions

All emails sent via `utils/notifier.py` → SMTP (or simulation fallback).

| Action | Function called | Recipient |
|---|---|---|
| Approve | `send_approved_email()` | `sub["contact_email"]` |
| Request Info | `send_action_required_email()` | `sub["contact_email"]` |
| Full packet ready | `send_auditor_notification()` (called from pipeline) | `SENIOR_AUDITOR_EMAIL` (from .env) |

Email addresses: all loaded from `.env`. Default: `youremailhere@domain.com`.

---

## 11. Page 2 — Vendor Master Ledger

**File:** `views/4_Vendor_Master.py`

### Purpose
A permanent, read-only ledger of all approved vendors. Used for ERP reconciliation and ongoing COI monitoring.

### Data Source
`read_submissions()` filtered to `status == "Approved"`.

### Columns

| Column | Source | Notes |
|---|---|---|
| ERP Key | `erp_vendor_key` | Monospace, bold |
| Company | `legal_name` | — |
| DBA | `dba_name` | — |
| FEIN | `fein` | — |
| State | `state_of_incorporation` | — |
| Payment Terms | `payment_terms` | — |
| COI Expiry | From `extracted_data` JSON | Colour-coded |
| COI Status | Calculated | Active / Expiring Soon / Expired |
| Approved Date | `updated_at` | Date only |
| Reviewer | `reviewer_username` (if stored) | — |

### Filtering
- Search by company name or ERP key
- Filter by COI status: All / Active / Expiring Soon / Expired

---

## 12. COI Expiry Monitoring

Uses `SYSTEM_DATE` loaded from `.env` (default: `2026-06-09`).

```python
expiry = parse_date(extracted_coi.get("earliestExpiryDate"))
if not expiry:
    coi_status = "Unknown"
elif expiry < SYSTEM_DATE:
    coi_status = "🔴 Expired"
elif (expiry - SYSTEM_DATE).days <= COI_EXPIRY_WARNING_DAYS:
    coi_status = "🟡 Expiring Soon"
else:
    coi_status = "🟢 Active"
```

### Visual Treatment

| Status | Row highlight | Badge |
|---|---|---|
| Active | None | 🟢 Active |
| Expiring Soon | Amber background | 🟡 Expiring Soon |
| Expired | Red background | 🔴 Expired |
| Unknown | None | ⚪ Unknown |

---

## 13. Audit Trail Integration

All reviewer actions are logged to `data/audit_logs.csv` via `write_audit_log()`.

### Action Types

| Action string | Triggered by |
|---|---|
| `human.approved` | Approve button click |
| `human.rejected` | Reject button click |
| `human.action_required` | Request Info button click |
| `human.login` | Successful login |
| `human.logout` | Logout button click |

### Viewing Audit Trail
The Dashboard includes an expandable "📋 Full Audit Log" section showing all logs across all vendors (reviewer view), filterable by reference code.

---

## 14. Security Design

| Control | Implementation |
|---|---|
| Authentication | Username/password checked on every page load |
| Session timeout | Session ends when browser tab is closed (Streamlit default) |
| Reviewer identity | `reviewer_username` from session state written to every audit log |
| Mobile blocking | CSS `.desktop-only-content` + `.mobile-warning-block` overlay |
| Read-only ledger | Vendor Master has no edit controls — only the Dashboard can change status |
| Action confirmation | Every destructive action requires an explicit second click to confirm |

---

## 15. Data Flow Diagram

```
Reviewer logs in
      │
      ▼
authenticate_user() ✓
      │
      ▼
read_submissions() → all records from submissions.csv
      │
      ▼
Review Queue table rendered
      │
Reviewer selects a submission
      │
      ▼
AI analysis section:
  - Document scores (from document_scores JSON)
  - Consistency rules (from consistency_checks JSON)
  - Risk flags (from risk_flags JSON)
  - Auto-recommendation (risk_recommendation field)
      │
Reviewer clicks: Approve / Request Info / Reject
      │
      ├── [Approve]
      │     ├── generate_erp_key()
      │     ├── save_single_submission() → submissions.csv
      │     ├── send_approved_email()   → SMTP / simulator
      │     └── write_audit_log("human.approved", ...)
      │
      ├── [Request Info]
      │     ├── save_single_submission() → status="Action Required"
      │     ├── send_action_required_email() → vendor
      │     └── write_audit_log("human.action_required", ...)
      │
      └── [Reject]
            ├── save_single_submission() → status="Rejected"
            └── write_audit_log("human.rejected", ...)
                        │
                        ▼
              Track Status page reflects new status
              Vendor ChatBot reads updated record
              Vendor Master ledger shows new approved vendor
```
