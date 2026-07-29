import os
import re
import csv
import difflib
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any

# Load settings from environment
COI_MIN_LIABILITY_USD = float(os.getenv("COI_MIN_LIABILITY_USD", "1000000"))
COI_EXPIRY_WARNING_DAYS = int(os.getenv("COI_EXPIRY_WARNING_DAYS", "30"))

def get_system_date() -> date:
    sys_date_str = os.getenv("SYSTEM_DATE")
    if sys_date_str:
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(sys_date_str.strip(), fmt).date()
            except ValueError:
                continue
    return date.today()

def clean_string(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = " ".join(s.split())
    # remove common corporate suffix terms
    for suffix in ["llc", "corp", "inc", "co", "ltd", "limited", "corporation", "company", "ventures"]:
        s = re.sub(rf"\b{suffix}\b", "", s)
    return " ".join(s.split())

def string_similarity(s1: str, s2: str) -> float:
    c1 = clean_string(s1)
    c2 = clean_string(s2)
    if not c1 or not c2:
        return 0.0
    return difflib.SequenceMatcher(None, c1, c2).ratio() * 100

def extract_domain(email_or_url: str) -> str:
    if not email_or_url:
        return ""
    email_or_url = email_or_url.strip().lower()
    if "@" in email_or_url:
        parts = email_or_url.split("@")
        if len(parts) > 1:
            domain = parts[1]
    else:
        domain = email_or_url.replace("http://", "").replace("https://", "").replace("www.", "")
        domain = domain.split("/")[0]
    return domain.strip()

GENERIC_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "mail.com", "zoho.com", "protonmail.com"}

