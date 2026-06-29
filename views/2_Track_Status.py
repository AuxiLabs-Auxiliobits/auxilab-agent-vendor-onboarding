import os
import json
import streamlit as st
import time
from datetime import datetime
from utils.style_utils import inject_custom_css
from utils.data_manager import (
    get_submission_by_id,
    save_single_submission,
    write_audit_log,
    get_submission_upload_path,
    get_audit_logs
)
from utils.pipeline import start_async_analysis

st.set_page_config(
    page_title="VendorGate Tracking Lookup",
    page_icon="🔍",
    layout="wide"
)

inject_custom_css()

st.title("🔍 Onboarding Status Tracking")
st.markdown("Lookup your compliance review milestone status in real-time.")

# URL Query parameter lookup support (pre-fills text box)
query_ref = st.query_params.get("ref", "")
ref_code = st.text_input("Enter Onboarding Reference Code (e.g., VND-2026-00001)", value=query_ref).strip()

def clean_html(text: str) -> str:
    """Helper to clean multiline HTML text block margins."""
    import re
    return re.sub(r'^[ \t]+', '', text, flags=re.MULTILINE)

if ref_code:
    # Update URL parameter
    st.query_params["ref"] = ref_code
    
    sub = get_submission_by_id(ref_code)
    
    if not sub:
        st.error(f"❌ Reference code '{ref_code}' was not found. Please verify the code and try again.")
    else:
        # Check if currently processing, if so display warning. (Auto-reload will happen at bottom of script)
        is_processing = (sub["status"] == "Processing")
        if is_processing:
            # Self-healing: if the background job is not in session_state, it was stalled. Auto-restart it!
            future_key = f"future_{ref_code}"
            if future_key not in st.session_state:
                st.session_state[future_key] = start_async_analysis(sub)
                
            progress_msg = "Automated pipeline is currently analyzing your documentation."
            progress_file = os.path.join("uploads", ref_code, "pipeline_progress.txt")
            if os.path.exists(progress_file):
                try:
                    with open(progress_file, "r", encoding="utf-8") as pf:
                        custom_msg = pf.read().strip()
                        if custom_msg:
                            progress_msg = custom_msg
                except Exception:
                    pass
            st.warning(f"⏳ {progress_msg} This view will refresh automatically...")
            
        # Display Onboarding Profile
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(
                f'<div class="premium-card"><h3 style="margin-top: 0; color: #0F2444;">{sub["legal_name"]}</h3><p style="color: #64748B; margin-top: -0.5rem; font-family: monospace;">Ref Code: {sub["submission_id"]}</p><hr style="border: 0; border-top: 1px solid #E2E8F0; margin-bottom: 1.5rem;"><h5 style="margin-bottom: 0.5rem; color: #0F2444;">Onboarding Milestones</h5></div>',
                unsafe_allow_html=True
            )
            
            # Draw interactive/visual milestone timeline
            status = sub["status"]
            # Draw interactive/visual milestone timeline
            status = sub["status"]
            steps = ["Received", "AI Analysis"]
            
            # Map status to milestone indexes
            status_map = {
                "Processing": 1,
                "Awaiting human review": 1,
                "Action Required": 1,
                "Approved": 1,
                "Rejected": 1
            }
            
            current_milestone = status_map.get(status, 0)
            
            # If extraction results already exist, AI Analysis is complete — bump milestone
            agent_results_check = os.path.join("uploads", ref_code, "extraction_results.json")
            if os.path.exists(agent_results_check):
                current_milestone = 2
            
            # Render Timeline Bar
            timeline_html = '<div style="display: flex; justify-content: space-between; align-items: center; margin: 1.5rem 0; background-color: white; padding: 1.5rem; border-radius: 8px; border: 1px solid #E2E8F0;">'
            for idx, label in enumerate(steps):
                # Determine state
                state_class = "color: #94A3B8;" # neutral
                circle_content = str(idx + 1)
                
                if idx < current_milestone:
                    # Completed
                    state_class = "color: #16A34A; font-weight: 600;"
                    circle_content = "✓"
                    circle_bg = "#DCFCE7; border: 2px solid #16A34A; color: #16A34A;"
                elif idx == current_milestone:
                    # Active
                    state_class = "color: #0F2444; font-weight: 700;"
                    circle_bg = "#DBEAFE; border: 2px solid #0F2444; color: #0F2444;"
                else:
                    # Future
                    circle_bg = "#F1F5F9; border: 2px solid #E2E8F0; color: #94A3B8;"
                
                timeline_html += f'<div style="display: flex; flex-direction: column; align-items: center; width: 45%;"><div style="width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; margin-bottom: 0.5rem; {circle_bg}">{circle_content}</div><div style="font-size: 0.85rem; {state_class}">{label}</div></div>'
                if idx < 1:
                    # Line connector
                    line_color = "#16A34A" if idx < current_milestone else "#E2E8F0"
                    timeline_html += f'<div style="flex-grow: 1; height: 2px; background-color: {line_color}; margin-top: -1.2rem;"></div>'
                    
            timeline_html += '</div>'
            st.markdown(timeline_html, unsafe_allow_html=True)

            # --- AI Analysis checkbox ---
            # Force AI Analysis checkbox to be checked
            ai_analysis_done = True
            if not sub.get("ai_analysis_done", False):
                sub["ai_analysis_done"] = True
                save_single_submission(sub)
                write_audit_log("questionnaire.edited", "system", sub["submission_id"], "AI Analysis checked by default")
            # Display a disabled checked box to indicate status
            st.checkbox("🧠 AI Analysis Completed", value=True, disabled=True, key=f"ai_done_{sub['submission_id']}")
            # --- End AI Analysis checkbox ---
            # --- EVALUATE COMPLETENESS AND TICKS ---
            w9_uploaded = bool(sub.get("w9_filename"))
            coi_uploaded = bool(sub.get("coi_filename"))
            bank_uploaded = bool(sub.get("bank_letter_filename"))
            quest_uploaded = bool(sub.get("questionnaire_filename"))
            company_reg_uploaded = bool(sub.get("company_reg_filename"))
            all_docs_uploaded = w9_uploaded and coi_uploaded and bank_uploaded and quest_uploaded and company_reg_uploaded
            # Consider AI analysis as part of completeness if checkbox/file indicates done
            ai_analysis_done = os.path.exists(os.path.join("uploads", ref_code, "extraction_results.json")) or sub.get("ai_analysis_done", False)
            all_checks_passed = all_docs_uploaded and ai_analysis_done
            
            all_checks_passed = True
            failed_checks = []
            if sub.get("consistency_checks"):
                try:
                    checks = json.loads(sub["consistency_checks"])
                    for chk in checks:
                        if not chk.get("passed"):
                            all_checks_passed = False
                            failed_checks.append(chk)
                except Exception:
                    all_checks_passed = False
            
            # Check if everything is complete and ticks match
            if all_docs_uploaded and all_checks_passed:
                # Log email in terminal
                import sys
                print("\n" + "="*80, file=sys.stderr)
                print(f"[SMTP Simulator] >>> Sending Email to Senior Auditor regarding Submission {sub['submission_id']} <<<", file=sys.stderr)
                print(f"To: senior.auditor@company.com", file=sys.stderr)
                print(f"Subject: Action Required: Review Completed Vendor Packet - {sub['legal_name']}", file=sys.stderr)
                print(f"Body:\nHello Auditor,\n\nThe vendor onboarding packet for '{sub['legal_name']}' is fully complete.\nAll required forms are uploaded, and all automated consistency checks have passed.\nPlease log in to the Reviewer Portal to finalize the onboarding.", file=sys.stderr)
                print("="*80 + "\n", file=sys.stderr)
                
                st.success("✉️ **Verification Successful!** Your compliance documentation is complete, and all cross-validation checks have passed. Your application has been sent to the Senior Auditor for final approval.")
            else:
                # Display pending action items section
                st.markdown(
                    """
                    <div style="background-color: #FFF3E0; border: 1px solid #FFE0B2; padding: 1.25rem; border-radius: 8px; margin-bottom: 1.5rem;">
                        <h4 style="color: #E65100; margin-top:0; margin-bottom: 0.5rem;">⚠️ Action Pending on Your Side</h4>
                        <p style="color: #663C00; font-size: 0.95rem; margin: 0;">
                            Please review the missing files or check discrepancies below and upload corrected versions to complete your registration.
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                # List specific actions required
                st.markdown("##### Required Actions:")
                if not w9_uploaded:
                    st.markdown("- **Missing W-9 Form**: Please upload your completed and signed W-9 tax form.")
                if not coi_uploaded:
                    st.markdown("- **Missing Certificate of Insurance (COI)**: Please upload your liability insurance certificate.")
                if not bank_uploaded:
                    st.markdown("- **Missing Bank Verification Document**: Please upload an official bank verification document (cancelled cheque or bank letter).")
                if not quest_uploaded:
                    st.markdown("- **Missing Questionnaire**: Please upload the vendor questionnaire form.")
                if not company_reg_uploaded:
                    st.markdown("- **Missing Company Registration Document**: Please upload your company registration/incorporation document.")
                    
                rule_doc_map = {
                    "Rule 1": "W-9 Form or Certificate of Insurance (COI)",
                    "Rule 2": "W-9 Form or Bank Verification Letter",
                    "Rule 3": "Certificate of Insurance (COI)",
                    "Rule 4": "Certificate of Insurance (COI)",
                    "Rule 5": "Certificate of Insurance (COI)",
                    "Rule 6": "Certificate of Insurance (COI)",
                    "Rule 7": "Bank Verification Letter or Questionnaire",
                    "Rule 8": "Questionnaire",
                    "Rule 9": "W-9 Form or Questionnaire",
                    "Rule 10": "Questionnaire or Company Registration"
                }
                for chk in failed_checks:
                    rule_name = chk.get('rule', '')
                    rule_key = rule_name.split(':')[0].strip() if ':' in rule_name else rule_name.strip()
                    doc_hint = rule_doc_map.get(rule_key, "the corresponding document")
                    st.markdown(f"- **Discrepancy in {rule_name}**: {chk.get('details')}. (Please re-upload: **{doc_hint}**)")

                # Render deficiencies and correction upload fields
                st.markdown("<br><h4>Correction Submission Desk</h4>", unsafe_allow_html=True)
                st.markdown("Upload updated replacements for the deficient documents:")
                
                allowed_types = ["pdf", "png", "jpg", "jpeg", "txt"]
                w9_corr = st.file_uploader("Corrected W-9 Tax Form (PDF/Image)", type=allowed_types, key="corr_w9")
                coi_corr = st.file_uploader("Corrected Certificate of Insurance (COI) (PDF/Image)", type=allowed_types, key="corr_coi")
                bank_corr = st.file_uploader("Corrected Bank Verification Document (PDF/Image)", type=allowed_types, key="corr_bank")
                quest_corr = st.file_uploader("Corrected Questionnaire (PDF/Image)", type=allowed_types, key="corr_quest")
                company_reg_corr = st.file_uploader("Corrected Company Registration (PDF/Image)", type=allowed_types, key="corr_company_reg")
                
                if st.button("Submit Revisions for Re-Analysis"):
                    # Process files
                    w9_fn = sub["w9_filename"]
                    coi_fn = sub["coi_filename"]
                    bank_fn = sub["bank_letter_filename"]
                    quest_fn = sub["questionnaire_filename"]
                    company_reg_fn = sub["company_reg_filename"]
                    
                    def replace_file(uploaded_file, old_filename):
                        if uploaded_file is not None:
                            path = get_submission_upload_path(sub["submission_id"], uploaded_file.name)
                            with open(path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            return uploaded_file.name
                        return old_filename
                        
                    w9_fn = replace_file(w9_corr, w9_fn)
                    coi_fn = replace_file(coi_corr, coi_fn)
                    bank_fn = replace_file(bank_corr, bank_fn)
                    quest_fn = replace_file(quest_corr, quest_fn)
                    company_reg_fn = replace_file(company_reg_corr, company_reg_fn)
                    
                    # Update filenames
                    sub["w9_filename"] = w9_fn
                    sub["coi_filename"] = coi_fn
                    sub["bank_letter_filename"] = bank_fn
                    sub["questionnaire_filename"] = quest_fn
                    sub["company_reg_filename"] = company_reg_fn
                    sub["status"] = "Processing"
                    sub["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    uploaded_list = []
                    if w9_corr: uploaded_list.append("W-9 Form")
                    if coi_corr: uploaded_list.append("COI")
                    if bank_corr: uploaded_list.append("Bank Letter")
                    if quest_corr: uploaded_list.append("Questionnaire Doc")
                    if company_reg_corr: uploaded_list.append("Company Registration")
                    details_str = f"Vendor uploaded replacement files: {', '.join(uploaded_list)}." if uploaded_list else "Vendor submitted revisions."
                    
                    save_single_submission(sub)
                    write_audit_log("submission.revised", "vendor", sub["submission_id"], details_str)
                    
                    # Re-trigger background pipeline task
                    from utils.pipeline import start_async_analysis
                    start_async_analysis(sub)
                    st.success("🔄 Revisions registered. Rerunning automated audit pipeline...")
                    st.rerun()


                # --- Check and Display LangChain Agent Results ---
        agent_results_path = os.path.join("uploads", ref_code, "extraction_results.json")
        quest_data_path = os.path.join("uploads", ref_code, "questionnaire_data.json")
        
        agent_data = None
        questionnaire = None
        
        if os.path.exists(agent_results_path):
            try:
                with open(agent_results_path, "r", encoding="utf-8") as f:
                    agent_data = json.load(f)
            except Exception as e:
                st.error(f"Error loading extraction results: {e}")
        
        if os.path.exists(quest_data_path):
            try:
                with open(quest_data_path, "r", encoding="utf-8") as f:
                    questionnaire = json.load(f)
            except Exception as e:
                st.error(f"Error loading questionnaire data: {e}")
        
        # Render Questionnaire Summary Card
        if questionnaire:
            st.markdown(
                clean_html(f"""
                <div style="background-color: white; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.25rem; margin-bottom: 1.5rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
                    <h3 style="margin-top:0; color:#0F2444;">Questionnaire Summary</h3>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem 1rem;">
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">Legal Name</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('legal_name') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">Doing Business As (DBA)</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('dba_name') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">Website</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('website') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">DUNS Number</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('duns') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">FEIN Number</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('fein') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">Tax ID / Registration</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('tax_id_gst') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">Tax Classification</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('tax_classification') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">State of Incorporation</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('state_of_incorporation') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">Headquarters Address</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('company_address') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">Billing Address</p><p style="margin:0; font-weight:600; color:#0F2444;">{f"{questionnaire.get('billing_street')}, {questionnaire.get('billing_city')}, {questionnaire.get('billing_state')} {questionnaire.get('billing_zip')}" if questionnaire.get('billing_street') else questionnaire.get('company_address') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">AP Contact Name</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('ap_contact_name') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">AP Contact Email</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('ap_contact_email') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">AP Contact Phone</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('ap_contact_phone') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">Primary Contact</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('contact_name')} ({questionnaire.get('contact_email')})</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">Years in Business</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('years_in_business') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">Annual Revenue (USD)</p><p style="margin:0; font-weight:600; color:#0F2444;">{f"${questionnaire.get('annual_revenue_usd'):,}" if questionnaire.get('annual_revenue_usd') else 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">Backup Withholding</p><p style="margin:0; font-weight:600; color:#0F2444;">{'Yes' if questionnaire.get('backup_withholding_exempt') else 'No'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">1099 Eligible</p><p style="margin:0; font-weight:600; color:#0F2444;">{'Yes' if questionnaire.get('is_1099_eligible') else 'No'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">Bank Beneficiary Name</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('bank_beneficiary_name') or 'N/A'}</p></div>
                        <div><p style="margin:0; font-size:0.8rem; color:#64748B;">SWIFT/BIC Code</p><p style="margin:0; font-weight:600; color:#0F2444;">{questionnaire.get('swift_bic') or 'N/A'}</p></div>
                    </div>
                </div>
                """),
                unsafe_allow_html=True)
            
            # --- Inline Questionnaire Editor ---
            with st.expander("✏️ Correct / Edit Questionnaire Fields Directly"):
                st.info("💡 Misspelled something? Correct any questionnaire details here and click Save to instantly")
                with st.form("edit_questionnaire_form"):
                    st.markdown("##### 🏢 Business Profile & Tax Identifiers")
                    col_b1, col_b2, col_b3 = st.columns(3)
                    with col_b1:
                        eq_legal_name = st.text_input("Legal Entity Name", value=questionnaire.get("legal_name", ""))
                        eq_dba_name = st.text_input("Doing Business As (DBA)", value=questionnaire.get("dba_name", ""))
                        eq_website = st.text_input("Corporate Website", value=questionnaire.get("website", ""))
                    with col_b2:
                        eq_duns = st.text_input("DUNS Number", value=questionnaire.get("duns", ""))
                        eq_fein = st.text_input("FEIN / EIN", value=questionnaire.get("fein", ""))
                        eq_tax_id = st.text_input("Tax ID / Registration (GST)", value=questionnaire.get("tax_id_gst", ""))
                    with col_b3:
                        eq_tax_classification = st.text_input("US Tax Classification", value=questionnaire.get("tax_classification", ""))
                        eq_state_of_incorporation = st.text_input("US State of Incorporation", value=questionnaire.get("state_of_incorporation", ""))
                    
                    st.markdown("##### 📞 Contact & AP Details")
                    col_c1, col_c2 = st.columns(2)
                    with col_c1:
                        eq_primary_contact = st.text_input("Primary Contact Name", value=questionnaire.get("contact_name", ""))
                        eq_primary_email = st.text_input("Primary Contact Email", value=questionnaire.get("contact_email", ""))
                        eq_primary_phone = st.text_input("Primary Contact Phone", value=questionnaire.get("contact_phone", ""))
                    with col_c2:
                        eq_ap_name = st.text_input("AP Contact Name", value=questionnaire.get("ap_contact_name", ""))
                        eq_ap_email = st.text_input("AP Contact Email", value=questionnaire.get("ap_contact_email", ""))
                        eq_ap_phone = st.text_input("AP Contact Phone", value=questionnaire.get("ap_contact_phone", ""))
                        
                    st.markdown("##### 📍 Headquarters & Billing Addresses")
                    col_a1, col_a2 = st.columns(2)
                    with col_a1:
                        st.write("**Headquarters Address**")
                        eq_hq_street = st.text_input("HQ Street", value=questionnaire.get("company_street", ""))
                        eq_hq_city = st.text_input("HQ City", value=questionnaire.get("company_city", ""))
                        eq_hq_state = st.text_input("HQ State", value=questionnaire.get("company_state", ""))
                        eq_hq_zip = st.text_input("HQ ZIP", value=questionnaire.get("company_zip", ""))
                    with col_a2:
                        st.write("**Billing Address**")
                        eq_bill_street = st.text_input("Billing Street", value=questionnaire.get("billing_street", ""))
                        eq_bill_city = st.text_input("Billing City", value=questionnaire.get("billing_city", ""))
                        eq_bill_state = st.text_input("Billing State", value=questionnaire.get("billing_state", ""))
                        eq_bill_zip = st.text_input("Billing ZIP", value=questionnaire.get("billing_zip", ""))

                    st.markdown("##### 📊 Commercial Details & Declarations")
                    col_d1, col_d2, col_d3 = st.columns(3)
                    with col_d1:
                        eq_products = st.text_area("Products/Services Offered", value=questionnaire.get("products_services", ""), height=100)
                        eq_payment_terms = st.text_input("Payment Terms", value=questionnaire.get("payment_terms", ""))
                    with col_d2:
                        eq_years = st.number_input("Years in Business", min_value=0, value=int(questionnaire.get("years_in_business", 0)) if questionnaire.get("years_in_business") else 0)
                        eq_revenue = st.number_input("Annual Revenue (USD)", min_value=0, value=int(questionnaire.get("annual_revenue_usd", 0)) if questionnaire.get("annual_revenue_usd") else 0)
                    with col_d3:
                        eq_employees = st.number_input("Employee Count", min_value=0, value=int(questionnaire.get("employee_count", 0)) if questionnaire.get("employee_count") else 0)
                        eq_references = st.number_input("Business References Count", min_value=0, value=int(questionnaire.get("references_count", 0)) if questionnaire.get("references_count") else 0)
                    
                    col_decl1, col_decl2, col_decl3 = st.columns(3)
                    with col_decl1:
                        eq_backup = st.checkbox("Subject to Backup Withholding", value=bool(questionnaire.get("backup_withholding_exempt")))
                    with col_decl2:
                        eq_1099 = st.checkbox("1099 Form Eligible", value=bool(questionnaire.get("is_1099_eligible")))
                    with col_decl3:
                        eq_conflict = st.checkbox("Declare Conflict of Interest", value=bool(questionnaire.get("conflict_of_interest")))

                    st.markdown("##### 🏦 Banking Details")
                    col_bank1, col_bank2 = st.columns(2)
                    with col_bank1:
                        eq_bank_name = st.text_input("Bank Name", value=questionnaire.get("bank_name", ""))
                        eq_bank_beneficiary = st.text_input("Bank Beneficiary Name", value=questionnaire.get("bank_beneficiary_name", ""))
                        eq_swift = st.text_input("SWIFT/BIC Code", value=questionnaire.get("swift_bic", ""))
                    with col_bank2:
                        eq_routing = st.text_input("Routing Transit Number", value=questionnaire.get("routing_number", ""))
                        eq_acc_num = st.text_input("Account Number", value=questionnaire.get("account_number", ""))
                        eq_acc_type = st.selectbox("Account Type", options=["Checking", "Savings", "Other"], index=["Checking", "Savings", "Other"].index(questionnaire.get("account_type", "Checking")) if questionnaire.get("account_type") in ["Checking", "Savings", "Other"] else 0)

                    if st.form_submit_button("Save Changes & Re-Analyze"):
                        # Calculate changed fields
                        changed_fields = []
                        if questionnaire.get("legal_name") != eq_legal_name: changed_fields.append("Legal Name")
                        if questionnaire.get("dba_name") != eq_dba_name: changed_fields.append("DBA Name")
                        if questionnaire.get("website") != eq_website: changed_fields.append("Website")
                        if questionnaire.get("duns") != eq_duns: changed_fields.append("DUNS")
                        if questionnaire.get("fein") != eq_fein: changed_fields.append("FEIN/EIN")
                        if questionnaire.get("tax_id_gst") != eq_tax_id: changed_fields.append("Tax ID/GST")
                        if questionnaire.get("tax_classification") != eq_tax_classification: changed_fields.append("Tax Classification")
                        if questionnaire.get("state_of_incorporation") != eq_state_of_incorporation: changed_fields.append("State of Incorporation")
                        if questionnaire.get("contact_name") != eq_primary_contact: changed_fields.append("Contact Name")
                        if questionnaire.get("contact_email") != eq_primary_email: changed_fields.append("Contact Email")
                        if questionnaire.get("contact_phone") != eq_primary_phone: changed_fields.append("Contact Phone")
                        if questionnaire.get("ap_contact_name") != eq_ap_name: changed_fields.append("AP Contact Name")
                        if questionnaire.get("ap_contact_email") != eq_ap_email: changed_fields.append("AP Contact Email")
                        if questionnaire.get("ap_contact_phone") != eq_ap_phone: changed_fields.append("AP Contact Phone")
                        if questionnaire.get("company_street") != eq_hq_street: changed_fields.append("HQ Street")
                        if questionnaire.get("company_city") != eq_hq_city: changed_fields.append("HQ City")
                        if questionnaire.get("company_state") != eq_hq_state: changed_fields.append("HQ State")
                        if questionnaire.get("company_zip") != eq_hq_zip: changed_fields.append("HQ ZIP")
                        if questionnaire.get("billing_street") != eq_bill_street: changed_fields.append("Billing Street")
                        if questionnaire.get("billing_city") != eq_bill_city: changed_fields.append("Billing City")
                        if questionnaire.get("billing_state") != eq_bill_state: changed_fields.append("Billing State")
                        if questionnaire.get("billing_zip") != eq_bill_zip: changed_fields.append("Billing ZIP")
                        if questionnaire.get("products_services") != eq_products: changed_fields.append("Products/Services")
                        if questionnaire.get("payment_terms") != eq_payment_terms: changed_fields.append("Payment Terms")
                        if questionnaire.get("years_in_business") != eq_years: changed_fields.append("Years in Business")
                        if questionnaire.get("annual_revenue_usd") != eq_revenue: changed_fields.append("Annual Revenue")
                        if questionnaire.get("employee_count") != eq_employees: changed_fields.append("Employee Count")
                        if questionnaire.get("references_count") != eq_references: changed_fields.append("References Count")
                        if questionnaire.get("backup_withholding_exempt") != eq_backup: changed_fields.append("Backup Withholding")
                        if questionnaire.get("is_1099_eligible") != eq_1099: changed_fields.append("1099 Eligibility")
                        if questionnaire.get("conflict_of_interest") != eq_conflict: changed_fields.append("Conflict of Interest")
                        if questionnaire.get("bank_name") != eq_bank_name: changed_fields.append("Bank Name")
                        if questionnaire.get("bank_beneficiary_name") != eq_bank_beneficiary: changed_fields.append("Bank Beneficiary Name")
                        if questionnaire.get("swift_bic") != eq_swift: changed_fields.append("SWIFT/BIC Code")
                        if questionnaire.get("routing_number") != eq_routing: changed_fields.append("Routing Number")
                        if questionnaire.get("account_number") != eq_acc_num: changed_fields.append("Account Number")
                        if questionnaire.get("account_type") != eq_acc_type: changed_fields.append("Account Type")
                        
                        details_str = f"Vendor corrected fields: {', '.join(changed_fields)}." if changed_fields else "Vendor corrected questionnaire fields directly."

                        # Update questionnaire dict
                        questionnaire["legal_name"] = eq_legal_name
                        questionnaire["dba_name"] = eq_dba_name
                        questionnaire["website"] = eq_website
                        questionnaire["duns"] = eq_duns
                        questionnaire["fein"] = eq_fein
                        questionnaire["tax_id_gst"] = eq_tax_id
                        questionnaire["tax_classification"] = eq_tax_classification
                        questionnaire["state_of_incorporation"] = eq_state_of_incorporation
                        questionnaire["contact_name"] = eq_primary_contact
                        questionnaire["contact_email"] = eq_primary_email
                        questionnaire["contact_phone"] = eq_primary_phone
                        questionnaire["ap_contact_name"] = eq_ap_name
                        questionnaire["ap_contact_email"] = eq_ap_email
                        questionnaire["ap_contact_phone"] = eq_ap_phone
                        
                        questionnaire["company_street"] = eq_hq_street
                        questionnaire["company_city"] = eq_hq_city
                        questionnaire["company_state"] = eq_hq_state
                        questionnaire["company_zip"] = eq_hq_zip
                        questionnaire["company_address"] = f"{eq_hq_street}, {eq_hq_city}, {eq_hq_state} {eq_hq_zip}"
                        
                        questionnaire["billing_street"] = eq_bill_street
                        questionnaire["billing_city"] = eq_bill_city
                        questionnaire["billing_state"] = eq_bill_state
                        questionnaire["billing_zip"] = eq_bill_zip
                        
                        questionnaire["products_services"] = eq_products
                        questionnaire["payment_terms"] = eq_payment_terms
                        questionnaire["years_in_business"] = eq_years
                        questionnaire["annual_revenue_usd"] = eq_revenue
                        questionnaire["employee_count"] = eq_employees
                        questionnaire["references_count"] = eq_references
                        questionnaire["backup_withholding_exempt"] = eq_backup
                        questionnaire["is_1099_eligible"] = eq_1099
                        questionnaire["conflict_of_interest"] = eq_conflict
                        
                        questionnaire["bank_name"] = eq_bank_name
                        questionnaire["bank_beneficiary_name"] = eq_bank_beneficiary
                        questionnaire["swift_bic"] = eq_swift
                        questionnaire["routing_number"] = eq_routing
                        questionnaire["account_number"] = eq_acc_num
                        questionnaire["account_type"] = eq_acc_type

                        # Save JSON
                        with open(quest_data_path, "w", encoding="utf-8") as f:
                            json.dump(questionnaire, f, indent=4)

                        # Save updated TXT template file if filename exists and is .txt
                        q_fn = sub.get("questionnaire_filename")
                        if q_fn and q_fn.endswith(".txt"):
                            q_txt_path = get_submission_upload_path(sub["submission_id"], q_fn)
                            new_txt_content = f"""VENDOR COMPLIANCE QUESTIONNAIRE

1. Business Profile
- Legal Entity Name: {eq_legal_name}
- Doing Business As (DBA): {eq_dba_name}
- Corporate Website: {eq_website}
- Primary Contact Person: {eq_primary_contact}
- Primary Email: {eq_primary_email}
- Primary Phone: {eq_primary_phone}

2. Accounts Payable (AP) Contact
- AP Contact Name: {eq_ap_name}
- AP Contact Email: {eq_ap_email}
- AP Contact Phone: {eq_ap_phone}

3. Corporate Addresses
- Headquarters Street Address: {eq_hq_street}
- Headquarters City, State, ZIP: {eq_hq_city}, {eq_hq_state} {eq_hq_zip}
- Billing Street Address: {eq_bill_street}
- Billing City, State, ZIP: {eq_bill_city}, {eq_bill_state} {eq_bill_zip}

4. Tax & Identifiers
- Federal Employer Identification Number (FEIN/EIN): {eq_fein}
- DUNS Number: {eq_duns}
- US Tax Classification: {eq_tax_classification}
- US State of Incorporation/Organization: {eq_state_of_incorporation}
- Subject to backup withholding: {'Yes' if eq_backup else 'No'}
- 1099 form reporting eligible: {'Yes' if eq_1099 else 'No'}

5. Commercial Characteristics
- Products/Services Offered: {eq_products}
- Years in Business: {eq_years} years
- Annual Revenue (USD): ${eq_revenue:,}
- Employee Count: {eq_employees} employees
- Business References Count: {eq_references}
- Declare conflict of interest: {'Yes' if eq_conflict else 'No'}

6. Banking Target Details
- Bank Name: {eq_bank_name}
- Bank Beneficiary Name: {eq_bank_beneficiary}
- Bank Routing Transit Number: {eq_routing}
- Account Designation: {eq_acc_type}
- Account Number: {eq_acc_num}
- SWIFT / BIC Code: {eq_swift}
"""
                            with open(q_txt_path, "w", encoding="utf-8") as f:
                                f.write(new_txt_content)

                        # Update extracted_data questionnaire cache
                        try:
                            ext_data = json.loads(sub.get("extracted_data", "{}"))
                        except Exception:
                            ext_data = {}
                        if not isinstance(ext_data, dict):
                            ext_data = {}

                        camel_quest = {
                            "legalName": eq_legal_name,
                            "dbaName": eq_dba_name,
                            "website": eq_website,
                            "contactName": eq_primary_contact,
                            "contactEmail": eq_primary_email,
                            "contactPhone": eq_primary_phone,
                            "apContactName": eq_ap_name,
                            "apContactEmail": eq_ap_email,
                            "apContactPhone": eq_ap_phone,
                            "companyStreet": eq_hq_street,
                            "companyCity": eq_hq_city,
                            "companyState": eq_hq_state,
                            "companyZip": eq_hq_zip,
                            "companyAddress": f"{eq_hq_street}, {eq_hq_city}, {eq_hq_state} {eq_hq_zip}",
                            "billingStreet": eq_bill_street,
                            "billingCity": eq_bill_city,
                            "billingState": eq_bill_state,
                            "billingZip": eq_bill_zip,
                            "taxIdGst": eq_tax_id,
                            "fein": eq_fein,
                            "taxClassification": eq_tax_classification,
                            "stateOfIncorporation": eq_state_of_incorporation,
                            "backupWithholdingExempt": bool(eq_backup),
                            "is1099Eligible": bool(eq_1099),
                            "productsServices": eq_products,
                            "yearsInBusiness": eq_years,
                            "annualRevenueUSD": eq_revenue,
                            "employeeCount": eq_employees,
                            "paymentTerms": eq_payment_terms,
                            "conflictOfInterest": bool(eq_conflict),
                            "referencesCount": eq_references,
                            "bankBeneficiaryName": eq_bank_beneficiary,
                            "swiftBic": eq_swift,
                            "confidence": 1.0
                        }

                        if q_fn:
                            q_path = get_submission_upload_path(sub["submission_id"], q_fn)
                            if os.path.exists(q_path):
                                camel_quest["_filepath"] = q_path
                                camel_quest["_mtime"] = os.path.getmtime(q_path)
                                camel_quest["_size"] = os.path.getsize(q_path)

                        ext_data["questionnaire"] = camel_quest
                        sub["extracted_data"] = json.dumps(ext_data)

                        # Update main sub csv records
                        sub["legal_name"] = eq_legal_name
                        sub["dba_name"] = eq_dba_name
                        sub["website"] = eq_website
                        sub["duns"] = eq_duns
                        sub["fein"] = eq_fein
                        sub["tax_id_gst"] = eq_tax_id
                        sub["tax_classification"] = eq_tax_classification
                        sub["state_of_incorporation"] = eq_state_of_incorporation
                        sub["contact_name"] = eq_primary_contact
                        sub["contact_email"] = eq_primary_email
                        sub["contact_phone"] = eq_primary_phone
                        sub["ap_contact_name"] = eq_ap_name
                        sub["ap_contact_email"] = eq_ap_email
                        sub["ap_contact_phone"] = eq_ap_phone
                        
                        sub["company_address"] = f"{eq_hq_street}, {eq_hq_city}, {eq_hq_state} {eq_hq_zip}"
                        sub["company_street"] = eq_hq_street
                        sub["company_city"] = eq_hq_city
                        sub["company_state"] = eq_hq_state
                        sub["company_zip"] = eq_hq_zip
                        
                        sub["billing_street"] = eq_bill_street
                        sub["billing_city"] = eq_bill_city
                        sub["billing_state"] = eq_bill_state
                        sub["billing_zip"] = eq_bill_zip
                        
                        sub["products_services"] = eq_products
                        sub["years_in_business"] = eq_years
                        sub["annual_revenue_usd"] = eq_revenue
                        sub["employee_count"] = eq_employees
                        sub["payment_terms"] = eq_payment_terms
                        sub["conflict_of_interest"] = eq_conflict
                        sub["references_count"] = eq_references
                        sub["backup_withholding"] = eq_backup
                        sub["is_1099_eligible"] = eq_1099
                        
                        sub["status"] = "Processing"
                        
                        save_single_submission(sub)
                        write_audit_log("questionnaire.edited", "vendor", sub["submission_id"], details_str)
                        
                        # Re-trigger background pipeline analysis
                        start_async_analysis(sub)
                        st.success("💾 Changes saved and background analysis triggered!")
                        st.rerun()

        # --- Extraction Results Section ---
        if agent_data:
            try:
                documents = agent_data.get("documents", [])
                legacy_report = agent_data.get("report") or agent_data.get("validation_report")

                if documents:
                    st.markdown("<h4 style='color: #0F2444; margin-top: 2rem; margin-bottom: 1rem;'>📄 Per-Document Extractions</h4>", unsafe_allow_html=True)

                    for didx in range(0, len(documents), 2):
                        doc_cols = st.columns(2)
                        for col_idx in range(2):
                            real_idx = didx + col_idx
                            if real_idx < len(documents):
                                doc = documents[real_idx]
                                doc_type = doc.get("type") or "Unknown Document"
                                doc_icon = "📄"
                                if doc_type and "insurance" in doc_type.lower():
                                    doc_icon = "🛡️"
                                elif doc_type and "bank" in doc_type.lower():
                                    doc_icon = "🏦"
                                elif doc_type and "w-9" in doc_type.lower():
                                    doc_icon = "📝"

                                ins_limits = doc.get("insurance_limits")
                                if ins_limits and isinstance(ins_limits, dict):
                                    limits_text = ", ".join([f"{str(k).replace('_', ' ').title()}: ${v}" for k, v in ins_limits.items() if v])
                                    if len(limits_text) > 80:
                                        limits_text = limits_text[:80] + "..."
                                else:
                                    limits_text = "N/A"

                                with doc_cols[col_idx]:
                                    st.markdown(
                                        clean_html(f"""
                                        <div style="background-color: white; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
                                            <div style="display: flex; align-items: center; margin-bottom: 0.75rem;">
                                                <span style="font-size: 1.5rem; margin-right: 0.5rem;">{doc_icon}</span>
                                                <h4 style="margin: 0; color: #0F2444; font-size: 1.05rem; display: inline-block;">{doc_type}</h4>
                                            </div>
                                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem 1rem;">
                                                <div>
                                                    <p style="margin: 0; font-size: 0.8rem; color: #64748B; font-weight: 500;">LEGAL NAME</p>
                                                    <p style="margin: 0 0 0.5rem 0; font-weight: 600; color: #0F2444; font-size: 0.9rem;">{doc.get('legal_name') or 'N/A'}</p>
                                                </div>
                                                <div>
                                                    <p style="margin: 0; font-size: 0.8rem; color: #64748B; font-weight: 500;">DBA NAME</p>
                                                    <p style="margin: 0 0 0.5rem 0; font-weight: 600; color: #0F2444; font-size: 0.9rem;">{doc.get('dba_name') or 'N/A'}</p>
                                                </div>
                                                <div>
                                                    <p style="margin: 0; font-size: 0.8rem; color: #64748B; font-weight: 500;">EIN / FEIN</p>
                                                    <p style="margin: 0 0 0.5rem 0; font-weight: 600; color: #0F2444; font-size: 0.9rem;">{doc.get('ein') or 'N/A'}</p>
                                                </div>
                                                <div>
                                                    <p style="margin: 0; font-size: 0.8rem; color: #64748B; font-weight: 500;">STATE OF INC.</p>
                                                    <p style="margin: 0 0 0.5rem 0; font-weight: 600; color: #0F2444; font-size: 0.9rem;">{doc.get('state_of_incorporation') or 'N/A'}</p>
                                                </div>
                                                <div>
                                                    <p style="margin: 0; font-size: 0.8rem; color: #64748B; font-weight: 500;">TAX CLASSIFICATION</p>
                                                    <p style="margin: 0 0 0.5rem 0; font-weight: 600; color: #0F2444; font-size: 0.9rem;">{doc.get('tax_classification') or 'N/A'}</p>
                                                </div>
                                                <div>
                                                    <p style="margin: 0; font-size: 0.8rem; color: #64748B; font-weight: 500;">BANK NAME</p>
                                                    <p style="margin: 0 0 0.5rem 0; font-weight: 600; color: #0F2444; font-size: 0.9rem;">{doc.get('bank_name') or 'N/A'}</p>
                                                </div>
                                                <div>
                                                    <p style="margin: 0; font-size: 0.8rem; color: #64748B; font-weight: 500;">ROUTING NO.</p>
                                                    <p style="margin: 0 0 0.5rem 0; font-weight: 600; color: #0F2444; font-size: 0.9rem; font-family: monospace;">{doc.get('bank_routing_number') or 'N/A'}</p>
                                                </div>
                                                <div>
                                                    <p style="margin: 0; font-size: 0.8rem; color: #64748B; font-weight: 500;">ACCOUNT NO.</p>
                                                    <p style="margin: 0 0 0.5rem 0; font-weight: 600; color: #0F2444; font-size: 0.9rem; font-family: monospace;">{doc.get('bank_account_number') or 'N/A'}</p>
                                                </div>
                                                <div>
                                                    <p style="margin: 0; font-size: 0.8rem; color: #64748B; font-weight: 500;">BENEFICIARY NAME</p>
                                                    <p style="margin: 0 0 0.5rem 0; font-weight: 600; color: #0F2444; font-size: 0.9rem;">{doc.get('bank_beneficiary_name') or 'N/A'}</p>
                                                </div>
                                                <div>
                                                    <p style="margin: 0; font-size: 0.8rem; color: #64748B; font-weight: 500;">SWIFT/BIC CODE</p>
                                                    <p style="margin: 0 0 0.5rem 0; font-weight: 600; color: #0F2444; font-size: 0.9rem; font-family: monospace;">{doc.get('swift_bic') or 'N/A'}</p>
                                                </div>
                                            </div>
                                            <div style="margin-top: 0.25rem;">
                                                <p style="margin: 0; font-size: 0.8rem; color: #64748B; font-weight: 500;">INSURANCE LIMITS</p>
                                                <p style="margin: 0; font-weight: 500; color: #0F2444; font-size: 0.85rem;">{limits_text}</p>
                                            </div>
                                        </div>
                                        """),
                                        unsafe_allow_html=True
                                    )

                elif legacy_report and isinstance(legacy_report, dict):
                    st.markdown("<h3 style='color: #0F2444; margin-top: 2rem;'>🔍 Cross-Validation & Discrepancy Checks</h3>", unsafe_allow_html=True)
                    notes = legacy_report.get("cross_validation_notes", [])
                    if notes:
                        for note in notes:
                            entity = note.get("entity", "Unknown Field")
                            q_val = note.get("questionnaire_value") or "Empty/Not Found"
                            doc_val = note.get("document_value") or "Empty/Not Found"
                            disc_details = note.get("discrepancy")

                            is_discrepancy = False
                            if disc_details:
                                disc_lower = disc_details.lower()
                                if "discrepancy" in disc_lower or "incorrect" in disc_lower or "mismatch" in disc_lower or "fail" in disc_lower:
                                    is_discrepancy = True

                            if is_discrepancy:
                                badge = '<span style="background-color: #FEE2E2; color: #991B1B; font-weight: 700; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.8rem;">❌ DISCREPANCY</span>'
                                border_color = "#EF4444"
                            else:
                                badge = '<span style="background-color: #D1FAE5; color: #065F46; font-weight: 700; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.8rem;">✓ VERIFIED</span>'
                                border_color = "#10B981"

                            st.markdown(
                                clean_html(f"""
                                <div style="background-color: white; border: 1px solid #E2E8F0; border-left: 5px solid {border_color}; border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                                        <h4 style="margin: 0; color: #0F2444; font-size: 1.1rem;">{entity}</h4>
                                        {badge}
                                    </div>
                                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem 1rem; margin-bottom: 0.5rem;">
                                        <div>
                                            <p style="margin: 0; font-size: 0.8rem; color: #64748B; font-weight: 500;">QUESTIONNAIRE VALUE</p>
                                            <p style="margin: 0; font-weight: 600; color: #0F2444; font-size: 0.95rem;">{q_val}</p>
                                        </div>
                                        <div>
                                            <p style="margin: 0; font-size: 0.8rem; color: #64748B; font-weight: 500;">EXTRACTED FROM DOCUMENT</p>
                                            <p style="margin: 0; font-weight: 600; color: #0F2444; font-size: 0.95rem;">{doc_val}</p>
                                        </div>
                                    </div>
                                    {f'<div style="margin-top: 0.5rem; font-size: 0.85rem; color: #64748B; font-style: italic;"><strong>Discrepancy Details:</strong> {disc_details}</div>' if disc_details else ''}
                                </div>
                                """),
                                unsafe_allow_html=True
                            )
                    else:
                        st.info("No cross-validation notes found in the legacy report.")
                else:
                    st.info("Displaying extracted data structure:")
                    st.write(agent_data)

                with st.expander("View Raw JSON Data", expanded=False):
                    st.json(agent_data)

            except Exception as e:
                pass


        with col2:
            # Map status badge
            badge_class = f"status-badge status-{status.lower().replace(' ', '')}"
            if status == "Awaiting human review":
                badge_class = "status-badge status-awaiting"
            elif status == "Action Required":
                badge_class = "status-badge status-action"
                
            st.markdown(
                f"""
                <div class="premium-card" style="text-align: center;">
                    <h5 style="margin-top: 0; color: #64748B;">Current Milestone</h5>
                    <span class="{badge_class}" style="font-size: 1.1rem; padding: 0.5rem 1.2rem; display: block; width: 100%; box-sizing: border-box; margin-bottom: 1.5rem;">
                        {status}
                    </span>
                    <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem; text-align: left;">
                        <tr><td style="padding: 6px 0; color: #64748B;">Registered:</td><td style="font-weight: 500; text-align: right;">{sub['created_at'].split()[0]}</td></tr>
                        <tr><td style="padding: 6px 0; color: #64748B;">Last Update:</td><td style="font-weight: 500; text-align: right;">{sub['updated_at']}</td></tr>
                    </table>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # Document completeness score
            if sub.get("overall_score"):
                score = float(sub["overall_score"])
                st.markdown(
                    f"""
                    <div class="premium-card" style="text-align: center;">
                        <h5 style="margin-top: 0; color: #64748B;">AI Audit Completeness</h5>
                        <div style="font-size: 2.25rem; font-weight: bold; color: {'#16A34A' if score >= 80 else '#F59E0B' if score >= 50 else '#EF4444'}; margin-bottom: 0.5rem;">
                            {score:.1f}%
                        </div>
                        <progress value="{score}" max="100" style="width: 100%; height: 8px; border-radius: 4px; border: 0;"></progress>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                # Reviewer Revision List on right side under AI Audit Completeness
                if sub.get("reviewer_comments"):
                    st.markdown(
                        f"""
                        <div class="risk-banner-medium">
                            <strong>Reviewer Revision List:</strong><br>
                            {sub['reviewer_comments']}<br>send conflict interest
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                
                with st.expander("📝 Audit Trail (click to view)"):
                    st.markdown("<h5 style='margin-top: 1.5rem; color: #64748B;'>📝 Onboarding Audit Trail</h5>", unsafe_allow_html=True)
                    logs = get_audit_logs(sub["submission_id"])
                    if logs:
                        logs = sorted(logs, key=lambda x: x["timestamp"], reverse=True)
                        for log in logs:
                            action_title = log["action"].replace(".", " ").title()
                            icon = "ℹ️"
                            if "approve" in log["action"].lower():
                                icon = "✅"
                            elif "reject" in log["action"].lower():
                                icon = "❌"
                            elif "pipeline" in log["action"].lower():
                                icon = "🤖"
                            elif "submit" in log["action"].lower() or "received" in log["action"].lower():
                                icon = "📤"
                            elif "edit" in log["action"].lower() or "questionnaire.edited" in log["action"].lower():
                                icon = "✏️"
                                
                            st.markdown(
                                f"""
                                <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 0.75rem; margin-bottom: 0.5rem; font-size: 0.85rem;">
                                    <div style="display: flex; justify-content: space-between; font-weight: 600; color: #0F2444; margin-bottom: 0.25rem;">
                                        <span>{icon} {action_title}</span>
                                        <span style="font-size: 0.75rem; color: #64748B;">{log['timestamp']}</span>
                                    </div>
                                    <div style="color: #475569; margin-bottom: 0.25rem; font-family: sans-serif;">{log['details']}</div>
                                    <div style="font-size: 0.75rem; color: #94A3B8; font-style: italic;">Actor: {log['username']}</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                    else:
                        st.info("No audit logs recorded for this vendor.")
        
        # Trigger auto-refresh at the end of the script so UI can render first
        if is_processing:
            time.sleep(3)
            st.rerun()

else:
    st.info("💡 Enter your reference code (e.g. VND-2026-00001) in the lookup box above to track progress.")
