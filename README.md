# 🌟 VendorGate Onboarding Platform

```
┌────────────────────────────────────────────────────────────────────────┐
│                        VendorGate Platform                             │
│                                                                        │
│   ┌────────────────┐   ┌───────────────────┐   ┌───────────────────┐   │
│   │  VendorApp.py  │   │  VendorAssistant  │   │  ReviewerApp.py   │   │
│   │  (Port 8501)   │   │  ChatBOT.py (8502)│   │  (Port 8503)      │   │
│   │  ────────────  │   │  ──────────────── │   │  ───────────────  │   │
│   │  • Home        │   │  • NLP Chat UI    │   │  • Admin Dash     │   │
│   │  • Submit Form │   │  • Status Card    │   │  • Vendor Master  │   │
│   │  • Track Status│   │  • Gemini LLM     │   │  • Review Queue   │   │
│   └───────┬────────┘   └─────────┬─────────┘   └─────────┬─────────┘   │
│           │                      │                       │             │
│           └──────────────────────┼───────────────────────┘             │
│                                  │                                     │
│                       ┌──────────▼──────────┐                          │
│                       │   utils/ (shared)   │                          │
│                       │   ───────────────   │                          │
│                       │  • data_manager.py  │                          │
│                       │  • pipeline.py      │                          │
│                       │  • extractor.py     │                          │
│                       │  • notifier.py      │                          │
│                       │  • style_utils.py   │                          │
│                       └──────────┬──────────┘                          │
│                                  │                                     │
│              ┌───────────────────┼────────────────────┐                │
│              │                   │                    │                │
│     ┌────────▼──────┐   ┌────────▼────────┐   ┌───────▼────────┐       │
│     │data/          │   │uploads/         │   │ Google Gemini  │       │
│     │submissions.csv│   │{ref}/docs + JSON│   │ 2.5 Flash API  │       │
│     │audit_logs.csv │   │                 │   │                │       │
│     └───────────────┘   └─────────────────┘   └────────────────┘       │
└────────────────────────────────────────────────────────────────────────┘
```

**VendorGate** is an enterprise-grade, AI-augmented vendor compliance onboarding platform. It is designed as a set of three independently deployable Streamlit applications ("plug-and-play components") sharing a unified utility library, async AI extraction pipeline, SMTP notifications dispatcher, and a flat-file database.

---

