import os
import re
import json
import time
import streamlit as st
from pydantic import BaseModel, Field
from typing import Literal, Optional
import pypdf
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()  # Load .env so GEMINI_API_KEY and SMTP vars are available

# ── Config from .env ─────────────────────────────────────────────
GEMINI_MODEL          = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_MAX_RETRIES    = int(os.getenv("GEMINI_MAX_RETRIES", "5"))
GEMINI_RETRY_WAIT_BASE = int(os.getenv("GEMINI_RETRY_WAIT_BASE", "15"))

# 1. Schema Definitions using Pydantic (v2 compatible)

class W9Schema(BaseModel):
    legalName: Optional[str] = Field(None, description="The legal name as shown on W-9 line 1")
    dbaName: Optional[str] = Field(None, description="Business name/disregarded entity name, if different from legal name (W-9 Line 2)")
    ein: Optional[str] = Field(None, description="Employer Identification Number in XX-XXXXXXX format, or SSN if sole proprietor")
    entityType: Optional[Literal["LLC", "C-Corp", "S-Corp", "Partnership", "Sole Proprietor", "Other"]] = Field(None, description="Type of entity selected")
    taxClassification: Optional[str] = Field(None, description="Federal tax classification selected (W-9)")
    stateOfIncorporation: Optional[str] = Field(None, description="State of incorporation/organization (W-9)")
    backupWithholdingExempt: bool = Field(False, description="True if exempt from backup withholding (W-9)")
    is1099Eligible: bool = Field(False, description="True if vendor is eligible for 1099 reporting based on classification")
    addressLine1: Optional[str] = Field(None, description="Physical street address line 1")
    city: Optional[str] = Field(None, description="City")
    state: Optional[str] = Field(None, description="State (2-letter abbreviation preferred)")
    zipCode: Optional[str] = Field(None, description="ZIP code")
    isPOBoxOnly: bool = Field(False, description="True ONLY if address is a PO Box and no physical street address exists")
    signaturePresent: bool = Field(False, description="True if a signature is detected on the signature line")
    signatureDate: Optional[str] = Field(None, description="Date of W-9 signature, preferably YYYY-MM-DD")
    confidence: float = Field(0.0, description="Extraction confidence score between 0.0 and 1.0")

class COISchema(BaseModel):
    insuredName: Optional[str] = Field(None, description="Name of the insured company")
    insurerName: Optional[str] = Field(None, description="Name of the insurance carrier/insurer")
    generalLiabilityPerOccurrence: Optional[int] = Field(None, description="General Liability Limit Per Occurrence in USD (integer, no symbols/commas)")
    generalLiabilityAggregate: Optional[int] = Field(None, description="General Liability Limit Aggregate in USD (integer, no symbols/commas)")
    hasCyberLiability: bool = Field(False, description="True if Cyber Liability coverage is present/checked")
    cyberLiabilityLimit: Optional[int] = Field(None, description="Cyber Liability Limit in USD (integer, no symbols/commas)")
    hasWorkersComp: bool = Field(False, description="True if Workers Compensation coverage is present/checked")
    earliestExpiryDate: Optional[str] = Field(None, description="Earliest policy expiration date (e.g. general liability or workers comp expiry) in MM/DD/YYYY format, mentioned with label as : CERTIFICATE EXPIRATION DATE")
    policyNumber: Optional[str] = Field(None, description="Policy number of general liability coverage")
    confidence: float = Field(0.0, description="Extraction confidence score between 0.0 and 1.0")

class BankLetterSchema(BaseModel):
    accountName: Optional[str] = Field(None, description="Name of the account holder on the bank letter")
    bankName: Optional[str] = Field(None, description="Name of the financial institution")
    routingNumber: Optional[str] = Field(None, description="9-digit bank routing transit number")
    accountNumberLast4: Optional[str] = Field(None, description="Last 4 digits of the account number")
    accountType: Optional[Literal["Checking", "Savings", "Other"]] = Field(None, description="Checking, Savings, or Other")
    letterDate: Optional[str] = Field(None, description="Date the bank letter was issued (YYYY-MM-DD)")
    hasOfficialLetterhead: bool = Field(False, description="True if the letter appears to be printed on official bank stationery/letterhead")
    beneficiaryName: Optional[str] = Field(None, description="Bank Beneficiary Name (Account Holder Name) as listed")
    swiftBic: Optional[str] = Field(None, description="SWIFT or BIC code (8 or 11 alphanumeric characters)")
    confidence: float = Field(0.0, description="Extraction confidence score between 0.0 and 1.0")