US_STATES = {
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

def parse_date(date_str: str) -> Any:
    if not date_str:
        return None
    val_str = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(val_str.split("T")[0], fmt).date()
        except ValueError:
            continue
    return None

def evaluate_compliance_rules(doc_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Evaluates extracted vendor fields against the 10 Consistency & Compliance Rules defined in CSV.
    """
    rules_csv_path = Path(__file__).parent.parent / "config" / "compliance_rules.csv"
    if not rules_csv_path.exists():
        return []

    evaluated_rules = []
    system_date = get_system_date()

    with open(rules_csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rule_id = row["rule_id"]
            title = row["rule_title"]
            rule_type = row["rule_type"]
            doc1 = row["doc_type_1"]
            field1 = row["field_1"]
            doc2 = row["doc_type_2"]
            field2 = row["field_2"]
            comparison = row["comparison_type"]
            threshold_raw = row["threshold"]
            description = row["description"]

            # Initialize outputs (enforce binary pass/fail - no skipping allowed)
            status = "Failed"
            details = "Deficiency: Required document missing or field not extracted."
            values = {}
            passed = False

            # 1. Fuzzy match rules (Rule 1, Rule 2, Rule 7)
            if rule_type == "cross_doc" and comparison == "fuzzy_match":
                v1 = doc_results.get(doc1, {}).get(field1)
                v2 = doc_results.get(doc2, {}).get(field2)
                if v1 is not None and v2 is not None:
                    values = {doc1: v1, doc2: v2}
                    sim = string_similarity(str(v1), str(v2))
                    threshold = float(threshold_raw) if threshold_raw else 70.0
                    passed = sim >= threshold
                    status = "Passed" if passed else "Failed"
                    details = f"Similarity: {sim:.1f}% (Required: >= {threshold}%)"

            # 2. COI Expiry date check (Rule 3)
            elif rule_type == "date_check" and comparison == "not_expired":
                v1 = doc_results.get(doc1, {}).get(field1)
                if v1 is not None:
                    values = {doc1: v1}
                    d1 = parse_date(str(v1))
                    if d1:
                        passed = d1 >= system_date
                        status = "Passed" if passed else "Failed"
                        details = f"Policy Expiry: {d1.strftime('%Y-%m-%d')} (System Date: {system_date.strftime('%Y-%m-%d')})"
                    else:
                        status = "Error"
                        details = f"Could not parse expiry date: '{v1}'"
                        passed = False

            # 3. Liability minimum limit check (Rule 4)
            elif rule_type == "value_check" and comparison == "min":
                v1 = doc_results.get(doc1, {}).get(field1)
                if v1 is not None:
                    values = {doc1: v1}
                    try:
                        num_str = re.sub(r"[^\d.]", "", str(v1))
                        num_val = float(num_str) if num_str else 0.0
                        threshold = float(threshold_raw) if threshold_raw else COI_MIN_LIABILITY_USD
                        passed = num_val >= threshold
                        status = "Passed" if passed else "Failed"
                        details = f"Liability: ${num_val:,.2f} (Required: >= ${threshold:,.2f})"
                    except ValueError:
                        status = "Error"
                        details = f"Could not validate limit value: '{v1}'"
                        passed = False

            # 4. Coverage check (Rule 5 / Rule 10)
            elif rule_type == "field_present" and comparison == "is_true":
                v1 = doc_results.get(doc1, {}).get(field1)
                if v1 is not None:
                    values = {doc1: v1}
                    passed = str(v1).lower() in ("true", "1", "yes", "y")
                    status = "Passed" if passed else "Failed"
                    if "cyber" in field1.lower():
                        details = f"Cyber Insurance Coverage: {'Present' if passed else 'Missing'}"
                    elif "signature" in field1.lower():
                        details = f"Signature Present: {'Yes' if passed else 'No'}"
                    else:
                        details = f"Field check for '{field1}': {'Present' if passed else 'Missing'}"

            # 5. Expiry warning (Rule 6)
            elif rule_type == "date_warning" and comparison == "expiry_warning":
                v1 = doc_results.get(doc1, {}).get(field1)
                if v1 is not None:
                    values = {doc1: v1}
                    d1 = parse_date(str(v1))
                    if d1:
                        days_left = (d1 - system_date).days
                        warning_days = int(threshold_raw) if threshold_raw else COI_EXPIRY_WARNING_DAYS
                        passed = days_left > warning_days
                        status = "Passed" if passed else "Warning"
                        details = f"Policy expires in {days_left} days (Warning threshold: < {warning_days} days)"
                    else:
                        status = "Error"
                        details = f"Could not parse date: '{v1}'"
                        passed = False

            # 6. Domain alignment (Rule 8)
            elif rule_type == "domain_match" and comparison == "domain_match":
                v1 = doc_results.get(doc1, {}).get(field1)
                v2 = doc_results.get(doc2, {}).get(field2)
                if v1 is not None and v2 is not None:
                    values = {f"{doc1} ({field1})": v1, f"{doc2} ({field2})": v2}
                    dom1 = extract_domain(str(v1))
                    dom2 = extract_domain(str(v2))
                    if not dom1 or not dom2:
                        status = "Failed"
                        details = "Could not resolve domains from inputs."
                        passed = False
                    elif dom1 in GENERIC_DOMAINS:
                        status = "Passed"
                        details = f"Generic email domain '{dom1}' ignored from mismatch checks."
                        passed = True
                    else:
                        passed = dom1 == dom2
                        status = "Passed" if passed else "Failed"
                        details = f"Email Domain: '{dom1}' | Website Domain: '{dom2}'"

            # 7. Exact identifier cross checks (Rule 9)
            elif rule_type == "cross_doc" and comparison == "exact_match":
                v1 = doc_results.get(doc1, {}).get(field1)
                v2 = doc_results.get(doc2, {}).get(field2)
                if v1 is not None and v2 is not None:
                    values = {doc1: v1, doc2: v2}
                    digits1 = re.sub(r"\D", "", str(v1))
                    digits2 = re.sub(r"\D", "", str(v2))
                    passed = digits1 == digits2 if (digits1 and digits2) else (str(v1).strip() == str(v2).strip())
                    status = "Passed" if passed else "Failed"
                    details = f"Agreement: '{v1}' vs '{v2}'"

            # 8. State matches (Rule 9: Smart Fallback supported)
            elif rule_type == "cross_doc" and comparison == "state_match":
                v1 = doc_results.get(doc1, {}).get(field1)
                v2 = doc_results.get(doc2, {}).get(field2)

                used_fallback = False
                fallback_source = ""

                # Smart Address-State Fallback if primary state field is empty/null
                if (v1 is None or str(v1).strip() == "") and doc1 in doc_results:
                    doc1_fields = doc_results[doc1]
                    state_candidate = doc1_fields.get("state") or doc1_fields.get("address_state")
                    if state_candidate and str(state_candidate).strip() != "":
                        v1 = state_candidate
                        used_fallback = True
                        fallback_source = f"{doc1} address state"
                    else:
                        addr = str(doc1_fields.get("address_line1") or doc1_fields.get("registered_address") or "")
                        match = re.search(r"\b([A-Z]{2})\b(?:\s+\d{5})?", addr)
                        if match:
                            v1 = match.group(1)
                            used_fallback = True
                            fallback_source = f"{doc1} address string"

                if v1 is not None and v2 is not None and str(v1).strip() != "" and str(v2).strip() != "":
                    values = {doc1: v1, doc2: v2}
                    clean1 = clean_string(str(v1))
                    clean2 = clean_string(str(v2))

                    norm1 = US_STATES.get(str(v1).strip().upper(), str(v1).strip())
                    norm2 = US_STATES.get(str(v2).strip().upper(), str(v2).strip())
                    clean_norm1 = clean_string(norm1)
                    clean_norm2 = clean_string(norm2)

                    passed = (
                        (clean1 in clean2) or (clean2 in clean1) or
                        (clean_norm1 in clean_norm2) or (clean_norm2 in clean_norm1) or
                        (string_similarity(norm1, norm2) >= 60.0)
                    )
                    status = "Passed" if passed else "Failed"
                    if used_fallback:
                        details = f"Agreement: '{v1}' (Smart fallback from {fallback_source}) matches '{v2}'"
                    else:
                        details = f"Agreement: '{v1}' vs '{v2}'"

            evaluated_rules.append({
                "rule_id": rule_id,
                "rule_title": title,
                "status": status,
                "passed": passed,
                "values": values,
                "details": details,
                "description": description
            })

    return evaluated_rules
