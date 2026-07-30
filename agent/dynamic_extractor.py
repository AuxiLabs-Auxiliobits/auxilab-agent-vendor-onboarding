import os
import json
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import re
# LangChain imports
from langchain_core.messages import HumanMessage

def _encode_bytes(data: bytes) -> str:
    """Encode binary bytes to base64 string."""
    return base64.b64encode(data).decode("utf-8")

def _extract_text_from_pdf(file_path: Path) -> str:
    """Tries to extract text from PDF using PyMuPDF (fitz) or pypdf."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        text = "\n".join([page.get_text() for page in doc])
        if text.strip():
            return text
    except Exception:
        pass

    try:
        import pypdf
        reader = pypdf.PdfReader(file_path)
        text = "\n".join([page.extract_text() for page in reader.pages])
        if text.strip():
            return text
    except Exception:
        pass

    return ""


def _file_to_content_blocks(file_path: Path, text_only: bool = False) -> List[Dict]:
    """
    Convert document pages or text files into list of human message content blocks.
    For PDF, tries to render pages as images (vision path).
    If text_only is True, falls back immediately to raw text extraction.
    """
    blocks = []
    suffix = file_path.suffix.lower()

    if text_only:
        # Standard text-only fallback path (zero PDF rendering)
        if suffix == ".pdf":
            text = _extract_text_from_pdf(file_path)
            if text:
                blocks.append({"type": "text", "text": f"Document text content:\n{text}"})
        elif suffix == ".txt":
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                blocks.append({"type": "text", "text": f"Document text content:\n{text}"})
            except Exception:
                pass
        return blocks

    # Vision-based multimodal path
    if suffix == ".pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            for page in doc:
                # Render page at 150 DPI for legibility and efficiency
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                blocks.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{_encode_bytes(img_bytes)}"}
                })
        except Exception as e:
            # If rendering fails (e.g. fitz not installed or error), try text extraction
            text = _extract_text_from_pdf(file_path)
            if text:
                blocks.append({"type": "text", "text": f"Document text content (fallback from render failure):\n{text}"})

    elif suffix in (".png", ".jpg", ".jpeg"):
        try:
            with open(file_path, "rb") as f:
                blocks.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{_encode_bytes(f.read())}"}
                })
        except Exception:
            pass

    elif suffix == ".txt":
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            blocks.append({"type": "text", "text": f"Document text content:\n{text}"})
        except Exception:
            pass

    return blocks


def _get_token_usage(response) -> tuple:
    """Safely extract input and output token counts from LangChain response metadata."""
    # 1. Standard usage_metadata
    usage = getattr(response, "usage_metadata", None)
    if usage:
        return usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        
    # 2. Alternative response_metadata structures
    metadata = getattr(response, "response_metadata", {})
    if "token_usage" in metadata:
        tu = metadata["token_usage"]
        inp = tu.get("input_tokens") or tu.get("prompt_tokens") or 0
        out = tu.get("output_tokens") or tu.get("completion_tokens") or 0
        return inp, out
    elif "usage" in metadata:
        u = metadata["usage"]
        inp = u.get("input_tokens") or u.get("prompt_tokens") or 0
        out = u.get("output_tokens") or u.get("completion_tokens") or 0
        return inp, out
        
    return 0, 0


def _parse_json_from_llm(raw: str) -> Any:
    """Robustly extract and parse JSON from a raw LLM response string."""
    raw = raw.strip()
    
    # Try parsing directly first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try removing markdown fences
    clean_raw = raw
    if clean_raw.startswith("```json"):
        clean_raw = clean_raw[7:]
    elif clean_raw.startswith("```"):
        clean_raw = clean_raw[3:]
    if clean_raw.endswith("```"):
        clean_raw = clean_raw[:-3]
    clean_raw = clean_raw.strip()

    try:
        return json.loads(clean_raw)
    except json.JSONDecodeError:
        pass

    # Try extracting the JSON block using bracket matching
    first_dict = clean_raw.find('{')
    first_array = clean_raw.find('[')
    
    start_idx = -1
    end_char = ''
    if first_dict != -1 and (first_array == -1 or first_dict < first_array):
        start_idx = first_dict
        end_char = '}'
    elif first_array != -1:
        start_idx = first_array
        end_char = ']'
        
    if start_idx != -1:
        end_idx = clean_raw.rfind(end_char)
        if end_idx != -1 and end_idx > start_idx:
            json_candidate = clean_raw[start_idx:end_idx + 1]
            try:
                return json.loads(json_candidate)
            except json.JSONDecodeError:
                pass
                
    # If all parsing attempts fail, raise a JSONDecodeError
    return json.loads(raw)


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_single_doc_prompt(document_type: str, fields: List[Dict], validation_rules: Dict) -> str:
    """Build the extraction prompt for a single document type."""

    field_lines = []
    for f in fields:
        rule_hint = ""
        if f["name"] in validation_rules:
            rule_hint = f" [Validation: {validation_rules[f['name']]}]"
        field_lines.append(f'  - "{f["name"]}": {f["description"]}{rule_hint}')

    fields_block = "\n".join(field_lines)

    return f"""You are a specialized compliance extraction agent. Analyze the attached document and extract the values for the following fields:

DOCUMENT TYPE: {document_type}

FIELDS TO EXTRACT:
{fields_block}

RULES:
1. Extract values exactly as they appear in the document (e.g. clean dates, identifiers, numbers).
2. If a field is not present or cannot be determined, output null for that field.
3. Validate format parameters if marked in brackets.
4. Output your response as a raw JSON object. Do not include markdown formatting or explanations.

OUTPUT FORMAT:
{{
  "field_name_1": "extracted_value_1",
  "field_name_2": null
}}
"""

def _build_cross_validation_prompt(country: str, doc_results: Dict[str, Dict], schema: Dict) -> Optional[str]:
    """Build cross-validation prompt if multiple documents are present."""
    lines = []
    for doc_type, data in doc_results.items():
        if "parse_error" in data or "llm_error" in data:
            continue
        # Strip internal tracking keys
        clean_data = {k: v for k, v in data.items() if not k.startswith("_")}
        lines.append(f"Document: {doc_type}\nExtracted Fields:\n{json.dumps(clean_data, indent=2)}")

    if not lines:
        return None

    docs_payload = "\n\n".join(lines)

    return f"""You are a compliance agent reviewing consistency across documents for a vendor onboarding in country: {country}.

Review the extracted values below for inconsistencies (e.g., mismatching legal names, tax IDs, routing numbers, addresses):

{docs_payload}

Identify key inconsistencies between documents. For each discrepancy, output a JSON item matching the format below.
If there are no inconsistencies, output an empty list [].

