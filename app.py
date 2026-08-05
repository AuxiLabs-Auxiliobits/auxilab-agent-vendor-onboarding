import os
import shutil
import gradio as gr
from pathlib import Path
from agent.config_loader import get_countries
from agent.pipeline import run_compliance_pipeline
from agent.report_generator import render_report_html

def process_onboarding(country, uploaded_files, text_only, progress=gr.Progress()):
    if not country:
        return "### Error: Please select a country.", {}, "<p style='color:red;'>Please select a country.</p>"
    if not uploaded_files:
        return "### Error: Please upload at least one document.", {}, "<p style='color:red;'>Please upload at least one document.</p>"
        
    temp_dir = Path("uploads") / "gradio_tmp"
    if temp_dir.exists():
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    local_files = []
    for f in uploaded_files:
        f_path = Path(f.name if hasattr(f, 'name') else f)
        target_path = temp_dir / f_path.name
        try:
            shutil.copy(f_path, target_path)
            local_files.append(target_path)
        except Exception as e:
            print(f"Error copying file: {e}")
            
    try:
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
        for lf in local_files:
            name_lower = lf.stem.lower().replace("-", "_").replace(" ", "_")
            matched = False
            for kw, dt in KEYWORD_MAP.items():
                if kw in name_lower and dt in configured_types:
                    documents.append((dt, lf))
                    matched = True
                    break
            if not matched:
                for ct in configured_types:
                    if ct.lower().replace("-","").replace(" ","") in name_lower.replace("_",""):
                        documents.append((ct, lf))
                        matched = True
                        break
            if not matched:
                unmapped.append(lf)
                
        mapped_types = [d[0] for d in documents]
        remaining = [ct for ct in configured_types if ct not in mapped_types]
        for lf in unmapped:
            if remaining:
                documents.append((remaining.pop(0), lf))
            elif configured_types:
                documents.append((configured_types[0], lf))
            else:
                documents.append(("Unknown Document", lf))
                
        # Setup progress tracker
        total_steps = len(documents) + 2
        current_step = 0
        
        def progress_cb(msg: str):
            nonlocal current_step
            current_step += 1
            val = min(0.95, current_step / total_steps)
            progress(val, desc=msg)
            
        report = run_compliance_pipeline(
            country=country,
            documents=documents,
            text_only=text_only,
            progress_callback=progress_cb
        )
        
        rec = report["summary"]["recommendation"]
        reason = report["summary"]["recommendation_reason"]
        score = report["summary"]["overall_completeness_pct"]
        
        rec_color = "#16A34A" if rec == "Approve" else ("#D97706" if rec == "Request Info" else "#DC2626")
        
        markdown_summary = f"""
# Compliance Recommendation: <span style='color:{rec_color}; font-weight:bold;'>{rec.upper()}</span>
**Reason:** {reason}

---

### 📊 Summary Metrics
- **Country Profile:** {country}
- **Overall Completeness:** {score:.1f}%
- **Documents Analyzed:** {len(report.get("document_results", []))}
- **Missing Required Documents:** {', '.join(report.get("missing_required_docs", [])) or "None"}

### 🔍 Deficiencies & Compliance Flags
"""
        val_errors = report.get("all_validation_errors", {})
        if val_errors:
            markdown_summary += "\n#### ⚠️ Validation Rule Failures:\n"
            for doc, fields in val_errors.items():
                for f, msg in fields.items():
                    markdown_summary += f"- **{doc}** ➜ `{f}`: {msg}\n"
        else:
            markdown_summary += "\n- ✅ No validation rule errors.\n"
            
        cross_val = report.get("cross_validation", [])
        inconsistent = [c for c in cross_val if isinstance(c, dict) and not c.get("consistent", True)]
        if inconsistent:
            markdown_summary += "\n#### 🔀 Cross-Document Inconsistencies:\n"
            for c in inconsistent:
                markdown_summary += f"- **Field `{c.get('field_name')}`**: {c.get('details')} (Values: {c.get('values_found')})\n"
        else:
            markdown_summary += "\n- ✅ No cross-document inconsistencies found.\n"
            
        html_report = render_report_html(report)
        
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
            
        return markdown_summary, report, html_report
        
    except Exception as e:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
        import traceback
        err_msg = f"### Pipeline Execution Failed\n\n```python\n{traceback.format_exc()}\n```"
        return err_msg, {"error": str(e)}, f"<p style='color:red;'>Error running pipeline: {e}</p>"

# Load countries
try:
    countries = get_countries()
except Exception:
    countries = ["USA", "India", "UK", "UAE", "Singapore"]

# Gradio CSS custom styling
custom_css = """
body {
    background-color: #0F172A;
}
.gradio-container {
    font-family: 'Outfit', sans-serif !important;
}
#title_banner {
    text-align: center;
    margin-bottom: 2rem;
}
#title_banner h1 {
    color: #F8FAFC !important;
    font-weight: 700;
}
#title_banner p {
    color: #94A3B8;
}
"""

with gr.Blocks() as demo:
    with gr.Row(elem_id="title_banner"):
        gr.Markdown(
            """
            # 🛡️ VendorGate AI Compliance Agent
            ### Standalone Vendor Onboarding Document Intake & Validation Agent
            """
        )
        
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 📥 Document Intake")
            country_drop = gr.Dropdown(
                choices=countries,
                value=countries[0] if countries else "USA",
                label="Target Country Profile",
                info="Determines the compliance rules and required documents."
            )
            files_upload = gr.File(
                file_count="multiple",
                file_types=[".pdf", ".png", ".jpg", ".jpeg", ".txt"],
                label="Upload Documents (Select required vendor files like W-9, COI, PAN, GST, bank letter)"
            )
            text_only_check = gr.Checkbox(
                label="Text-Only Fallback",
                value=False,
                info="Extract text directly instead of rendering document pages to images. Enable if your API key doesn't support multimodal vision."
            )
            analyze_btn = gr.Button("🔍 Run Compliance Verification", variant="primary")
            
        with gr.Column(scale=2):
            gr.Markdown("### 📋 Compliance Verification Output")
            
            with gr.Tabs():
                with gr.TabItem("💡 Summary Recommendation"):
                    md_output = gr.Markdown("Submit documents to see the compliance recommendation.")
                    
                with gr.TabItem("📊 Interactive Report"):
                    html_output = gr.HTML("<p style='color:#64748B;'>Submit documents to view the report dashboard.</p>")
                    
                with gr.TabItem("⚙️ Raw JSON Data"):
                    json_output = gr.JSON(label="Structured Extract Data")
                    
    analyze_btn.click(
        fn=process_onboarding,
        inputs=[country_drop, files_upload, text_only_check],
        outputs=[md_output, json_output, html_output]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1", 
        server_port=8000,
        inbrowser=True,
        theme=gr.themes.Soft(primary_hue="indigo", secondary_hue="slate"),
        css=custom_css
    )