## 📖 Table of Contents
1. [Platform Architecture & Components](#-platform-architecture--components)
2. [Workflow Cycle](#-workflow-cycle)
3. [Project Directory & File Structure](#-project-directory--file-structure)
4. [Installation & Setup](#-installation--setup)
5. [Environment Configuration (`.env`)](#-environment-configuration-env)
6. [The 10 Consistency & Compliance Rules](#-the-10-consistency--compliance-rules)
7. [AI Pipeline & Smart Fallback](#-ai-pipeline--smart-fallback)
8. [Database & Audit Trail System](#-database--audit-trail-system)
9. [Detailed Documentation Resources](#-detailed-documentation-resources)

---

## 🏗️ Platform Architecture & Components

The system is split into three self-contained entry-point applications:

1. **Vendor Onboarding Portal** ([VendorApp.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/VendorApp.py)) - *Port 8501 (Default)*
   - Dedicated interface for vendors to submit onboarding packets via a 5-step registration wizard (Company Details, Contacts, Business Profile, Document Upload, and Review).
   - Includes a **Track Status** sub-page for real-time milestone tracking, direct field corrections, and replacement document uploads.

2. **Self-Service Support ChatBot** ([VendorAssistantChatBOT.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/VendorAssistantChatBOT.py)) - *Port 8502 (Default)*
   - A standalone application allowing vendors to look up their registration using their reference number.
   - Provides an AI chatbot powered by Google Gemini 2.5 Flash, providing contextual compliance help (e.g. why their documents failed, what liability limit is expected, how to resolve specific deficiencies).

3. **Internal Reviewer Dashboard** ([ReviewerApp.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/ReviewerApp.py)) - *Port 8503 (Default)*
   - The administration dashboard for procurement specialists and auditors to inspect submissions.
   - Displays AI-extracted fields, status of compliance checks, auto-recommendations (Approve, Request Info, Escalate), and allows the auditor to Approve (generating an ERP Vendor Key), Request Info (with a customizable list of action items), or Reject.
   - Includes the **Vendor Master** ledger displaying color-coded Certificate of Insurance (COI) expiry status compared against `SYSTEM_DATE`.

---

## 🔄 Workflow Cycle

```
[Vendor Registration Wizard] ──(Uploads 5 Documents)──> [Flat-file Persistence & CSV Lock]
                                                                  │
                                                        (Triggers Async Pipeline)
                                                                  │
                                                                  ▼
                                                      [Google Gemini AI Engine]
                                                                  │
                                                    (Extracts Fields & Pydantic Schemas)
                                                                  │
                                                                  ▼
                                                      [10 Consistency Rules Engine]
                                                                  │
                                                     (Calculates Weighted Score &
                                                      Generates Risk Flags/Recommendation)
                                                                  │
                                                                  ▼
                                                    [Status: Awaiting Human Review]
                                                                  │
                                                        (Notifies Reviewers)
                                                                  │
                                                                  ▼
                                                    [Reviewer App Panel Inspection]
                                                                  │
                                           ┌──────────────────────┼──────────────────────┐
                                           │                      │                      │
                                           ▼                      ▼                      ▼
                                      [✔ APPROVE]         [⚠️ REQUEST INFO]          [❌ REJECT]
                                    Generates ERP Key     Sends Action Items         Sends Rejection
                                    Notifies Vendor       Vendor updates fields      Notifies Vendor
                                                          & doc replacements
```

---

## 📁 Project Directory & File Structure

Here is a breakdown of the key files in the repository:

### Core Entry Points
* [VendorApp.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/VendorApp.py): Main entry point for the Vendor Onboarding Portal.
* [VendorAssistantChatBOT.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/VendorAssistantChatBOT.py): Standalone script executing the AI Support ChatBot.
* [ReviewerApp.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/ReviewerApp.py): Main entry point for the Reviewer Application.

### Shared Utility Library (`utils/`)
* [utils/data_manager.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/utils/data_manager.py): Coordinates filesystem persistence (reading/writing `submissions.csv` and `audit_logs.csv`), hashes/verifies reviewer passwords using `bcrypt`, handles transaction locks, and hosts mock database seeding.
* [utils/extractor.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/utils/extractor.py): Defines structured Pydantic schemas and controls calls to the Google GenAI SDK to retrieve structured text from W-9, COI, Bank Letters, Questionnaires, and Company Registration papers.
* [utils/pipeline.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/utils/pipeline.py): orchestrates the ingestion pipeline. Translates raw data into compliance scores, evaluates the 10 consistency rules, and saves risk recommendations.
* [utils/notifier.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/utils/notifier.py): Integrates SMTP email services. Sends transactional notifications (received, approved, corrections requested) with a failover simulated mailbox logging to session state.
* [utils/style_utils.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/utils/style_utils.py): Holds shared design themes, CSS sheets, customized badges, and a CSS-based layout blocker blocking access to internal dashboards on mobile.

### Views (`views/`)
* [views/0_Home.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/views/0_Home.py): Welcome dashboard on Vendor App.
* [views/1_Submit_Form.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/views/1_Submit_Form.py): Stepper wizard collecting company details and documents.
* [views/2_Track_Status.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/views/2_Track_Status.py): Portal for vendors to check progress, see audit logs, and submit revisions.
* [views/3_Dashboard.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/views/3_Dashboard.py): Audit queue, risk flags, and actions for procurement reviewers.
* [views/4_Vendor_Master.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/views/4_Vendor_Master.py): Read-only vendor master ledger tracking ERP keys and active insurance limits.

### Agent Directory (`agent/`)
* [agent/extractor_agent.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/agent/extractor_agent.py): Holds LangChain-based generative agents to perform unified entity synthesis and cross-comparisons across uploaded attachments.

---

## ⚙️ Installation & Setup

1. **Clone the project & initialize python environment:**
   ```powershell
   cd "c:/Users/anmol.main/Downloads/Vendor Onboarding"
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Install dependencies:**
   Ensure the following packages are installed:
   ```bash
   pip install streamlit google-genai langchain langchain-google-genai pypdf bcrypt python-dotenv RapidFuzz
   ```

3. **Initialize the local flat-file database:**
   Running any of the applications will automatically initialize the `data/` and `uploads/` directories. On the first import of `utils/data_manager.py`, the system seeds the DB with default users and 3 mock vendor submissions:
   - **Default Admin Reviewer Credentials:**
     - **Username:** `admin` | **Password:** `admin`
     - **Username:** `reviewer` | **Password:** `password`

---

## 🌐 Environment Configuration (`.env`)

Configure the environment details inside the [.env](file:///c:/Users/anmol.main/Downloads/Vendor%20Onboarding/.env) file located in the project root:

```env
# ── SMTP Mail Services ────────────────────────────────────────────────
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=youremailhere@domain.com
SMTP_PASSWORD=<app-password>
SENDER_EMAIL=youremailhere@domain.com
SENIOR_AUDITOR_EMAIL=youremailhere@domain.com
REVIEWER_EMAIL=youremailhere@domain.com

# ── Google Gemini Configuration ───────────────────────────────────────
GEMINI_API_KEY=<your-google-api-key>
GEMINI_MODEL=gemini-2.5-flash
GEMINI_AGENT_MODEL=gemini-2.5-flash
GEMINI_MAX_TOKENS=4096
GEMINI_MAX_RETRIES=5
GEMINI_RETRY_WAIT_BASE=15
GEMINI_CALL_DELAY_SECONDS=4

# ── Compliance Engine Parameters ──────────────────────────────────────
COI_MIN_LIABILITY_USD=1000000
COI_EXPIRY_WARNING_DAYS=30
SYSTEM_DATE=2026-06-09

# ── Styling & SLA Specifications ──────────────────────────────────────
APP_NAME=VendorGate
APP_SLA_HOURS=1
SUBMISSION_ID_PREFIX=VND-2026
```

---

## 🛡️ The 10 Consistency & Compliance Rules

The onboarding pipeline evaluates submissions against 10 built-in compliance checks:

| Rule | Rule Title | Evaluation Details |
| :--- | :--- | :--- |
| **Rule 1** | **W-9 Legal Name vs COI Insured Name** | Matches W-9 entity name to COI policy holder name using fuzzy matching (similarity $\ge$ 70%). |
| **Rule 2** | **W-9 Legal Name vs Bank Account Name** | Verifies that the legal entity matches the name listed on the bank letter (similarity $\ge$ 70%). |
| **Rule 3** | **COI Validity Check** | Verifies the policy expiration date on the Certificate of Insurance is greater than the current `SYSTEM_DATE`. |
| **Rule 4** | **General Liability Limit Check** | Confirms General Liability Per Occurrence is $\ge$ `COI_MIN_LIABILITY_USD` ($1,000,000). |
| **Rule 5** | **Cyber Liability Presence** | Validates the presence of cyber insurance coverage. |
| **Rule 6** | **COI Expiration Warning** | Flags policies set to expire within `COI_EXPIRY_WARNING_DAYS` (30 days) of `SYSTEM_DATE`. |
| **Rule 7** | **Questionnaire Beneficiary vs Bank Account Name** | Compares the questionnaire beneficiary field to the bank confirmation letter name. |
| **Rule 8** | **Contact Domain Match** | Checks if contact email domain matches the vendor website domain (ignores generic providers like gmail.com). |
| **Rule 9** | **FEIN Agreement** | Cross-validates FEIN tax identifier between questionnaire and the W-9 form. |
| **Rule 10**| **Incorporation State Agreement** | Cross-checks state of incorporation between questionnaire and state registration document. |

---

## 🤖 AI Pipeline & Smart Fallback

1. **Text Extraction:** Uses `pypdf` to read PDF uploads. For images (PNG/JPG), it passes file metadata hints.
2. **LLM Parsing:** Queries Google Gemini 2.5 Flash, feeding it document contents and forcing schema matching using Pydantic parameters.
3. **API Rate Guarding:** Injects a 4-second delay between sequential API queries, catching `429` (Quota Exceeded) or `503` server faults with exponential retry backoffs.
4. **Local Simulation Fallback:** If the `GEMINI_API_KEY` is not present, or all retry thresholds are exceeded, the pipeline falls back to a mock extraction engine that provides realistic mock structured schemas to ensure local development and demo evaluations can proceed without interruptions.

---

## 💾 Database & Audit Trail System

- **Storage Engine:** Flat-file CSV structures located in `data/submissions.csv` and `data/audit_logs.csv`. Reviewer profiles are saved in `data/users.json`.
- **Thread Safety:** Every file operation in [utils/data_manager.py](file:///c:/Users/anmol.main/Downloads/Vendor Onboarding/utils/data_manager.py) is guarded by a global Python `threading.Lock` (`_db_lock`) ensuring thread safety during multi-user access.
- **Audit Logging:** Every user action, automated pipeline task, correction, and approval generates a detailed log record inside `data/audit_logs.csv` tracking:
  - Timestamp
  - Action key (e.g. `submission.received`, `questionnaire.edited`, `human.approved`)
  - Username / Actor details
  - Detailed value diff descriptions (e.g., *Field "billing_state" changed from "NY" to "DE"*).

---

## 🚀 Running the Apps Locally

You can launch the applications in separate terminal sessions:

```powershell
# Terminal 1: Vendor Portal
streamlit run VendorApp.py --server.port 8501

# Terminal 2: AI Support ChatBot
streamlit run VendorAssistantChatBOT.py --server.port 8502

# Terminal 3: Reviewer App
streamlit run ReviewerApp.py --server.port 8503
```

---

## 📚 Detailed Documentation Resources

For in-depth software designs and component specifics, refer to the documents in the `Documentation/` folder:
- 📖 [Combined SDD Blueprint](SDD_Combined_VendorGate.md): Combined software architecture, endpoints, database fields, and scaling guides.
- 📝 [Component 1 — Onboarding Portal SDD](SDD_Component1_VendorPortal.md): Specifications of the onboarding wizard and tracking views.
- 🤖 [Component 2 — AI Assistant SDD](SDD_Component2_ChatBot.md): NLP rules, system prompts, context parameters, and Chat UI design.
- 📊 [Component 3 — Reviewer App SDD](SDD_Component3_ReviewerApp.md): Security details, reviewer queue, dashboard widgets, and ERP ledger.
