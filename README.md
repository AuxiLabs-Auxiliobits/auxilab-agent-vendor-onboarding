# 🛡️ VendorGate AI Onboarding & Compliance Agent

**VendorGate** is a standalone, configuration-driven, AI-augmented vendor compliance onboarding agent. It automatically ingests vendor-submitted onboarding documents (such as W-9 forms, Certificates of Insurance, Bank Verification Letters, and Company Registrations), performs dynamic LLM-based field extraction, validates extracted values against regional rules, runs cross-document consistency checks, and generates structured compliance recommendations.

Built to conform to the **AuxiLab Publishing Standard**, VendorGate runs with:
*   **Zero external databases** (operates entirely statelessly using file inputs/outputs).
*   **Zero port multiplexing** (runs on fixed ports: Gradio UI on port `8000`, Streamlit on port `8501`).
*   **Fully local, csv-driven configurations** for regional schemas and consistency rules.

---

## 🔄 End-to-End Process Flowchart

The following flowchart outlines the step-by-step pipeline of VendorGate, starting from intake to schema resolution, LLM extraction, validation, compliance checks, and final dashboard rendering:

```text
+-----------------------------------------------------------------------------------+
|                            1. INTAKE & ENTRYPOINTS                                |
|  +-------------------------------------+  +------------------------------------+  |
|  | CLI Agent: extractor_agent.py       |  | Gradio UI: app.py (Port 8000)      |  |
|  | (Ingests document_paths.txt or dir) |  | (Interactive Web Upload Intake)    |  |
|  +------------------+------------------+  +------------------+-----------------+  |
+---------------------|----------------------------------------|--------------------+
                      |                                        |
                      +-------------------+--------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                     2. DOCUMENT DISCOVERY & SCHEMA RESOLUTION                     |
|  +-----------------------------------------------------------------------------+  |
|  | Discover Vendor Documents & Parse Optional Manifest (document_manifest.json)|  |
|  +--------------------------------------+--------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  | Keyword Mapping -> Document Types (W-9, COI, Bank Letter, Company Reg)      |  |
|  +--------------------------------------+--------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  | Load Regional Extraction Schema & Config (config/onboarding_config.csv)     |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------|-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                   3. MULTIMODAL EXTRACTION & LLM PIPELINE                         |
|  +-----------------------------------------------------------------------------+  |
|  | Convert PDF Pages to 150 DPI Images (Vision) OR Text Fallback (text_only=True)|  |
|  +--------------------------------------+--------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  | Build Dynamic Prompts per Doc Type & Invoke LLM (Gemini 2.5 Flash / Claude) |  |
|  +--------------------------------------+--------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  | Accumulate Input & Output Token Usage + Print Raw Document JSON to Terminal |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------|-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        4. FORMAT & FIELD VALIDATION                               |
|  +-----------------------------------------------------------------------------+  |
|  | Evaluate Field-Level Completeness % (Present Fields vs Expected Fields)      |  |
|  | Run Format Expression Rules (EIN Regex, Digit Length, Numeric Min Bounds)    |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------|-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|               5. THE 10 CONSISTENCY & COMPLIANCE RULES ENGINE                     |
|  +-----------------------------------------------------------------------------+  |
|  | Load Rule Specifications from CSV (config/compliance_rules.csv)             |  |
|  +--------------------------------------+--------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  |  Rule 1: W-9 Legal Name vs COI Insured Name (Fuzzy Match >= 70%)            |  |
|  |  Rule 2: W-9 Legal Name vs Bank Account Name (Fuzzy Match >= 70%)            |  |
|  |  Rule 3: COI Expiration Check (Expiry Date >= SYSTEM_DATE)                    |  |
|  |  Rule 4: General Liability Limit Check (Coverage >= $1,000,000)             |  |
|  |  Rule 5: Cyber Liability Coverage Verification                             |  |
|  |  Rule 6: COI Expiration Warning Flag (Expires within 30 Days)                |  |
|  |  Rule 7: W-9 Legal Name vs Company Registration Name (Fuzzy Match >= 70%)     |  |
|  |  Rule 8: Bank Account Name vs Bank Beneficiary Name (Fuzzy Match >= 70%)       |  |
|  |  Rule 9: Incorporation State Agreement (Fuzzy Match & Address State Fallback)|  |
|  |  Rule 10: W-9 Signature Presence Verification                              |  |
|  +--------------------------------------+--------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  | Enforce Binary Status Reporting: Every Rule Output is PASSED or FAILED      |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------|-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                      6. COMPLIANCE DECISION ENGINE                                |
|  +--------------------------------------+--------------------------------------+  |
|  |                                      |                                      |  |
|  v                                      v                                      v  |
| +-------------------------+  +--------------------------+  +-------------------+ |
| |        APPROVE          |  |       REQUEST INFO       |  |     ESCALATE      | |
| | All Required Docs OK &  |  | Rule Failures Detected,  |  | Critical Deficit: | |
| | All 10 Rules Passed     |  | Completeness < 70%, or   |  | Missing Docs,     | |
| |                         |  | Warning Flags Triggered  |  | Completeness <40%,| |
| |                         |  |                          |  | or >= 3 Failures  | |
| +-------------------------+  +--------------------------+  +-------------------+ |
+-----------------------------------------|-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                 7. REPORT GENERATION & OUTPUT PRESENTATION                        |
|  +-----------------------------------------------------------------------------+  |
|  | Compile Structured JSON Report -> Save Artifact to compliance_report.json   |  |
|  | Output Terminal Decision Summary Card (Recommendation, Token Stats, Rules)  |  |
|  | Render HTML Visual Dashboard in Gradio App / 100% Full-Width Streamlit Viewer |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 📂 Project Directory Structure

```text
├── app.py                      # Interactive Web UI entrypoint (Gradio dashboard)
├── report_viewer.py            # Standalone Streamlit visualizer (has no connection to the agent pipeline; purely for viewing pre-extracted JSONs)
├── requirements.txt            # Python package dependencies
├── .env                        # Local credentials & system-wide threshold properties
├── document_paths.txt          # Target list of document files for local testing
├── config/                     # Config database
│   ├── onboarding_config.csv   # Regional extraction schemas & country configurations
│   └── compliance_rules.csv    # Dynamic consistency rules specifications
├── templates/                  # Sample mock PDF documents & text templates for validation
└── agent/                      # Core Compliance Agent pipeline source code
    ├── extractor_agent.py      # Command-line CLI entrypoint orchestrating local execution
    ├── pipeline.py             # Orchestrates the intake, extraction, rules, and decision steps
    ├── dynamic_extractor.py    # Vision/text extraction using Google Gemini or Anthropic Claude
    ├── compliance_checker.py   # Rule evaluator executing the 10 consistency checks
    ├── config_loader.py        # Parser loading CSVs into structured python schemas
    └── report_generator.py     # HTML report compiler and markdown formatter
