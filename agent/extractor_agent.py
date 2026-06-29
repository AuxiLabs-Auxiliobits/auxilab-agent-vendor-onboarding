import os
import sys
import json
import argparse
import base64
from pathlib import Path

try:
    import fitz  # PyMuPDF
    from dotenv import load_dotenv
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage
except ImportError:
    print("[Error] Missing required libraries. Please install them by running:")
    print("pip install pymupdf langchain-google-genai langchain-core python-dotenv")
    sys.exit(1)

# Load environment variables from project root .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# ── Config from .env ─────────────────────────────────────────────
GEMINI_AGENT_MODEL  = os.getenv("GEMINI_AGENT_MODEL", "gemini-2.5-flash")
GEMINI_MAX_TOKENS   = int(os.getenv("GEMINI_MAX_TOKENS", "4096"))

def encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode("utf-8")

def process_file_to_messages(file_path: Path):
    """Convert a file (PDF, Image, or Text) into LangChain message content blocks."""
    content_blocks = []
    
    if file_path.suffix.lower() == '.pdf':
        print(f"[Agent] Processing PDF: {file_path.name}")
        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            content_blocks.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{encode_image(img_bytes)}"
                }
            })
    elif file_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
        print(f"[Agent] Processing Image: {file_path.name}")
        with open(file_path, "rb") as f:
            img_bytes = f.read()
            mime_type = "image/png" if file_path.suffix.lower() == '.png' else "image/jpeg"
            content_blocks.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{encode_image(img_bytes)}"
                }
            })
    elif file_path.suffix.lower() == '.txt':
        print(f"[Agent] Processing Text: {file_path.name}")
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text_content = f.read()
            content_blocks.append({
                "type": "text",
                "text": f"Document content for {file_path.name}:\n{text_content}"
            })
        except Exception as e:
            print(f"[Agent] Error reading text file: {e}")
            
    return content_blocks

