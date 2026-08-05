from datetime import datetime
from typing import Dict, List, Any

def build_report(
    extraction_result: Dict,
    submission_id: str = "direct-run",
    vendor_name: str = "Direct Input Vendor",
    contact_email: str = ""
) -> Dict:
    """
    Constructs a structured, human-readable report dictionary from the raw extraction results.
    """
    country = extraction_result.get("country", "USA")
    extracted_at = extraction_result.get("extracted_at", "")
    overall_pct = extraction_result.get("overall_completeness_pct", 0.0)
    missing_docs = extraction_result.get("missing_required_docs", [])
    val_errors = extraction_result.get("validation_errors", {})
    cross_val = extraction_result.get("cross_validation", [])

    # Assemble Document Results
    document_results = []
    for doc_type, result in extraction_result.get("documents", {}).items():
        comp = extraction_result.get("completeness", {}).get(doc_type, {})
        doc_val_errors = val_errors.get(doc_type, {})

        fields_extracted = []
        for k, v in result.items():
            if k.startswith("_"):
                continue  # skip internal tags
            fields_extracted.append({
                "name": k,
                "value": v,
                "has_error": k in doc_val_errors,
                "error": doc_val_errors.get(k, "")
            })

        document_results.append({
            "doc_type": doc_type,
            "file_name": result.get("_file_name", ""),
            "completeness_score": comp.get("score", 0.0),
            "total_fields": comp.get("total_fields", 0),
            "present_fields": comp.get("present_fields", 0),
            "missing_fields": comp.get("missing_fields", []),
            "extraction_confidence": result.get("extraction_confidence", 1.0),
            "notes": result.get("notes", ""),
            "fields": fields_extracted,
            "validation_errors": doc_val_errors,
            "has_parse_error": result.get("parse_error", False),
            "has_llm_error": "llm_error" in result,
        })

    # Auto recommendations
    recommendations = []
    if missing_docs:
        recommendations.append(f"Request missing required documents: {', '.join(missing_docs)}")
    if val_errors:
        recommendations.append("Resolve document field validation rule errors.")
    
    inconsistent = [c for c in cross_val if isinstance(c, dict) and not c.get("consistent", True)]
    if inconsistent:
        for inc in inconsistent:
            recommendations.append(f"Resolve cross-document conflict in '{inc.get('field_name')}': {inc.get('details')}")

    if overall_pct < 70:
        recommendations.append("Overall document completeness is low. Ensure all required fields are filled and documents are legible.")

    # 3-State overall recommendation
    if missing_docs or overall_pct < 40:
        recommendation = "Escalate"
        reason = f"Critical compliance deficiency: Missing required documents or overall completeness is below 40%."
    elif val_errors or inconsistent or overall_pct < 70:
        recommendation = "Request Info"
        reason = "Minor compliance deficiency: Validation rule errors or cross-document consistency issues detected, or completeness is below 70%."
    else:
        recommendation = "Approve"
        reason = "Clean compliance: All required documents are present, fields validated, and consistent."

    report = {
        "meta": {
            "submission_id": submission_id,
            "vendor_name": vendor_name,
            "contact_email": contact_email,
            "country": country,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "extracted_at": extracted_at,
        },
        "summary": {
            "overall_completeness_pct": overall_pct,
            "status": "✅ Complete" if recommendation == "Approve" else ("⚠️ Needs Review" if recommendation == "Request Info" else "❌ Action Required"),
            "status_reason": reason,
            "total_docs_uploaded": len(document_results),
            "total_docs_missing": len(missing_docs),
            "total_cross_checks": len(cross_val),
            "failed_cross_checks": len(inconsistent),
            "total_validation_errors": sum(len(e) for e in val_errors.values()),
            "recommendation": recommendation,
            "recommendation_reason": reason,
        },
        "document_results": document_results,
        "cross_validation": cross_val,
        "missing_required_docs": missing_docs,
        "all_validation_errors": val_errors,
        "recommendations": recommendations,
    }

    return report


# ─────────────────────────────────────────────────────────────────────────────
# Interactive UI HTML Report Generator
# ─────────────────────────────────────────────────────────────────────────────

