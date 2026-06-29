import os
import json
import uuid
import re
from datetime import datetime
import streamlit as st
import sys
from utils.style_utils import inject_custom_css
from utils.data_manager import (
    save_single_submission,
    write_audit_log,
    get_submission_upload_path,
    read_submissions
)
from utils.pipeline import start_async_analysis
from utils.notifier import send_submission_received_email

# Set wide page configuration
st.set_page_config(
    page_title="VendorGate Onboarding Submission",
    page_icon="📋",
    layout="wide"
)

inject_custom_css()

# 1. Establish persistent draft ID using URL query parameters to survive tab refreshes
if "draft_id" in st.query_params:
    draft_id = st.query_params["draft_id"]
else:
    draft_id = f"draft-{uuid.uuid4().hex[:8]}"
    st.query_params["draft_id"] = draft_id

DRAFT_FILE = os.path.join("data", f"{draft_id}.json")

# Helper to load cache
def load_draft_cache():
    if os.path.exists(DRAFT_FILE):
        try:
            with open(DRAFT_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

# Helper to save cache
def save_draft_cache(data):
    os.makedirs("data", exist_ok=True)
    try:
        with open(DRAFT_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Failed to save draft cache: {e}")

# Load draft data
draft_data = load_draft_cache()

# 2. Form Data Persistence Layer (Avoids unmounting deletion issues in Streamlit)
if "form_data" not in st.session_state:
    st.session_state["form_data"] = {}
    defaults = {
        "legal_name": "", "dba_name": "", "website": "", "duns": "", "contact_name": "", "contact_email": "",
        "contact_phone": "", "ap_contact_name": "", "ap_contact_email": "", "ap_contact_phone": "",
        "company_address": "", 
        "company_street": "", "company_city": "", "company_state": "DE", "company_zip": "",
        "same_as_company_addr": True,
        "billing_street": "", "billing_city": "", "billing_state": "DE", "billing_zip": "",
        "tax_id_gst": "", "fein": "", "tax_classification": "LLC - C Corp", "state_of_incorporation": "DE",
        "backup_withholding": False, "is_1099_eligible": False,
        "products_services": "",
        "years_in_business": 2, "annual_revenue_usd": 100000, "employee_count": 5,
        "payment_terms": "Net 30", "conflict_of_interest": False, "references_count": 2,
        "bank_name": "", "routing_number": "", "account_number": "", "account_type": "Checking",
        "bank_beneficiary_name": "", "swift_bic": "",
        "terms_declared": False
    }
    for k, default_val in defaults.items():
        st.session_state["form_data"][k] = draft_data.get(k, default_val)
    # Load any previously uploaded filenames into form_data
    for file_key in ["w9_filename", "coi_filename", "bank_letter_filename", "questionnaire_filename", "company_reg_filename", "other_doc_1_filename", "other_doc_2_filename"]:
        if draft_data.get(file_key):
            st.session_state["form_data"][file_key] = draft_data[file_key]

if "step" not in st.session_state:
    st.session_state["step"] = draft_data.get("step", 1)

# Sync backup to current session_state keys before rendering widgets
for k, val in st.session_state["form_data"].items():
    st.session_state[k] = val

# Always re-sync uploaded file keys from disk cache on every run so that
# document status is correctly reflected even across page navigations/reruns.
for file_key in ["w9_filename", "coi_filename", "bank_letter_filename", "questionnaire_filename", "company_reg_filename", "other_doc_1_filename", "other_doc_2_filename"]:
    saved = draft_data.get(file_key, "")
    if saved:
        st.session_state["form_data"][file_key] = saved
        st.session_state[file_key] = saved

# Sync UI changes to local file cache
def update_cache():
    # If same billing address is checked, copy company address
    if st.session_state.get("same_as_company_addr"):
        st.session_state["billing_street"] = st.session_state.get("company_street", "")
        st.session_state["billing_city"] = st.session_state.get("company_city", "")
        st.session_state["billing_state"] = st.session_state.get("company_state", "DE")
        st.session_state["billing_zip"] = st.session_state.get("company_zip", "")

    # Sync company_address text representation
    c_street = st.session_state.get("company_street", "").strip()
    c_city = st.session_state.get("company_city", "").strip()
    c_state = st.session_state.get("company_state", "").strip()
    c_zip = st.session_state.get("company_zip", "").strip()
    if c_street or c_city or c_zip:
        st.session_state["company_address"] = f"{c_street}, {c_city}, {c_state} {c_zip}"

    # Sync current session_state widget values back to backing dictionary
    for k in st.session_state["form_data"].keys():
        if k in st.session_state:
            st.session_state["form_data"][k] = st.session_state[k]
            
    # Compile and save full cache file
    cache_data = {"step": st.session_state["step"]}
    for k, val in st.session_state["form_data"].items():
        cache_data[k] = val
    save_draft_cache(cache_data)

def render_wizard_bar(current_step):
    steps = ["Company Info", "Documents", "Banking", "Review & Submit"]
    html = '<div class="wizard-container">'
    for i, label in enumerate(steps, 1):
        status_class = ""
        if i < current_step:
            status_class = "wizard-step-completed"
        elif i == current_step:
            status_class = "wizard-step-active"
        else:
            status_class = "wizard-step-inactive"
        
        circle_content = "✓" if i < current_step else str(i)
        html += f'<div class="wizard-step {status_class}"><div class="wizard-step-circle">{circle_content}</div><div class="wizard-step-label">{label}</div></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def generate_next_submission_id():
    submissions = read_submissions()
    if not submissions:
        return "VND-2026-00001"
    
    nums = []
    for s in submissions:
        sub_id = s.get("submission_id", "")
        match = re.search(r"VND-2026-(\d+)", sub_id)
        if match:
            nums.append(int(match.group(1)))
            
    next_num = max(nums) + 1 if nums else 1
    return f"VND-2026-{next_num:05d}"

# Render Wizard Tracker
render_wizard_bar(st.session_state["step"])

# Submission Completed View (Screen 3)
if st.session_state.get("submitted", False):
    st.html(
        f"""
        <div class="landing-container" style="border-top: 5px solid #16A34A; margin-top: 1rem;">
            <div style="font-size: 4rem; color: #16A34A; margin-bottom: 1rem;">✅</div>
            <h2 style="color: #0F2444; margin-bottom: 0.5rem;">Submission Successful</h2>
            <p style="color: #64748B; font-size: 1.1rem; margin-bottom: 2rem;">
                Your vendor onboarding pack has been registered in our system.
            </p>

            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; text-align: left;">
                <p style="margin: 0 0 0.5rem 0; color: #475569;"><strong>Tracking Reference:</strong></p>
                <div style="font-family: monospace; font-size: 1.5rem; color: #0F2444; font-weight: bold; background-color: white; padding: 0.5rem 1rem; border-radius: 4px; border: 1px solid #CBD5E1; display: inline-block;">
                    {st.session_state.get('sub_ref_code')}
                </div>
                <p style="margin: 1.5rem 0 0.5rem 0; color: #475569;"><strong>Estimated Service Level Agreement:</strong></p>
                <p style="margin: 0; color: #0F2444; font-weight: 500;">
                    ⏳ Automated analysis completes under 1 minute. Reviewer action completes in under 1 hour.
                </p>
            </div>

            <p style="color: #475569; font-size: 0.95rem; margin-bottom: 2rem;">
                A receipt confirmation has been dispatched to <strong>{st.session_state.get('contact_email')}</strong>. Keep this tracking code to look up milestones.
            </p>
        </div>
        """
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Lookup Status Now"):
            st.switch_page("views/2_Track_Status.py")
    with col2:
        if st.button("Return to Home"):
            # Clear cache and go home
            if os.path.exists(DRAFT_FILE):
                try:
                    os.remove(DRAFT_FILE)
                except Exception:
                    pass
            st.query_params.clear()
            st.switch_page("views/0_Home.py")
            
    st.stop()

# --- STEP 1: COMPANY INFO ---
if st.session_state["step"] == 1:
    st.subheader("Step 1: US Company Profile & Operations")
    st.info("Input company characteristics and compliance details. Draft will autosave continuously.")
    
    # US States dropdown list
    us_states = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
                 "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
                 "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
                 "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
                 "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]
                 
    # Inline validation feedback variables
    duns_error = ""
    email_error = ""
    name_error = ""
    ap_email_error = ""
    fein_error = ""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🏢 Legal Entity Coordinates")
        legal_name = st.text_input(
            "Legal Business Name *",
            key="legal_name",
            on_change=update_cache
        )
        if not st.session_state["legal_name"].strip():
            name_error = "⚠️ Legal Business Name is required."
            st.caption(f"<span style='color: #EF4444;'>{name_error}</span>", unsafe_allow_html=True)
            
        dba_name = st.text_input(
            "Trade Name / DBA (Doing Business As) (Optional)",
            key="dba_name",
            on_change=update_cache
        )
        
        website = st.text_input(
            "Company Website URL *",
            key="website",
            on_change=update_cache
        )
        if not st.session_state["website"].strip():
            st.caption("<span style='color: #EF4444;'>⚠️ Company Website is required.</span>", unsafe_allow_html=True)

        duns = st.text_input(
            "DUNS Number (9 Digits) *",
            max_chars=9,
            key="duns",
            on_change=update_cache
        )
        if st.session_state["duns"] and not re.match(r"^\d{9}$", st.session_state["duns"]):
            duns_error = "⚠️ DUNS must be exactly 9 numeric digits."
            st.caption(f"<span style='color: #EF4444;'>{duns_error}</span>", unsafe_allow_html=True)
        elif not st.session_state["duns"]:
            duns_error = "⚠️ DUNS number is required."
            st.caption(f"<span style='color: #EF4444;'>{duns_error}</span>", unsafe_allow_html=True)
            
        fein = st.text_input(
            "Federal Employer Identification Number (FEIN/EIN/SSN) *",
            key="fein",
            on_change=update_cache
        )
        if st.session_state["fein"] and not re.match(r"^\d{2}-\d{7}$|^\d{9}$", st.session_state["fein"]):
            fein_error = "⚠️ FEIN must be in format XX-XXXXXXX or 9 digits."
            st.caption(f"<span style='color: #EF4444;'>{fein_error}</span>", unsafe_allow_html=True)
        elif not st.session_state["fein"]:
            fein_error = "⚠️ FEIN is required."
            st.caption(f"<span style='color: #EF4444;'>{fein_error}</span>", unsafe_allow_html=True)
            
        tax_id_gst = st.text_input(
            "Tax ID / State / GST Registration Number *",
            key="tax_id_gst",
            on_change=update_cache
        )
        if not st.session_state["tax_id_gst"].strip():
            st.caption("<span style='color: #EF4444;'>⚠️ Tax ID / Registration number is required.</span>", unsafe_allow_html=True)
            
        tax_classification = st.selectbox(
            "US Tax Classification *",
            ["Individual/Sole Proprietor", "C-Corporation", "S-Corporation", "Partnership", "Trust/Estate", "LLC - C Corp", "LLC - S Corp", "LLC - Partnership", "Single-Member LLC"],
            key="tax_classification",
            on_change=update_cache
        )
        
        state_of_incorporation = st.selectbox(
            "US State of Incorporation/Organization *",
            options=us_states,
            key="state_of_incorporation",
            on_change=update_cache
        )

        st.markdown("<br>##### 📍 Headquarters Address", unsafe_allow_html=True)
        company_street = st.text_input(
            "Street Address *",
            key="company_street",
            on_change=update_cache
        )
        company_city = st.text_input(
            "City *",
            key="company_city",
            on_change=update_cache
        )
        col_c_st, col_c_zip = st.columns(2)
        with col_c_st:
            company_state = st.selectbox(
                "State *",
                options=us_states,
                key="company_state",
                on_change=update_cache
            )
        with col_c_zip:
            company_zip = st.text_input(
                "ZIP Code *",
                key="company_zip",
                on_change=update_cache
            )
            
        st.markdown("<br>##### 📬 Billing Address", unsafe_allow_html=True)
        same_addr = st.checkbox(
            "Same as Company Address",
            key="same_as_company_addr",
            on_change=update_cache
        )
        
        if not same_addr:
            billing_street = st.text_input(
                "Billing Street Address *",
                key="billing_street",
                on_change=update_cache
            )
            billing_city = st.text_input(
                "Billing City *",
                key="billing_city",
                on_change=update_cache
            )
            col_b_st, col_b_zip = st.columns(2)
            with col_b_st:
                billing_state = st.selectbox(
                    "Billing State *",
                    options=us_states,
                    key="billing_state",
                    on_change=update_cache
                )
            with col_b_zip:
                billing_zip = st.text_input(
                    "Billing ZIP Code *",
                    key="billing_zip",
                    on_change=update_cache
                )

    with col2:
        st.markdown("#### 👤 Contact Points")
        st.markdown("##### Primary Purchasing Contact")
        contact_name = st.text_input(
            "Primary Contact Name *",
            key="contact_name",
            on_change=update_cache
        )
        if not st.session_state["contact_name"].strip():
            st.caption("⚠️ Contact name is required.")
            
        contact_email = st.text_input(
            "Primary Contact Email *",
            key="contact_email",
            on_change=update_cache
        )
        if st.session_state["contact_email"] and not re.match(r"^[\w\.\-]+@[\w\.\-]+\.\w+$", st.session_state["contact_email"]):
            email_error = "⚠️ Please supply a valid email address."
            st.caption(f"<span style='color: #EF4444;'>{email_error}</span>", unsafe_allow_html=True)
        elif not st.session_state["contact_email"]:
            email_error = "⚠️ Email is required."
            st.caption(f"<span style='color: #EF4444;'>{email_error}</span>", unsafe_allow_html=True)

        contact_phone = st.text_input(
            "Contact Phone Number *",
            key="contact_phone",
            on_change=update_cache
        )
        if not st.session_state["contact_phone"].strip():
            st.caption("<span style='color: #EF4444;'>⚠️ Contact Phone Number is required.</span>", unsafe_allow_html=True)
            
        st.markdown("##### Accounts Payable (AP) Billing Contact")
        ap_contact_name = st.text_input(
            "AP Contact Name *",
            key="ap_contact_name",
            on_change=update_cache
        )
        if not st.session_state["ap_contact_name"].strip():
            st.caption("⚠️ AP Contact Name is required.")
            
        ap_contact_email = st.text_input(
            "AP Contact Email *",
            key="ap_contact_email",
            on_change=update_cache
        )
        if st.session_state["ap_contact_email"] and not re.match(r"^[\w\.\-]+@[\w\.\-]+\.\w+$", st.session_state["ap_contact_email"]):
            ap_email_error = "⚠️ Please supply a valid email address."
            st.caption(f"<span style='color: #EF4444;'>{ap_email_error}</span>", unsafe_allow_html=True)
        elif not st.session_state["ap_contact_email"]:
            ap_email_error = "⚠️ AP Email is required."
            st.caption(f"<span style='color: #EF4444;'>{ap_email_error}</span>", unsafe_allow_html=True)

        ap_contact_phone = st.text_input(
            "AP Contact Phone Number *",
            key="ap_contact_phone",
            on_change=update_cache
        )
        if not st.session_state["ap_contact_phone"].strip():
            st.caption("<span style='color: #EF4444;'>⚠️ AP Contact Phone is required.</span>", unsafe_allow_html=True)

        st.markdown("#### ⚙️ Commercial Profile")
        payment_terms = st.selectbox(
            "Payment Terms Requested",
            ["Net 30", "Net 45", "Net 60", "Due on Receipt"],
            key="payment_terms",
            on_change=update_cache
        )
        
        products_services = st.text_area(
            "Products / Services Offered *",
            key="products_services",
            on_change=update_cache
        )
        if not st.session_state["products_services"].strip():
            st.caption("<span style='color: #EF4444;'>⚠️ Products / Services Offered is required.</span>", unsafe_allow_html=True)

        years_in_business = st.number_input(
            "Years in Business",
            min_value=0, max_value=100,
            key="years_in_business",
            on_change=update_cache
        )
        
        annual_revenue = st.number_input(
            "Annual Revenue (USD)",
            min_value=0, max_value=1000000000,
            step=10000,
            key="annual_revenue_usd",
            on_change=update_cache
        )
        
        employee_count = st.number_input(
            "Employee Count",
            min_value=1, max_value=100000,
            key="employee_count",
            on_change=update_cache
        )
        
        references_count = st.number_input(
            "Business References Count",
            min_value=0, max_value=20,
            key="references_count",
            on_change=update_cache
        )
        
        conflict = st.checkbox(
            "Declare potential conflict of interest with our employees",
            key="conflict_of_interest",
            on_change=update_cache
        )

        st.markdown("##### US Compliance Affirmations")
        backup_withholding = st.checkbox(
            "We are subject to Backup Withholding by the IRS",
            key="backup_withholding",
            on_change=update_cache
        )
        is_1099_eligible = st.checkbox(
            "Eligible for 1099 Form Reporting",
            key="is_1099_eligible",
            on_change=update_cache
        )
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Check billing address presence
    billing_address_valid = True
    if not st.session_state["same_as_company_addr"]:
        billing_address_valid = (
            st.session_state.get("billing_street", "").strip() != "" and
            st.session_state.get("billing_city", "").strip() != "" and
            st.session_state.get("billing_zip", "").strip() != ""
        )
        
    # Enable Next button only if inputs validate
    step1_valid = (
        st.session_state["legal_name"].strip() != "" and
        st.session_state["website"].strip() != "" and
        st.session_state["company_street"].strip() != "" and
        st.session_state["company_city"].strip() != "" and
        st.session_state["company_zip"].strip() != "" and
        billing_address_valid and
        re.match(r"^\d{9}$", st.session_state["duns"]) is not None and
        re.match(r"^\d{2}-\d{7}$|^\d{9}$", st.session_state["fein"]) is not None and
        st.session_state["tax_id_gst"].strip() != "" and
        st.session_state["contact_name"].strip() != "" and
        re.match(r"^[\w\.\-]+@[\w\.\-]+\.\w+$", st.session_state["contact_email"]) is not None and
        st.session_state["contact_phone"].strip() != "" and
        st.session_state["ap_contact_name"].strip() != "" and
        re.match(r"^[\w\.\-]+@[\w\.\-]+\.\w+$", st.session_state["ap_contact_email"]) is not None and
        st.session_state["ap_contact_phone"].strip() != "" and
        st.session_state["products_services"].strip() != ""
    )
    
    if st.button("Continue to Documents", disabled=not step1_valid):
        st.session_state["step"] = 2
        update_cache()
        st.rerun()

# --- STEP 2: DOCUMENTS UPLOAD ---
elif st.session_state["step"] == 2:
    st.subheader("Step 2: Upload Compliance Documentation")
    st.warning("Upload required documents. Formats restricted to PDF, PNG, JPG, JPEG, or TXT. Maximum file size: 200MB per file.")
    
    # Document Uploaders
    allowed_types = ["pdf", "png", "jpg", "jpeg", "txt"]
    w9_file = st.file_uploader("Upload W-9 Tax Form *", type=allowed_types, key="w9_uploader")
    coi_file = st.file_uploader("Upload Certificate of Insurance (COI) *", type=allowed_types, key="coi_uploader")
    bank_file = st.file_uploader("Upload Bank Verification Document (Cancelled Cheque/Bank Letter) *", type=allowed_types, key="bank_uploader")
    quest_file = st.file_uploader("Upload Signed Questionnaire *", type=allowed_types, key="quest_uploader")
    company_reg_file = st.file_uploader("Upload Company Registration Document *", type=allowed_types, key="company_reg_uploader")
    
    # Optional additional files
    st.markdown("##### Optional Additional Documents (Up to 2)")
    other_doc_1_file = st.file_uploader("Additional Document 1 (Optional)", type=allowed_types, key="other_doc_1_uploader")
    other_doc_2_file = st.file_uploader("Additional Document 2 (Optional)", type=allowed_types, key="other_doc_2_uploader")
    
    def save_draft_file(uploaded_file, file_key):
        """Save an uploaded file to disk and return (filename, is_new_upload)."""
        if uploaded_file is not None:
            # Validate size
            if uploaded_file.size > 200 * 1024 * 1024:
                st.error(f"File {uploaded_file.name} exceeds the 200MB limit.")
                return None, False
            path = get_submission_upload_path(draft_id, uploaded_file.name)
            with open(path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            # Store filename in draft data, form_data dict, and top-level session state for persistence
            draft_data[file_key] = uploaded_file.name
            st.session_state["form_data"][file_key] = uploaded_file.name
            st.session_state[file_key] = uploaded_file.name
            save_draft_cache(draft_data)
            return uploaded_file.name, True   # new file saved
        return draft_data.get(file_key, ""), False  # cached / not uploaded yet

    # Process uploaded files — only rerun when a genuinely new file was saved
    w9_name, w9_new = save_draft_file(w9_file, "w9_filename")
    coi_name, coi_new = save_draft_file(coi_file, "coi_filename")
    bank_name, bank_new = save_draft_file(bank_file, "bank_letter_filename")
    quest_name, quest_new = save_draft_file(quest_file, "questionnaire_filename")
    company_reg_name, company_reg_new = save_draft_file(company_reg_file, "company_reg_filename")
    other_doc_1_name, other_doc_1_new = save_draft_file(other_doc_1_file, "other_doc_1_filename")
    other_doc_2_name, other_doc_2_new = save_draft_file(other_doc_2_file, "other_doc_2_filename")

    pass

    # Read settled filenames from session state for display/logic
    w9_name = st.session_state.get('w9_filename', '')
    coi_name = st.session_state.get('coi_filename', '')
    bank_name = st.session_state.get('bank_letter_filename', '')
    quest_name = st.session_state.get('questionnaire_filename', '')
    company_reg_name = st.session_state.get('company_reg_filename', '')
    other_doc_1_name = st.session_state.get('other_doc_1_filename', '')
    other_doc_2_name = st.session_state.get('other_doc_2_filename', '')

    # Visual Upload Status feedback
    st.markdown("<br><h5>Upload Status Ledger</h5>", unsafe_allow_html=True)
    status_cols = st.columns(4)
    with status_cols[0]:
        st.markdown(f"**W-9:** {'🟢 Uploaded: ' + w9_name if w9_name else '🔴 Missing'}")
        st.markdown(f"**COI:** {'🟢 Uploaded: ' + coi_name if coi_name else '🔴 Missing'}")
    with status_cols[1]:
        st.markdown(f"**Bank Verification:** {'🟢 Uploaded: ' + bank_name if bank_name else '🔴 Missing'}")
        st.markdown(f"**Questionnaire:** {'🟢 Uploaded: ' + quest_name if quest_name else '🔴 Missing'}")
    with status_cols[2]:
        st.markdown(f"**Company Reg:** {'🟢 Uploaded: ' + company_reg_name if company_reg_name else '🔴 Missing'}")
    with status_cols[3]:
        st.markdown(f"**Other Doc 1:** {'🟢 Uploaded: ' + other_doc_1_name if other_doc_1_name else '⚪ Empty'}")
        st.markdown(f"**Other Doc 2:** {'🟢 Uploaded: ' + other_doc_2_name if other_doc_2_name else '⚪ Empty'}")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Previous Step"):
            st.session_state["step"] = 1
            update_cache()
            st.rerun()
    with col2:
        has_min_docs = bool(w9_name and coi_name and bank_name and quest_name and company_reg_name)
        btn_label = "Continue to Banking"
        if not has_min_docs:
            btn_label = "Continue (Upload W-9, COI, Bank, Questionnaire, Company Registration first)"
            
        if st.button(btn_label, disabled=not has_min_docs):
            st.session_state["step"] = 3
            update_cache()
            st.rerun()

# --- STEP 3: BANK DETAILS ---
elif st.session_state["step"] == 3:
    st.subheader("Step 3: Banking Information & Disclosures")
    
    st.markdown(
        """
        <div style="background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem; display: flex; align-items: center;">
            <div style="font-size: 1.5rem; margin-right: 0.75rem;">🔒</div>
            <div style="font-size: 0.85rem; color: #065F46; line-height: 1.4;">
                <strong>Secure Banking Gateway:</strong> Banking coordinates are encrypted in transit via TLS and persisted at rest under AES-256 standard encryption mechanisms, strictly adhering to Nacha compliance policies.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    col1, col2 = st.columns(2)
    with col1:
        bank_name = st.text_input(
            "Institution Bank Name *",
            key="bank_name",
            on_change=update_cache
        )
        
        routing_number = st.text_input(
            "9-Digit Routing Transit Number (ACH/Direct Deposit) *",
            max_chars=9,
            key="routing_number",
            on_change=update_cache
        )
        if st.session_state["routing_number"] and not re.match(r"^\d{9}$", st.session_state["routing_number"]):
            st.caption("<span style='color: #EF4444;'>⚠️ Routing number must be exactly 9 digits.</span>", unsafe_allow_html=True)

        swift_bic = st.text_input(
            "SWIFT / BIC Code (Required for International / Wire Transfers) *",
            key="swift_bic",
            on_change=update_cache
        )
        if st.session_state["swift_bic"] and not re.match(r"^[A-Z0-9]{8}$|^[A-Z0-9]{11}$", st.session_state["swift_bic"].upper()):
            st.caption("<span style='color: #EF4444;'>⚠️ SWIFT/BIC must be 8 or 11 alphanumeric characters.</span>", unsafe_allow_html=True)

    with col2:
        account_type = st.selectbox(
            "Account Designation *",
            ["Checking", "Savings", "Other"],
            key="account_type",
            on_change=update_cache
        )
        
        account_number = st.text_input(
            "Account Number *",
            type="password",
            key="account_number",
            on_change=update_cache
        )
        if st.session_state["account_number"] and not re.match(r"^\d{8,17}$", st.session_state["account_number"]):
            st.caption("<span style='color: #EF4444;'>⚠️ Account number must be between 8 and 17 digits.</span>", unsafe_allow_html=True)
            
        # Prefill beneficiary name if empty
        if not st.session_state.get("bank_beneficiary_name"):
            st.session_state["bank_beneficiary_name"] = st.session_state.get("legal_name", "")
            
        bank_beneficiary_name = st.text_input(
            "Bank Beneficiary Name (Account Holder Name) *",
            key="bank_beneficiary_name",
            on_change=update_cache
        )
        if not st.session_state["bank_beneficiary_name"].strip():
            st.caption("<span style='color: #EF4444;'>⚠️ Bank Beneficiary Name is required.</span>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Enable Next only if bank inputs are filled and validated
    swift_valid = True
    if st.session_state["swift_bic"]:
        swift_valid = re.match(r"^[A-Z0-9]{8}$|^[A-Z0-9]{11}$", st.session_state["swift_bic"].upper()) is not None
        
    bank_valid = (
        st.session_state["bank_name"].strip() != "" and
        re.match(r"^\d{9}$", st.session_state["routing_number"]) is not None and
        re.match(r"^\d{8,17}$", st.session_state["account_number"]) is not None and
        st.session_state["bank_beneficiary_name"].strip() != "" and
        swift_valid
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Previous Step"):
            st.session_state["step"] = 2
            update_cache()
            st.rerun()
    with col2:
        if st.button("Continue to Review", disabled=not bank_valid):
            st.session_state["step"] = 4
            update_cache()
            st.rerun()

# --- STEP 4: REVIEW & SUBMIT ---
elif st.session_state["step"] == 4:
    st.subheader("Step 4: Review Details & Authenticated Submission")
    st.info("Please audit all parameters below before completing submission.")
    
    # Read-only Summary Cards
    st.markdown("<h4>Onboarding Summary Overview</h4>", unsafe_allow_html=True)
    
    sum_col1, sum_col2 = st.columns(2)
    with sum_col1:
        st.markdown(
            f"""
            <div class="premium-card">
                <h5 style="margin-top: 0; color: #0F2444;">🏢 Entity Details</h5>
                <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
                    <tr><td style="padding: 4px 0; color: #64748B;">Company Legal Name:</td><td style="font-weight: 500;">{st.session_state['legal_name']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Doing Business As:</td><td style="font-weight: 500;">{st.session_state['dba_name'] or 'N/A'}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Company Website:</td><td style="font-weight: 500;">{st.session_state['website']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">DUNS Number:</td><td style="font-weight: 500;">{st.session_state['duns']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">FEIN:</td><td style="font-weight: 500;">{st.session_state['fein']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Tax ID / Registration:</td><td style="font-weight: 500;">{st.session_state['tax_id_gst']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Tax Classification:</td><td style="font-weight: 500;">{st.session_state['tax_classification']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">State of Incorporation:</td><td style="font-weight: 500;">{st.session_state['state_of_incorporation']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Company Address:</td><td style="font-weight: 500;">{st.session_state['company_address']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Billing Address:</td><td style="font-weight: 500;">{st.session_state['billing_street']}, {st.session_state['billing_city']}, {st.session_state['billing_state']} {st.session_state['billing_zip'] if not st.session_state['same_as_company_addr'] else st.session_state['company_address']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Years in Business:</td><td style="font-weight: 500;">{st.session_state['years_in_business']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Annual Revenue (USD):</td><td style="font-weight: 500;">${st.session_state['annual_revenue_usd']:,}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Employee Count:</td><td style="font-weight: 500;">{st.session_state['employee_count']}</td></tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Get uploaded files from draft data
        w9_n = st.session_state.get('w9_filename', '')
        coi_n = st.session_state.get('coi_filename', '')
        bank_n = st.session_state.get('bank_letter_filename', '')
        quest_n = st.session_state.get('questionnaire_filename', '')
        company_reg_n = st.session_state.get('company_reg_filename', '')
        other_1_n = st.session_state.get('other_doc_1_filename', '')
        other_2_n = st.session_state.get('other_doc_2_filename', '')
        
        st.markdown(
            f"""
            <div class="premium-card">
                <h5 style="margin-top: 0; color: #0F2444;">📁 Document Checklist</h5>
                <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
                    <tr><td style="padding: 4px 0; color: #64748B;">W-9 Form:</td><td style="font-weight: 500;">{'🟢 ' + w9_n if w9_n else '🔴 Missing'}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">COI Policy:</td><td style="font-weight: 500;">{'🟢 ' + coi_n if coi_n else '🔴 Missing'}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Bank Verification:</td><td style="font-weight: 500;">{'🟢 ' + bank_n if bank_n else '🔴 Missing'}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Questionnaire:</td><td style="font-weight: 500;">{'🟢 ' + quest_n if quest_n else '🔴 Missing'}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Company Registration:</td><td style="font-weight: 500;">{'🟢 ' + company_reg_n if company_reg_n else '🔴 Missing'}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Other Doc 1 (Opt):</td><td style="font-weight: 500;">{'🟢 ' + other_1_n if other_1_n else '⚪ Empty'}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Other Doc 2 (Opt):</td><td style="font-weight: 500;">{'🟢 ' + other_2_n if other_2_n else '⚪ Empty'}</td></tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True
        )
        
    with sum_col2:
        st.markdown(
            f"""
            <div class="premium-card">
                <h5 style="margin-top: 0; color: #0F2444;">👤 Contact Coordinates</h5>
                <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
                    <tr><td style="padding: 4px 0; color: #64748B;">Primary Contact Name:</td><td style="font-weight: 500;">{st.session_state['contact_name']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Primary Contact Email:</td><td style="font-weight: 500;">{st.session_state['contact_email']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Primary Contact Phone:</td><td style="font-weight: 500;">{st.session_state['contact_phone']}</td></tr>
                    <tr style="border-top: 1px solid #E2E8F0;"><td style="padding: 4px 0; color: #64748B; font-weight: bold;">AP Billing Contact Name:</td><td style="font-weight: 500;">{st.session_state['ap_contact_name']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">AP Billing Contact Email:</td><td style="font-weight: 500;">{st.session_state['ap_contact_email']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">AP Billing Contact Phone:</td><td style="font-weight: 500;">{st.session_state['ap_contact_phone']}</td></tr>
                    <tr style="border-top: 1px solid #E2E8F0;"><td style="padding: 4px 0; color: #64748B;">Payment Terms:</td><td style="font-weight: 500;">{st.session_state['payment_terms']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Conflict Declared:</td><td style="font-weight: 500;">{'⚠️ Yes' if st.session_state['conflict_of_interest'] else '✅ No'}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Products/Services:</td><td style="font-weight: 500;">{st.session_state['products_services']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Subject to Backup Withholding:</td><td style="font-weight: 500;">{'⚠️ Yes' if st.session_state['backup_withholding'] else '✅ No'}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">1099 Reportable:</td><td style="font-weight: 500;">{'🟢 Yes' if st.session_state['is_1099_eligible'] else '⚪ No'}</td></tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        mask_acc = f"•••• •••• •••• {st.session_state['account_number'][-4:]}" if len(st.session_state['account_number']) >= 4 else "••••"
        st.markdown(
            f"""
            <div class="premium-card">
                <h5 style="margin-top: 0; color: #0F2444;">🏦 Bank Account Target</h5>
                <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
                    <tr><td style="padding: 4px 0; color: #64748B;">Bank Name:</td><td style="font-weight: 500;">{st.session_state['bank_name']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Beneficiary Name:</td><td style="font-weight: 500;">{st.session_state['bank_beneficiary_name']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Routing Transit:</td><td style="font-weight: 500;">{st.session_state['routing_number']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Account Type:</td><td style="font-weight: 500;">{st.session_state['account_type']}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">Account Number:</td><td style="font-weight: 500; font-family: monospace;">{mask_acc}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748B;">SWIFT/BIC Code:</td><td style="font-weight: 500; font-family: monospace;">{st.session_state['swift_bic'] or 'N/A (US Domestic)'}</td></tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True
        )
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Require accuracy checkbox
    terms_declared = st.checkbox(
        "I declare under penalty of perjury that the information provided is true, accurate, and complete to the best of my knowledge.",
        key="terms_declared",
        on_change=update_cache
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Previous Step"):
            st.session_state["step"] = 3
            update_cache()
            st.rerun()
            
    with col2:
        submit_enabled = st.session_state["terms_declared"]
        if st.button("Submit Onboarding Packet", disabled=not submit_enabled):
            # Process final dispatch!
            sub_id = generate_next_submission_id()
            
            # Move draft uploads to final location
            draft_w9 = draft_data.get("w9_filename", "")
            draft_coi = draft_data.get("coi_filename", "")
            draft_bank = draft_data.get("bank_letter_filename", "")
            draft_quest = draft_data.get("questionnaire_filename", "")
            draft_company_reg = draft_data.get("company_reg_filename", "")
            draft_other_1 = draft_data.get("other_doc_1_filename", "")
            draft_other_2 = draft_data.get("other_doc_2_filename", "")
            
            # Helper to move file from draft folder to final submission folder
            def finalize_file(filename):
                if not filename:
                    return ""
                src_path = os.path.join("uploads", draft_id, filename)
                dest_dir = os.path.join("uploads", sub_id)
                dest_path = os.path.join(dest_dir, filename)
                if os.path.exists(src_path):
                    os.makedirs(dest_dir, exist_ok=True)
                    if os.path.exists(dest_path):
                        try:
                            os.remove(dest_path)
                        except Exception:
                            pass
                    os.rename(src_path, dest_path)
                return filename
                
            w9_final = finalize_file(draft_w9)
            coi_final = finalize_file(draft_coi)
            bank_final = finalize_file(draft_bank)
            quest_final = finalize_file(draft_quest)
            company_reg_final = finalize_file(draft_company_reg)
            other_1_final = finalize_file(draft_other_1)
            other_2_final = finalize_file(draft_other_2)
 
            # Clean up draft artifacts now that submission is complete
            draft_upload_dir = os.path.join("uploads", draft_id)
            try:
                if os.path.exists(draft_upload_dir):
                    os.rmdir(draft_upload_dir)
            except Exception:
                pass
            try:
                if os.path.exists(DRAFT_FILE):
                    os.remove(DRAFT_FILE)
            except Exception:
                pass
            
            # Construct submission record (expanded to match all 20 columns)
            submission_record = {
                "submission_id": sub_id,
                "legal_name": st.session_state["legal_name"],
                "dba_name": st.session_state["dba_name"],
                "website": st.session_state["website"],
                "duns": st.session_state["duns"],
                "contact_name": st.session_state["contact_name"],
                "contact_email": st.session_state["contact_email"],
                "contact_phone": st.session_state["contact_phone"],
                "ap_contact_name": st.session_state["ap_contact_name"],
                "ap_contact_email": st.session_state["ap_contact_email"],
                "ap_contact_phone": st.session_state["ap_contact_phone"],
                "company_address": st.session_state["company_address"],
                "company_street": st.session_state["company_street"],
                "company_city": st.session_state["company_city"],
                "company_state": st.session_state["company_state"],
                "company_zip": st.session_state["company_zip"],
                "billing_street": st.session_state["billing_street"],
                "billing_city": st.session_state["billing_city"],
                "billing_state": st.session_state["billing_state"],
                "billing_zip": st.session_state["billing_zip"],
                "tax_id_gst": st.session_state["tax_id_gst"],
                "fein": st.session_state["fein"],
                "tax_classification": st.session_state["tax_classification"],
                "state_of_incorporation": st.session_state["state_of_incorporation"],
                "backup_withholding": st.session_state["backup_withholding"],
                "is_1099_eligible": st.session_state["is_1099_eligible"],
                "products_services": st.session_state["products_services"],
                "years_in_business": st.session_state["years_in_business"],
                "annual_revenue_usd": st.session_state["annual_revenue_usd"],
                "employee_count": st.session_state["employee_count"],
                "payment_terms": st.session_state["payment_terms"],
                "conflict_of_interest": st.session_state["conflict_of_interest"],
                "references_count": st.session_state["references_count"],
                "bank_name": st.session_state["bank_name"],
                "routing_number": st.session_state["routing_number"],
                "account_number": st.session_state["account_number"],
                "account_type": st.session_state["account_type"],
                "bank_beneficiary_name": st.session_state["bank_beneficiary_name"],
                "swift_bic": st.session_state["swift_bic"],
                "w9_filename": w9_final,
                "coi_filename": coi_final,
                "bank_letter_filename": bank_final,
                "questionnaire_filename": quest_final,
                "company_reg_filename": company_reg_final,
                "other_doc_1_filename": other_1_final,
                "other_doc_2_filename": other_2_final,
                "status": "Processing",
                "overall_score": 0.0,
                "risk_recommendation": "",
                "risk_flags": "",
                "consistency_checks": "",
                "document_scores": "",
                "extracted_data": "",
                "reviewer_comments": "",
                "erp_vendor_key": "",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # 1. Save record in database
            save_single_submission(submission_record)
 
            # 1.5 Save questionnaire data as JSON in the vendor's upload folder (expanded mapping)
            questionnaire_data = {
                "legal_name": st.session_state["legal_name"],
                "dba_name": st.session_state["dba_name"],
                "website": st.session_state["website"],
                "duns": st.session_state["duns"],
                "contact_name": st.session_state["contact_name"],
                "contact_email": st.session_state["contact_email"],
                "contact_phone": st.session_state["contact_phone"],
                "ap_contact_name": st.session_state["ap_contact_name"],
                "ap_contact_email": st.session_state["ap_contact_email"],
                "ap_contact_phone": st.session_state["ap_contact_phone"],
                "company_street": st.session_state["company_street"],
                "company_city": st.session_state["company_city"],
                "company_state": st.session_state["company_state"],
                "company_zip": st.session_state["company_zip"],
                "company_address": st.session_state["company_address"],
                "billing_street": st.session_state["billing_street"],
                "billing_city": st.session_state["billing_city"],
                "billing_state": st.session_state["billing_state"],
                "billing_zip": st.session_state["billing_zip"],
                "tax_id_gst": st.session_state["tax_id_gst"],
                "fein": st.session_state["fein"],
                "tax_classification": st.session_state["tax_classification"],
                "state_of_incorporation": st.session_state["state_of_incorporation"],
                "backup_withholding_exempt": st.session_state["backup_withholding"],
                "is_1099_eligible": st.session_state["is_1099_eligible"],
                "products_services": st.session_state["products_services"],
                "years_in_business": st.session_state["years_in_business"],
                "annual_revenue_usd": st.session_state["annual_revenue_usd"],
                "employee_count": st.session_state["employee_count"],
                "payment_terms": st.session_state["payment_terms"],
                "conflict_of_interest": st.session_state["conflict_of_interest"],
                "references_count": st.session_state["references_count"],
                "bank_name": st.session_state["bank_name"],
                "routing_number": st.session_state["routing_number"],
                "account_number": st.session_state["account_number"],
                "account_type": st.session_state["account_type"],
                "bank_beneficiary_name": st.session_state["bank_beneficiary_name"],
                "swift_bic": st.session_state["swift_bic"]
            }
            
            vendor_upload_dir = os.path.join("uploads", sub_id)
            os.makedirs(vendor_upload_dir, exist_ok=True)
            quest_json_path = os.path.join(vendor_upload_dir, "questionnaire_data.json")
            try:
                with open(quest_json_path, "w", encoding="utf-8") as f:
                    json.dump(questionnaire_data, f, indent=4)
            except Exception as e:
                print(f"Failed to save questionnaire JSON: {e}")
 
            write_audit_log("submission.received", "system", sub_id, f"Onboarding packet submitted by vendor. Email: {st.session_state['contact_email']}")
            
            # 2. Trigger asynchronous analysis pipeline task
            start_async_analysis(submission_record)
 
            # 3. Trigger Standalone LangChain Extractor Agent in the background
            agent_script_path = os.path.join("agent", "extractor_agent.py")
            if os.path.exists(agent_script_path):
                import subprocess
                try:
                    subprocess.Popen(
                        [sys.executable, agent_script_path, sub_id],
                        stdout=sys.stdout,
                        stderr=sys.stderr
                    )
                except Exception as e:
                    print(f"Failed to spawn extractor agent: {e}")
            
            # 4. Dispatch Notification email
            send_submission_received_email(
                st.session_state["contact_email"],
                sub_id,
                st.session_state["legal_name"]
            )
            
            # Write system state success
            st.session_state["submitted"] = True
            st.session_state["sub_ref_code"] = sub_id
            st.rerun()