```

---

## 🌐 Dynamic Regional Profiles & Country Configurations

The agent reads [`config/onboarding_config.csv`](config/onboarding_config.csv) to discover what documents are required for a target country and which fields should be dynamically extracted from each document. 

VendorGate comes pre-configured with 5 regional profiles:

| Country Profile | Document Type | Required? | Key Extracted Fields |
| :--- | :--- | :--- | :--- |
| **USA** | W-9 Tax Form | Yes | `legal_name`, `ein`, `tax_classification`, `address_line1`, `state`, `zip_code`, `signature_present` |
| | Certificate of Insurance | Yes | `insured_name`, `insurer_name`, `general_liability_per_occurrence`, `has_cyber_liability`, `expiry_date` |
| | Bank Verification Letter | Yes | `account_name`, `bank_name`, `routing_number`, `account_number_last4`, `beneficiary_name` |
| | Company Registration | Yes | `company_name`, `registration_number`, `registration_date`, `jurisdiction`, `entity_type` |
| **India** | GST Registration Certificate | Yes | `business_name`, `gstin`, `registration_date`, `state`, `authorized_signatory` |
| | PAN Card | Yes | `entity_name`, `pan_number`, `entity_type`, `father_or_dob` |
| | Bank Account Verification | Yes | `account_holder_name`, `bank_name`, `account_number`, `ifsc_code`, `branch` |
| | Certificate of Incorporation | Yes | `company_name`, `cin_number`, `date_of_incorporation`, `registered_office` |
| **UK** | W-8BEN-E Form | Yes | `entity_name`, `country_of_incorporation`, `tin_number`, `chapter3_status`, `fatca_status` |
| | Certificate of Incorporation | Yes | `company_name`, `company_number`, `date_of_incorporation`, `registered_office` |
| | Bank Verification Letter | Yes | `account_name`, `bank_name`, `sort_code`, `account_number`, `iban`, `swift_bic` |
| | VAT Registration Certificate | Yes | `business_name`, `vat_number`, `effective_date`, `principal_business_activity` |
| **UAE** | Trade License | Yes | `company_name`, `license_number`, `license_type`, `issue_date`, `expiry_date`, `owner_name` |
| | TRN Certificate | Yes | `taxable_person_name`, `trn_number`, `registration_date` |
| | Bank Account Verification | Yes | `account_holder_name`, `bank_name`, `account_number`, `iban`, `swift_bic` |
| **Singapore**| ACRA Business Profile | Yes | `company_name`, `uen_number`, `registration_date`, `company_type`, `registered_address` |
| | GST Registration | Yes | `entity_name`, `gst_number`, `effective_date`, `business_name` |
| | Bank Account Verification | Yes | `account_holder_name`, `bank_name`, `account_number`, `swift_bic` |

### Custom Regex & Formatting Validations
Within [`config/onboarding_config.csv`](config/onboarding_config.csv), you can specify field-level regex rules under the `validation_rules` column:
*   **EIN Format Validation:** `ein:format=\d{2}-\d{7}` (Matches US W-9 standard tax identifiers).
*   **9-Digit Routing Verification:** `routing_number:digits=9` (US transit bank numbers).
*   **IFSC Code format (India):** `ifsc_code:format=[A-Z]{4}0[A-Z0-9]{6}`.
*   **UEN Format (Singapore):** `uen_number:format=[0-9]{9}[A-Z]`.

---

## 🛡️ The 10 Consistency & Compliance Rules Engine

The agent parses [`config/compliance_rules.csv`](config/compliance_rules.csv) to evaluate every submission against 10 built-in compliance checks:

| Rule ID | Rule Title | Evaluation Type | Rule Logic & Thresholds |
| :--- | :--- | :--- | :--- |
| **Rule 1** | W-9 Legal Name vs COI Insured Name | Cross-document fuzzy matching | Compares W-9 `legal_name` and COI `insured_name`. Cleans common corporate suffix terms (e.g., *LLC, Corp, Inc*) and ensures a character similarity score $\ge 70\%$. |
| **Rule 2** | W-9 Legal Name vs Bank Account Name | Cross-document fuzzy matching | Compares W-9 `legal_name` to Bank Letter `account_name` ($\ge 70\%$). |
| **Rule 3** | COI Validity Check | Date Comparison | Checks if the COI policy expiration date is greater than or equal to the configured `SYSTEM_DATE`. |
| **Rule 4** | General Liability Limit Check | Value Threshold | Verifies that the General Liability Per Occurrence limit is $\ge$ `COI_MIN_LIABILITY_USD` (Default: `$1,000,000`). |
| **Rule 5** | Cyber Liability Presence | Presence Flag | Checks if the extracted `has_cyber_liability` field evaluates to `True`. |
| **Rule 6** | COI Expiration Warning | Warning Buffer | Flags a warning if the policy expiration date is within `COI_EXPIRY_WARNING_DAYS` (Default: `30` days) of the `SYSTEM_DATE`. |
| **Rule 7** | W-9 Legal Name vs Company Registration Name | Cross-document fuzzy matching | Compares W-9 `legal_name` with Company Registration `company_name` ($\ge 70\%$). |
| **Rule 8** | Bank Account Name vs Bank Beneficiary Name | Internal document fuzzy matching | Ensures the account holder name on the Bank Verification Letter matches the beneficiary name ($\ge 70\%$). |
| **Rule 9** | Incorporation State Agreement | Cross-document fuzzy matching with Address Fallback | Compares W-9 `state_of_incorporation` with Company Registration `jurisdiction`. Supports **Smart Address State Fallback** (see below). |
| **Rule 10**| W-9 Signature Verification | Presence Flag | Verifies that `signature_present` on W-9 is `True`. |

### Smart State Fallback Logic (Rule 9)
If the W-9 `state_of_incorporation` is missing or blank, the compliance engine automatically triggers fallback checks:
1.  It checks if a state code is present under the W-9 `state` or `address_state` field.
2.  If still missing, it runs a regex regex-parser against the W-9 `address_line1` block to look for a US two-letter state abbreviation matching `\b([A-Z]{2})\b(?:\s+\d{5})?`.
3.  Once the fallback state is identified, it resolves standard US state names (e.g. "IL" maps to "Illinois") and performs a comparison with the Company Registration jurisdiction.

---

## 🎯 Vendor Risk Score Matrix (0–100 Rating)

VendorGate computes a dynamic **Vendor Risk Score** (0–100) using a weighted compliance index. The compliance score is calculated using four distinct variables:

$$\text{Compliance Score} = (0.30 \times \text{Completeness}) + (0.40 \times \text{RulesPassed}) + (0.15 \times \text{ValScore}) + (0.15 \times \text{Confidence})$$

$$\text{Vendor Risk Score} = 100 - \text{Compliance Score}$$

### Scoring Variables
1.  **Completeness (30% Weight):** Calculated as `(present_fields / expected_fields) * 100` averaged across all required documents.
2.  **Rules Passed % (40% Weight):** Percentage of the 10 consistency rules that returned a `Passed` status.
3.  **Validation Score (15% Weight):** Starts at `100.0` points. For each field-level regex or formatting error, `20.0` points are deducted (to a floor of `0.0`).
4.  **LLM Confidence (15% Weight):** The average confidence percentage of the LLM parser output across all documents.

### Risk Level Categorizations
*   🟢 **LOW RISK:** Risk Score $\le 15.0$ (Compliance Score $\ge 85.0\%$)
*   🟡 **MEDIUM RISK:** Risk Score between $15.1$ and $35.0$ (Compliance Score $65.0\% - 84.9\%$)
*   🔴 **HIGH RISK:** Risk Score $> 35.0$ (Compliance Score $< 65.0\%$)

---

## 🤖 Compliance Decision Engine

The final workflow recommendation is automatically generated based on the severity of the findings:

| Recommendation | Decision Code | Criteria Triggered |
| :--- | :--- | :--- |
| **ESCALATE** | `Escalate` | 1. Any required documents are missing entirely, OR<br>2. Document completeness is under **40%**, OR<br>3. **3 or more** consistency rules failed. |
| **REQUEST INFO**| `Request Info`| 1. Field validation errors (regex format mismatches) exist, OR<br>2. **1 or 2** consistency rules failed or triggered a warning (e.g. COI expiring soon), OR<br>3. Overall document completeness is between **40% and 70%**. |
| **APPROVE** | `Approve` | All required documents are uploaded, completeness is $\ge 70\%$, zero validation errors, and all 10 consistency rules are successfully passed. |

---

## ⚙️ Installation & Setup

1.  **Initialize your virtual environment:**
    ```bash
    python -m venv .venv
    
    # On Windows
    .venv\Scripts\activate      
    
    # On macOS/Linux
    source .venv/bin/activate    
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure environment variables (`.env`):**
    Create a `.env` file in the project root:
    ```env
    LLM_PROVIDER=google
    TEXT_ONLY_FALLBACK=false

    GEMINI_API_KEY=your_gemini_api_key_here
    GEMINI_AGENT_MODEL=gemini-2.5-flash
    GEMINI_MAX_TOKENS=4096
    
    SYSTEM_DATE=2026-06-09
    COI_MIN_LIABILITY_USD=1000000
    COI_EXPIRY_WARNING_DAYS=30
    ```

---

## 🚀 Running the App

### 1. Run the Interactive Web UI (Gradio Dashboard)
Start the primary web application:
```bash
python app.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser. Here you can upload documents, select regional profiles (USA, India, etc.), toggle the "Text-Only Fallback" mode, and view validation summaries alongside visual HTML reports.

### 2. Run the CLI Compliance Agent
Execute a local command-line run over list files or directories:
```bash
python agent/extractor_agent.py document_paths.txt USA
```
This prints document parsing statuses, displays a terminal decision card with token usage, and creates `compliance_report.json` in the root workspace.

### 3. Run the Standalone Report Viewer (Streamlit)

> [!IMPORTANT]
> **No Agent Integration:** The Streamlit application has **no connection or integration** with the active compliance agent pipeline. The agent itself is fully standalone. This Streamlit page is created purely as a visualization tool to let you upload or paste a generated compliance JSON report so you can get a quick visual glimpse of the dashboard structure.

To visualize a pre-extracted `compliance_report.json` (such as the one produced by the CLI command) without triggering new LLM calls:
```bash
streamlit run report_viewer.py
```
Open **[http://localhost:8501](http://localhost:8501)** in your browser to inspect or paste the JSON report structure.