def render_report_html(report: Dict) -> str:
    """
    Render the report as an HTML string suitable for st.markdown(unsafe_allow_html=True) or Gradio.
    """
    meta = report.get("meta", {})
    summary = report.get("summary", {})
    doc_results = report.get("document_results", [])
    cross_val = report.get("cross_validation", [])
    missing_docs = report.get("missing_required_docs", [])
    recommendations = report.get("recommendations", [])

    status = summary.get("status", "Unknown")
    pct = summary.get("overall_completeness_pct", 0.0)

    # Status color
    if "✅" in status:
        status_color = "#16A34A"
        status_bg = "#F0FDF4"
        status_border = "#86EFAC"
    elif "❌" in status:
        status_color = "#DC2626"
        status_bg = "#FEF2F2"
        status_border = "#FECACA"
    else:
        status_color = "#D97706"
        status_bg = "#FFFBEB"
        status_border = "#FDE68A"

    # Completeness bar color
    if pct >= 80:
        bar_color = "#16A34A"
    elif pct >= 50:
        bar_color = "#D97706"
    else:
        bar_color = "#DC2626"

    html_parts = []

    # ── Header card ──────────────────────────────────────────────────────────
    html_parts.append(f"""
<div style="background: linear-gradient(135deg, #0F2444 0%, #1a3a6b 100%); 
     border-radius: 12px; padding: 1.5rem 2rem; margin-bottom: 1.5rem; color: white;">
  <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem;">
    <div>
      <h2 style="margin: 0; font-size: 1.4rem; font-weight: 700; color: white;">📋 Vendor Onboarding Summary Report</h2>
      <p style="margin: 0.3rem 0 0; opacity: 0.8; font-size: 0.9rem;">
        {meta.get('vendor_name', 'Unknown Vendor')} &nbsp;·&nbsp; 
        <code style="font-size:0.85rem; color: gray;">{meta.get('submission_id', 'N/A')}</code>
      </p>
    </div>
    <div style="text-align: right;">
      <span style="background: rgba(255,255,255,0.15); border-radius: 20px; padding: 0.3rem 0.9rem; font-size: 0.85rem;">
        🌍 {meta.get('country', 'N/A')}
      </span>
      <p style="margin: 0.5rem 0 0; font-size: 0.8rem; opacity: 0.7;">
        Generated {meta.get('generated_at', '')}
      </p>
    </div>
  </div>
</div>
""")

    # ── Status + completeness bar ─────────────────────────────────────────────
    html_parts.append(f"""
<div style="background: {status_bg}; border: 1px solid {status_border}; 
     border-radius: 10px; padding: 1.2rem 1.5rem; margin-bottom: 1.5rem;">
  <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem;">
    <div>
      <span style="font-size: 1.1rem; font-weight: 700; color: {status_color};">{status}</span>
      <p style="margin: 0.2rem 0 0; color: #475569; font-size: 0.88rem;">{summary.get('status_reason', '')}</p>
    </div>
    <div style="min-width: 200px;">
      <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
        <span style="font-size: 0.8rem; color: #64748B;">Overall Completeness</span>
        <span style="font-size: 0.85rem; font-weight: 700; color: {bar_color};">{pct:.1f}%</span>
      </div>
      <div style="background: #E2E8F0; border-radius: 9999px; height: 8px;">
        <div style="background: {bar_color}; border-radius: 9999px; height: 8px; width: {min(pct, 100):.1f}%;"></div>
      </div>
    </div>
  </div>
</div>
""")

    # ── Risk Score Matrix card ────────────────────────────────────────────────
    risk_score = summary.get("vendor_risk_score")
    risk_badge = summary.get("risk_badge", "🟢 LOW RISK")
    compliance_score = summary.get("vendor_compliance_score", 100.0)
    matrix = summary.get("risk_matrix_breakdown", {})

    if risk_score is not None:
        risk_color = "#16A34A" if "LOW" in risk_badge else ("#D97706" if "MEDIUM" in risk_badge else "#DC2626")
        risk_bg = "#F0FDF4" if "LOW" in risk_badge else ("#FFFBEB" if "MEDIUM" in risk_badge else "#FEF2F2")
        risk_border = "#86EFAC" if "LOW" in risk_badge else ("#FDE68A" if "MEDIUM" in risk_badge else "#FECACA")

        html_parts.append(f"""
<div style="background: {risk_bg}; border: 1.5px solid {risk_border}; border-radius: 10px; padding: 1.2rem 1.5rem; margin-bottom: 1.5rem;">
  <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
    <div>
      <span style="font-size: 0.82rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px;">Vendor Risk Score Matrix</span>
      <h3 style="margin: 0.2rem 0 0; color: {risk_color}; font-size: 1.5rem; font-weight: 800;">
        {risk_badge} &nbsp;&bull;&nbsp; Risk Score: {risk_score} / 100
      </h3>
      <p style="margin: 0.3rem 0 0; color: #475569; font-size: 0.85rem;">
        Weighted Compliance Rating: <strong>{compliance_score}%</strong> (Higher is better)
      </p>
    </div>
    <div style="background: white; border: 1px solid {risk_border}; border-radius: 8px; padding: 0.6rem 1rem; font-size: 0.78rem; min-width: 250px;">
      <div style="font-weight: 700; color: #0F2444; margin-bottom: 0.3rem;">📊 Matrix Breakdown:</div>
      <div style="display: flex; justify-content: space-between;"><span>• Doc Completeness (30%):</span> <strong>{matrix.get('completeness_score_weight_30', 0)}%</strong></div>
      <div style="display: flex; justify-content: space-between;"><span>• Rules Passed (40%):</span> <strong>{matrix.get('rules_passed_pct_weight_40', 0)}%</strong></div>
      <div style="display: flex; justify-content: space-between;"><span>• Field Validation (15%):</span> <strong>{matrix.get('validation_score_weight_15', 0)}%</strong></div>
      <div style="display: flex; justify-content: space-between;"><span>• LLM Confidence (15%):</span> <strong>{matrix.get('extraction_confidence_weight_15', 0)}%</strong></div>
    </div>
  </div>
</div>
""")

    # ── Summary stats ─────────────────────────────────────────────────────────
    stats = [
        ("📁 Docs Uploaded", summary.get("total_docs_uploaded", 0), "#0F2444"),
        ("🔴 Docs Missing", summary.get("total_docs_missing", 0), "#DC2626" if summary.get("total_docs_missing", 0) > 0 else "#16A34A"),
        ("🔀 Cross-Checks", summary.get("total_cross_checks", 0), "#0F2444"),
        ("❌ Failed Checks", summary.get("failed_cross_checks", 0), "#DC2626" if summary.get("failed_cross_checks", 0) > 0 else "#16A34A"),
        ("⚠️ Field Errors", summary.get("total_validation_errors", 0), "#D97706" if summary.get("total_validation_errors", 0) > 0 else "#16A34A"),
    ]
    stat_cards = "".join([
        f"""<div style="background: white; border: 1px solid #E2E8F0; border-radius: 8px; padding: 0.75rem 1rem; text-align: center; flex: 1; min-width: 120px;">
  <div style="font-size: 1.4rem; font-weight: 800; color: {c};">{v}</div>
  <div style="font-size: 0.75rem; color: #64748B; margin-top: 0.2rem;">{l}</div>
</div>"""
        for l, v, c in stats
    ])
    html_parts.append(f"""
<div style="display: flex; gap: 0.75rem; margin-bottom: 1.5rem; flex-wrap: wrap;">
{stat_cards}
</div>
""")

    # ── Missing required documents ────────────────────────────────────────────
    if missing_docs:
        items = "".join([f"<li style='margin-bottom:0.3rem;'><strong>{d}</strong></li>" for d in missing_docs])
        html_parts.append(f"""
<div style="background: #FEF2F2; border: 1px solid #FECACA; border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 1.5rem;">
  <h4 style="margin: 0 0 0.5rem; color: #DC2626;">🔴 Missing Required Documents</h4>
  <ul style="margin: 0; padding-left: 1.25rem; color: #7F1D1D;">{items}</ul>
</div>
""")

    # ── Compliance Rules (10-Rule Check) ──────────────────────────────────────
    compliance_rules = report.get("compliance_rules", [])
    if compliance_rules:
        html_parts.append("<h3 style='margin: 1.5rem 0 0.75rem; color: #0F2444;'>🛡️ Consistency & Compliance Checks (10-Rule Verification)</h3>")
        
        rule_rows = ""
        for rule in compliance_rules:
            status_label = rule.get("status", "Skipped")
            details_text = rule.get("details", "")
            desc_text = rule.get("description", "")
            title_text = rule.get("rule_title", "")
            rid = rule.get("rule_id", "")
            
            if status_label == "Passed":
                bg = "#E8F5E9"
                border = "#A5D6A7"
                color = "#2E7D32"
                icon = "✅"
            elif status_label in ("Failed", "Error"):
                bg = "#FFEBEE"
                border = "#EF9A9A"
                color = "#C62828"
                icon = "❌"
            elif status_label == "Warning":
                bg = "#FFF3E0"
                border = "#FFCC80"
                color = "#EF6C00"
                icon = "⚠️"
            else: # Skipped
                bg = "#F5F5F5"
                border = "#E0E0E0"
                color = "#616161"
                icon = "⚪"
                
            rule_rows += f"""
<div style="background: {bg}; border: 1px solid {border}; border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 0.6rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
  <div style="flex: 1; min-width: 250px;">
    <span style="font-weight: 700; color: #0F2444; font-size: 0.88rem;">{rid}: {title_text}</span>
    <p style="margin: 0.2rem 0 0; color: #64748B; font-size: 0.78rem; font-style: italic;">{desc_text}</p>
    <p style="margin: 0.3rem 0 0; color: #334155; font-size: 0.82rem; font-weight: 500;">{details_text}</p>
  </div>
  <div style="background: {bg}; border: 1.5px solid {border}; color: {color}; border-radius: 20px; padding: 0.2rem 0.75rem; font-size: 0.78rem; font-weight: 700; display: inline-flex; align-items: center; gap: 0.3rem;">
    {icon} {status_label.upper()}
  </div>
</div>
"""
        html_parts.append(rule_rows)

    # ── Document extraction results ───────────────────────────────────────────
    html_parts.append("<h3 style='margin: 1.5rem 0 0.75rem; color: #0F2444;'>📄 Document Extraction Results</h3>")

    for doc in doc_results:
        doc_pct = doc.get("completeness_score", 0.0)
        if doc_pct >= 80:
            doc_color = "#16A34A"
        elif doc_pct >= 50:
            doc_color = "#D97706"
        else:
            doc_color = "#DC2626"

        conf = doc.get("extraction_confidence")
        conf_str = f"{conf*100:.0f}%" if conf is not None else "N/A"

        # Construct rows for fields
        field_rows = ""
        for field in doc.get("fields", []):
            name = field.get("name", "")
            val = field.get("value")
            val_str = f"<code>{val}</code>" if val is not None else "<span style='color:#94A3B8;'>null (missing)</span>"
            
            err_msg = field.get("error", "")
            err_html = f"<div style='color:#DC2626; font-size:0.75rem; margin-top:0.25rem;'>⚠️ {err_msg}</div>" if err_msg else ""
            
            field_rows += f"""
<tr style="border-bottom: 1px solid #F1F5F9;">
  <td style="padding: 0.6rem 0.75rem; font-size: 0.82rem; font-weight: 600; color: #334155;">{name}</td>
  <td style="padding: 0.6rem 0.75rem; font-size: 0.82rem;">{val_str}{err_html}</td>
</tr>
"""

        notes_section = ""
        if doc.get("notes"):
            notes_section = f"""
<div style="background: #F8FAFC; border-left: 3px solid #64748B; padding: 0.6rem 0.8rem; margin: 0.75rem 0.75rem 0; font-size: 0.8rem; color: #475569; border-radius: 0 4px 4px 0;">
  <strong>Notes:</strong> {doc.get('notes')}
</div>
"""

        html_parts.append(f"""
<div style="background: white; border: 1px solid #E2E8F0; border-radius: 8px; margin-bottom: 1rem; overflow: hidden; padding-bottom: 0.75rem;">
  <div style="background: #F8FAFC; border-bottom: 1px solid #E2E8F0; padding: 0.75rem 1rem; display: flex; justify-content: space-between; align-items: center;">
    <div>
      <span style="font-weight: 700; color: #0F2444; font-size: 0.95rem;">{doc.get('doc_type')}</span>
      <p style="margin: 0.1rem 0 0; font-size: 0.72rem; color: #64748B;">{doc.get('file_name')}</p>
    </div>
    <div style="display: flex; gap: 0.75rem; align-items: center;">
      <span style="font-size: 0.75rem; color: #64748B;">Confidence: <strong>{conf_str}</strong></span>
      <span style="background: {doc_color}15; color: {doc_color}; border: 1px solid {doc_color}30; border-radius: 4px; padding: 0.15rem 0.5rem; font-size: 0.75rem; font-weight: 700;">
        {doc_pct:.1f}% Complete
      </span>
    </div>
  </div>
  <table style="width: 100%; border-collapse: collapse; margin-top: 0.25rem;">
    {field_rows}
  </table>
  {notes_section}
</div>
""")

    # ── Actionable Recommendations ────────────────────────────────────────────
    if recommendations:
        rec_items = "".join([f"<li style='margin-bottom:0.4rem;'>{r}</li>" for r in recommendations])
        html_parts.append(f"""
<div style="background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 8px; padding: 1.2rem 1.5rem; margin-top: 1.5rem;">
  <h4 style="margin: 0 0 0.6rem; color: #D97706; font-size: 1rem;">📋 Recommended Remediation Steps</h4>
  <ol style="margin: 0; padding-left: 1.25rem; color: #78350F; font-size: 0.88rem;">{rec_items}</ol>
</div>
""")

    # Wrap in container
    return f"""
<div class="compliance-report-container" style="max-width: 100%; margin: 0 auto; color: #1E293B; line-height: 1.5;">
  {"".join(html_parts)}
</div>
"""