OUTPUT FORMAT:
[
  {{
    "field_name": "company_name",
    "consistent": false,
    "details": "Name on W-9 is 'Alpha LLC' but COI lists 'Beta LLC'"
  }}
]
"""

# ─────────────────────────────────────────────────────────────────────────────
# Core Extraction Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def _run_field_validation(field_name: str, value, rule_expr: str) -> Optional[str]:
    """
    Apply a validation rule to an extracted value.
    Returns None if valid, or a string description of the error if invalid.
    """
    if value is None or value == "":
        return None  # Completeness is tracked separately

    rule_type, _, rule_val = rule_expr.partition("=")
    rule_type = rule_type.strip()

    if rule_type == "format":
        pattern = rule_val.strip()
        try:
            if not re.match(f"^{pattern}$", str(value)):
                return f"Value '{value}' does not match format pattern '{pattern}'"
        except re.error:
            pass

    elif rule_type == "digits":
        expected_len = int(rule_val.strip())
        digits = re.sub(r"\D", "", str(value))
        if len(digits) != expected_len:
            return f"Expected {expected_len} digits, but got {len(digits)} in '{value}'"

    elif rule_type == "min":
        try:
            min_val = float(rule_val.strip())
            # strip symbols and commas
            clean_val = float(re.sub(r"[^\d.]", "", str(value)))
            if clean_val < min_val:
                return f"Value {clean_val} is less than minimum limit: {min_val}"
        except ValueError:
            return f"Invalid numeric representation: '{value}'"

    elif rule_type == "not_expired":
        # Handled by the consistency compliance rules (10-rule verification)
        pass

    return None


def run_dynamic_extraction(
    country: str,
    schema: Dict,
    documents: List[Tuple[str, Path]],
    progress_callback=None,
    text_only: bool = False
) -> Dict:
    """
    Iterate over documents, send extraction messages to Gemini or Claude,
    calculate completeness, and run field format validation.

    Parameters
    ----------
    country : str
        Target region profile.
    schema : Dict
        Keys are document_type strings; values contain "fields" and "validation_rules".
    documents : List[Tuple[document_type, Path]]
        Uploaded file paths.
    progress_callback : callable, optional
        Called with a string message as each step completes.
    text_only : bool, optional
        If True, runs text-only document extraction without vision features.

    Returns
    -------
    Dict with keys:
      - "country": str
      - "documents": Dict[document_type → extraction result dict]
      - "cross_validation": List of cross-validation results
      - "completeness": Dict[document_type → {score, missing_fields}]
      - "validation_errors": Dict[document_type → Dict[field_name → error_msg]]
      - "missing_required_docs": List[str]
      - "overall_completeness_pct": float
    """
    from typing import Optional
    
    if text_only is None:
        text_only = os.getenv("TEXT_ONLY_FALLBACK", "false").lower() == "true"

    llm_provider = os.getenv("LLM_PROVIDER", "google").lower()
    
    if llm_provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError(
                "Anthropic LLM provider selected but 'langchain-anthropic' is not installed. "
                "Please run: pip install langchain-anthropic"
            )
        model_name = os.getenv("ANTHROPIC_MODEL", os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022"))
        max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096"))
        api_key = os.getenv("ANTHROPIC_API_KEY")
        llm = ChatAnthropic(model=model_name, max_tokens=max_tokens, api_key=api_key)
    elif llm_provider == "groq":
        try:
            from langchain_groq import ChatGroq
        except ImportError:
            raise ImportError(
                "Groq LLM provider selected but 'langchain-groq' is not installed. "
                "Please run: pip install langchain-groq"
            )
        model_name = os.getenv("GROQ_MODEL", os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"))
        max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "4096"))
        api_key = os.getenv("GROQ_API_KEY")
        if "vision" not in model_name.lower():
            text_only = True
        llm = ChatGroq(model=model_name, max_tokens=max_tokens, groq_api_key=api_key)
    else:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError(
                "Google Gemini LLM provider selected but 'langchain-google-genai' is not installed. "
                "Please run: pip install langchain-google-genai"
            )
        model_name = os.getenv("GEMINI_AGENT_MODEL", os.getenv("LLM_MODEL", "gemini-2.5-flash"))
        max_tokens = int(os.getenv("GEMINI_MAX_TOKENS", "8192"))
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        llm = ChatGoogleGenerativeAI(model=model_name, max_tokens=max_tokens, google_api_key=api_key)

    doc_results: Dict[str, Dict] = {}
    completeness: Dict[str, Dict] = {}
    validation_errors: Dict[str, Dict] = {}
    total_input_tokens = 0
    total_output_tokens = 0

    # Track which required docs were uploaded
    uploaded_doc_types = {doc_type for doc_type, _ in documents}
    missing_required = [
        doc_type
        for doc_type, cfg in schema.items()
        if cfg["required"] and doc_type not in uploaded_doc_types
    ]

    # ── Per-document extraction ───────────────────────────────────────────────
    for doc_type, file_path in documents:
        if doc_type not in schema:
            # Unknown doc type — do a generic extraction
            doc_schema_cfg = {
                "fields": [{"name": "extracted_text", "description": "Full text content of the document"}],
                "validation_rules": {}
            }
        else:
            doc_schema_cfg = schema[doc_type]

        if progress_callback:
            progress_callback(f"Extracting fields from: {doc_type} ({file_path.name})...")

        prompt_text = _build_single_doc_prompt(
            doc_type,
            doc_schema_cfg["fields"],
            doc_schema_cfg["validation_rules"]
        )

        content_blocks = [{"type": "text", "text": prompt_text}]
        content_blocks += _file_to_content_blocks(file_path, text_only=text_only)


        try:
            message = HumanMessage(content=content_blocks)
            response = llm.invoke([message])
            inp_tok, out_tok = _get_token_usage(response)
            total_input_tokens += inp_tok
            total_output_tokens += out_tok

            raw = response.content.strip()
            try:
                extracted = _parse_json_from_llm(raw)
            except json.JSONDecodeError:
                extracted = {"parse_error": True, "raw_response": raw[:500]}

        except Exception as e:
            extracted = {"llm_error": str(e)}

        # Print the extracted JSON of each document immediately to standard output
        print(f"\n  [Pipeline] Extracted JSON for {doc_type} ({file_path.name}):")
        clean_print_dict = {k: v for k, v in extracted.items() if not k.startswith("_")}
        print(json.dumps(clean_print_dict, indent=2, ensure_ascii=False))
        print("  ---------------------------------------------------\n")

        # Enrich with metadata
        extracted["_doc_type"] = doc_type
        extracted["_file_name"] = file_path.name
        doc_results[doc_type] = extracted

        # ── Completeness scoring ──────────────────────────────────────────────
        expected_fields = [f["name"] for f in doc_schema_cfg["fields"]]
        present_fields = [
            fn for fn in expected_fields
            if extracted.get(fn) is not None and extracted.get(fn) != ""
        ]
        missing_fields = [fn for fn in expected_fields if fn not in present_fields]
        score = (len(present_fields) / len(expected_fields) * 100) if expected_fields else 0.0

        completeness[doc_type] = {
            "score": round(score, 1),
            "total_fields": len(expected_fields),
            "present_fields": len(present_fields),
            "missing_fields": missing_fields,
        }

        # ── Field-level validation ────────────────────────────────────────────
        doc_errors = {}
        for field_name, rule_expr in doc_schema_cfg["validation_rules"].items():
            val = extracted.get(field_name)
            err = _run_field_validation(field_name, val, rule_expr)
            if err:
                doc_errors[field_name] = err

        if doc_errors:
            validation_errors[doc_type] = doc_errors

    # ── Cross-document validation ─────────────────────────────────────────────
    cross_validation = []
    if len(doc_results) > 1:
        if progress_callback:
            progress_callback("Running cross-document consistency checks...")

        cross_prompt = _build_cross_validation_prompt(country, doc_results, schema)
        if cross_prompt:
            try:
                message = HumanMessage(content=[{"type": "text", "text": cross_prompt}])
                response = llm.invoke([message])
                inp_tok, out_tok = _get_token_usage(response)
                total_input_tokens += inp_tok
                total_output_tokens += out_tok
                raw = response.content.strip()
                cross_validation = _parse_json_from_llm(raw)
            except Exception as e:
                cross_validation = [{"error": f"Cross-validation failed: {str(e)}"}]

    # ── Overall completeness ──────────────────────────────────────────────────
    if completeness:
        overall_pct = sum(v["score"] for v in completeness.values()) / len(completeness)
    else:
        overall_pct = 0.0

    if progress_callback:
        progress_callback("Extraction complete.")

    return {
        "country": country,
        "documents": doc_results,
        "cross_validation": cross_validation,
        "completeness": completeness,
        "validation_errors": validation_errors,
        "missing_required_docs": missing_required,
        "overall_completeness_pct": round(overall_pct, 1),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