def run_extraction_agent(vendor_id: str):
    print(f"\n[Agent] Starting Extraction & Validation Agent for Vendor: {vendor_id}")
    
    # 1. Locate the vendor's upload folder
    base_dir = Path(__file__).parent.parent
    upload_dir = base_dir / "uploads" / vendor_id
    
    if not upload_dir.exists():
        print(f"[Error] No upload directory found for {vendor_id} at {upload_dir}")
        return
        
    print(f"[Agent] Located upload directory: {upload_dir}")
    
    # 2. Gather files in the folder
    files = list(upload_dir.glob("*"))
    doc_files = [f for f in files if f.suffix.lower() in ['.pdf', '.png', '.jpg', '.jpeg', '.txt']]
    json_files = [f for f in files if f.name == 'questionnaire_data.json']
    
    if not doc_files:
        print("[Agent] No documents found to process.")
        return
        
    print(f"[Agent] Found {len(doc_files)} document(s) and {len(json_files)} JSON(s)")
    
    # Load questionnaire data
    questionnaire_data = {}
    if json_files:
        try:
            with open(json_files[0], 'r', encoding='utf-8') as f:
                questionnaire_data = json.load(f)
            print("[Agent] Loaded questionnaire_data.json")
        except Exception as e:
            print(f"[Agent] Error reading questionnaire JSON: {e}")

    # 3. Define the strict output schema
    EXTRACTION_SCHEMA = {
        "vendor_name_cross_validation": {
            "questionnaire_legal_name": None,
            "document_legal_names": [],
            "match": None
        },
        "extracted_entities": {
            "questionnaire": {
                "legal_name": None,
                "dba_name": None,
                "website": None,
                "contact_name": None,
                "contact_email": None,
                "contact_phone": None,
                "ap_contact_name": None,
                "ap_contact_email": None,
                "ap_contact_phone": None,
                "company_street": None,
                "company_city": None,
                "company_state": None,
                "company_zip": None,
                "company_address": None,
                "billing_street": None,
                "billing_city": None,
                "billing_state": None,
                "billing_zip": None,
                "tax_id_gst": None,
                "fein": None,
                "tax_classification": None,
                "state_of_incorporation": None,
                "backup_withholding_exempt": None,
                "is_1099_eligible": None,
                "products_services": None,
                "years_in_business": None,
                "annual_revenue_usd": None,
                "employee_count": None,
                "payment_terms": None,
                "conflict_of_interest": None,
                "references_count": None,
                "bank_name": None,
                "bank_routing_number": None,
                "bank_account_number": None,
                "bank_beneficiary_name": None,
                "swift_bic": None
            },
            "documents": []
        }
    }

    DOCUMENT_SCHEMA = {
        "type": None,
        "legal_name": None,
        "dba_name": None,
        "duns": None,
        "ein": None,
        "tax_classification": None,
        "state_of_incorporation": None,
        "backup_withholding_exempt": None,
        "is_1099_eligible": None,
        "insurance_limits": None,
        "bank_routing_number": None,
        "bank_account_number": None,
        "bank_name": None,
        "bank_beneficiary_name": None,
        "swift_bic": None
    }

    schema_example = json.dumps(EXTRACTION_SCHEMA, indent=2)

    # 4. Prepare LangChain messages with strict schema prompt
    print("[Agent] Preparing documents for LLM extraction...")

    prompt_text = f"""You are an expert vendor compliance analyst. Review ALL the following documents and the attached questionnaire JSON data.

Your task:
1. Extract key entities from the questionnaire and from EACH uploaded document.
2. Cross-validate the legal name between the questionnaire and all documents.

You MUST return ONLY a valid JSON object matching this EXACT schema. No markdown, no commentary, no extra fields.

REQUIRED OUTPUT SCHEMA:
{schema_example}

RULES:
- "vendor_name_cross_validation.questionnaire_legal_name": The legal name from the questionnaire JSON.
- "vendor_name_cross_validation.document_legal_names": A list of ALL legal names found across ALL uploaded documents.
- "vendor_name_cross_validation.match": true if questionnaire legal name matches any document legal name, false otherwise.
- "extracted_entities.questionnaire": Extract these fields from the questionnaire JSON data. Use null if not found.
- "extracted_entities.documents": An array with ONE entry per uploaded document. Each entry MUST have ALL these fields:
    - "type": The document type (e.g., "W-9 Form", "Certificate of Liability Insurance", "Bank Statement/Certification")
    - "legal_name": Legal name found in this specific document, or null
    - "dba_name": Doing Business As name if found, or null
    - "duns": DUNS number found in this document, or null
    - "ein": EIN/Tax ID/FEIN found in this document, or null
    - "tax_classification": US tax classification if found, or null
    - "state_of_incorporation": State of incorporation/organization if found, or null
    - "backup_withholding_exempt": Exempt from backup withholding status if found (true/false), or null
    - "is_1099_eligible": Eligible for 1099 reporting status if found (true/false), or null
    - "insurance_limits": An object with limit fields if this is an insurance document, or null
    - "bank_routing_number": Routing number found in this document, or null
    - "bank_account_number": Account number found in this document, or null
    - "bank_name": Bank name found in this document, or null
    - "bank_beneficiary_name": Bank beneficiary name / account holder name found in this document, or null
    - "swift_bic": SWIFT or BIC code found in this document, or null

IMPORTANT: Every field must be present in the output. Use null for fields that cannot be extracted. Do NOT omit any field. Do NOT add extra fields. Return ONLY the JSON object."""

    message_content = [
        {"type": "text", "text": prompt_text}
    ]
    
    if questionnaire_data:
        message_content.append({
            "type": "text",
            "text": f"Questionnaire Data: {json.dumps(questionnaire_data, indent=2)}"
        })
        
    for doc_file in doc_files:
        message_content.append({
            "type": "text",
            "text": f"--- Document: {doc_file.name} ---"
        })
        blocks = process_file_to_messages(doc_file)
        message_content.extend(blocks)
        
    # 5. Invoke LLM
    print("\n[Agent] Invoking LangChain model (gemini-2.5-flash)...")
    try:
        llm = ChatGoogleGenerativeAI(model=GEMINI_AGENT_MODEL, max_tokens=GEMINI_MAX_TOKENS)
        message = HumanMessage(content=message_content)
        
        response = llm.invoke([message])
        
        # Clean up potential markdown formatting
        clean_json_str = response.content.strip()
        if clean_json_str.startswith("```json"):
            clean_json_str = clean_json_str[7:]
        if clean_json_str.startswith("```"):
            clean_json_str = clean_json_str[3:]
        if clean_json_str.endswith("```"):
            clean_json_str = clean_json_str[:-3]
        clean_json_str = clean_json_str.strip()

        # Parse the LLM response
        try:
            raw_result = json.loads(clean_json_str)
        except json.JSONDecodeError:
            print("[Agent] Warning: LLM returned invalid JSON. Saving raw output.")
            raw_result = {}

        # Normalize the result to match the strict schema
        import copy
        result = copy.deepcopy(EXTRACTION_SCHEMA)

        # Merge vendor_name_cross_validation
        vnc = raw_result.get("vendor_name_cross_validation", {}) or {}
        result["vendor_name_cross_validation"]["questionnaire_legal_name"] = vnc.get("questionnaire_legal_name")
        result["vendor_name_cross_validation"]["document_legal_names"] = vnc.get("document_legal_names", []) or []
        result["vendor_name_cross_validation"]["match"] = vnc.get("match")

        # Merge extracted_entities.questionnaire
        raw_q = (raw_result.get("extracted_entities", {}) or {}).get("questionnaire", {}) or {}
        for key in EXTRACTION_SCHEMA["extracted_entities"]["questionnaire"]:
            result["extracted_entities"]["questionnaire"][key] = raw_q.get(key)

        # Merge extracted_entities.documents
        raw_docs = (raw_result.get("extracted_entities", {}) or {}).get("documents", []) or []
        normalized_docs = []
        for doc in raw_docs:
            norm_doc = copy.deepcopy(DOCUMENT_SCHEMA)
            for key in DOCUMENT_SCHEMA:
                if key in doc:
                    norm_doc[key] = doc[key]
            normalized_docs.append(norm_doc)
        result["extracted_entities"]["documents"] = normalized_docs

        # Pretty-print for console
        final_json = json.dumps(result, indent=2, ensure_ascii=False)
        print("\n" + "="*50)
        print("EXTRACTION RESULTS")
        print("="*50)
        print(final_json)
        print("="*50 + "\n")
        
        # Save results
        results_path = upload_dir / "extraction_results.json"
        with open(results_path, 'w', encoding='utf-8') as f:
            f.write(final_json)
            
    except Exception as e:
        print(f"\n[Error] LLM Extraction failed: {e}")
        print("Hint: Make sure your GEMINI_API_KEY is correct in your .env file.")
    
    print("[Agent] Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LangChain Extractor Agent")
    parser.add_argument("vendor_id", type=str, help="The Vendor ID (e.g., VND-2026-00004)")
    args = parser.parse_args()
    
    run_extraction_agent(args.vendor_id)