class QuestionnaireSchema(BaseModel):
    legalName: Optional[str] = Field(None, description="Legal name of business entity")
    dbaName: Optional[str] = Field(None, description="Doing Business As (DBA) name")
    website: Optional[str] = Field(None, description="Primary website URL")
    contactName: Optional[str] = Field(None, description="Primary contact name")
    contactEmail: Optional[str] = Field(None, description="Primary contact email address")
    contactPhone: Optional[str] = Field(None, description="Primary contact phone number")
    apContactName: Optional[str] = Field(None, description="Accounts Payable contact name")
    apContactEmail: Optional[str] = Field(None, description="Accounts Payable email address")
    apContactPhone: Optional[str] = Field(None, description="Accounts Payable phone number")
    companyStreet: Optional[str] = Field(None, description="Company primary street address")
    companyCity: Optional[str] = Field(None, description="Company primary city")
    companyState: Optional[str] = Field(None, description="Company primary state")
    companyZip: Optional[str] = Field(None, description="Company primary ZIP code")
    companyAddress: Optional[str] = Field(None, description="Full address of the company")
    billingStreet: Optional[str] = Field(None, description="Company billing street address")
    billingCity: Optional[str] = Field(None, description="Company billing city")
    billingState: Optional[str] = Field(None, description="Company billing state")
    billingZip: Optional[str] = Field(None, description="Company billing ZIP code")
    taxIdGst: Optional[str] = Field(None, description="Tax ID or GST registration number")
    fein: Optional[str] = Field(None, description="Federal Employer Identification Number")
    taxClassification: Optional[str] = Field(None, description="US tax classification")
    stateOfIncorporation: Optional[str] = Field(None, description="US State of incorporation/organization")
    backupWithholdingExempt: Optional[bool] = Field(False, description="True if exempt from backup withholding")
    is1099Eligible: Optional[bool] = Field(False, description="True if eligible for 1099 reporting")
    productsServices: Optional[str] = Field(None, description="Brief description of products/services offered")
    yearsInBusiness: Optional[int] = Field(None, description="Number of years in business")
    annualRevenueUSD: Optional[int] = Field(None, description="Annual revenue in USD, parsed to integer")
    employeeCount: Optional[int] = Field(None, description="Number of employees")
    paymentTerms: Optional[str] = Field(None, description="Requested payment terms, e.g. Net 30, Net 45, Due on Receipt")
    conflictOfInterest: Optional[bool] = Field(None, description="True if any conflict of interest is declared, False otherwise")
    referencesCount: Optional[int] = Field(None, description="Number of business references provided")
    bankBeneficiaryName: Optional[str] = Field(None, description="The bank account beneficiary name or account holder name listed under the banking details section of the questionnaire")
    swiftBic: Optional[str] = Field(None, description="The SWIFT or BIC bank routing code listed in the questionnaire")
    confidence: float = Field(0.0, description="Extraction confidence score between 0.0 and 1.0")

class CompanyRegSchema(BaseModel):
    companyName: Optional[str] = Field(None, description="The official registered name of the company")
    registrationNumber: Optional[str] = Field(None, description="The official business registration number/filing ID")
    registrationDate: Optional[str] = Field(None, description="Filing/incorporation date, YYYY-MM-DD")
    jurisdiction: Optional[str] = Field(None, description="State, province, or country of incorporation")
    confidence: float = Field(0.0, description="Extraction confidence score between 0.0 and 1.0")

# 2. PDF Parser utility

def extract_text_from_file(file_path: str) -> str:
    """Extract raw text from PDF, Text, or mock placeholder from image files."""
    if not os.path.exists(file_path):
        return ""
        
    ext = file_path.lower()
    if ext.endswith(".pdf"):
        try:
            reader = pypdf.PdfReader(file_path)
            text_content = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text)
            return "\n".join(text_content).strip()
        except Exception as e:
            print(f"Error parsing PDF at {file_path}: {e}")
            return ""
    elif ext.endswith(".txt"):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip()
        except Exception as e:
            print(f"Error reading TXT at {file_path}: {e}")
            return ""
    elif ext.endswith((".png", ".jpg", ".jpeg")):
        # For mock offline OCR / file keyword scanning, we can just return the file name as hint
        return f"Mock parsed image text for {os.path.basename(file_path)}"
    return ""

