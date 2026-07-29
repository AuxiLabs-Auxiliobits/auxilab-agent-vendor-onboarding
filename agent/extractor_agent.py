"""
extractor_agent.py
==================
Command-line agent entry-point for the vendor document compliance onboarding.

Usage:
    python agent/extractor_agent.py <input_source> <country> [--text-only]
    
    input_source: Either a vendor directory ID (e.g. VND-2026-00012) OR a path to a .txt file containing document file paths.
"""

import os
import sys
import json
import argparse
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print("[Error] Missing 'python-dotenv'. Run: pip install python-dotenv")
    sys.exit(1)

# Load environment variables from project root .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path so we can import utils
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agent.config_loader import build_extraction_schema
from agent.pipeline import run_compliance_pipeline

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt"}

def discover_documents(upload_dir: Path, country: str) -> list:
    """
    Discover uploaded documents in the vendor's upload directory.
    Checks for a 'document_manifest.json' file first.
    Falls back to filename-based hinting for manually placed files.
    """
    manifest_path = upload_dir / "document_manifest.json"
    
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            pairs = []
            for entry in manifest.get("documents", []):
                doc_type = entry.get("document_type", "Unknown Document")
                file_name = entry.get("file_name", "")
                file_path = upload_dir / file_name
                if file_path.exists() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    pairs.append((doc_type, file_path))
            if pairs:
                return pairs
        except Exception as e:
            print(f"[Agent] Warning: Could not read manifest ({e}). Falling back to filename hinting.")

    # Fallback to filename keyword mapping
    from agent.config_loader import get_config_for_country
    doc_configs = get_config_for_country(country)
    configured_types = [c["document_type"] for c in doc_configs]

    KEYWORD_MAP = {
        "w9": "W-9 Tax Form",
        "w-9": "W-9 Tax Form",
        "coi": "Certificate of Insurance",
        "insurance": "Certificate of Insurance",
        "bank": "Bank Verification Letter",
        "bank_letter": "Bank Verification Letter",
        "questionnaire": "Questionnaire",
        "company_reg": "Company Registration",
        "registration": "Company Registration",
        "gst": "GST Registration Certificate",
        "pan": "PAN Card",
        "trade_license": "Trade License",
        "trn": "TRN Certificate",
        "acra": "ACRA Business Profile",
        "vat": "VAT Registration Certificate",
        "incorporation": "Certificate of Incorporation",
        "w-8ben": "W-8BEN-E Form",
        "w8ben": "W-8BEN-E Form"
    }

    files = [
        f for f in upload_dir.glob("*")
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        and f.name not in ("document_manifest.json", "extraction_results.json", "compliance_report.json")
    ]

    pairs = []
    unmapped = []
    for f in files:
        name_lower = f.stem.lower().replace("-", "_").replace(" ", "_")
        matched = False
        for kw, dt in KEYWORD_MAP.items():
            if kw in name_lower and dt in configured_types:
                pairs.append((dt, f))
                matched = True
                break
        if not matched:
            for ct in configured_types:
                if ct.lower().replace("-","").replace(" ","") in name_lower.replace("_",""):
                    pairs.append((ct, f))
                    matched = True
                    break
        if not matched:
            unmapped.append(f)

    # Distribute remaining unmapped files
    mapped_types = [p[0] for p in pairs]
    remaining_reqs = [ct for ct in configured_types if ct not in mapped_types]
    for uf in unmapped:
        if remaining_reqs:
            pairs.append((remaining_reqs.pop(0), uf))
        elif configured_types:
            pairs.append((configured_types[0], uf))
        else:
            pairs.append(("Unknown Document", uf))

    return pairs

