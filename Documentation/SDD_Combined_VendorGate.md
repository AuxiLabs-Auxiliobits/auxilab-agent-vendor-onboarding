# VendorGate Platform — Combined Software Design Document (SDD)
**Version:** 1.0  
**Date:** 2026-06-28  
**Status:** Production  

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Product Overview](#3-product-overview)
4. [Shared Infrastructure](#4-shared-infrastructure)
5. [Component 1 — Vendor Onboarding Portal](#5-component-1--vendor-onboarding-portal)
6. [Component 2 — VendorGate AI ChatBot](#6-component-2--vendorgate-ai-chatbot)
7. [Component 3 — Reviewer App](#7-component-3--reviewer-app)
8. [Data Models](#8-data-models)
9. [AI & Extraction Pipeline](#9-ai--extraction-pipeline)
10. [Configuration & Environment](#10-configuration--environment)
11. [Security Design](#11-security-design)
12. [Email Notification System](#12-email-notification-system)
13. [Audit Trail System](#13-audit-trail-system)
14. [Deployment Architecture](#14-deployment-architecture)

---

## 1. Executive Summary

**VendorGate** is an enterprise-grade, AI-augmented vendor onboarding platform consisting of three independently deployable Streamlit applications ("plug-and-play components"). It automates the entire lifecycle of vendor compliance registration — from document submission through AI extraction, cross-document validation, human review, and final ERP activation.

| Component | Entry Point | Port (default) | Audience |
|---|---|---|---|
| Vendor Onboarding Portal | `VendorApp.py` | 8501 | Vendors / Suppliers |
| AI ChatBot | `VendorAssistantChatBOT.py` | 8502 | Vendors (self-service support) |
| Reviewer App | `ReviewerApp.py` | 8503 | Internal Procurement / Auditors |

All three components share a **common data layer** (`utils/`) and a **flat-file persistence layer** (`data/submissions.csv`, `data/audit_logs.csv`), making the platform deployable without a database server.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        VendorGate Platform                           │
│                                                                      │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────┐  │
│  │ VendorApp.py    │  │VendorAssistant   │  │  ReviewerApp.py    │  │
│  │ (Port 8501)     │  │ChatBOT.py (8502) │  │  (Port 8503)       │  │
│  │                 │  │                  │  │                    │  │
│  │ • Home          │  │ • NLP Chat UI    │  │ • Admin Dashboard  │  │
│  │ • Submit Form   │  │ • Status Lookup  │  │ • Vendor Master    │  │
│  │ • Track Status  │  │ • Gemini LLM     │  │ • Approve/Reject   │  │
│  └────────┬────────┘  └────────┬─────────┘  └────────┬───────────┘  │
│           │                   │                      │              │
│           └───────────────────┴──────────────────────┘              │
│                               │                                      │
│                    ┌──────────▼──────────┐                           │
│                    │   utils/ (shared)   │                           │
│                    │                     │                           │
│                    │ data_manager.py     │                           │
│                    │ pipeline.py         │                           │
│                    │ extractor.py        │                           │
│                    │ notifier.py         │                           │
│                    │ style_utils.py      │                           │
│                    └──────────┬──────────┘                           │
│                               │                                      │
│           ┌───────────────────┼────────────────────┐                 │
│           │                   │                    │                 │
│  ┌────────▼──────┐  ┌─────────▼───────┐  ┌────────▼──────┐         │
│  │data/          │  │uploads/          │  │ Gemini API    │         │
│  │submissions.csv│  │{ref}/docs + JSON │  │ (Google AI)   │         │
│  │audit_logs.csv │  │                  │  │               │         │
│  └───────────────┘  └──────────────────┘  └───────────────┘         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Product Overview

### 3.1 Plug-and-Play Design
Each component is a standalone Streamlit application. They **share** `utils/` and `data/` but can be deployed independently on separate ports, servers, or containers. There are no cross-app HTTP calls; all integration is through the shared file system.

### 3.2 Workflow Overview

```
Vendor fills questionnaire → Uploads 5 docs → Submission saved
         ↓
AI pipeline triggered (background thread)
- Gemini extracts structured data from each doc
- 10 cross-document consistency rules evaluated
- Risk flags generated
- Auto-recommendation: approve / request_info / escalate
         ↓
Status → "Awaiting human review"
         ↓
Reviewer logs in → Views AI analysis → Takes action
- Approve → ERP key assigned → Vendor notified
- Request info → Action items sent → Vendor re-uploads
- Reject → Vendor notified
         ↓
Approved vendors written to Vendor Master ledger
```

---

## 4. Shared Infrastructure

### 4.1 `utils/data_manager.py`
Central persistence and data access layer.

| Function | Description |
|---|---|
| `read_submissions()` | Reads all records from `data/submissions.csv` |
| `save_single_submission(sub)` | Thread-safe upsert of one submission record |
| `get_submission_by_id(ref)` | Lookup by reference code |
| `write_audit_log(action, actor, ref, detail)` | Append to `data/audit_logs.csv` |
| `get_audit_logs(ref)` | Return filtered audit trail for one vendor |
| `authenticate_user(username, password)` | Validate reviewer credentials |
| `get_submission_upload_path(ref, filename)` | Resolve absolute path for uploaded files |

**Thread Safety:** A `threading.Lock` (`_db_lock`) guards all CSV reads and writes.

### 4.2 `utils/style_utils.py`
Injects shared CSS (Outfit font, status badges, card styles, wizard steps, mobile warning overlay). Called at the top of every page via `inject_custom_css()`.

### 4.3 `utils/notifier.py`
SMTP email dispatcher. Reads all credentials from `.env`. Falls back to a console/session-state simulator when credentials are missing.

**Notification events:**
- `send_submission_received_email()` — on new submission
- `send_approved_email()` — on reviewer approval
- `send_action_required_email()` — on reviewer requesting corrections

### 4.4 `.env` — Central Configuration
All runtime configuration (SMTP, Gemini model, thresholds, system date) is stored in `.env`. No values are hardcoded in Python files.

---

## 5. Component 1 — Vendor Onboarding Portal

### Entry Point
`VendorApp.py` → 3 pages via `st.navigation()`

| Page | File | Purpose |
|---|---|---|
| 🏠 Home | `views/0_Home.py` | Welcome page + instructions |
| 📝 Submit Form | `views/1_Submit_Form.py` | 5-step wizard for data entry + doc upload |
| 🔍 Track Status | `views/2_Track_Status.py` | Real-time milestone tracking + corrections |

### Submit Form (5-Step Wizard)
1. **Company Details** — Legal name, DBA, DUNS, website, FEIN, tax classification, state of incorporation
2. **Contact Information** — Primary contact, AP contact, HQ and billing addresses
3. **Business Profile** — Years in business, revenue, employee count, payment terms, COI details
4. **Document Upload** — W-9, COI, Bank Letter, Questionnaire, Company Registration (PDF/PNG/JPG/TXT)
5. **Review & Submit** — Summary review → generates reference code → triggers AI pipeline

### Track Status Page
- **Milestone timeline** — Received → AI Analysis (2-step visual tracker)
- **Action Required section** — Lists specific rule failures with re-upload instructions
- **Correction Desk** — File upload widgets for replacing deficient documents
- **Questionnaire editor** — Inline editing of all submitted fields with audit logging
- **AI Analysis checkbox** — Manual override flag (auto-set to `True`)
- **Right panel — Audit trail** — Collapsible expander showing full audit log with field-change diffs
- **Right panel — Status info** — Current milestone, registration date, last update

---

## 6. Component 2 — VendorGate AI ChatBot

### Entry Point
`VendorAssistantChatBOT.py` (standalone, no `st.navigation()`)

### Layout
Two-column layout:
- **Left column** — Application Lookup + Status Card
- **Right column** — AI Chat Interface

### Application Lookup
- Vendor enters their reference code (e.g., `VND-2026-00001`)
- System loads the submission from `data_manager`
- Status card renders: compliance score bar, document checklist, risk banner

### AI Chat Interface
- **LLM:** Google Gemini 2.5 Flash via `google-genai` SDK
- **Context injection:** Full submission data is serialized into the system prompt — including status, scores, rule results, risk flags, reviewer comments
- **NLP processing:** Gemini interprets natural language questions like "What documents are missing?", "Why did I fail?", "What are my next steps?"
- **Quick-question chips:** 6 pre-built one-click questions
- **Conversation history:** Last 20 message turns are sent in each API call
- **Fallback:** If API key is missing or quota is exceeded, a clear error message is shown

### Security
- No PII is sent to Gemini beyond what the vendor already submitted
- API key loaded from `.env`; never exposed in UI

---

## 7. Component 3 — Reviewer App

### Entry Point
`ReviewerApp.py` → 2 pages via `st.navigation()`

| Page | File | Purpose |
|---|---|---|
| 📊 Admin Dashboard | `views/3_Dashboard.py` | Review queue, AI analysis, approve/reject |
| 📋 Vendor Master | `views/4_Vendor_Master.py` | Approved vendor ledger |

### Admin Dashboard
**Authentication:** Username/password gate (credentials stored in `data_manager`).

**Review Queue:** Filterable table of all submissions showing status, score, recommendation, risk flags.

**Vendor Detail Panel:** On row selection:
- Full AI extraction results per document
- 10 consistency rule results with pass/fail badges
- High/medium risk flag breakdown
- Document completeness scores
- AI auto-recommendation (approve / request_info / escalate)

**Action Buttons:**
- ✅ **Approve** → Generates ERP vendor key → updates status → sends approval email → logs to audit trail
- ⚠️ **Request Info** → Opens text area for action items → sends action-required email to vendor → logs audit
- ❌ **Reject** → Updates status → logs rejection
- All actions trigger confirmation overlay before executing

### Vendor Master Ledger
- Displays all approved vendors with ERP key, approval date, COI expiry status
- Colour-coded COI expiry warnings (red = expired, amber = expiring within 30 days)
- Date comparison uses `SYSTEM_DATE` from `.env`

---

## 8. Data Models

### 8.1 Submission Record (CSV columns)

| Field | Type | Description |
|---|---|---|
| `submission_id` | `str` | Auto-generated, e.g. `VND-2026-00001` |
| `legal_name` | `str` | Company legal name |
| `dba_name` | `str` | Doing Business As |
| `website` | `str` | Company website |
| `fein` | `str` | Federal EIN |
| `contact_email` | `str` | Primary contact email |
| `status` | `str` | Processing / Awaiting human review / Approved / Action Required / Rejected |
| `overall_score` | `float` | Weighted completeness score 0–100 |
| `risk_recommendation` | `str` | approve / request_info / escalate |
| `risk_flags` | `JSON str` | `{"high": [...], "medium": [...]}` |
| `consistency_checks` | `JSON str` | Array of 10 rule results |
| `document_scores` | `JSON str` | Per-doc completeness scores |
| `extracted_data` | `JSON str` | Raw Gemini-extracted schemas |
| `erp_vendor_key` | `str` | Assigned on approval |
| `ai_analysis_done` | `bool` | Manual override flag |
| `w9_filename` / `coi_filename` / etc. | `str` | Uploaded file names |
| `created_at` / `updated_at` | `datetime str` | Timestamps |

### 8.2 Audit Log Record

| Field | Description |
|---|---|
| `timestamp` | ISO datetime |
| `action` | e.g. `questionnaire.edited`, `pipeline.complete`, `human.approved` |
| `actor` | `system` or reviewer username |
| `submission_id` | Reference code |
| `detail` | Human-readable description of the change |

---

## 9. AI & Extraction Pipeline

### Pipeline Steps (triggered on submission)
1. **File path resolution** — Locate uploaded documents
2. **Text extraction** — PDF text via `pypdf`; images return filename hint
3. **Gemini structured extraction** — Per document, Pydantic schema forced via `response_schema`
4. **Completeness scoring** — Weighted field presence check per document type
5. **10 cross-document consistency rules** — Fuzzy name matching, COI expiry, liability limits, FEIN match, state match, etc.
6. **Risk classification** — High / medium flags generated
7. **Auto-recommendation** — `approve`, `request_info`, or `escalate`

### Consistency Rules Summary

| Rule | Check |
|---|---|
| Rule 1 | W-9 Legal Name vs COI Insured Name (fuzzy, ≥70% similarity) |
| Rule 2 | W-9 Legal Name vs Bank Account Name (fuzzy, ≥70%) |
| Rule 3 | COI is not expired (vs `SYSTEM_DATE`) |
| Rule 4 | COI General Liability ≥ `COI_MIN_LIABILITY_USD` ($1M) |
| Rule 5 | Cyber Liability coverage present |
| Rule 6 | COI expiry not within `COI_EXPIRY_WARNING_DAYS` (30 days) |
| Rule 7 | Questionnaire Beneficiary name vs Bank Account Name (fuzzy) |
| Rule 8 | Contact email domain matches website domain (non-generic) |
| Rule 9 | FEIN on W-9 matches questionnaire FEIN |
| Rule 10 | State of Incorporation consistent between Questionnaire and Company Reg |

### Quota Management
- 4-second delay (`GEMINI_CALL_DELAY_SECONDS`) between each of the 5 Gemini calls
- Retry with exponential backoff on 429/503 errors (configurable via `GEMINI_MAX_RETRIES` and `GEMINI_RETRY_WAIT_BASE`)
- Graceful fallback to smart mock extractor on all retries exhausted

### Agent (LangChain)
`agent/extractor_agent.py` — Used for cross-validation view on the Track Status page. Uses LangChain `ChatGoogleGenerativeAI` to extract a unified cross-vendor entity comparison JSON (legal names, DUNS, EIN, insurance limits, bank details) from all uploaded documents simultaneously.

---

## 10. Configuration & Environment

All values configurable via `.env` in the project root:

```env
# SMTP
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=youremailhere@domain.com
SMTP_PASSWORD=<app-password>
SENDER_EMAIL=youremailhere@domain.com
SENIOR_AUDITOR_EMAIL=youremailhere@domain.com
REVIEWER_EMAIL=youremailhere@domain.com

# Gemini AI
GEMINI_API_KEY=<key>
GEMINI_MODEL=gemini-2.5-flash
GEMINI_AGENT_MODEL=gemini-2.5-flash
GEMINI_MAX_TOKENS=4096
GEMINI_MAX_RETRIES=5
GEMINI_RETRY_WAIT_BASE=15
GEMINI_CALL_DELAY_SECONDS=4

# Compliance Thresholds
COI_MIN_LIABILITY_USD=1000000
COI_EXPIRY_WARNING_DAYS=30
SYSTEM_DATE=2026-06-09

# Branding
APP_NAME=VendorGate
APP_SLA_HOURS=1
SUBMISSION_ID_PREFIX=VND-2026
```

---

## 11. Security Design

| Area | Implementation |
|---|---|
| Reviewer authentication | Username/password checked via `data_manager.authenticate_user()` |
| Session isolation | Streamlit session state is per-browser-session |
| File storage | Uploaded docs stored in `uploads/{ref}/` — no public web serving |
| API key handling | Loaded from `.env` only; never rendered in UI |
| Audit trail | All state changes logged with actor, timestamp, and field diffs |
| Mobile access | Reviewer dashboard blocked on mobile via CSS/HTML overlay |

---

## 12. Email Notification System

**Trigger → Recipient → Content:**

| Event | Recipient | Template |
|---|---|---|
| New submission | Vendor contact email | Submission received confirmation with reference code |
| Approved | Vendor contact email | Approval with ERP vendor key |
| Action Required | Vendor contact email | Bullet list of deficiencies |
| Full packet complete | Senior Auditor | Packet ready for review notification |

All emails have both plain-text and HTML alternatives. Falls back to session-state simulator (console log + toast) when SMTP credentials are not set.

---

## 13. Audit Trail System

Every state change is logged to `data/audit_logs.csv`:
- **Action types:** `submission.received`, `pipeline.queued`, `pipeline.start`, `pipeline.complete`, `questionnaire.edited`, `document.reuploaded`, `human.approved`, `human.rejected`, `human.action_required`
- **Field-change format:** `Field "fieldName" changed from "oldValue" to "newValue"`
- **Displayed in:** Track Status page (right column, collapsible expander, sorted newest-first)

---

## 14. Deployment Architecture

### Local Development (current)
```
streamlit run VendorApp.py            # Port 8501
streamlit run VendorAssistantChatBOT.py # Port 8502
streamlit run ReviewerApp.py          # Port 8503
```

### Shared Filesystem Requirements
All three apps must share access to:
- `data/submissions.csv`
- `data/audit_logs.csv`
- `uploads/` directory
- `.env` file

### Scaling Considerations
- For multi-instance deployments, replace the CSV persistence layer with a database (PostgreSQL / SQLite) and update `data_manager.py`
- The AI pipeline runs in a `ThreadPoolExecutor` — inherently async and non-blocking
- File-based locking (`threading.Lock`) is sufficient for single-server deployments
