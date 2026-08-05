# 🛡️ VendorGate AI Onboarding & Compliance Agent

**VendorGate** is a standalone, configuration-driven, AI-augmented vendor compliance onboarding agent. It automatically ingests vendor-submitted onboarding documents (such as W-9 forms, Certificates of Insurance, Bank Verification Letters, and Company Registrations), performs dynamic LLM-based field extraction, validates extracted values against regional rules, runs cross-document consistency checks, and generates structured compliance recommendations.

Built to conform to the **AuxiLab Publishing Standard**, VendorGate runs with:
*   **Zero external databases** (operates entirely statelessly using file inputs/outputs).
*   **Zero port multiplexing** (runs on fixed port: Gradio UI on port `8000`).
*   **Fully local, CSV-driven configurations** for regional schemas and consistency rules.

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
|  | Render HTML Visual Dashboard in Gradio App                                  |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 📂 Project Directory Structure

```text
├── app.py                      # Interactive Gradio web interface (runs on port 8000)
├── requirements.txt            # Python package dependencies
├── .env                        # Local API credentials & system-wide threshold parameters
├── .env.example                # Template for local credentials and thresholds
├── document_paths.txt          # Target list of document files for local testing
├── compliance_report.json      # Output artifact containing the compiled compliance report
├── config/                     # Configuration database
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

The agent reads `config/onboarding_config.csv` to dynamically discover what documents are required for a target country and which fields should be extracted from each document. 

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
Within `config/onboarding_config.csv`, you can specify field-level validation rules under the `validation_rules` column (delimited by `|`):
*   **Format Regex matching:** e.g., `ein:format=\d{2}-\d{7}` (Matches standard US W-9 tax identifiers).
*   **Exact Digit Count check:** e.g., `routing_number:digits=9` (US transit bank numbers) or `company_number:digits=8` (UK company registration).
*   **Minimum numeric boundary:** e.g., `general_liability_per_occurrence:min=1000000` (requires minimum liability limits).

---

## 🤖 Configurable LLM Extraction Architecture

VendorGate uses LangChain to connect to different LLM providers. You can switch between them dynamically by modifying the `LLM_PROVIDER` variable in your `.env` file:

*   **Google Gemini (Default):** Runs multimodally (rendering PDF pages to images for vision extraction) using `gemini-2.5-flash`.
*   **Anthropic Claude:** Runs multimodally using `claude-3-5-sonnet-20241022`.
*   **Groq:** Runs using `llama-3.3-70b-versatile`. When using Groq (unless a specific vision model is defined), the system automatically falls back to **Text-Only mode** to ensure maximum compatibility.

### 📄 Text-Only Fallback & Dual-Library PDF Parser
To run document processing without a vision model, you can set `TEXT_ONLY_FALLBACK=true` in your `.env` or run the CLI with the `--text-only` flag (or toggle it via the Gradio UI checkbox). 

When extracting text contents:
1.  **PyMuPDF (fitz):** The agent first attempts to extract document text using PyMuPDF.
2.  **pypdf Fallback:** If `fitz` fails or is not present, the agent automatically falls back to `pypdf` to extract text from the PDF pages.
3.  **Direct Read:** If both PDF parsers fail or the file is plain text, it falls back to a UTF-8 raw text reader.

---

## 🛡️ The 10 Consistency & Compliance Rules Engine

The agent parses `config/compliance_rules.csv` to evaluate every submission against 10 built-in compliance checks:

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
2.  If still missing, it runs a regex parser against the W-9 `address_line1` block to look for a US two-letter state abbreviation matching `\b([A-Z]{2})\b(?:\s+\d{5})?`.
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
    Create a `.env` file in the project root using `.env.example` as a template.
    
    Example `.env` configuration:
    ```env
    # Options: google, anthropic, groq
    LLM_PROVIDER=google
    TEXT_ONLY_FALLBACK=false

    # Google Gemini Settings
    GEMINI_API_KEY=your_gemini_api_key_here
    GEMINI_AGENT_MODEL=gemini-2.5-flash
    GEMINI_MAX_TOKENS=4096

    # Groq Settings (Optional)
    # GROQ_API_KEY=your_groq_api_key_here
    # GROQ_MODEL=llama-3.3-70b-versatile
    # GROQ_MAX_TOKENS=4096

    # Anthropic Settings (Optional)
    # ANTHROPIC_API_KEY=your_anthropic_api_key_here
    # ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
    # ANTHROPIC_MAX_TOKENS=4096
    
    # Compliance Threshold Properties
    COI_MIN_LIABILITY_USD=YOUR_DATA_HERE
    COI_EXPIRY_WARNING_DAYS=YOUR_DATA_HERE
    ```

---

## 🚀 Running the App

### 1. Run the Interactive Web UI (Gradio Dashboard)
Start the primary web application:
```bash
python app.py
```
This will automatically open your default browser to **[http://127.0.0.1:8000](http://127.0.0.1:8000)** (using the `inbrowser=True` parameter). The web interface now includes a real-time progress bar tracking the document extraction steps and validation rules in the background. Here you can upload files, choose country profiles, toggle "Text-Only Fallback" mode, and inspect summary cards alongside the visual HTML dashboard.

### 2. Run the CLI Compliance Agent
Execute a local command-line run by specifying the input source and country profile:
```bash
python agent/extractor_agent.py <input_source> <country> [--text-only]
```

*   `<input_source>` can be:
    *   A path to a `.txt` file containing document file paths (e.g., `document_paths.txt`).
    *   A vendor directory ID (e.g., `VND-2026-00012`). In this case, the agent searches for files under the corresponding subfolder: `uploads/<input_source>`.
*   `<country>` specifies the country profile matching `onboarding_config.csv` (e.g., `USA`, `India`, `UK`, `UAE`, `Singapore`).
*   `--text-only` is an optional flag to override vision capabilities and use direct text extraction.

Example:
```bash
python agent/extractor_agent.py document_paths.txt USA
```
This prints document parsing statuses, displays a terminal decision card with token usage, and creates `compliance_report.json` in the root workspace.

---

## 🧪 Running Unit Tests
VendorGate includes a comprehensive, deterministic unit test suite in the `tests/` directory. These tests evaluate the compliance pipeline recommendation engine across three distinct scenarios using mocked LLM extraction responses, bypassing actual network API calls:

1. **Clean Vendor Submission**: All USA required documents are present and pass the 10 consistency rules (expected result: `APPROVE`).
2. **Flagged Submission (2 Rule Failures)**: Mismatching legal names and an expired COI policy (expected result: `REQUEST INFO`).
3. **Escalated Submission**: Missing required documents and document completeness falls below 40% (expected result: `ESCALATE`).

To run the unit tests:
VendorGate includes a comprehensive, deterministic, and traceback-free unit test suite in the `tests/` directory. These tests evaluate the compliance pipeline recommendation engine across the three distinct scenarios requested by your manager using static mock document extraction payloads:

### Test Scenarios Covered
1. **Test 1: Clean Vendor Submission (APPROVE)**:
   * **Setup**: Mocks a complete USA onboarding package (W-9, COI, Bank Letter, and Registration) with 100% completeness where all 10 consistency rules pass.
   * **Expected Decision**: `APPROVE`
2. **Test 2: Flagged Vendor Submission (REQUEST INFO)**:
   * **Setup**: Mocks a USA package with exactly two compliance failures: a legal name mismatch between W-9 and COI, and an expired COI policy date.
   * **Expected Decision**: `REQUEST INFO`
3. **Test 3: Deficient Vendor Submission (ESCALATE)**:
   * **Setup**: Mocks a USA package missing required documents (COI, Bank Verification Letter, Company Registration) where the overall completeness is under 40% (specifically 25%).
   * **Expected Decision**: `ESCALATE`

### Key Design Features
* **Zero Network Requests**: The extraction outputs are mocked locally from `tests/mock_data.json` using Python's `unittest.mock.patch` library. No LLM APIs are called, making the tests extremely fast (execution time < 15ms) and 100% deterministic.
* **Dynamic Date Logic**: To prevent the test mock policies from becoming stale, the test suite fetches `datetime.date.today()` at runtime and dynamically adjusts mock expiration dates relative to it (e.g. `today + 90 days` for active policies, `today - 90 days` for expired policies).
* **Alphabetical Ordering**: Test cases are prefixed numerically (`test_1_approve_scenario`, `test_2_request_info_scenario`, `test_3_escalate_scenario`) to ensure they execute sequentially in the exact 1, 2, 3 order.
* **Traceback-Free Failure Logging**: Assertions are wrapped in custom try-except blocks. If any validation fails, the runner logs a clear ❌ failure box outlining the mismatch reasons to stdout/stderr instead of dumping a long Python traceback exception, while still exiting the process with code `1` (supporting standard CI/CD checks).

### Execution Commands

To run the entire compliance test suite from the project root:
```bash
python -m unittest tests/test_compliance.py
```

To run the tests with verbose output (printing each scenario name as it executes):
```bash
python -m unittest tests/test_compliance.py -v
```

To run a single test case (e.g. Test 1):
```bash
python -m unittest tests.test_compliance.TestVendorGateCompliance.test_1_approve_scenario
```


---

## Built By

| Name | GitHub |
|------|--------|
| Brajendra Singh | [@brajendrasingh-auxiliobits](https://github.com/brajendrasingh-auxiliobits) |
| Anmol Main | [@anmolmain-ABT](https://github.com/anmolmain-ABT) |

Built during the **AuxiLab Founding Hackathon** by [Auxiliobits Technologies](https://auxiliobits.com) · [AuxiLab Catalogue](https://auxiliobits.com/auxilab)
