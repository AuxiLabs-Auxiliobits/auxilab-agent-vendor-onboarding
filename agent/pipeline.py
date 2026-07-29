import os
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from dotenv import load_dotenv
load_dotenv()

from agent.config_loader import build_extraction_schema
from agent.dynamic_extractor import run_dynamic_extraction
from agent.report_generator import build_report
from agent.compliance_checker import evaluate_compliance_rules

def run_compliance_pipeline(
    country: str,
    documents: List[Tuple[str, Path]],
    text_only: bool = False,
    progress_callback=None
) -> dict:
    """
    Executes the vendor onboarding compliance pipeline.
    
    1. Loads extraction schema for the country.
    2. Runs dynamic LLM-based field extraction.
    3. Computes completeness scores and validation rules.
    4. Evaluates extracted fields against the 10 built-in compliance and consistency rules.
    5. Evaluates risk flags and makes a compliance recommendation (Approve, Request Info, Escalate).
    """
    if not documents:
        raise ValueError("No documents provided for compliance analysis.")
        
    # 1. Load schema from config CSV
    schema = build_extraction_schema(country)
    if not schema:
        raise ValueError(f"No compliance schema configuration found for country: {country}")
        
    # 2. Run extraction
    if progress_callback:
        progress_callback(f"Starting analysis for country: {country}")
        
    extraction_result = run_dynamic_extraction(
        country=country,
        schema=schema,
        documents=documents,
        progress_callback=progress_callback,
        text_only=text_only
    )
    
    # 3. Build summary report
    report = build_report(
        extraction_result=extraction_result,
        submission_id="direct-run",
        vendor_name="Direct Input Vendor"
    )
    
    # 4. Evaluate the 10 compliance rules
    if progress_callback:
        progress_callback("Running the 10 compliance & consistency rules verification...")
        
    evaluated_rules = evaluate_compliance_rules(extraction_result.get("documents", {}))
    report["compliance_rules"] = evaluated_rules
    
    # 5. Determine auto-recommendation & reason based on rules and completeness
    missing_docs = extraction_result.get("missing_required_docs", [])
    val_errors = extraction_result.get("validation_errors", {})
    overall_pct = extraction_result.get("overall_completeness_pct", 0.0)
    
    failed_rules = [r for r in evaluated_rules if r["status"] == "Failed"]
    warning_rules = [r for r in evaluated_rules if r["status"] == "Warning"]
    
    failed_names = [r["rule_title"] for r in failed_rules]
    warning_names = [r["rule_title"] for r in warning_rules]
    
    if missing_docs or overall_pct < 40 or len(failed_rules) >= 3:
        recommendation = "Escalate"
        reason = "Critical compliance deficiency: "
        if missing_docs:
            reason += f"Missing required documents ({', '.join(missing_docs)}). "
        if overall_pct < 40:
            reason += f"Overall completeness is too low ({overall_pct:.1f}%). "
        if len(failed_rules) >= 3:
            reason += f"Multiple rule failures detected ({', '.join(failed_names)})."
    elif val_errors or len(failed_rules) > 0 or len(warning_rules) > 0 or overall_pct < 70:
        recommendation = "Request Info"
        reason = "Compliance reviews flagged: "
        if failed_rules:
            reason += f"Failed Rules: {', '.join(failed_names)}. "
        if warning_rules:
            reason += f"Warning Rules: {', '.join(warning_names)}. "
        if val_errors:
            reason += "Document field validation rule errors. "
        if overall_pct < 70:
            reason += f"Overall completeness is {overall_pct:.1f}%."
    else:
        recommendation = "Approve"
        reason = "Clean compliance: All required documents are present, fields validated, and all consistency checks passed."
        
    report["summary"]["recommendation"] = recommendation
    report["summary"]["recommendation_reason"] = reason
    report["summary"]["failed_cross_checks"] = len(failed_rules)
    report["summary"]["total_cross_checks"] = len(evaluated_rules)
    report["summary"]["total_input_tokens"] = extraction_result.get("total_input_tokens", 0)
    report["summary"]["total_output_tokens"] = extraction_result.get("total_output_tokens", 0)
    
    # 6. Calculate Vendor Risk Score Matrix (0-100 Rating)
    passed_rules_count = len([r for r in evaluated_rules if r.get("status") == "Passed"])
    total_rules_count = len(evaluated_rules)
    rules_passed_pct = (passed_rules_count / total_rules_count * 100.0) if total_rules_count > 0 else 100.0
    
    total_val_err_count = sum(len(e) for e in val_errors.values())
    val_score = max(0.0, 100.0 - (total_val_err_count * 20.0))
    
    doc_results_dict = extraction_result.get("documents", {})
    confidences = [
        d.get("extraction_confidence", 1.0)
        for d in doc_results_dict.values()
        if isinstance(d, dict) and "extraction_confidence" in d
    ]
    avg_conf_pct = (sum(confidences) / len(confidences) * 100.0) if confidences else 100.0
    
    compliance_score = round(
        (0.30 * overall_pct) +
        (0.40 * rules_passed_pct) +
        (0.15 * val_score) +
        (0.15 * avg_conf_pct),
        1
    )
    risk_score = round(max(0.0, min(100.0, 100.0 - compliance_score)), 1)
    
    if risk_score <= 15.0:
        risk_level = "LOW RISK"
        risk_badge = "🟢 LOW RISK"
    elif risk_score <= 35.0:
        risk_level = "MEDIUM RISK"
        risk_badge = "🟡 MEDIUM RISK"
    else:
        risk_level = "HIGH RISK"
        risk_badge = "🔴 HIGH RISK"
        
    report["summary"]["vendor_compliance_score"] = compliance_score
    report["summary"]["vendor_risk_score"] = risk_score
    report["summary"]["risk_level"] = risk_level
    report["summary"]["risk_badge"] = risk_badge
    report["summary"]["risk_matrix_breakdown"] = {
        "completeness_score_weight_30": round(overall_pct, 1),
        "rules_passed_pct_weight_40": round(rules_passed_pct, 1),
        "validation_score_weight_15": round(val_score, 1),
        "extraction_confidence_weight_15": round(avg_conf_pct, 1),
    }

    # Sync with status description
    if recommendation == "Escalate":
        report["summary"]["status"] = "❌ Action Required"
        report["summary"]["status_reason"] = reason
    elif recommendation == "Request Info":
        report["summary"]["status"] = "⚠️ Needs Review"
        report["summary"]["status_reason"] = reason
    else:
        report["summary"]["status"] = "✅ Complete"
        report["summary"]["status_reason"] = reason
        
    return report