def run_cli_agent(input_source: str, country: str, text_only: bool = False):
    print(f"\n[Agent] ===================================================")
    print(f"[Agent] Compliance Verification Agent | Source: {input_source} | Country: {country}")
    print(f"[Agent] ===================================================\n")

    base_dir = Path(__file__).parent.parent
    
    # Check if input_source is a text file containing file paths
    is_txt_file = input_source.lower().endswith(".txt") and os.path.isfile(input_source)

    if is_txt_file:
        print(f"[Agent] Reading document paths from text file: {input_source}")
        with open(input_source, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        
        file_paths = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = Path(line)
            # Resolve relative paths against workspace root if not absolute
            if not p.exists() and not p.is_absolute():
                p = base_dir / p
            if p.exists() and p.is_file():
                file_paths.append(p)
            else:
                print(f"[Agent] Warning: File path from list does not exist: {line}")
                
        if not file_paths:
            print(f"[Agent] ERROR: No valid document file paths found in {input_source}")
            sys.exit(1)
            
        # Map/discover document types for files
        from agent.config_loader import get_config_for_country
        doc_configs = get_config_for_country(country)
        configured_types = [c["document_type"] for c in doc_configs]

        KEYWORD_MAP = {
            "w9": "W-9 Tax Form",
            "w-9": "W-9 Tax Form",
            "coi": "Certificate of Insurance",
            "insurance": "Certificate of Insurance",
            "bank": "Bank Verification Letter",
            "bank_letter": "Bank Verification Letter",
            "questionnaire": "Questionnaire",
            "company_reg": "Company Registration",
            "registration": "Company Registration",
            "gst": "GST Registration Certificate",
            "pan": "PAN Card",
            "trade_license": "Trade License",
            "trn": "TRN Certificate",
            "acra": "ACRA Business Profile",
            "vat": "VAT Registration Certificate",
            "incorporation": "Certificate of Incorporation",
            "w-8ben": "W-8BEN-E Form",
            "w8ben": "W-8BEN-E Form"
        }

        documents = []
        unmapped = []
        for f in file_paths:
            name_lower = f.stem.lower().replace("-", "_").replace(" ", "_")
            matched = False
            for kw, dt in KEYWORD_MAP.items():
                if kw in name_lower and dt in configured_types:
                    documents.append((dt, f))
                    matched = True
                    break
            if not matched:
                for ct in configured_types:
                    if ct.lower().replace("-","").replace(" ","") in name_lower.replace("_",""):
                        documents.append((ct, f))
                        matched = True
                        break
            if not matched:
                unmapped.append(f)

        # Distribute remaining unmapped files
        mapped_types = [d[0] for d in documents]
        remaining = [ct for ct in configured_types if ct not in mapped_types]
        for f in unmapped:
            if remaining:
                documents.append((remaining.pop(0), f))
            elif configured_types:
                documents.append((configured_types[0], f))
            else:
                documents.append(("Unknown Document", f))
                
        report_output_path = Path(input_source).parent / "compliance_report.json"
    else:
        # Standard directory mapping
        upload_dir = base_dir / "uploads" / input_source

        if not upload_dir.exists():
            print(f"[Agent] ERROR: Vendor upload directory not found: {upload_dir}")
            sys.exit(1)

        documents = discover_documents(upload_dir, country)
        if not documents:
            print("[Agent] ERROR: No documents found in vendor folder.")
            sys.exit(1)
            
        report_output_path = upload_dir / "compliance_report.json"

    print(f"[Agent] Loaded {len(documents)} document(s) for verification:")
    for doc_type, file_path in documents:
        print(f"  - {file_path.name} mapped as '{doc_type}'")

    # 2. Run compliance pipeline
    print("\n[Agent] Processing compliance analysis pipeline...")
    
    def progress_cb(msg: str):
        print(f"  [Pipeline] {msg}")

    try:
        report = run_compliance_pipeline(
            country=country,
            documents=documents,
            text_only=text_only,
            progress_callback=progress_cb
        )
    except Exception as e:
        print(f"[Agent] ERROR during pipeline execution: {e}")
        sys.exit(1)

    # 3. Save report output
    with open(report_output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    print(f"\n[Agent] Detailed compliance report saved to: {report_output_path}")

    # 4. Console output summary
    rec = report["summary"]["recommendation"]
    reason = report["summary"]["recommendation_reason"]
    completeness = report["summary"]["overall_completeness_pct"]

    print(f"\n[Agent] ===================================================")
    print(f"[Agent] COMPLIANCE VERIFICATION DECISION")
    print(f"[Agent] ---------------------------------------------------")
    print(f"[Agent] Overall Recommendation : {rec.upper()}")
    print(f"[Agent] Risk Rating            : {report['summary'].get('risk_level', 'LOW RISK')}")
    print(f"[Agent] Vendor Risk Score      : {report['summary'].get('vendor_risk_score', 0)} / 100")
    print(f"[Agent] Weighted Compliance    : {report['summary'].get('vendor_compliance_score', 100)}%")
    print(f"[Agent] Decision Reason        : {reason}")
    print(f"[Agent] Overall Completeness   : {completeness:.1f}%")
    print(f"[Agent] Total Input Tokens     : {report['summary'].get('total_input_tokens', 0)}")
    print(f"[Agent] Total Output Tokens    : {report['summary'].get('total_output_tokens', 0)}")
    
    missing_docs = report.get("missing_required_docs", [])
    if missing_docs:
        print(f"[Agent] Missing Required Docs  : {', '.join(missing_docs)}")

    val_errors = report.get("all_validation_errors", {})
    if val_errors:
        total_errors = sum(len(e) for e in val_errors.values())
        print(f"[Agent] Validation Failures    : {total_errors} fields failed")
        for doc, errs in val_errors.items():
            for f, msg in errs.items():
                print(f"    - {doc} -> {f}: {msg}")

    cross_val = report.get("cross_validation", [])
    inconsistent = [c for c in cross_val if isinstance(c, dict) and not c.get("consistent", True)]
    if inconsistent:
        print(f"[Agent] Cross-Doc Mismatches   : {len(inconsistent)} conflicts")
        for c in inconsistent:
            print(f"    - {c.get('field_name')}: {c.get('details')}")

    print(f"[Agent] ===================================================\n")

    # 5. Output complete JSON details to console as requested
    # print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Standalone Compliance Verification Agent")
    parser.add_argument("input_source", type=str, help="Either a vendor reference ID or a path to a .txt file containing document file paths")
    parser.add_argument("country", type=str, help="Target country compliance profile (e.g., USA, India)")
    parser.add_argument("--text-only", action="store_true", help="Enable text-only fallback (no vision model used)")
    args = parser.parse_args()

    report = run_cli_agent(args.input_source, args.country, text_only=args.text_only)

    print("--- BEGIN COMPLIANCE JSON REPORT ---")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("--- END COMPLIANCE JSON REPORT ---\n")
