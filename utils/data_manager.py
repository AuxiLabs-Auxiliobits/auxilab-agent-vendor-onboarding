import os
import csv
import json
import threading
from datetime import datetime
import bcrypt

# Thread locks to prevent concurrent write issues on flat files
_db_lock = threading.Lock()

DATA_DIR = "data"
UPLOAD_DIR = "uploads"
SUBMISSIONS_FILE = os.path.join(DATA_DIR, "submissions.csv")
AUDIT_LOG_FILE = os.path.join(DATA_DIR, "audit_logs.csv")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

def init_directories():
    """Create data and uploads directories if they don't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password using bcrypt."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

# CSV Column Definitions for Submissions
SUBMISSIONS_COLUMNS = [
    "submission_id", "legal_name", "dba_name", "website", 
    "duns", "contact_name", "contact_email", "contact_phone",
    "ap_contact_name", "ap_contact_email", "ap_contact_phone",
    "company_address", 
    "company_street", "company_city", "company_state", "company_zip",
    "billing_street", "billing_city", "billing_state", "billing_zip",
    "tax_id_gst", "fein", "tax_classification", "state_of_incorporation",
    "backup_withholding", "is_1099_eligible",
    "products_services", "years_in_business", "annual_revenue_usd", "employee_count",
    "payment_terms", "conflict_of_interest", "references_count", 
    "w9_filename", "coi_filename", "bank_letter_filename", "questionnaire_filename", 
    "company_reg_filename", "other_doc_1_filename", "other_doc_2_filename", 
    "status", "overall_score", "risk_recommendation", "risk_flags", 
    "consistency_checks", "document_scores", "extracted_data", "reviewer_comments", 
    "erp_vendor_key", "created_at", "updated_at"
]

def read_submissions():
    """Read all submissions from CSV."""
    init_directories()
    with _db_lock:
        if not os.path.exists(SUBMISSIONS_FILE):
            return []
        submissions = []
        with open(SUBMISSIONS_FILE, mode="r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert string representation of types
                for key in ["years_in_business", "annual_revenue_usd", "employee_count", "references_count"]:
                    if row.get(key):
                        try:
                            row[key] = int(row[key])
                        except ValueError:
                            row[key] = None
                for key in ["overall_score"]:
                    if row.get(key):
                        try:
                            row[key] = float(row[key])
                        except ValueError:
                            row[key] = 0.0
                submissions.append(dict(row))
        return submissions

def save_submissions(submissions_list):
    """Save all submissions to CSV (overwrites existing)."""
    init_directories()
    with _db_lock:
        with open(SUBMISSIONS_FILE, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=SUBMISSIONS_COLUMNS)
            writer.writeheader()
            for sub in submissions_list:
                # Ensure all columns are present
                row = {col: sub.get(col, "") for col in SUBMISSIONS_COLUMNS}
                writer.writerow(row)

def save_single_submission(sub):
    """Save or update a single submission record."""
    submissions = read_submissions()
    found = False
    for i, s in enumerate(submissions):
        if s["submission_id"] == sub["submission_id"]:
            submissions[i] = sub
            found = True
            break
    if not found:
        submissions.append(sub)
    save_submissions(submissions)

def get_submission_by_id(submission_id):
    """Get a submission by its ID."""
    submissions = read_submissions()
    for s in submissions:
        if s["submission_id"] == submission_id:
            return s
    return None

def write_audit_log(action, username, submission_id, details=""):
    """Append a log entry to audit_logs.csv."""
    init_directories()
    columns = ["timestamp", "action", "username", "submission_id", "details"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _db_lock:
        file_exists = os.path.exists(AUDIT_LOG_FILE)
        with open(AUDIT_LOG_FILE, mode="a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "timestamp": timestamp,
                "action": action,
                "username": username,
                "submission_id": submission_id,
                "details": details
            })

def get_audit_logs(submission_id=None):
    """Get all audit logs, optionally filtered by submission_id."""
    init_directories()
    with _db_lock:
        if not os.path.exists(AUDIT_LOG_FILE):
            return []
        logs = []
        with open(AUDIT_LOG_FILE, mode="r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                logs.append(dict(row))
        if submission_id:
            return [log for log in logs if log["submission_id"] == submission_id]
        return logs

def read_users():
    """Read reviewer credentials from users.json."""
    init_directories()
    with _db_lock:
        if not os.path.exists(USERS_FILE):
            return {}
        try:
            with open(USERS_FILE, mode="r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

def save_users(users_dict):
    """Save reviewer credentials to users.json."""
    init_directories()
    with _db_lock:
        with open(USERS_FILE, mode="w", encoding="utf-8") as f:
            json.dump(users_dict, f, indent=4)

def authenticate_user(username, password):
    """Authenticate a reviewer user."""
    users = read_users()
    if username not in users:
        return False
    user_data = users[username]
    return verify_password(password, user_data.get("password_hash", ""))

def create_user(username, password, full_name):
    """Create a reviewer user if it doesn't already exist."""
    users = read_users()
    if username in users:
        return False
    users[username] = {
        "password_hash": hash_password(password),
        "full_name": full_name
    }
    save_users(users)
    return True

