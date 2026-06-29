import os
import re
import json
import time
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
from dotenv import load_dotenv
load_dotenv()
from utils.data_manager import save_single_submission, write_audit_log, get_submission_upload_path
from utils.extractor import run_extraction_pipeline

# ── Config from .env ─────────────────────────────────────────────
SYSTEM_DATE_STR         = os.getenv("SYSTEM_DATE", datetime.now().strftime("%Y-%m-%d"))
SYSTEM_DATE             = datetime.strptime(SYSTEM_DATE_STR, "%Y-%m-%d").date()
COI_MIN_LIABILITY_USD   = int(os.getenv("COI_MIN_LIABILITY_USD", "1000000"))
COI_EXPIRY_WARNING_DAYS = int(os.getenv("COI_EXPIRY_WARNING_DAYS", "30"))
GEMINI_CALL_DELAY       = float(os.getenv("GEMINI_CALL_DELAY_SECONDS", "4"))

def get_thread_pool() -> ThreadPoolExecutor:
    """Get or create ThreadPoolExecutor in Streamlit session state."""
    if "thread_pool" not in st.session_state:
        st.session_state["thread_pool"] = ThreadPoolExecutor(max_workers=5)
    return st.session_state["thread_pool"]

def fuzzy_token_match(name1: str, name2: str) -> tuple[bool, float]:
    """
    Fuzzy match W-9 legal name vs another name.
    Strips common corporate suffixes, lowercases, and checks token overlap (Jaccard similarity).
    Returns (Passed: bool, Similarity: float)
    """
    if not name1 or not name2:
        return False, 0.0
        
    def clean_tokens(name_str):
        ns = name_str.lower()
        # Remove common corporate suffixes
        ns = re.sub(r'\b(llc|inc|corp|corporation|co|company|group|solutions|supplies|logistics|partnership|l\.l\.c\.)\b', '', ns)
        tokens = set(re.findall(r'\b\w+\b', ns))
        return tokens
        
    t1 = clean_tokens(name1)
    t2 = clean_tokens(name2)
    
    if not t1 or not t2:
        return False, 0.0
        
    intersection = t1.intersection(t2)
    union = t1.union(t2)
    similarity = len(intersection) / len(union) if union else 0.0
    
    return similarity >= 0.7, similarity

# Step 3: Completeness Scoring (Deterministic)
def calculate_document_completeness(doc_type: str, data: dict) -> float:
    """Calculate the completeness score of a parsed document out of 100.0."""
    if not data:
        return 0.0
        
    # Weight maps as specified in rules
    weights = {}
    if doc_type == "w9":
        weights = {
            "legalName": 20,
            "ein": 25,
            "entityType": 15,
            "addressLine1": 20,
            "city": 10,
            "state": 5,
            "dbaName": 5
        }
    elif doc_type == "coi":
        weights = {
            "insuredName": 20,
            "generalLiabilityPerOccurrence": 25,
            "hasCyberLiability": 15,
            "earliestExpiryDate": 25,
            "insurerName": 15
        }
    elif doc_type == "bank":
        weights = {
            "accountName": 20,
            "bankName": 20,
            "routingNumber": 20,
            "accountNumberLast4": 20,
            "accountType": 5,
            "swiftBic": 15
        }
    elif doc_type == "questionnaire":
        weights = {
            "contactName": 4,
            "contactEmail": 4,
            "contactPhone": 4,
            "apContactName": 4,
            "apContactEmail": 4,
            "apContactPhone": 4,
            "companyStreet": 8,
            "companyCity": 3,
            "companyState": 3,
            "companyZip": 3,
            "billingStreet": 8,
            "billingCity": 3,
            "billingState": 3,
            "billingZip": 3,
            "taxIdGst": 5,
            "fein": 5,
            "taxClassification": 5,
            "stateOfIncorporation": 5,
            "backupWithholdingExempt": 1,
            "is1099Eligible": 1,
            "productsServices": 2,
            "yearsInBusiness": 2,
            "annualRevenueUSD": 2,
            "employeeCount": 2,
            "paymentTerms": 2,
            "conflictOfInterest": 2,
            "referencesCount": 2,
            "bankBeneficiaryName": 1,
            "swiftBic": 1,
            "dbaName": 2,
            "website": 2
        }
    elif doc_type == "company_reg":
        weights = {
            "companyName": 40,
            "registrationNumber": 40,
            "registrationDate": 20
        }
        
    score = 0.0
    for key, weight in weights.items():
        val = data.get(key)
        # Check presence
        if val is not None and val != "":
            score += weight
            
    return float(score)