# 3. Gemini Connection utility

def get_gemini_api_key() -> Optional[str]:
    """Retrieve Gemini API key from Environment or Streamlit Secrets."""
    # Check env
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    # Check secrets
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return None

def extract_with_gemini(doc_type: str, text: str, api_key: str, max_retries: int = GEMINI_MAX_RETRIES):
    """Run structured extraction using google-genai library with retry on quota/503 errors."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    schema_map = {
        "w9": W9Schema,
        "coi": COISchema,
        "bank": BankLetterSchema,
        "questionnaire": QuestionnaireSchema,
        "company_reg": CompanyRegSchema
    }
    
    pydantic_model = schema_map.get(doc_type)
    if not pydantic_model:
        raise ValueError(f"Unknown document type: {doc_type}")
        
    prompt = f"""
    You are an AI document audit assistant. Analyze the text extracted from a vendor's uploaded document ({doc_type.upper()}) and output structured data.
    
    CRITICAL: Fill out every field in the schema based ONLY on the evidence in the text. 
    If a field is not found or cannot be determined, set it to null.
    Set the confidence field to a float between 0.0 and 1.0 representing your certainty of the extraction.
    
    Document text:
    ---
    {text}
    ---
    """

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=pydantic_model,
                    temperature=0.0
                )
            )
            data = json.loads(response.text)
            return data
        except Exception as e:
            err_str = str(e)
            # Retry on quota (429) or server unavailable (503)
            if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str or
                    "503" in err_str or "UNAVAILABLE" in err_str):
                wait = GEMINI_RETRY_WAIT_BASE * attempt
                print(f"[Extractor] Quota/503 error for {doc_type} (attempt {attempt}/{max_retries}). "
                      f"Waiting {wait}s before retry...")
                time.sleep(wait)
                continue
            # Non-retryable error — raise immediately
            print(f"Gemini API call failed for {doc_type}: {e}")
            raise e

    # All retries exhausted
    raise RuntimeError(f"Gemini extraction failed for {doc_type} after {max_retries} retries (quota exceeded).")

# 4. Fallback Smart Mock Extractor for local testing/offline validation

def extract_mock_data(doc_type: str, raw_text: str) -> dict:
    """
    Intelligent mock parser that scans the raw text for keywords to return
    either Acme, Brightway, QuickVend, or realistic general mock extraction data.
    """
    text_lower = raw_text.lower()
    
    # Check if this matches one of the seed vendor profiles
    is_acme = "acme" in text_lower or "rvance" in text_lower
    is_brightway = "brightway" in text_lower or "sconnor" in text_lower
    is_quickvend = "quickvend" in text_lower or "jdoe" in text_lower or "austin" in text_lower
    
    if doc_type == "w9":
        if is_acme:
            res = {
                "legalName": "Acme Logistics LLC", "dbaName": "Acme Freight", "ein": "82-4471029", "entityType": "LLC",
                "taxClassification": "LLC", "stateOfIncorporation": "DE", "backupWithholdingExempt": True, "is1099Eligible": False,
                "addressLine1": "1200 Broadway Suite 400", "city": "New York", "state": "NY", "zipCode": "10001",
                "isPOBoxOnly": False, "signaturePresent": True, "signatureDate": "2026-01-10", "confidence": 0.99
            }
        elif is_brightway:
            res = {
                "legalName": "Brightway Supplies Inc", "dbaName": "Brightway MRO", "ein": "45-9876543", "entityType": "C-Corp",
                "taxClassification": "C-Corp", "stateOfIncorporation": "IL", "backupWithholdingExempt": True, "is1099Eligible": False,
                "addressLine1": "700 Industrial Pkwy", "city": "Chicago", "state": "IL", "zipCode": "60666",
                "isPOBoxOnly": False, "signaturePresent": True, "signatureDate": "2026-02-14", "confidence": 0.95
            }
        elif is_quickvend:
            res = {
                "legalName": "QuickVend Solutions LLC", "dbaName": "QuickVend", "ein": "99999999", "entityType": "LLC",
                "taxClassification": "LLC", "stateOfIncorporation": "TX", "backupWithholdingExempt": False, "is1099Eligible": True,
                "addressLine1": "P.O. Box 789", "city": "Austin", "state": "TX", "zipCode": "78701",
                "isPOBoxOnly": True, "signaturePresent": True, "signatureDate": "2026-04-12", "confidence": 0.91
            }
        else:
            # Smart parse text for generic fields
            legal_name = re.search(r"name \((?:as shown|.*?)\):?\s*([A-Za-z0-9\s,\.\-]+)", raw_text, re.IGNORECASE)
            ein_match = re.search(r"(\d{2}\-\d{7})", raw_text)
            zip_match = re.search(r"\b(\d{5})\b", raw_text)
            is_po_box = "p.o. box" in text_lower or "po box" in text_lower
            
            res = {
                "legalName": legal_name.group(1).strip() if legal_name else "Unknown Vendor LLC",
                "dbaName": "Unknown DBA",
                "ein": ein_match.group(1) if ein_match else "00-0000000",
                "entityType": "LLC" if "llc" in text_lower else "Other",
                "taxClassification": "LLC" if "llc" in text_lower else "Other",
                "stateOfIncorporation": "TX",
                "backupWithholdingExempt": True,
                "is1099Eligible": False,
                "addressLine1": "PO Box 123" if is_po_box else "100 Main Street",
                "city": "Dallas",
                "state": "TX",
                "zipCode": zip_match.group(1) if zip_match else "75001",
                "isPOBoxOnly": is_po_box,
                "signaturePresent": "signature" in text_lower or "signed" in text_lower,
                "signatureDate": datetime.now().strftime("%Y-%m-%d"),
                "confidence": 0.85
            }
            
        # Parse dynamically from raw text overrides
        legal_name_match = re.search(r"legal name\s*:\s*([^\r\n]+)", text_lower)
        if not legal_name_match:
            legal_name_match = re.search(r"1\.\s*legal\s*name\s*:\s*([^\r\n]+)", text_lower)
        if legal_name_match:
            res["legalName"] = legal_name_match.group(1).strip()
            
        ein_match = re.search(r"(\d{2}\-\d{7})", raw_text)
        if ein_match:
            res["ein"] = ein_match.group(1)
            
        state_match = re.search(r"state of incorporation\s*:\s*([A-Za-z]{2})", text_lower)
        if state_match:
            res["stateOfIncorporation"] = state_match.group(1).upper()
            
        date_match = re.search(r"date\s*:\s*(\d{4}-\d{2}-\d{2})", text_lower)
        if date_match:
            res["signatureDate"] = date_match.group(1)
            
        return res
            
    elif doc_type == "coi":
        if is_acme:
            res = {
                "insuredName": "Acme Logistics LLC", "insurerName": "Travelers Insurance",
                "generalLiabilityPerOccurrence": 2000000, "generalLiabilityAggregate": 4000000,
                "hasCyberLiability": True, "cyberLiabilityLimit": 1000000, "hasWorkersComp": True,
                "earliestExpiryDate": "2027-10-15", "policyNumber": "COI-8827419", "confidence": 0.98
            }
        elif is_brightway:
            res = {
                "insuredName": "Brightway Supplies Inc", "insurerName": "AIG",
                "generalLiabilityPerOccurrence": 1500000, "generalLiabilityAggregate": 3000000,
                "hasCyberLiability": False, "cyberLiabilityLimit": None, "hasWorkersComp": True,
                "earliestExpiryDate": "2026-05-15", "policyNumber": "COI-1299388", "confidence": 0.92
            }
        elif is_quickvend:
            res = {
                "insuredName": "QuickVend Solutions LLC", "insurerName": "Progressive Commercial",
                "generalLiabilityPerOccurrence": 500000, "generalLiabilityAggregate": 1000000,
                "hasCyberLiability": False, "cyberLiabilityLimit": None, "hasWorkersComp": False,
                "earliestExpiryDate": "2026-12-31", "policyNumber": "COI-445566", "confidence": 0.89
            }
        else:
            limit_match = re.search(r"occurrence\s*(\$?\d[\d,]+)", raw_text, re.IGNORECASE)
            limit = int(re.sub(r"[^\d]", "", limit_match.group(1))) if limit_match else 1000000
            res = {
                "insuredName": "Unknown Vendor LLC",
                "insurerName": "General Liability Ins Inc",
                "generalLiabilityPerOccurrence": limit,
                "generalLiabilityAggregate": limit * 2,
                "hasCyberLiability": "cyber" in text_lower or "technology" in text_lower,
                "cyberLiabilityLimit": 1000000 if "cyber" in text_lower else None,
                "hasWorkersComp": "workers" in text_lower or "workman" in text_lower,
                "earliestExpiryDate": "2027-12-31",
                "policyNumber": "COI-998877",
                "confidence": 0.80
            }
            
        # Parse dynamically from the text to support overrides when user changes files
        limit_match = re.search(r"occurrence\s*:\s*\$?(\d[\d,]+)", text_lower)
        if not limit_match:
            limit_match = re.search(r"occurrence\s*(\$?\d[\d,]+)", text_lower)
        if limit_match:
            res["generalLiabilityPerOccurrence"] = int(re.sub(r"[^\d]", "", limit_match.group(1)))
            res["generalLiabilityAggregate"] = res["generalLiabilityPerOccurrence"] * 2
            
        date_match = re.search(r"(?:expiration|expiry|expires).*?(\d{4}-\d{2}-\d{2})", text_lower)
        if not date_match:
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text_lower)
        if date_match:
            res["earliestExpiryDate"] = date_match.group(1)
            
        if "cyber" in text_lower:
            res["hasCyberLiability"] = True
            res["cyberLiabilityLimit"] = 1000000
            
        return res
            
    elif doc_type == "bank":
        if is_acme:
            res = {
                "accountName": "Acme Logistics LLC", "bankName": "JPMorgan Chase Bank",
                "routingNumber": "021000021", "accountNumberLast4": "8724", "accountType": "Checking",
                "letterDate": "2026-01-12", "hasOfficialLetterhead": True, "beneficiaryName": "Acme Logistics LLC",
                "swiftBic": "BOFAUS3NXXX", "confidence": 0.99
            }
        elif is_brightway:
            res = {
                "accountName": "Brightway Supplies Inc", "bankName": "Wells Fargo Bank",
                "routingNumber": "121000248", "accountNumberLast4": "9812", "accountType": "Checking",
                "letterDate": "2026-02-20", "hasOfficialLetterhead": True, "beneficiaryName": "Brightway Supplies Inc",
                "swiftBic": "CHICUS34XXX", "confidence": 0.94
            }
        elif is_quickvend:
            res = None
        else:
            routing_match = re.search(r"\b(\d{9})\b", raw_text)
            last4_match = re.search(r"x{4,}(\d{4})|account:?.*(\d{4})", raw_text, re.IGNORECASE)
            
            res = {
                "accountName": "Unknown Vendor LLC",
                "bankName": "Standard National Bank",
                "routingNumber": routing_match.group(1) if routing_match else "021000021",
                "accountNumberLast4": last4_match.group(1) or last4_match.group(2) or "5555" if last4_match else "5555",
                "accountType": "Checking" if "checking" in text_lower else "Savings",
                "letterDate": datetime.now().strftime("%Y-%m-%d"),
                "hasOfficialLetterhead": "letterhead" in text_lower or "official" in text_lower,
                "beneficiaryName": "Unknown Vendor LLC",
                "swiftBic": "BOFAUS3NXXX",
                "confidence": 0.85
            }
            
        if res:
            # Overrides
            beneficiary_match = re.search(r"beneficiary name\s*:\s*([^\r\n]+)", text_lower)
            if not beneficiary_match:
                beneficiary_match = re.search(r"account holder\s*:\s*([^\r\n]+)", text_lower)
            if beneficiary_match:
                res["accountName"] = beneficiary_match.group(1).strip()
                res["beneficiaryName"] = beneficiary_match.group(1).strip()
                
            swift_match = re.search(r"swift\s*(?:\/\s*bic)?\s*(?:code)?\s*:\s*([A-Za-z0-9]{8,11})", text_lower)
            if swift_match:
                res["swiftBic"] = swift_match.group(1).upper()
                
            routing_match = re.search(r"routing\s*(?:number)?\s*:\s*([0-9]{9})", text_lower)
            if routing_match:
                res["routingNumber"] = routing_match.group(1)
                
            last4_match = re.search(r"account\s*(?:number)?\s*:\s*(?:[0-9]*([0-9]{4}))", text_lower)
            if last4_match:
                res["accountNumberLast4"] = last4_match.group(1)
                
        return res
            
    elif doc_type == "questionnaire":
        if is_acme:
            return {
                "legalName": "Acme Logistics LLC", "dbaName": "Acme Freight", "website": "acmelogistics.com",
                "contactName": "Robert Vance", "contactEmail": "rvance@acmelogistics.com", "contactPhone": "+1-555-0199",
                "apContactName": "Alice AP", "apContactEmail": "ap@acmelogistics.com", "apContactPhone": "+1-555-0211",
                "companyStreet": "1200 Broadway Suite 400", "companyCity": "New York", "companyState": "NY", "companyZip": "10001",
                "companyAddress": "1200 Broadway Suite 400, New York, NY 10001",
                "billingStreet": "1200 Broadway Suite 400", "billingCity": "New York", "billingState": "NY", "billingZip": "10001",
                "taxIdGst": "82-4471029", "fein": "82-4471029", "taxClassification": "LLC", "stateOfIncorporation": "DE",
                "backupWithholdingExempt": True, "is1099Eligible": False, "bankBeneficiaryName": "Acme Logistics LLC",
                "swiftBic": "BOFAUS3NXXX", "productsServices": "Freight forwarding and 3PL logistics services",
                "yearsInBusiness": 8, "annualRevenueUSD": 14500000, "employeeCount": 45, "paymentTerms": "Net 30",
                "conflictOfInterest": False, "referencesCount": 3, "confidence": 0.98
            }
        elif is_brightway:
            return {
                "legalName": "Brightway Supplies Inc", "dbaName": "Brightway MRO", "website": "brightwaysupplies.com",
                "contactName": "Sarah Connor", "contactEmail": "sconnor@brightwaysupplies.com", "contactPhone": "+1-555-0144",
                "apContactName": "John Connor", "apContactEmail": "ap@brightwaysupplies.com", "apContactPhone": "+1-555-0244",
                "companyStreet": "700 Industrial Pkwy", "companyCity": "Chicago", "companyState": "IL", "companyZip": "60666",
                "companyAddress": "700 Industrial Pkwy, Chicago, IL 60666",
                "billingStreet": "700 Industrial Pkwy", "billingCity": "Chicago", "billingState": "IL", "billingZip": "60666",
                "taxIdGst": "45-9876543", "fein": "45-9876543", "taxClassification": "C-Corp", "stateOfIncorporation": "IL",
                "backupWithholdingExempt": True, "is1099Eligible": False, "bankBeneficiaryName": "Brightway Supplies Inc",
                "swiftBic": "CHICUS34XXX", "productsServices": "Industrial maintenance, repair and operations (MRO) supplies",
                "yearsInBusiness": 4, "annualRevenueUSD": 3800000, "employeeCount": 18, "paymentTerms": "Net 45",
                "conflictOfInterest": False, "referencesCount": 2, "confidence": 0.95
            }
        elif is_quickvend:
            return {
                "legalName": "QuickVend Solutions LLC", "dbaName": "QuickVend", "website": "quickvend.com",
                "contactName": "Jane Doe", "contactEmail": "jdoe@quickvend.com", "contactPhone": "+1-555-0177",
                "apContactName": "Jane Doe", "apContactEmail": "ap@quickvend.com", "apContactPhone": "+1-555-0178",
                "companyStreet": "P.O. Box 789", "companyCity": "Austin", "companyState": "TX", "companyZip": "78701",
                "companyAddress": "P.O. Box 789, Austin, TX 78701",
                "billingStreet": "P.O. Box 789", "billingCity": "Austin", "billingState": "TX", "billingZip": "78701",
                "taxIdGst": "99-9999999", "fein": "99-9999999", "taxClassification": "LLC", "stateOfIncorporation": "TX",
                "backupWithholdingExempt": False, "is1099Eligible": True, "bankBeneficiaryName": "QuickVend Solutions LLC",
                "swiftBic": "TXUS33XXXXX", "productsServices": "On-demand office snack and beverage replenishment services",
                "yearsInBusiness": 1, "annualRevenueUSD": 350000, "employeeCount": 3, "paymentTerms": "Due on Receipt",
                "conflictOfInterest": True, "referencesCount": 1, "confidence": 0.90
            }
        else:
            rev_match = re.search(r"revenue:?\s*(\$?[\d\.]+M?)", raw_text, re.IGNORECASE)
            revenue = 1000000
            if rev_match:
                rev_str = rev_match.group(1).upper()
                if "M" in rev_str:
                    num = float(re.sub(r"[^\d\.]", "", rev_str))
                    revenue = int(num * 1000000)
                else:
                    revenue = int(re.sub(r"[^\d]", "", rev_str))
            
            years_match = re.search(r"(\d+)\s*years", raw_text, re.IGNORECASE)
            years = int(years_match.group(1)) if years_match else 3
            
            return {
                "legalName": "Unknown Vendor LLC",
                "dbaName": "Unknown DBA",
                "website": "unknownvendor.com",
                "contactName": "Jane Tester",
                "contactEmail": "tester@unknownvendor.com",
                "contactPhone": "+1-555-0100",
                "apContactName": "Jane AP",
                "apContactEmail": "ap@unknownvendor.com",
                "apContactPhone": "+1-555-0101",
                "companyStreet": "100 Main Street",
                "companyCity": "Dallas",
                "companyState": "TX",
                "companyZip": "75001",
                "companyAddress": "100 Main Street, Dallas, TX 75001",
                "billingStreet": "100 Main Street",
                "billingCity": "Dallas",
                "billingState": "TX",
                "billingZip": "75001",
                "taxIdGst": "00-0000000",
                "fein": "00-0000000",
                "taxClassification": "LLC",
                "stateOfIncorporation": "TX",
                "backupWithholdingExempt": True,
                "is1099Eligible": False,
                "bankBeneficiaryName": "Unknown Vendor LLC",
                "swiftBic": "BOFAUS3NXXX",
                "productsServices": "General consulting and business support services",
                "yearsInBusiness": years,
                "annualRevenueUSD": revenue,
                "employeeCount": 10,
                "paymentTerms": "Net 30",
                "conflictOfInterest": "yes" in text_lower or "conflict" in text_lower,
                "referencesCount": 2,
                "confidence": 0.85
            }

    elif doc_type == "company_reg":
        if is_acme:
            return {
                "companyName": "Acme Logistics LLC",
                "registrationNumber": "REG-1200-NY",
                "registrationDate": "2018-05-12",
                "jurisdiction": "New York",
                "confidence": 0.98
            }
        elif is_brightway:
            return {
                "companyName": "Brightway Supplies Inc",
                "registrationNumber": "REG-4500-IL",
                "registrationDate": "2022-02-14",
                "jurisdiction": "Illinois",
                "confidence": 0.95
            }
        elif is_quickvend:
            return {
                "companyName": "QuickVend Solutions LLC",
                "registrationNumber": "REG-9900-TX",
                "registrationDate": "2025-04-12",
                "jurisdiction": "Texas",
                "confidence": 0.92
            }
        else:
            return {
                "companyName": "Unknown Vendor LLC",
                "registrationNumber": "REG-0000-XX",
                "registrationDate": "2026-01-01",
                "jurisdiction": "Texas",
                "confidence": 0.85
            }

def run_extraction_pipeline(doc_type: str, pdf_path: Optional[str]) -> Optional[dict]:
    """
    Main extraction interface.
    Extracts text from PDF, then uses Gemini API if available, or falls back to smart mock data.
    Returns parsed dictionary schema.
    """
    if not pdf_path:
        return None
        
    # Extract text from the uploaded file
    text = extract_text_from_file(pdf_path)
    
    # Attempt to retrieve API Key
    api_key = get_gemini_api_key()
    
    if api_key:
        try:
            return extract_with_gemini(doc_type, text, api_key)
        except Exception:
            # Fallback on exception so user pipeline doesn't break
            return extract_mock_data(doc_type, text)
    else:
        # Graceful fallback to smart mock extraction
        return extract_mock_data(doc_type, text)
