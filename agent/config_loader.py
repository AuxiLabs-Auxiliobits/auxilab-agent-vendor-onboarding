"""
config_loader.py
================
Reads and parses config/onboarding_config.csv and serves structured
configuration to the rest of the pipeline.

CSV columns:
    country              - Country/region name (e.g. USA, India, UK)
    document_type        - Human-readable document label
    required             - 'yes' or 'no'
    fields_to_extract    - Pipe-separated list of field names
    field_descriptions   - Pipe-separated list of field descriptions (must match fields_to_extract count)
    validation_rules     - Optional pipe-separated rules (e.g. ein:format=\\d{2}-\\d{7})
"""

import csv
import os
from pathlib import Path
from typing import Dict, List, Optional

# Default path — resolves relative to the project root
_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "onboarding_config.csv"


def load_config(config_path: Optional[str] = None) -> List[Dict]:
    """
    Load and parse onboarding_config.csv.

    Returns a list of document config dicts, each containing:
      - country: str
      - document_type: str
      - required: bool
      - fields: List[Dict] with keys: name, description
      - validation_rules: Dict[str, str]  e.g. {"ein": "format=\\d{2}-\\d{7}"}
      - raw_fields_str: str (original pipe-separated string, for reference)
    """
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH

    if not path.exists():
        raise FileNotFoundError(
            f"onboarding_config.csv not found at: {path}\n"
            "Please create the file at config/onboarding_config.csv"
        )

    configs = []
    errors = []

    with open(path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for line_num, row in enumerate(reader, start=2):  # start=2 accounts for header row
            if not any(row.values()):
                continue

            country = (row.get("country") or "").strip()
            document_type = (row.get("document_type") or "").strip()
            required_raw = (row.get("required") or "yes").strip().lower()
            fields_raw = (row.get("fields_to_extract") or "").strip()
            descriptions_raw = (row.get("field_descriptions") or "").strip()
            validation_raw = (row.get("validation_rules") or "").strip()

            if not country or not document_type:
                errors.append(f"Row {line_num}: Missing 'country' or 'document_type'.")
                continue

            if not fields_raw:
                errors.append(f"Row {line_num} ({country} / {document_type}): No fields defined.")
                continue

            field_names = [f.strip() for f in fields_raw.split("|") if f.strip()]
            descriptions = [d.strip() for d in descriptions_raw.split("|") if d.strip()] if descriptions_raw else []

            while len(descriptions) < len(field_names):
                descriptions.append(field_names[len(descriptions)])

            fields = [
                {"name": fn, "description": fd}
                for fn, fd in zip(field_names, descriptions)
            ]

            validation_rules = {}
            if validation_raw:
                for rule in validation_raw.split("|"):
                    rule = rule.strip()
                    if ":" in rule:
                        field_name, rule_expr = rule.split(":", 1)
                        validation_rules[field_name.strip()] = rule_expr.strip()

            configs.append({
                "country": country,
                "document_type": document_type,
                "required": required_raw == "yes",
                "fields": fields,
                "validation_rules": validation_rules,
                "raw_fields_str": fields_raw,
            })

    if errors:
        import warnings
        for err in errors:
            warnings.warn(f"[config_loader] {err}", UserWarning)

    return configs


def get_countries(config_path: Optional[str] = None) -> List[str]:
    """Return a sorted, deduplicated list of available countries from the CSV."""
    configs = load_config(config_path)
    seen = []
    for cfg in configs:
        if cfg["country"] not in seen:
            seen.append(cfg["country"])
    return seen


def get_config_for_country(country: str, config_path: Optional[str] = None) -> List[Dict]:
    """
    Return all document configs for a given country.
    """
    configs = load_config(config_path)
    return [cfg for cfg in configs if cfg["country"].lower() == country.lower()]


def get_required_doc_types(country: str, config_path: Optional[str] = None) -> List[str]:
    """Return list of required document_type strings for a given country."""
    return [
        cfg["document_type"]
        for cfg in get_config_for_country(country, config_path)
        if cfg["required"]
    ]


def get_all_field_names_for_country(country: str, config_path: Optional[str] = None) -> List[str]:
    """Return a flat, deduplicated list of all field names across all doc types for a country."""
    seen = []
    for cfg in get_config_for_country(country, config_path):
        for field in cfg["fields"]:
            if field["name"] not in seen:
                seen.append(field["name"])
    return seen


def build_extraction_schema(country: str, config_path: Optional[str] = None) -> Dict:
    """
    Build a dynamic extraction schema dict for use in LLM prompts.
    """
    schema = {}
    for cfg in get_config_for_country(country, config_path):
        schema[cfg["document_type"]] = {
            "fields": cfg["fields"],
            "validation_rules": cfg["validation_rules"],
            "required": cfg["required"],
        }
    return schema