def get_submission_upload_path(submission_id, filename):
    """Get path to save uploaded document."""
    sub_dir = os.path.join(UPLOAD_DIR, submission_id)
    os.makedirs(sub_dir, exist_ok=True)
    return os.path.join(sub_dir, filename)

def seed_database_if_empty():
    """Seed the database with default reviewer and mock submissions if empty."""
    init_directories()
    
    # 1. Seed reviewer users if users.json is empty
    users = read_users()
    if not users:
        create_user("admin", "admin", "System Reviewer")
        create_user("reviewer", "password", "Onboarding Specialist")
    
    # 2. Seed submissions if empty
    submissions = read_submissions()
    if not submissions:
        mock_subs = []
        
        # # Vendor 1: Acme Logistics LLC (Clean / Auto-approved)
        # v1_w9_extracted = {
        #     "legalName": "Acme Logistics LLC",
        #     "dbaName": "Acme Freight",
        #     "ein": "82-4471029",
        #     "entityType": "LLC",
        #     "taxClassification": "LLC",
        #     "stateOfIncorporation": "DE",
        #     "backupWithholdingExempt": True,
        #     "is1099Eligible": False,
        #     "addressLine1": "1200 Broadway Suite 400",
        #     "city": "New York",
        #     "state": "NY",
        #     "zipCode": "10001",
        #     "isPOBoxOnly": False,
        #     "signaturePresent": True,
        #     "signatureDate": "2026-01-10",
        #     "confidence": 0.99
        # }
        # v1_coi_extracted = {
        #     "insuredName": "Acme Logistics LLC",
        #     "insurerName": "Travelers Insurance",
        #     "generalLiabilityPerOccurrence": 2000000,
        #     "generalLiabilityAggregate": 4000000,
        #     "hasCyberLiability": True,
        #     "cyberLiabilityLimit": 1000000,
        #     "hasWorkersComp": True,
        #     "earliestExpiryDate": "2027-10-15",
        #     "policyNumber": "COI-8827419",
        #     "confidence": 0.98
        # }
        # v1_bank_extracted = {
        #     "accountName": "Acme Logistics LLC",
        #     "bankName": "JPMorgan Chase Bank",
        #     "routingNumber": "021000021",
        #     "accountNumberLast4": "8724",
        #     "accountType": "Checking",
        #     "letterDate": "2026-01-12",
        #     "hasOfficialLetterhead": True,
        #     "beneficiaryName": "Acme Logistics LLC",
        #     "swiftBic": "BOFAUS3NXXX",
        #     "confidence": 0.99
        # }
        # v1_quest_extracted = {
        #     "legalName": "Acme Logistics LLC",
        #     "dbaName": "Acme Freight",
        #     "website": "acmelogistics.com",
        #     "apContactName": "Alice AP",
        #     "apContactEmail": "ap@acmelogistics.com",
        #     "apContactPhone": "+1-555-0211",
        #     "companyStreet": "1200 Broadway Suite 400",
        #     "companyCity": "New York",
        #     "companyState": "NY",
        #     "companyZip": "10001",
        #     "billingStreet": "1200 Broadway Suite 400",
        #     "billingCity": "New York",
        #     "billingState": "NY",
        #     "billingZip": "10001",
        #     "fein": "82-4471029",
        #     "taxClassification": "LLC",
        #     "stateOfIncorporation": "DE",
        #     "backupWithholdingExempt": True,
        #     "is1099Eligible": False,
        #     "bankBeneficiaryName": "Acme Logistics LLC",
        #     "swiftBic": "BOFAUS3NXXX",
        #     "contactName": "Robert Vance",
        #     "contactEmail": "rvance@acmelogistics.com",
        #     "contactPhone": "+1-555-0199",
        #     "companyAddress": "1200 Broadway Suite 400, New York, NY 10001",
        #     "taxIdGst": "82-4471029",
        #     "productsServices": "Freight forwarding and 3PL logistics services",
        #     "yearsInBusiness": 8,
        #     "annualRevenueUSD": 14500000,
        #     "employeeCount": 45,
        #     "paymentTerms": "Net 30",
        #     "conflictOfInterest": False,
        #     "referencesCount": 3,
        #     "confidence": 0.98
        # }
        # v1_company_reg_extracted = {
        #     "companyName": "Acme Logistics LLC",
        #     "registrationNumber": "REG-1200-NY",
        #     "registrationDate": "2018-05-12",
        #     "jurisdiction": "New York",
        #     "confidence": 0.98
        # }
        
        # mock_subs.append({
        #     "submission_id": "VND-2026-00001",
        #     "legal_name": "Acme Logistics LLC",
        #     "dba_name": "Acme Freight",
        #     "website": "acmelogistics.com",
        #     "duns": "123456789",
        #     "contact_name": "Robert Vance",
        #     "contact_email": "rvance@acmelogistics.com",
        #     "contact_phone": "+1-555-0199",
        #     "ap_contact_name": "Alice AP",
        #     "ap_contact_email": "ap@acmelogistics.com",
        #     "ap_contact_phone": "+1-555-0211",
        #     "company_address": "1200 Broadway Suite 400, New York, NY 10001",
        #     "company_street": "1200 Broadway Suite 400",
        #     "company_city": "New York",
        #     "company_state": "NY",
        #     "company_zip": "10001",
        #     "billing_street": "1200 Broadway Suite 400",
        #     "billing_city": "New York",
        #     "billing_state": "NY",
        #     "billing_zip": "10001",
        #     "tax_id_gst": "82-4471029",
        #     "fein": "82-4471029",
        #     "tax_classification": "LLC",
        #     "state_of_incorporation": "DE",
        #     "backup_withholding": False,
        #     "is_1099_eligible": False,
        #     "products_services": "Freight forwarding and 3PL logistics services",
        #     "years_in_business": 8,
        #     "annual_revenue_usd": 14500000,
        #     "employee_count": 45,
        #     "payment_terms": "Net 30",
        #     "conflict_of_interest": False,
        #     "references_count": 3,
        #     "w9_filename": "w9_acme.pdf",
        #     "coi_filename": "coi_acme.pdf",
        #     "bank_letter_filename": "bank_letter_acme.pdf",
        #     "questionnaire_filename": "questionnaire_acme.pdf",
        #     "company_reg_filename": "company_registration_acme.pdf",
        #     "other_doc_1_filename": "",
        #     "other_doc_2_filename": "",
        #     "status": "Approved",
        #     "overall_score": 100.0,
        #     "risk_recommendation": "approve",
        #     "risk_flags": json.dumps({"high": [], "medium": []}),
        #     "consistency_checks": json.dumps([
        #         {"rule": "W-9 Legal Name vs COI Insured Name", "passed": True, "details": "Match (100% token similarity)"},
        #         {"rule": "W-9 Legal Name vs Bank Account Name", "passed": True, "details": "Match (100% token similarity)"},
        #         {"rule": "COI Expiration Check", "passed": True, "details": "Active (Expires 2027-10-15)"},
        #         {"rule": "COI Liability Limit Check", "passed": True, "details": "$2,000,000 >= $1,000,000 limit"},
        #         {"rule": "Cyber Liability Presence", "passed": True, "details": "Cyber liability is explicitly present ($1,000,000 limit)"},
        #         {"rule": "COI Expiry Within 30 Days", "passed": True, "details": "Active (More than 30 days remaining)"},
        #         {"rule": "Questionnaire Beneficiary vs Bank Letter Account Name", "passed": True, "details": "Match (100% token similarity)"},
        #         {"rule": "Contact Email Domain vs Website Domain match", "passed": True, "details": "Match (acmelogistics.com)"},
        #         {"rule": "FEIN Match (W-9 vs Questionnaire)", "passed": True, "details": "Match (82-4471029)"},
        #         {"rule": "State of Incorporation Consistency", "passed": True, "details": "Match (DE)"}
        #     ]),
        #     "document_scores": json.dumps({
        #         "w9": 100.0, "coi": 100.0, "bank": 100.0, "questionnaire": 100.0, "company_reg": 100.0
        #     }),
        #     "extracted_data": json.dumps({
        #         "w9": v1_w9_extracted, "coi": v1_coi_extracted, "bank": v1_bank_extracted, "questionnaire": v1_quest_extracted, "company_reg": v1_company_reg_extracted
        #     }),
        #     "reviewer_comments": "Auto-approved. Zero risk markers identified.",
        #     "erp_vendor_key": "ERP-ACME-824",
        #     "created_at": "2026-06-09 09:15:30",
        #     "updated_at": "2026-06-09 09:16:02"
        # })
        
        # # Vendor 2: Brightway Supplies Inc (Escalate Risk - Name Mismatch & Expired COI)
        # v2_w9_extracted = {
        #     "legalName": "Brightway Supplies Inc",
        #     "dbaName": "Brightway MRO",
        #     "ein": "45-9876543",
        #     "entityType": "C-Corp",
        #     "taxClassification": "C-Corp",
        #     "stateOfIncorporation": "IL",
        #     "backupWithholdingExempt": True,
        #     "is1099Eligible": False,
        #     "addressLine1": "700 Industrial Pkwy",
        #     "city": "Chicago",
        #     "state": "IL",
        #     "zipCode": "60666",
        #     "isPOBoxOnly": False,
        #     "signaturePresent": True,
        #     "signatureDate": "2026-02-14",
        #     "confidence": 0.95
        # }
        # v2_coi_extracted = {
        #     "insuredName": "Brightway Supplies Inc",  # Variant Mismatch
        #     "insurerName": "AIG",
        #     "generalLiabilityPerOccurrence": 1500000,
        #     "generalLiabilityAggregate": 3000000,
        #     "hasCyberLiability": False,                 # Mismatch/Missing
        #     "cyberLiabilityLimit": None,
        #     "hasWorkersComp": True,
        #     "earliestExpiryDate": "2026-05-15",          # Expired (current is 2026-06-09)
        #     "policyNumber": "COI-1299388",
        #     "confidence": 0.92
        # }
        # v2_bank_extracted = {
        #     "accountName": "Brightway Supplies Inc",
        #     "bankName": "Wells Fargo Bank",
        #     "routingNumber": "121000248",
        #     "accountNumberLast4": "9812",
        #     "accountType": "Checking",
        #     "letterDate": "2026-02-20",
        #     "hasOfficialLetterhead": True,
        #     "beneficiaryName": "Brightway Supplies Inc",
        #     "swiftBic": "CHICUS34XXX",
        #     "confidence": 0.94
        # }
        # v2_quest_extracted = {
        #     "legalName": "Brightway Supplies Inc",
        #     "dbaName": "Brightway MRO",
        #     "website": "brightwaysupplies.com",
        #     "apContactName": "John Connor",
        #     "apContactEmail": "ap@brightwaysupplies.com",
        #     "apContactPhone": "+1-555-0244",
        #     "companyStreet": "700 Industrial Pkwy",
        #     "companyCity": "Chicago",
        #     "companyState": "IL",
        #     "companyZip": "60666",
        #     "billingStreet": "700 Industrial Pkwy",
        #     "billingCity": "Chicago",
        #     "billingState": "IL",
        #     "billingZip": "60666",
        #     "fein": "45-9876543",
        #     "taxClassification": "C-Corp",
        #     "stateOfIncorporation": "IL",
        #     "backupWithholdingExempt": True,
        #     "is1099Eligible": False,
        #     "bankBeneficiaryName": "Brightway Supplies Inc",
        #     "swiftBic": "CHICUS34XXX",
        #     "contactName": "Sarah Connor",
        #     "contactEmail": "sconnor@brightwaysupplies.com",
        #     "contactPhone": "+1-555-0144",
        #     "companyAddress": "700 Industrial Pkwy, Chicago, IL 60666",
        #     "taxIdGst": "45-9876543",
        #     "productsServices": "Industrial maintenance, repair and operations (MRO) supplies",
        #     "yearsInBusiness": 4,
        #     "annualRevenueUSD": 3800000,
        #     "employeeCount": 18,
        #     "paymentTerms": "Net 45",
        #     "conflictOfInterest": False,
        #     "referencesCount": 2,
        #     "confidence": 0.95
        # }
        # v2_company_reg_extracted = {
        #     "companyName": "Brightway Supplies Inc",
        #     "registrationNumber": "REG-4500-IL",
        #     "registrationDate": "2022-02-14",
        #     "jurisdiction": "Illinois",
        #     "confidence": 0.95
        # }
        
        # mock_subs.append({
        #     "submission_id": "VND-2026-00002",
        #     "legal_name": "Brightway Supplies Inc",
        #     "dba_name": "Brightway MRO",
        #     "website": "brightwaysupplies.com",
        #     "duns": "987654321",
        #     "contact_name": "Sarah Connor",
        #     "contact_email": "sconnor@brightwaysupplies.com",
        #     "contact_phone": "+1-555-0144",
        #     "ap_contact_name": "John Connor",
        #     "ap_contact_email": "ap@brightwaysupplies.com",
        #     "ap_contact_phone": "+1-555-0244",
        #     "company_address": "700 Industrial Pkwy, Chicago, IL 60666",
        #     "company_street": "700 Industrial Pkwy",
        #     "company_city": "Chicago",
        #     "company_state": "IL",
        #     "company_zip": "60666",
        #     "billing_street": "700 Industrial Pkwy",
        #     "billing_city": "Chicago",
        #     "billing_state": "IL",
        #     "billing_zip": "60666",
        #     "tax_id_gst": "45-9876543",
        #     "fein": "45-9876543",
        #     "tax_classification": "C-Corp",
        #     "state_of_incorporation": "IL",
        #     "backup_withholding": False,
        #     "is_1099_eligible": False,
        #     "products_services": "Industrial maintenance, repair and operations (MRO) supplies",
        #     "years_in_business": 4,
        #     "annual_revenue_usd": 3800000,
        #     "employee_count": 18,
        #     "payment_terms": "Net 45",
        #     "conflict_of_interest": False,
        #     "references_count": 2,
        #     "w9_filename": "w9_brightway.pdf",
        #     "coi_filename": "coi_brightway.pdf",
        #     "bank_letter_filename": "bank_letter_brightway.pdf",
        #     "questionnaire_filename": "questionnaire_brightway.pdf",
        #     "company_reg_filename": "company_registration_brightway.pdf",
        #     "other_doc_1_filename": "",
        #     "other_doc_2_filename": "",
        #     "status": "Awaiting human review",
        #     "overall_score": 96.25, # calculated from weights (W-9: 100%, COI: 85%, Bank: 100%, Questionnaire: 100%)
        #     "risk_recommendation": "request_info", # Since > 2 Medium Risk flags
        #     "risk_flags": json.dumps({
        #         "high": [],
        #         "medium": [
        #             "Cross-document consistency check failed (W-9 name vs COI insured name mismatch)",
        #             "Cross-document consistency check failed (COI policy expired on 2026-05-15)",
        #             "Cross-document consistency check failed (Lack of cyber liability coverage)"
        #         ]
        #     }),
        #     "consistency_checks": json.dumps([
        #         {"rule": "W-9 Legal Name vs COI Insured Name", "passed": False, "details": "Mismatch ('Brightway Supplies Inc' vs 'Brightway Supplies Inc' token overlap 57%)"},
        #         {"rule": "W-9 Legal Name vs Bank Account Name", "passed": True, "details": "Match (100% token similarity)"},
        #         {"rule": "COI Expiration Check", "passed": False, "details": "Expired (policy ended 2026-05-15)"},
        #         {"rule": "COI Liability Limit Check", "passed": True, "details": "$1,500,000 >= $1,000,000 limit"},
        #         {"rule": "Cyber Liability Presence", "passed": False, "details": "Cyber liability is missing"},
        #         {"rule": "COI Expiry Within 30 Days", "passed": False, "details": "Expired (policy ended 2026-05-15)"},
        #         {"rule": "Questionnaire Beneficiary vs Bank Letter Account Name", "passed": True, "details": "Match (100% token similarity)"},
        #         {"rule": "Contact Email Domain vs Website Domain match", "passed": True, "details": "Match (brightwaysupplies.com)"},
        #         {"rule": "FEIN Match (W-9 vs Questionnaire)", "passed": True, "details": "Match (45-9876543)"},
        #         {"rule": "State of Incorporation Consistency", "passed": True, "details": "Match (IL)"}
        #     ]),
        #     "document_scores": json.dumps({
        #         "w9": 100.0, "coi": 85.0, "bank": 100.0, "questionnaire": 100.0, "company_reg": 100.0
        #     }),
        #     "extracted_data": json.dumps({
        #         "w9": v2_w9_extracted, "coi": v2_coi_extracted, "bank": v2_bank_extracted, "questionnaire": v2_quest_extracted, "company_reg": v2_company_reg_extracted
        #     }),
        #     "reviewer_comments": "",
        #     "erp_vendor_key": "",
        #     "created_at": "2026-06-09 11:22:15",
        #     "updated_at": "2026-06-09 11:23:45"
        # })
        
        # # Vendor 3: QuickVend Solutions LLC (High Danger Profile)
        # v3_w9_extracted = {
        #     "legalName": "QuickVend Solutions LLC",
        #     "dbaName": "QuickVend",
        #     "ein": "99999999",                             # Invalid EIN Format
        #     "entityType": "LLC",
        #     "taxClassification": "LLC",
        #     "stateOfIncorporation": "TX",
        #     "backupWithholdingExempt": False,
        #     "is1099Eligible": True,
        #     "addressLine1": "P.O. Box 789",                 # PO Box Only
        #     "city": "Austin",
        #     "state": "TX",
        #     "zipCode": "78701",
        #     "isPOBoxOnly": True,
        #     "signaturePresent": True,
        #     "signatureDate": "2026-04-12",
        #     "confidence": 0.91
        # }
        # v3_coi_extracted = {
        #     "insuredName": "QuickVend Solutions LLC",
        #     "insurerName": "Progressive Commercial",
        #     "generalLiabilityPerOccurrence": 500000,        # Under $1,000,000
        #     "generalLiabilityAggregate": 1000000,
        #     "hasCyberLiability": False,                     # Mismatch/Missing
        #     "cyberLiabilityLimit": None,
        #     "hasWorkersComp": False,
        #     "earliestExpiryDate": "2026-12-31",
        #     "policyNumber": "COI-445566",
        #     "confidence": 0.89
        # }
        # v3_bank_extracted = None # Missing bank confirmation letter
        # v3_quest_extracted = {
        #     "legalName": "QuickVend Solutions LLC",
        #     "dbaName": "QuickVend",
        #     "website": "quickvend.com",
        #     "apContactName": "Jane Doe",
        #     "apContactEmail": "ap@quickvend.com",
        #     "apContactPhone": "+1-555-0178",
        #     "companyStreet": "P.O. Box 789",
        #     "companyCity": "Austin",
        #     "companyState": "TX",
        #     "companyZip": "78701",
        #     "billingStreet": "P.O. Box 789",
        #     "billingCity": "Austin",
        #     "billingState": "TX",
        #     "billingZip": "78701",
        #     "fein": "99-9999999",
        #     "taxClassification": "LLC",
        #     "stateOfIncorporation": "TX",
        #     "backupWithholdingExempt": False,
        #     "is1099Eligible": True,
        #     "bankBeneficiaryName": "QuickVend Solutions LLC",
        #     "swiftBic": "TXUS33XXXXX",
        #     "contactName": "Jane Doe",
        #     "contactEmail": "jdoe@quickvend.com",
        #     "contactPhone": "+1-555-0177",
        #     "companyAddress": "P.O. Box 789, Austin, TX 78701",
        #     "taxIdGst": "99-9999999",
        #     "productsServices": "On-demand office snack and beverage replenishment services",
        #     "yearsInBusiness": 1,
        #     "annualRevenueUSD": 350000,
        #     "employeeCount": 3,
        #     "paymentTerms": "Due on Receipt",
        #     "conflictOfInterest": True,
        #     "referencesCount": 1,
        #     "confidence": 0.90
        # }
        # v3_company_reg_extracted = {
        #     "companyName": "QuickVend Solutions LLC",
        #     "registrationNumber": "REG-9900-TX",
        #     "registrationDate": "2025-04-12",
        #     "jurisdiction": "Texas",
        #     "confidence": 0.92
        # }
        
        # mock_subs.append({
        #     "submission_id": "VND-2026-00003",
        #     "legal_name": "QuickVend Solutions LLC",
        #     "dba_name": "QuickVend",
        #     "website": "quickvend.com",
        #     "duns": "112233445",
        #     "contact_name": "Jane Doe",
        #     "contact_email": "jdoe@quickvend.com",
        #     "contact_phone": "+1-555-0177",
        #     "ap_contact_name": "Jane Doe",
        #     "ap_contact_email": "ap@quickvend.com",
        #     "ap_contact_phone": "+1-555-0178",
        #     "company_address": "P.O. Box 789, Austin, TX 78701",
        #     "company_street": "P.O. Box 789",
        #     "company_city": "Austin",
        #     "company_state": "TX",
        #     "company_zip": "78701",
        #     "billing_street": "P.O. Box 789",
        #     "billing_city": "Austin",
        #     "billing_state": "TX",
        #     "billing_zip": "78701",
        #     "tax_id_gst": "99-9999999",
        #     "fein": "99-9999999",
        #     "tax_classification": "LLC",
        #     "state_of_incorporation": "TX",
        #     "backup_withholding": True,
        #     "is_1099_eligible": True,
        #     "products_services": "On-demand office snack and beverage replenishment services",
        #     "years_in_business": 1,
        #     "annual_revenue_usd": 350000,
        #     "employee_count": 3,
        #     "payment_terms": "Due on Receipt",
        #     "conflict_of_interest": True,
        #     "references_count": 1,
        #     "w9_filename": "w9_quickvend.pdf",
        #     "coi_filename": "coi_quickvend.pdf",
        #     "bank_letter_filename": "",
        #     "questionnaire_filename": "questionnaire_quickvend.pdf",
        #     "company_reg_filename": "company_registration_quickvend.pdf",
        #     "other_doc_1_filename": "",
        #     "other_doc_2_filename": "",
        #     "status": "Awaiting human review",
        #     "overall_score": 67.5, # (100% W-9, 70% COI, 0% Bank, 100% Questionnaire) / 4
        #     "risk_recommendation": "escalate", # >= 1 High Risk flag
        #     "risk_flags": json.dumps({
        #         "high": [
        #             "Invalid EIN Format (99999999) - Must match XX-XXXXXXX",
        #             "Physical address is PO Box Only",
        #             "Missing mandatory document: Bank Letter"
        #         ],
        #         "medium": [
        #             "Business age is under 2 years (1 year)",
        #             "Lack of cyber liability coverage",
        #             "Cross-document consistency check failed (W-9 name vs Bank account name - bank letter missing)",
        #             "Cross-document consistency check failed (COI General Liability Per Occurrence $500,000 is under $1,000,000 threshold)",
        #             "Cross-document consistency check failed (Lack of cyber liability coverage)"
        #         ]
        #     }),
        #     "consistency_checks": json.dumps([
        #         {"rule": "W-9 Legal Name vs COI Insured Name", "passed": True, "details": "Match (100% token similarity)"},
        #         {"rule": "W-9 Legal Name vs Bank Account Name", "passed": False, "details": "Fail (Missing bank letter)"},
        #         {"rule": "COI Expiration Check", "passed": True, "details": "Active (Expires 2026-12-31)"},
        #         {"rule": "COI Liability Limit Check", "passed": False, "details": "Under threshold ($500,000 < $1,000,000)"},
        #         {"rule": "Cyber Liability Presence", "passed": False, "details": "Cyber liability is missing"},
        #         {"rule": "COI Expiry Within 30 Days", "passed": True, "details": "Active (More than 30 days remaining)"},
        #         {"rule": "Questionnaire Beneficiary vs Bank Letter Account Name", "passed": False, "details": "Fail (Missing bank letter)"},
        #         {"rule": "Contact Email Domain vs Website Domain match", "passed": True, "details": "Match (quickvend.com)"},
        #         {"rule": "FEIN Match (W-9 vs Questionnaire)", "passed": False, "details": "Mismatch ('99999999' vs '99-9999999')"},
        #         {"rule": "State of Incorporation Consistency", "passed": True, "details": "Match (TX)"}
        #     ]),
        #     "document_scores": json.dumps({
        #         "w9": 100.0, "coi": 70.0, "bank": 0.0, "questionnaire": 100.0, "company_reg": 100.0
        #     }),
        #     "extracted_data": json.dumps({
        #         "w9": v3_w9_extracted, "coi": v3_coi_extracted, "bank": v3_bank_extracted, "questionnaire": v3_quest_extracted, "company_reg": v3_company_reg_extracted
        #     }),
        #     "reviewer_comments": "",
        #     "erp_vendor_key": "",
        #     "created_at": "2026-06-09 14:05:00",
        #     "updated_at": "2026-06-09 14:06:12"
        # })
        
        save_submissions(mock_subs)
        
        # Write seed audit logs
        write_audit_log("seed.initialize", "system", "SYSTEM", "Seeded system reviewer and 3 default test submissions.")
        write_audit_log("pipeline.complete", "system", "VND-2026-00001", "Auto-analyzed Acme Logistics LLC. Recommendation: approve.")
        write_audit_log("human.approved", "admin", "VND-2026-00001", "Manual review bypass. ERP key assigned: ERP-ACME-824.")
        write_audit_log("pipeline.complete", "system", "VND-2026-00002", "Auto-analyzed Brightway Supplies Inc. Recommendation: request_info.")
        write_audit_log("pipeline.complete", "system", "VND-2026-00003", "Auto-analyzed QuickVend Solutions LLC. Recommendation: escalate.")

# Automatically seed database on import to ensure all Streamlit pages are initialized
seed_database_if_empty()
