# SDD — Component 1: Vendor Onboarding Portal
**Product:** VendorGate  
**Entry Point:** `VendorApp.py`  
**Version:** 1.0  
**Date:** 2026-06-28  

---

## Table of Contents
1. [Overview](#1-overview)
2. [Page Structure](#2-page-structure)
3. [Page 0 — Home](#3-page-0--home)
4. [Page 1 — Submit Form (5-Step Wizard)](#4-page-1--submit-form-5-step-wizard)
5. [Page 2 — Track Status](#5-page-2--track-status)
6. [Document Upload System](#6-document-upload-system)
7. [AI Pipeline Integration](#7-ai-pipeline-integration)
8. [Inline Questionnaire Editor](#8-inline-questionnaire-editor)
9. [Correction Desk](#9-correction-desk)
10. [Audit Trail Display](#10-audit-trail-display)
11. [Reference Code System](#11-reference-code-system)
12. [State Management](#12-state-management)
13. [Data Flow Diagram](#13-data-flow-diagram)

---

## 1. Overview

The **Vendor Onboarding Portal** is the primary vendor-facing application. It allows suppliers to:
1. Submit their full compliance documentation package
2. Receive a unique reference code
3. Track their application status in real-time
4. Correct deficiencies flagged by the AI system

**Tech stack:** Streamlit multi-page app · Python · CSS (Outfit font, custom cards) · Google Gemini API · pypdf · python-dotenv

---

## 2. Page Structure

```
VendorApp.py
└── st.navigation()
    ├── views/0_Home.py          🏠 Home
    ├── views/1_Submit_Form.py   📝 Submit Form (5-step wizard)
    └── views/2_Track_Status.py  🔍 Track Status
```

---

## 3. Page 0 — Home

**File:** `views/0_Home.py`

### Purpose
Landing/welcome page introducing the portal and guiding vendors to the submission form.

### Sections
| Section | Content |
|---|---|
| Hero banner | VendorGate logo, tagline, "Start Onboarding" CTA button |
| Process overview | 4-step visual guide: Submit → AI Review → Human Review → Approval |
| Requirements card | List of 5 mandatory documents with format requirements |
| Green info banner | SLA note (under 1 Minute automated review) |

### Technical Notes
- Uses `inject_custom_css()` for consistent styling
- No session state or data interaction

---

## 4. Page 1 — Submit Form (5-Step Wizard)

**File:** `views/1_Submit_Form.py`

### Wizard Architecture
The form is divided into 5 sequential steps, tracked in `st.session_state["current_step"]` (0–4). Navigation is controlled by "Back" / "Continue" buttons. Each step validates required fields before allowing progression.

### Step 1 — Company Details

| Field | Type | Validation |
|---|---|---|
| Legal Name (as shown on W-9) | `text_input` | Required |
| Doing Business As (DBA) | `text_input` | Optional |
| DUNS Number | `text_input` | 9-digit numeric |
| Website | `text_input` | Optional |
| FEIN / EIN | `text_input` | Required |
| Tax ID / Registration # | `text_input` | Required |
| Tax Classification | `selectbox` | LLC/C-Corp/S-Corp/Partnership/Sole Proprietor |
| State of Incorporation | `selectbox` | US states |
| Is 1099 Eligible? | `checkbox` | — |
| Backup Withholding Exempt? | `checkbox` | — |

### Step 2 — Contact Information

| Field | Type |
|---|---|
| Primary Contact Name | `text_input` |
| Primary Contact Email | `text_input` |
| Primary Contact Phone | `text_input` |
| AP Contact Name | `text_input` |
| AP Contact Email | `text_input` |
| AP Contact Phone | `text_input` |
| Headquarters Address (Street, City, State, ZIP) | `text_input` × 4 |
| Billing Address (Street, City, State, ZIP) | `text_input` × 4 |

### Step 3 — Business Profile

| Field | Type | Notes |
|---|---|---|
| Years in Business | `number_input` | min=0, max=200 |
| Annual Revenue (USD) | `number_input` | Optional |
| Employee Count | `number_input` | Optional |
| Products / Services Description | `text_area` | — |
| Payment Terms | `selectbox` | Net 30 / Net 45 / Net 60 / Due on Receipt |
| Conflict of Interest | `checkbox` | — |
| Number of References | `number_input` | — |
| Bank Beneficiary Name | `text_input` | — |
| SWIFT/BIC Code | `text_input` | — |

### Step 4 — Document Upload

Five document upload widgets (each: PDF, PNG, JPG, JPEG, TXT; 200MB max):

| Document | Field Key | Purpose |
|---|---|---|
| W-9 Tax Form | `w9_file` | IRS tax classification proof |
| Certificate of Insurance (COI) | `coi_file` | Liability insurance verification |
| Bank Verification Letter | `bank_letter_file` | Bank account confirmation |
| Vendor Questionnaire | `questionnaire_file` | Filled questionnaire PDF |
| Company Registration | `company_reg_file` | Incorporation/registration certificate |

**Pre-fill:** If a draft was saved in a previous session, previously uploaded filenames are shown.

**Draft saving:** Files are saved to `uploads/draft-{uuid}/` on upload.

### Step 5 — Review & Submit

- Displays a full summary table of all entered data
- Shows document upload status (✅/❌ per document)
- "Edit" buttons to jump back to any step
- **Submit button** → triggers:
  1. Reference code generation (`VND-2026-XXXXX`)
  2. Draft files moved to `uploads/{ref}/`
  3. Questionnaire data serialized to `uploads/{ref}/questionnaire_data.json`
  4. Submission record saved to `data/submissions.csv`
  5. Confirmation email sent via `notifier.py`
  6. AI pipeline queued via `start_async_analysis()`
  7. Session state cleared; reference code displayed to vendor

### Submission ID Generation
```python
def generate_submission_id():
    # Reads all existing IDs from submissions.csv
    # Finds the highest VND-2026-XXXXX number
    # Returns next sequential ID
    prefix = os.getenv("SUBMISSION_ID_PREFIX", "VND-2026")
    return f"{prefix}-{next_num:05d}"
```

---

## 5. Page 2 — Track Status

**File:** `views/2_Track_Status.py`

### URL Parameter Support
Reference code is read from query param: `?ref=VND-2026-00001` and pre-fills the lookup box.

### Layout
```
┌──────────────────────────────────────┬──────────────────────┐
│  col1 (weight 2)                     │  col2 (weight 1)     │
│                                      │                      │
│  Company card (name + ref code)      │  AI Analysis ☑       │
│  Milestone timeline                  │  Status info panel   │
│  Status banner (green/amber/red)     │  Audit Trail ▼       │
│  Required Actions list               │                      │
│  Correction Desk (uploads)           │                      │
│  Questionnaire Summary               │                      │
│  Edit Questionnaire expander         │                      │
│  Cross-validation JSON viewer        │                      │
└──────────────────────────────────────┴──────────────────────┘
```

### Milestone Timeline
Visual 2-step tracker rendered as inline HTML:
- **Received** (step 0) — always green ✓
- **AI Analysis** (step 1) — green ✓ if `extraction_results.json` exists, else active

### Status Banners

| Status | Banner Color | Message |
|---|---|---|
| Processing | Blue | "Automated pipeline is currently analyzing…" |
| Awaiting human review | Green | "Verification Successful! Sent to Senior Auditor…" |
| Action Required | Amber | "Action Pending on Your Side" + list of issues |
| Approved | Green | "Approved!" + ERP key |
| Rejected | Red | "Application Rejected" |

### Required Actions List
Generated from `consistency_checks` JSON. For each failed rule:
- Displays the rule name and failure detail
- Suggests which document to re-upload

Also shows missing mandatory documents as individual action items.

### Auto-refresh
In "Processing" status, page auto-refreshes every few seconds via `st_autorefresh` or `time.sleep` + `st.rerun`.

---

## 6. Document Upload System

### Storage Structure
```
uploads/
├── draft-{uuid}/          ← temporary during form fill
│   ├── w9Form.pdf
│   └── ...
└── VND-2026-00001/        ← finalized on submission
    ├── w9Form.pdf
    ├── COI.pdf
    ├── bankLetter.pdf
    ├── questionnaire.pdf
    ├── companyReg.pdf
    ├── questionnaire_data.json
    ├── extraction_results.json    ← written by AI pipeline
    └── pipeline_progress.txt      ← transient, deleted after run
```

### File Naming
Files are saved with their original names. Duplicate handling: overwrite on re-upload.

### Re-upload (Correction Desk)
Vendors can replace individual documents on the Track Status page. On re-upload:
1. File saved to `uploads/{ref}/`
2. Submission record filename field updated
3. Audit log entry written: `document.reuploaded`
4. Pipeline re-triggered for the updated document

---

## 7. AI Pipeline Integration

**File:** `utils/pipeline.py`

### Triggering
Called via `start_async_analysis(sub)` after submission:
```python
executor = ThreadPoolExecutor(max_workers=5)
future = executor.submit(analyze_submission_sync, sub)
```
Runs in background — does not block the Streamlit UI.

### Pipeline Progress
A `pipeline_progress.txt` file is written to the upload directory at each step. The Track Status page reads this file to display the current progress message.

### Output
On completion:
- `sub["extracted_data"]` — raw Gemini schemas per document (JSON)
- `sub["consistency_checks"]` — 10 rule results (JSON)
- `sub["document_scores"]` — per-doc completeness (JSON)
- `sub["overall_score"]` — weighted average
- `sub["risk_flags"]` — high/medium arrays (JSON)
- `sub["risk_recommendation"]` — approve / request_info / escalate
- `sub["status"]` → "Awaiting human review"
- `uploads/{ref}/extraction_results.json` — written as permanent record

---

## 8. Inline Questionnaire Editor

Located inside a collapsible `st.expander("✏️ Correct / Edit Questionnaire Fields Directly")` on the Track Status page.

### Editable Fields
All business, tax, and banking fields are exposed as `st.text_input` / `st.selectbox` / `st.number_input` widgets, pre-filled with current values.

### Save Logic
On "Save Changes" button click:
1. Each changed field is identified by comparing new vs. old value
2. Change logged to audit trail: `Field "fieldName" changed from "oldValue" to "newValue"`
3. Submission record updated via `save_single_submission()`
4. If business-critical fields changed (FEIN, legal name), re-analysis is offered

---

## 9. Correction Desk

Displayed only when status is "Action Required".

For each flagged document category, a `st.file_uploader` is shown. On upload:
1. File saved to `uploads/{ref}/`
2. Submission record updated
3. Audit log entry written
4. Re-analysis pipeline re-queued

---

## 10. Audit Trail Display

Located in `col2` (right column) inside a `st.expander("📋 Audit Trail")`.

### Display Format
Each entry shown as a card with:
- Timestamp (formatted as readable date/time)
- Action type icon (📝 edit, 📄 document, ⚙️ pipeline, ✅ approval, etc.)
- Actor (system / reviewer username)
- Detail string (including field-change diffs)

Sorted newest-first. Only logs for the current reference code are shown.

---

## 11. Reference Code System

Format: `{SUBMISSION_ID_PREFIX}-{5-digit-sequence}`  
Default prefix: `VND-2026`  
Example: `VND-2026-00014`

Generated sequentially by scanning existing IDs in `submissions.csv`. Thread-safe via `_db_lock`.

---

## 12. State Management

| Key | Type | Description |
|---|---|---|
| `current_step` | `int` (0–4) | Active wizard step |
| `form_data` | `dict` | All entered field values |
| `uploaded_files` | `dict` | Uploaded file objects |
| `draft_ref` | `str` | Temp draft folder ID |
| `submission_done` | `bool` | True after successful submit |
| `ref_code` | `str` | Generated reference code |

---

## 13. Data Flow Diagram

```
User Input (Step 1-3)
       │
       ▼
st.session_state["form_data"]
       │
       ├── Step 4: File uploads → uploads/draft-{uuid}/
       │
       ▼
Step 5: Review & Submit
       │
       ├── 1. generate_submission_id()
       ├── 2. Move files: draft-{uuid}/ → uploads/{ref}/
       ├── 3. Write questionnaire_data.json
       ├── 4. save_single_submission(sub) → data/submissions.csv
       ├── 5. send_submission_received_email()
       └── 6. start_async_analysis(sub)
                      │
                      ▼
            Background Thread (ThreadPoolExecutor)
                      │
                      ├── run_extraction_pipeline() × 5 docs
                      │         └── Gemini API (with retry)
                      ├── Cross-document rules (1–10)
                      ├── Risk scoring
                      ├── Auto-recommendation
                      └── save_single_submission(updated_sub)
                                    │
                                    ▼
                         Track Status page reads live data
```
