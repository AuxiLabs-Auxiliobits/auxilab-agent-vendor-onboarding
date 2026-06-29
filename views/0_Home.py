import streamlit as st
from utils.style_utils import inject_custom_css
from utils.data_manager import seed_database_if_empty

# Set Wide page layout config
st.set_page_config(
    page_title="VendorGate Onboarding Portal",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Seed database with initial reviewer and test records if missing
seed_database_if_empty()

# Inject custom premium CSS styling
inject_custom_css()

# Center minimal layout (~50% width) using column margins
left_spacer, center_col, right_spacer = st.columns([1, 2, 1])

with center_col:
    st.markdown(
        '<div class="landing-container" style="margin-top: 2rem;">'
        '<div style="font-size: 3.5rem; margin-bottom: 0.5rem;">🛡️</div>'
        '<h1 style="margin-bottom: 0.5rem; font-size: 2.5rem;">VendorGate</h1>'
        '<p style="color: #64748B; font-size: 1.15rem; margin-bottom: 2rem; font-weight: 500;">'
        'Enterprise-Grade Vendor Onboarding &amp; Verification Portal'
        '</p>'
        '<hr style="border: 0; border-top: 1px solid #E2E8F0; margin-bottom: 2rem;">'
        '<div style="text-align: left; margin-bottom: 2rem;">'
        '<h3 style="margin-bottom: 1rem; font-size: 1.5rem; color: #0F2444;">Establish Your Partnership</h3>'
        '<p style="color: #475569; line-height: 1.6; font-size: 1rem; margin-bottom: 1rem;">'
        'Welcome to the corporate procurement portal. To complete onboarding, vendors are required to submit key compliance documentation. Our system uses advanced AI validation to streamline and expedite review.'
        '</p>'
        '<p style="color: #475569; line-height: 1.6; font-size: 1rem;">'
        'Please prepare the following four mandatory files in PDF format:'
        '</p>'
        '<ul style="color: #475569; line-height: 1.6; font-size: 0.95rem; padding-left: 1.5rem;">'
        '<li><strong>W-9 Tax Form</strong> (Signed and dated within the current year)</li>'
        '<li><strong>Certificate of Insurance (COI)</strong> (General and cyber liability thresholds)</li>'
        '<li><strong>Official Bank Confirmation Letter</strong> (Specifying account and routing details)</li>'
        '<li><strong>Vendor Questionnaire</strong> (Contact and business operations overview)</li>'
        '</ul>'
        '</div>'
        '<div style="background-color: #F0FDF4; border: 1px solid #DCFCE7; padding: 1.2rem; border-radius: 8px; text-align: left; margin-bottom: 2.5rem; border-left: 5px solid #16A34A;">'
        '<h5 style="margin-top: 0; margin-bottom: 0.5rem; color: #14532D; font-size: 1.05rem;">⏱️ Express Review SLA</h5>'
        '<p style="margin: 0; font-size: 0.9rem; color: #166534; line-height: 1.5;">'
        'Once submitted, our deterministic AI verification pipeline parses your materials in <strong>under 1 hour</strong> (often under 60 seconds) to initiate internal approval.'
        '</p>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # CTA Buttons styled inside columns for high visual appeal
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        st.page_link(
            "views/1_Submit_Form.py",
            label="Begin Onboarding Submission",
            icon="📝",
            use_container_width=True
        )
    with btn_col2:
        st.page_link(
            "views/2_Track_Status.py",
            label="Track Existing Onboarding",
            icon="🔍",
            use_container_width=True
        )