def parse_date(date_str: str) -> date:
    """Try to parse a YYYY-MM-DD date, return None if fails."""
    if not date_str:
        return None
    # Strip any extra text/whitespace
    clean_date = date_str.split("T")[0].strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(clean_date, fmt).date()
        except ValueError:
            continue
    return None

def update_pipeline_progress(sub_id: str, message: str):
    try:
        sub_dir = os.path.join("uploads", sub_id)
        os.makedirs(sub_dir, exist_ok=True)
        progress_file = os.path.join(sub_dir, "pipeline_progress.txt")
        with open(progress_file, "w", encoding="utf-8") as f:
            f.write(message)
    except Exception:
        pass

def clear_pipeline_progress(sub_id: str):
    try:
        progress_file = os.path.join("uploads", sub_id, "pipeline_progress.txt")
        if os.path.exists(progress_file):
            os.remove(progress_file)
    except Exception:
        pass

def analyze_submission_sync(sub: dict) -> dict:
    """
    Executes the 6-step Analysis Pipeline for a submission.
    This runs synchronously within a thread of the ThreadPoolExecutor.
    """
    sub_id = sub["submission_id"]
    write_audit_log("pipeline.start", "system", sub_id, "Analysis pipeline initiated.")
    
    # 1. Paths to uploaded files
    w9_path = get_submission_upload_path(sub_id, sub["w9_filename"]) if sub["w9_filename"] else None
    coi_path = get_submission_upload_path(sub_id, sub["coi_filename"]) if sub["coi_filename"] else None
    bank_path = get_submission_upload_path(sub_id, sub["bank_letter_filename"]) if sub["bank_letter_filename"] else None
    quest_path = get_submission_upload_path(sub_id, sub["questionnaire_filename"]) if sub["questionnaire_filename"] else None
    company_reg_path = get_submission_upload_path(sub_id, sub["company_reg_filename"]) if sub["company_reg_filename"] else None
    
    # Load existing extraction data for caching
    existing_ext = {}
    if sub.get("extracted_data"):
        try:
            existing_ext = json.loads(sub["extracted_data"])
        except Exception:
            existing_ext = {}
    if not isinstance(existing_ext, dict):
        existing_ext = {}

    def get_or_extract_doc(doc_type, file_path, progress_message):
        if not file_path or not os.path.exists(file_path):
            return None
            
        current_mtime = os.path.getmtime(file_path)
        current_size = os.path.getsize(file_path)
        
        cached = existing_ext.get(doc_type)
        if (cached and isinstance(cached, dict) and 
            cached.get("_filepath") == file_path and 
            cached.get("_mtime") == current_mtime and 
            cached.get("_size") == current_size):
            return cached
            
        update_pipeline_progress(sub_id, progress_message)
        data = run_extraction_pipeline(doc_type, file_path)
        if data and isinstance(data, dict):
            data["_filepath"] = file_path
            data["_mtime"] = current_mtime
            data["_size"] = current_size
            time.sleep(GEMINI_CALL_DELAY)
        return data

    # 2. Extract structured JSON using cache if available
    w9_data = get_or_extract_doc("w9", w9_path, "Extracting and analyzing W-9 Tax Form...")
    coi_data = get_or_extract_doc("coi", coi_path, "Extracting and verifying Certificate of Liability Insurance (COI)...")
    bank_data = get_or_extract_doc("bank", bank_path, "Extracting and verifying Bank Confirmation Letter...")
    quest_data = get_or_extract_doc("questionnaire", quest_path, "Extracting and verifying Onboarding Questionnaire...")
    company_reg_data = get_or_extract_doc("company_reg", company_reg_path, "Extracting and verifying Company Registration Document...")
    
    update_pipeline_progress(sub_id, "Executing cross-document consistency checks and risk evaluation...")
    
    # Save the extracted schemas
    extracted_schemas = {
        "w9": w9_data,
        "coi": coi_data,
        "bank": bank_data,
        "questionnaire": quest_data,
        "company_reg": company_reg_data
    }
    
    # 3. Completeness Scoring
    w9_score = calculate_document_completeness("w9", w9_data)
    coi_score = calculate_document_completeness("coi", coi_data)
    bank_score = calculate_document_completeness("bank", bank_data)
    quest_score = calculate_document_completeness("questionnaire", quest_data)
    company_reg_score = calculate_document_completeness("company_reg", company_reg_data)
    
    doc_scores = {
        "w9": w9_score,
        "coi": coi_score,
        "bank": bank_score,
        "questionnaire": quest_score,
        "company_reg": company_reg_score
    }
    
    overall_score = (w9_score + coi_score + bank_score + quest_score + company_reg_score) / 5.0
    
    # 4. Cross-Document Consistency Checks
    consistency_results = []
    
    # Rule 1: Fuzzy match W-9 legal name vs COI insured name
    r1_pass, r1_sim = False, 0.0
    if w9_data and coi_data:
        r1_pass, r1_sim = fuzzy_token_match(w9_data.get("legalName"), coi_data.get("insuredName"))
    r1_details = f"Similarity: {r1_sim:.0%} ('{w9_data.get('legalName')}' vs '{coi_data.get('insuredName')}')" if (w9_data and coi_data) else "Missing document(s) for verification"
    consistency_results.append({
        "rule": "Rule 1: W-9 Legal Name vs COI Insured Name",
        "passed": r1_pass,
        "details": r1_details
    })
    
    # Rule 2: Fuzzy match W-9 legal name vs Bank Letter account name
    r2_pass, r2_sim = False, 0.0
    if w9_data and bank_data:
        r2_pass, r2_sim = fuzzy_token_match(w9_data.get("legalName"), bank_data.get("accountName"))
    r2_details = f"Similarity: {r2_sim:.0%} ('{w9_data.get('legalName')}' vs '{bank_data.get('accountName')}')" if (w9_data and bank_data) else "Missing document(s) for verification"
    consistency_results.append({
        "rule": "Rule 2: W-9 Legal Name vs Bank Account Name",
        "passed": r2_pass,
        "details": r2_details
    })
    
    # Rule 3: Check COI is not expired against current system date
    r3_pass = False
    r3_details = "COI document missing"
    if coi_data:
        expiry = parse_date(coi_data.get("earliestExpiryDate"))
        if expiry:
            if expiry >= SYSTEM_DATE:
                r3_pass = True
                r3_details = f"Active (Expires {expiry.strftime('%Y-%m-%d')})"
            else:
                r3_pass = False
                r3_details = f"Expired on {expiry.strftime('%Y-%m-%d')}"
        else:
            r3_details = f"Invalid or missing expiration date ({coi_data.get('earliestExpiryDate')})"
    consistency_results.append({
        "rule": "Rule 3: COI Expiration Check",
        "passed": r3_pass,
        "details": r3_details
    })
    
    # Rule 4: Verify COI General Liability Per Occurrence is >= $1,000,000
    r4_pass = False
    r4_details = "COI document missing"
    if coi_data:
        limit = coi_data.get("generalLiabilityPerOccurrence")
        if limit is not None:
            if limit >= COI_MIN_LIABILITY_USD:
                r4_pass = True
                r4_details = f"Passed: ${limit:,} limit >= ${COI_MIN_LIABILITY_USD:,}"
            else:
                r4_pass = False
                r4_details = f"Failed: ${limit:,} limit is under ${COI_MIN_LIABILITY_USD:,} threshold"
        else:
            r4_details = "General Liability limit not found"
    consistency_results.append({
        "rule": "Rule 4: COI Liability Limit Check",
        "passed": r4_pass,
        "details": r4_details
    })
    
    # Rule 5: Ensure Cyber liability coverage is explicitly present
    r5_pass = False
    r5_details = "COI document missing"
    if coi_data:
        cyber = coi_data.get("hasCyberLiability")
        cyber_limit = coi_data.get("cyberLiabilityLimit")
        if cyber:
            r5_pass = True
            r5_details = f"Cyber coverage present (Limit: ${cyber_limit:,})" if cyber_limit else "Cyber coverage present"
        else:
            r5_pass = False
            r5_details = "Cyber liability coverage not checked/present"
    consistency_results.append({
        "rule": "Rule 5: Cyber Liability Presence",
        "passed": r5_pass,
        "details": r5_details
    })
    
    # Rule 6: Check if COI expires within the next 30 days
    r6_pass = True # defaults to passing if active and far out
    r6_details = "COI document missing"
    if coi_data:
        expiry = parse_date(coi_data.get("earliestExpiryDate"))
        if expiry:
            days_left = (expiry - SYSTEM_DATE).days
            if days_left < 0:
                r6_pass = False
                r6_details = f"Failed: Already expired by {abs(days_left)} days"
            elif days_left <= COI_EXPIRY_WARNING_DAYS:
                r6_pass = False
                r6_details = f"Failed: Policy expires in {days_left} days (under {COI_EXPIRY_WARNING_DAYS}-day threshold)"
            else:
                r6_pass = True
                r6_details = f"Passed: Policy expires in {days_left} days"
        else:
            r6_pass = False
            r6_details = "Invalid expiration date"
    consistency_results.append({
        "rule": "Rule 6: COI Expiry Within 30 Days",
        "passed": r6_pass,
        "details": r6_details
    })
    
    # Rule 7: Questionnaire Beneficiary vs Bank Letter Account Name
    r7_pass, r7_sim = False, 0.0
    q_beneficiary = quest_data.get("bankBeneficiaryName") if quest_data else None
    if not q_beneficiary and quest_data:
        q_beneficiary = quest_data.get("legalName")
    if q_beneficiary and bank_data:
        r7_pass, r7_sim = fuzzy_token_match(q_beneficiary, bank_data.get("accountName"))
    r7_details = f"Similarity: {r7_sim:.0%} ('{q_beneficiary}' vs '{bank_data.get('accountName')}')" if (q_beneficiary and bank_data) else "Missing document(s)/data for verification"
    consistency_results.append({
        "rule": "Rule 7: Questionnaire Beneficiary vs Bank Letter Account Name",
        "passed": r7_pass,
        "details": r7_details
    })
    
    # Rule 8: Contact Email Domain vs Website Domain match
    r8_pass = False
    r8_details = "Missing email or website domain"
    c_email = sub.get("contact_email")
    website = sub.get("website")
    if c_email and website:
        email_domain = c_email.split("@")[-1].strip().lower()
        # Clean website domain
        web_clean = re.sub(r'^(https?://)?(www\.)?', '', website.strip().lower()).split('/')[0]
        generic_domains = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com", "icloud.com"}
        if email_domain in generic_domains:
            r8_pass = False
            r8_details = f"Failed: Contact email uses generic domain '{email_domain}'"
        elif email_domain == web_clean or email_domain in web_clean or web_clean in email_domain:
            r8_pass = True
            r8_details = f"Passed: Domains match ('{email_domain}' vs '{web_clean}')"
        else:
            r8_pass = False
            r8_details = f"Failed: Email domain '{email_domain}' doesn't match website domain '{web_clean}'"
    consistency_results.append({
        "rule": "Rule 8: Contact Email Domain vs Website Domain match",
        "passed": r8_pass,
        "details": r8_details
    })
    
    # Rule 9: FEIN Match (W-9 vs Questionnaire)
    r9_pass = False
    r9_details = "Missing W-9 or Questionnaire FEIN"
    q_fein = sub.get("fein")
    if w9_data and q_fein:
        w9_fein = w9_data.get("ein")
        if w9_fein and q_fein:
            w9_clean = re.sub(r'\D', '', w9_fein)
            q_clean = re.sub(r'\D', '', q_fein)
            if w9_clean == q_clean:
                r9_pass = True
                r9_details = f"Passed: FEIN matches ('{w9_fein}' vs '{q_fein}')"
            else:
                r9_pass = False
                r9_details = f"Failed: FEIN mismatch ('{w9_fein}' vs '{q_fein}')"
    consistency_results.append({
        "rule": "Rule 9: FEIN Match (W-9 vs Questionnaire)",
        "passed": r9_pass,
        "details": r9_details
    })
    
    # Rule 10: State of Incorporation Consistency
    r10_pass = False
    r10_details = "Missing Company Reg or Questionnaire State of Incorporation"
    q_state = sub.get("state_of_incorporation")
    if company_reg_data and q_state:
        reg_jurisdiction = company_reg_data.get("jurisdiction")
        if reg_jurisdiction:
            state_map = {
                "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
                "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
                "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
                "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
                "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
                "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
                "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
                "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
                "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
                "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"
            }
            q_state_clean = q_state.strip().upper()
            reg_state_clean = reg_jurisdiction.strip().upper()
            
            q_full = state_map.get(q_state_clean, q_state_clean).lower()
            reg_full = state_map.get(reg_state_clean, reg_state_clean).lower()
            
            if q_full == reg_full or q_state_clean == reg_state_clean or q_full in reg_full or reg_full in q_full:
                r10_pass = True
                r10_details = f"Passed: States match ('{q_state}' vs '{reg_jurisdiction}')"
            else:
                r10_pass = False
                r10_details = f"Failed: State mismatch ('{q_state}' vs '{reg_jurisdiction}')"
    consistency_results.append({
        "rule": "Rule 10: State of Incorporation Consistency",
        "passed": r10_pass,
        "details": r10_details
    })
    
    # 5. Apply Risk Rules
    high_risks = []
    medium_risks = []
    
    # High Risk Flags
    # A. Invalid EIN formatting (XX-XXXXXXX)
    if w9_data:
        ein = w9_data.get("ein")
        if not ein or not re.match(r"^\d{2}-\d{7}$", str(ein)):
            high_risks.append(f"Invalid EIN Format ({ein}) - Must match XX-XXXXXXX")
    else:
        high_risks.append("Invalid EIN Format - W-9 document missing")
        
    # B. PO-Box only address
    if w9_data:
        if w9_data.get("isPOBoxOnly"):
            high_risks.append("Physical address is PO Box Only")
            
    # C. Any missing document
    missing_docs = []
    if not w9_path: missing_docs.append("W-9")
    if not coi_path: missing_docs.append("COI")
    if not bank_path: missing_docs.append("Bank Verification Document")
    if not quest_path: missing_docs.append("Questionnaire")
    if not company_reg_path: missing_docs.append("Company Registration Document")
    if missing_docs:
        high_risks.append(f"Missing mandatory document: {', '.join(missing_docs)}")
        
    # Medium Risk Flags
    # A. Business age < 2 years
    if quest_data:
        years = quest_data.get("yearsInBusiness")
        if years is not None and years < 2:
            medium_risks.append(f"Business age is under 2 years ({years} year)")
    else:
        medium_risks.append("Business age undetermined - Questionnaire missing")
        
    # B. Lack of cyber liability
    if coi_data:
        if not coi_data.get("hasCyberLiability"):
            medium_risks.append("Lack of cyber liability coverage")
            
    # C. Any cross-document consistency failure
    for res in consistency_results:
        if not res["passed"]:
            medium_risks.append(f"Cross-document consistency check failed ({res['rule'].replace('Rule ', '')})")
            
    risk_flags = {
        "high": high_risks,
        "medium": list(set(medium_risks)) # deduplicate
    }
    
    # 6. Auto-Recommendation Generation
    if len(high_risks) >= 1:
        recommendation = "escalate"
    elif overall_score < 80.0 or len(risk_flags["medium"]) > 2:
        recommendation = "request_info"
    else:
        recommendation = "approve"
        
    # Update submission dictionary fields
    sub["overall_score"] = overall_score
    sub["risk_recommendation"] = recommendation
    sub["risk_flags"] = json.dumps(risk_flags)
    sub["consistency_checks"] = json.dumps(consistency_results)
    sub["document_scores"] = json.dumps(doc_scores)
    sub["extracted_data"] = json.dumps(extracted_schemas)
    sub["status"] = "Awaiting human review"
    
    # If auto-approved, let's put it as "Processing" or auto-approved (wait: "Otherwise -> approve (Approve for onboarding)").
    # But wait, does it auto-approve instantly, or does it say "Awaiting human review" and the reviewer is presented with auto-recommendation 'approve'?
    # Usually in enterprise workflows, "approve" auto-recommendation goes to "Awaiting human review" but is marked as green/approved, or can be auto-routed.
    # The prompt says: "If reviewer selects an item from the queue... Clicking an action button reveals a confirmation overlay. Approving automatically writes the vendor to the permanent system ledger and triggers a confirmation notification email."
    # So the pipeline status starts as "Processing" or "Awaiting human review". Let's set the status to "Awaiting human review" (or if recommendation is "approve", we can set it to "Awaiting human review" but flag it as "Recommended for Approval"). This gives the reviewer control. Wait!
    # Let's set it to "Awaiting human review" for all, but display the auto-recommendation clearly in the dashboard.
    
    sub["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Save submission
    save_single_submission(sub)
    write_audit_log("pipeline.complete", "system", sub_id, f"Auto-analyzed submission. Recommendation: {recommendation}.")
    
    clear_pipeline_progress(sub_id)
    return sub

def start_async_analysis(sub: dict):
    """
    Triggers the 6-step analysis pipeline in the background using ThreadPoolExecutor.
    Updates the session state with status updates.
    """
    executor = get_thread_pool()
    
    # Put submission status to 'Processing' immediately
    sub["status"] = "Processing"
    sub["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_single_submission(sub)
    write_audit_log("pipeline.queued", "system", sub["submission_id"], "Queued for async processing.")
    
    # Submit task to ThreadPoolExecutor
    future = executor.submit(analyze_submission_sync, sub)
    return future
