import os
import json
import streamlit as st
import pandas as pd
from datetime import datetime
from utils.style_utils import inject_custom_css, render_mobile_warning
from utils.data_manager import (
    read_submissions,
    save_single_submission,
    write_audit_log,
    authenticate_user,
    get_audit_logs,
    get_submission_by_id
)
from utils.notifier import send_approved_email, send_action_required_email

# Set wide layout page configuration
st.set_page_config(
    page_title="VendorGate Reviewer Dashboard",
    page_icon="🔐",
    layout="wide"
)

inject_custom_css()

# Render Mobile Intercept Warning in CSS/HTML
render_mobile_warning()

# Main page layout wrapped in desktop-only class
st.markdown('<div class="desktop-only-content">', unsafe_allow_html=True)

# 1. Enforce reviewer authentication
if "reviewer_authenticated" not in st.session_state:
    st.session_state["reviewer_authenticated"] = False
    st.session_state["reviewer_username"] = ""

if not st.session_state["reviewer_authenticated"]:
    # Render premium login form
    login_col1, login_col2, login_col3 = st.columns([1, 1.5, 1])
    with login_col2:
        st.markdown(
            """
            <div class="landing-container" style="margin-top: 4rem;">
                <div style="font-size: 3rem; margin-bottom: 0.5rem;">🔐</div>
                <h3 style="margin-top: 0; color: #0F2444; margin-bottom: 1.5rem;">Reviewer Portal Login</h3>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        with st.form("login_form"):
            username = st.text_input("Username").strip()
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Authenticate", use_container_width=True)
            
            if submitted:
                if authenticate_user(username, password):
                    st.session_state["reviewer_authenticated"] = True
                    st.session_state["reviewer_username"] = username
                    st.success("Successfully authenticated!")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or credentials. Please try again.")
        st.stop()

# --- AUTHENTICATED DASHBOARD & QUEUE ---

# Helper to log out
def logout_user():
    st.session_state["reviewer_authenticated"] = False
    st.session_state["reviewer_username"] = ""
    st.rerun()

submissions = read_submissions()

# Calculate Platform Health Metrics (Sidebar KPIs)
total_count = len(submissions)
awaiting_action_count = sum(1 for s in submissions if s["status"] in ("Awaiting human review", "Processing", "Action Required"))
approved_count = sum(1 for s in submissions if s["status"] == "Approved")

# Calculate Average Processing Time from seed/real audits
# Processing duration = difference between created_at and updated_at (or seed metrics)
durations = []
for s in submissions:
    try:
        c_time = datetime.strptime(s["created_at"], "%Y-%m-%d %H:%M:%S")
        u_time = datetime.strptime(s["updated_at"], "%Y-%m-%d %H:%M:%S")
        diff = (u_time - c_time).total_seconds()
        durations.append(diff)
    except Exception:
        continue
avg_duration_minutes = (sum(durations) / len(durations) / 60.0) if durations else 0.00

# Sidebar Controls & KPIs
st.sidebar.markdown(f"👤 Reviewer: **{st.session_state['reviewer_username']}**")
if st.sidebar.button("Secure Logout", use_container_width=True):
    logout_user()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Platform Health")
st.sidebar.metric("Total Submissions Registered", total_count)
st.sidebar.metric("Pending Attention Items", awaiting_action_count)
st.sidebar.metric("Average Processing Duration", f"{avg_duration_minutes:.1f} Mins")

# State tracking for evaluating items
if "selected_sub_id" not in st.session_state:
    st.session_state["selected_sub_id"] = None

# If no item selected, render Screen 5 & 6 (The Queue)
if not st.session_state["selected_sub_id"]:
    st.title("🛡️ Onboarding Review Queue")
    st.markdown("Assess incoming vendor registration compliance packets.")
    
    if not submissions:
        st.info("No vendor packets have been submitted yet.")
    else:
        # Construct Pandas Queue Dataframe for column-sorting mechanisms
        rows = []
        for s in submissions:
            # Count how many files out of 5 are uploaded
            docs = 0
            for doc_field in ["w9_filename", "coi_filename", "bank_letter_filename", "questionnaire_filename", "company_reg_filename"]:
                if s.get(doc_field):
                    docs += 1
                    
            # Calculate duration in queue or processing duration
            try:
                c_time = datetime.strptime(s["created_at"], "%Y-%m-%d %H:%M:%S")
                u_time = datetime.strptime(s["updated_at"], "%Y-%m-%d %H:%M:%S")
                duration_str = f"{(u_time - c_time).total_seconds() / 60.0:.1f}m"
            except Exception:
                duration_str = "N/A"
                
            # Extracted data structures parse
            try:
                extracted = json.loads(s["extracted_data"])
                # Overall average confidence from extracted W-9, COI, Bank, Questionnaire, Company Reg
                confidences = []
                for dkey in ["w9", "coi", "bank", "questionnaire", "company_reg"]:
                    ddata = extracted.get(dkey)
                    if ddata and "confidence" in ddata:
                        confidences.append(ddata["confidence"])
                avg_conf = f"{sum(confidences)/len(confidences):.0%}" if confidences else "N/A"
            except Exception:
                avg_conf = "N/A"
                
            # Get Risk recommendations
            reco = s.get("risk_recommendation", "N/A")
            
            rows.append({
                "Reference": s["submission_id"],
                "Vendor Legal Name": s["legal_name"],
                "Status": s["status"],
                "AI Recommendation": reco,
                "Duration": duration_str,
                "Docs Uploaded": f"{docs}/5",
                "AI Confidence": avg_conf,
                "Date": s["created_at"]
            })
            
        df = pd.DataFrame(rows)
        # Sort rows by newest items first (Date descending)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date", ascending=False)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # Display sorting queue
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Action selector mapping
        st.markdown("### 📋 Process Submission Details")
        selected_option = st.selectbox(
            "Select a submission from the ledger to inspect:",
            options=["-- Select --"] + [f"{s['submission_id']} - {s['legal_name']}" for s in submissions]
        )
        
        if selected_option != "-- Select --":
            sub_id = selected_option.split(" - ")[0]
            st.session_state["selected_sub_id"] = sub_id
            st.rerun()

# --- SCREEN 7: DEEP ANALYTICAL EVALUATION VIEW ---
else:
    sub_id = st.session_state["selected_sub_id"]
    sub = get_submission_by_id(sub_id)
    
    if not sub:
        st.error(f"Error fetching submission {sub_id}")
        if st.button("Return to Queue"):
            st.session_state["selected_sub_id"] = None
            st.rerun()
        st.stop()
        
    st.markdown(f"### Onboarding Packet Evaluation: {sub['legal_name']}")
    
    # -------------------------------------------------------------
    # STICKY EVALUATION HEADER CONTAINER (Review Actions)
    # -------------------------------------------------------------
    st.markdown('<div class="sticky-header">', unsafe_allow_html=True)
    
    header_cols = st.columns([2, 3])
    with header_cols[0]:
        st.markdown(
            f"""
            <h4 style="margin: 0; color: #0F2444;">ID: {sub['submission_id']}</h4>
            <div style="font-size: 0.9rem; color: #64748B;">
                Current Status: <span class="status-badge status-{sub['status'].lower().replace(' ', '')}">{sub['status']}</span>
            </div>
            """,
            unsafe_allow_html=True
        )
    with header_cols[1]:
        # Form buttons inside the header
        btn_cols = st.columns(4)
        with btn_cols[0]:
            approve_btn = st.button("Approve (A)", key="approve_btn_top", use_container_width=True)
        with btn_cols[1]:
            req_info_btn = st.button("Request Info (R)", key="req_info_btn_top", use_container_width=True)
        with btn_cols[2]:
            escalate_btn = st.button("Escalate (E)", key="escalate_btn_top", use_container_width=True)
        with btn_cols[3]:
            if st.button("Back to Queue", key="back_btn_top", use_container_width=True):
                st.session_state["selected_sub_id"] = None
                st.rerun()
                
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Inject JavaScript keyboard shortcuts mapping A, R, E to parent actions
    # This works by querying for buttons with specific labels and programmatically invoking click
    st.components.v1.html(
        """
        <script>
        const doc = window.parent.document;
        
        // Listen to parent DOM keypress events
        doc.addEventListener('keydown', function(event) {
            // Check active element is not a text input or textarea
            const activeTag = doc.activeElement ? doc.activeElement.tagName.toLowerCase() : '';
            if (activeTag === 'input' || activeTag === 'textarea') {
                return;
            }
            
            const key = event.key.toLowerCase();
            if (key === 'a') {
                // Click Approve button
                const btn = Array.from(doc.querySelectorAll('button')).find(el => el.textContent.includes('Approve (A)'));
                if (btn) btn.click();
            } else if (key === 'r') {
                // Click Request Info button
                const btn = Array.from(doc.querySelectorAll('button')).find(el => el.textContent.includes('Request Info (R)'));
                if (btn) btn.click();
            } else if (key === 'e') {
                // Click Escalate button
                const btn = Array.from(doc.querySelectorAll('button')).find(el => el.textContent.includes('Escalate (E)'));
                if (btn) btn.click();
            }
        });
        </script>
        """,
        height=0
    )
    
    # -------------------------------------------------------------
    # ACTION OVERLAY CONFIRMATION PANELS (Overlays triggered by buttons)
    # -------------------------------------------------------------
    # Render inline confirmation menus based on session state selection
    if "action_override" not in st.session_state:
        st.session_state["action_override"] = None
        
    if approve_btn:
        st.session_state["action_override"] = "approve"
    elif req_info_btn:
        st.session_state["action_override"] = "request_info"
    elif escalate_btn:
        st.session_state["action_override"] = "escalate"
        
    if st.session_state["action_override"] == "approve":
        st.markdown(
            """
            <div style="background-color: #E8F5E9; border: 1px solid #C8E6C9; padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem;">
                <h4 style="color: #2E7D32; margin-top:0;">Confirm Submission Approval</h4>
                <p style="color: #1B5E20; font-size: 0.95rem;">
                    Approving writes this company to the master vendor ledger, allocates a unique ERP key, and sends an authorization notification.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        erp_key = st.text_input("Assign ERP Vendor Key *", value=f"ERP-{sub['legal_name'][:4].upper()}-{sub['submission_id'][-3:]}").strip()
        comments = st.text_area("Reviewer Approval Comments", "Compliance package satisfies procurement policies.")
        
        o_col1, o_col2 = st.columns(2)
        with o_col1:
            if st.button("Confirm Approval", key="confirm_app_real", use_container_width=True):
                # Update status
                sub["status"] = "Approved"
                sub["erp_vendor_key"] = erp_key
                sub["reviewer_comments"] = comments
                sub["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                save_single_submission(sub)
                write_audit_log("human.approved", st.session_state["reviewer_username"], sub_id, f"Approved with ERP Key {erp_key}. Remarks: {comments}")
                
                # Dispatch approved email
                send_approved_email(sub["contact_email"], sub_id, sub["legal_name"], erp_key)
                
                st.session_state["action_override"] = None
                st.session_state["selected_sub_id"] = None
                st.success(f"Vendor Approved! ERP Key {erp_key} assigned.")
                st.rerun()
        with o_col2:
            if st.button("Cancel Action", key="cancel_app_real", use_container_width=True):
                st.session_state["action_override"] = None
                st.rerun()
                
    elif st.session_state["action_override"] == "request_info":
        st.markdown(
            """
            <div style="background-color: #FFF3E0; border: 1px solid #FFE0B2; padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem;">
                <h4 style="color: #E65100; margin-top:0;">Request Additional Information / Revisions</h4>
                <p style="color: #E65100; font-size: 0.95rem;">
                    Flagging revisions changes status to Action Required and alerts the contact details below with list items.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        deficiencies = st.text_area("Bullet index of deficiencies / requested items (e.g. W-9 signature missing, COI expired):")
        
        o_col1, o_col2 = st.columns(2)
        with o_col1:
            if st.button("Send Deficiencies Notice", key="confirm_req_real", use_container_width=True):
                # Update status
                sub["status"] = "Action Required"
                sub["reviewer_comments"] = deficiencies
                sub["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                save_single_submission(sub)
                write_audit_log("human.request_info", st.session_state["reviewer_username"], sub_id, f"Flagged deficiencies: {deficiencies}")
                
                # Split deficiencies text to list
                items_needed = [item.strip("- *• ") for item in deficiencies.split("\n") if item.strip()]
                if not items_needed:
                    items_needed = ["A reviewer requested revisions. Please check remarks."]
                    
                send_action_required_email(sub["contact_email"], sub_id, sub["legal_name"], items_needed)
                
                st.session_state["action_override"] = None
                st.session_state["selected_sub_id"] = None
                st.warning("Action Required notification dispatched.")
                st.rerun()
        with o_col2:
            if st.button("Cancel Action", key="cancel_req_real", use_container_width=True):
                st.session_state["action_override"] = None
                st.rerun()
                
    elif st.session_state["action_override"] == "escalate":
        st.markdown(
            """
            <div style="background-color: #FFEBEE; border: 1px solid #FFCDD2; padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem;">
                <h4 style="color: #C62828; margin-top:0;">Escalate Submission / Mark Review Complete</h4>
                <p style="color: #B71C1C; font-size: 0.95rem;">
                    Mark item as Rejected or escalate to supervisor panel reviews.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        comments = st.text_area("Escalation / Rejection Comments", "Packet possesses structural threats.")
        
        o_col1, o_col2 = st.columns(2)
        with o_col1:
            if st.button("Confirm Rejection", key="confirm_rej_real", use_container_width=True):
                sub["status"] = "Rejected"
                sub["reviewer_comments"] = comments
                sub["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                save_single_submission(sub)
                write_audit_log("human.rejected", st.session_state["reviewer_username"], sub_id, f"Rejected. Remarks: {comments}")
                
                st.session_state["action_override"] = None
                st.session_state["selected_sub_id"] = None
                st.error("Submission rejected.")
                st.rerun()
        with o_col2:
            if st.button("Cancel Action", key="cancel_rej_real", use_container_width=True):
                st.session_state["action_override"] = None
                st.rerun()

    # --- TELEMETRY AND ANALYSIS DETAILS (6 EXPANDER PANELS) ---
    
    # Load extracted data structures
    try:
        extracted = json.loads(sub["extracted_data"])
    except Exception:
        extracted = {}
        
    w9_data = extracted.get("w9", {})
    coi_data = extracted.get("coi", {})
    bank_data = extracted.get("bank", {})
    quest_data = extracted.get("questionnaire", {})
    company_reg_data = extracted.get("company_reg", {})

    # Expanders
    # Panel 1: Profile Fact Sheet
    with st.expander("📊 1. Profile Fact Sheet", expanded=True):
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            st.markdown("##### 🏢 Entity Details")
            st.markdown(f"**Legal Name:** {sub.get('legal_name')}")
            st.markdown(f"**Doing Business As (DBA):** {sub.get('dba_name') or 'N/A'}")
            st.markdown(f"**Company Website:** {sub.get('website') or 'N/A'}")
            st.markdown(f"**DUNS Number:** {sub.get('duns')}")
            st.markdown(f"**FEIN Number:** {sub.get('fein') or 'N/A'}")
            st.markdown(f"**Tax ID / GST Number:** {sub.get('tax_id_gst')}")
            st.markdown(f"**Tax Classification:** {sub.get('tax_classification') or 'N/A'}")
            st.markdown(f"**State of Incorporation:** {sub.get('state_of_incorporation') or 'N/A'}")
            st.markdown(f"**Headquarters Address:** {sub.get('company_street')}, {sub.get('company_city')}, {sub.get('company_state')} {sub.get('company_zip')}")
            st.markdown(f"**Billing Address:** {f'{sub.get('billing_street')}, {sub.get('billing_city')}, {sub.get('billing_state')} {sub.get('billing_zip')}' if sub.get('billing_street') else sub.get('company_address')}")
        with f_col2:
            st.markdown("##### 👤 Contact & Commercial Profile")
            st.markdown(f"**Primary Buyer Contact:** {sub.get('contact_name')} ({sub.get('contact_email')} / {sub.get('contact_phone')})")
            st.markdown(f"**Accounts Payable (AP) Contact:** {sub.get('ap_contact_name')} ({sub.get('ap_contact_email')} / {sub.get('ap_contact_phone')})")
            st.markdown(f"**Products / Services Offered:** {sub.get('products_services')}")
            st.markdown(f"**Years in Business:** {sub.get('years_in_business')} years")
            st.markdown(f"**Annual Revenue:** ${sub.get('annual_revenue_usd'):,}")
            st.markdown(f"**Employee Count:** {sub.get('employee_count')} workers")
            st.markdown(f"**Requested Payment Terms:** {sub.get('payment_terms')}")
            st.markdown(f"**Conflict of Interest Flagged:** {'⚠️ Yes' if sub.get('conflict_of_interest') else '✅ No'}")
            st.markdown(f"**Subject to Backup Withholding:** {'⚠️ Yes' if sub.get('backup_withholding') else '✅ No'}")
            st.markdown(f"**Eligible for 1099 Form:** {'🟢 Yes' if sub.get('is_1099_eligible') else '⚪ No'}")
            st.markdown(f"**Bank Beneficiary Name:** {sub.get('bank_beneficiary_name') or 'N/A'}")
            st.markdown(f"**SWIFT/BIC Code:** {sub.get('swift_bic') or 'N/A'}")

    # Panel 2: Document Parsing Tables
    with st.expander("🔍 2. Document Parsing Tables (Side-by-Side Verification)", expanded=False):
        st.markdown("Verify the parsed details from all uploaded files side-by-side:")
        
        # Side-by-side verification parameters dataframe
        parsing_rows = [
            {"Parameter": "Legal Entity Name", 
             "W-9 Extracted": w9_data.get("legalName") if w9_data else "N/A", 
             "COI Extracted": coi_data.get("insuredName") if coi_data else "N/A", 
             "Bank Extracted": bank_data.get("accountName") if bank_data else "N/A", 
             "Questionnaire Extracted": quest_data.get("legalName") if quest_data else "N/A",
             "Company Reg Extracted": company_reg_data.get("companyName") if company_reg_data else "N/A"},
            {"Parameter": "Doing Business As (DBA)",
             "W-9 Extracted": w9_data.get("dbaName") if w9_data else "N/A",
             "COI Extracted": "N/A", "Bank Extracted": "N/A",
             "Questionnaire Extracted": quest_data.get("dbaName") if quest_data else "N/A",
             "Company Reg Extracted": "N/A"},
            {"Parameter": "Tax ID / EIN / FEIN", 
             "W-9 Extracted": w9_data.get("ein") if w9_data else "N/A", 
             "COI Extracted": "N/A", "Bank Extracted": "N/A", 
             "Questionnaire Extracted": quest_data.get("fein") or quest_data.get("taxIdGst") if quest_data else "N/A",
             "Company Reg Extracted": company_reg_data.get("registrationNumber") if company_reg_data else "N/A"},
            {"Parameter": "Tax Classification", 
             "W-9 Extracted": w9_data.get("taxClassification") if w9_data else "N/A", 
             "COI Extracted": "N/A", "Bank Extracted": "N/A", 
             "Questionnaire Extracted": quest_data.get("taxClassification") if quest_data else "N/A",
             "Company Reg Extracted": "N/A"},
            {"Parameter": "State of Incorporation", 
             "W-9 Extracted": w9_data.get("stateOfIncorporation") if w9_data else "N/A", 
             "COI Extracted": "N/A", "Bank Extracted": "N/A", 
             "Questionnaire Extracted": quest_data.get("stateOfIncorporation") if quest_data else "N/A",
             "Company Reg Extracted": company_reg_data.get("jurisdiction") if company_reg_data else "N/A"},
            {"Parameter": "Bank Beneficiary Name", 
             "W-9 Extracted": "N/A", "COI Extracted": "N/A", 
             "Bank Extracted": bank_data.get("beneficiaryName") if bank_data else "N/A", 
             "Questionnaire Extracted": quest_data.get("bankBeneficiaryName") if quest_data else "N/A",
             "Company Reg Extracted": "N/A"},
            {"Parameter": "SWIFT / BIC Code", 
             "W-9 Extracted": "N/A", "COI Extracted": "N/A", 
             "Bank Extracted": bank_data.get("swiftBic") if bank_data else "N/A", 
             "Questionnaire Extracted": quest_data.get("swiftBic") if quest_data else "N/A",
             "Company Reg Extracted": "N/A"}
        ]
        pdf_df = pd.DataFrame(parsing_rows)
        st.table(pdf_df)

    # Panel 3: Completeness Card
    with st.expander("📈 3. Completeness Card", expanded=False):
        try:
            scores = json.loads(sub["document_scores"])
        except Exception:
            scores = {"w9": 0.0, "coi": 0.0, "bank": 0.0, "questionnaire": 0.0, "company_reg": 0.0}
            
        c_col1, c_col2 = st.columns([1, 2])
        with c_col1:
            st.markdown(
                f"""
                <div class="premium-card" style="text-align: center; border-left: 5px solid #0F2444;">
                    <h5 style="margin-top:0; color:#64748B;">AI Audit Score</h5>
                    <div style="font-size: 2.5rem; font-weight: bold; color: #0F2444;">{sub.get('overall_score'):.1f}%</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with c_col2:
            st.markdown(f"**W-9 Completion:** {scores.get('w9', 0.0)}% (Weights: Legal Name: 20, EIN: 25, Entity: 15, Address: 20, City: 10, State: 5, DBA: 5)")
            st.markdown(f"**COI Completion:** {scores.get('coi', 0.0)}% (Weights: Insured: 20, GL Limit: 25, Cyber: 15, Expiration: 25, Carrier: 15)")
            st.markdown(f"**Bank Letter Completion:** {scores.get('bank', 0.0)}% (Weights: Account Name: 20, Bank Name: 20, Routing: 20, Account Last 4: 20, Type: 5, SWIFT: 15)")
            st.markdown(f"**Questionnaire Completion:** {scores.get('questionnaire', 0.0)}% (Weights: Purchasing Contact: 15, AP Billing Contact: 15, Addresses: 30, Tax Info & Identifiers: 20, Commercial Profile & Declarations: 20)")
            st.markdown(f"**Company Registration Completion:** {scores.get('company_reg', 0.0)}% (Weights: Name: 40, Reg Number: 40, Reg Date: 20)")

    # Panel 4: Integrity Matrices
    with st.expander("⚖️ 4. Integrity Matrices (Consistency Checks)", expanded=False):
        try:
            checks = json.loads(sub["consistency_checks"])
        except Exception:
            checks = []
            
        if not checks:
            st.info("No consistency checks have been performed.")
        else:
            for chk in checks:
                status_icon = "✅ Passed" if chk["passed"] else "❌ Failed"
                color = "#16A34A" if chk["passed"] else "#EF4444"
                st.markdown(
                    f"""
                    <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 0.75rem; border-radius: 6px; margin-bottom: 0.5rem;">
                        <span style="font-weight: 600; color: #0F2444;">{chk['rule']}</span><br>
                        <span style="color: {color}; font-weight: 500;">{status_icon}</span> — <span style="color: #475569; font-size: 0.9rem;">{chk['details']}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    # Panel 5: Threat Matrices
    with st.expander("⚠️ 5. Threat Matrices (Flagged Risks)", expanded=False):
        try:
            flags = json.loads(sub["risk_flags"])
        except Exception:
            flags = {"high": [], "medium": []}
            
        high_list = flags.get("high", [])
        med_list = flags.get("medium", [])
        
        if not high_list and not med_list:
            st.success("✅ Zero risk markers identified in submission compliance materials.")
        else:
            if high_list:
                st.markdown("##### 🔴 High Risk Markers")
                for hr in high_list:
                    st.markdown(f"- **[HIGH]** {hr}")
            if med_list:
                st.markdown("##### 🟡 Medium Risk Markers")
                for mr in med_list:
                    st.markdown(f"- **[MEDIUM]** {mr}")

    # Panel 6: AI Pipeline Advice Wrap-up
    with st.expander("💡 6. AI Pipeline Advice Wrap-up", expanded=False):
        reco = sub.get("risk_recommendation", "escalate").upper()
        color = "#16A34A" if reco == "APPROVE" else "#F59E0B" if reco == "REQUEST_INFO" else "#EF4444"
        st.markdown(
            f"""
            <div class="premium-card" style="border-top: 4px solid {color};">
                <h5 style="margin-top:0; color: #0F2444;">System Recommendation Summary</h5>
                <p>AI Recommendation: <strong style="color: {color}; font-size: 1.1rem;">{reco}</strong></p>
                <p style="color: #475569; font-size: 0.95rem; line-height: 1.5;">
                    The analysis loop completed structured document extraction. The computed recommendations indicate: 
                    {f"The packet is clean with low risk profiles and completeness score >= 80%. System suggests instant Approval." if reco == "APPROVE" else 
                     f"Some files possess completeness scores < 80% or Medium Risk triggers exceed 2. System recommends requesting additional revisions." if reco == "REQUEST_INFO" else
                     "A High Risk indicator (PO-Box Address, EIN syntax failure, or a completely missing mandatory file) was triggered. Escalating for mandatory human reviewer override is enforced."}
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Display Submission Audit Trail
        st.markdown("<h5>Submission Audit Trail Log</h5>", unsafe_allow_html=True)
        logs = get_audit_logs(sub_id)
        if logs:
            log_df = pd.DataFrame(logs)
            log_df = log_df.rename(columns={"timestamp": "Time", "action": "Action", "username": "Actor", "details": "Details"})
            st.dataframe(log_df[["Time", "Action", "Actor", "Details"]], hide_index=True, use_container_width=True)

# Close desktop layout block
st.markdown('</div>', unsafe_allow_html=True)
