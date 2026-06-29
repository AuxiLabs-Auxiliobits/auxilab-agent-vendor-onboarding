import streamlit as st

def inject_custom_css():
    """
    Injects global CSS to style the Streamlit app to look like a premium B2B SaaS portal.
    Applies Deep Navy (#0F2444) as primary and Warm Amber (#F59E0B) as risk/warning colors.
    """
    css = """
    <style>
        /* Import premium font */
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
        
        /* Apply premium font only — no background override */
        html, body, [class*="css"], .stApp {
            font-family: 'Outfit', sans-serif;
        }
        
        /* Hide default header and footer */
        header {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Headings — use Streamlit default colours */
        h1, h2, h3, h4, h5, h6 {
            font-weight: 600 !important;
        }
        
        /* Button styling - Premium Deep Navy */
        div.stButton > button {
            background-color: #0F2444 !important;
            color: white !important;
            border-radius: 8px !important;
            border: 1px solid #0F2444 !important;
            padding: 0.5rem 2.5rem !important;
            font-size: 1rem !important;
            font-weight: 500 !important;
            box-shadow: 0 4px 6px -1px rgba(15, 36, 68, 0.15), 0 2px 4px -1px rgba(15, 36, 68, 0.1);
            transition: all 0.2s ease-in-out;
            width: auto;
        }
        div.stButton > button:hover {
            background-color: #1e3a60 !important;
            border-color: #1e3a60 !important;
            color: white !important;
            transform: translateY(-1px);
            box-shadow: 0 10px 15px -3px rgba(15, 36, 68, 0.2), 0 4px 6px -2px rgba(15, 36, 68, 0.1);
        }
        
        /* Warning action buttons (Amber) */
        div.stButton > button.warning-btn {
            background-color: #F59E0B !important;
            border-color: #F59E0B !important;
            color: #0F2444 !important;
        }
        div.stButton > button.warning-btn:hover {
            background-color: #D97706 !important;
            border-color: #D97706 !important;
            color: white !important;
        }
        
        /* Cards styling with 8px radius and subtle shadow */
        .premium-card {
            background-color: white;
            border-radius: 8px;
            padding: 1.5rem;
            border: 1px solid #E2E8F0;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            margin-bottom: 1.5rem;
        }
        
        /* Risk Banner */
        .risk-banner-medium {
            background-color: #FEF3C7;
            color: #92400E;
            border-left: 5px solid #F59E0B;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            font-weight: 500;
        }
        .risk-banner-high {
            background-color: #FEE2E2;
            color: #991B1B;
            border-left: 5px solid #EF4444;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            font-weight: 500;
        }
        
        /* Status Badges */
        .status-badge {
            display: inline-block;
            padding: 0.35rem 0.75rem;
            font-size: 0.85rem;
            font-weight: 600;
            border-radius: 20px;
            text-align: center;
        }
        .status-processing { background-color: #DBEAFE; color: #1E40AF; }
        .status-awaiting { background-color: #FEF3C7; color: #92400E; }
        .status-approved { background-color: #D1FAE5; color: #065F46; }
        .status-action { background-color: #FFEDD5; color: #9A3412; }
        .status-rejected { background-color: #FEE2E2; color: #991B1B; }
        
        /* Step Wizard Tracker Bar */
        .wizard-container {
            display: flex;
            justify-content: space-between;
            margin-bottom: 2rem;
            position: relative;
            background-color: white;
            padding: 1.2rem;
            border-radius: 8px;
            border: 1px solid #E2E8F0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        }
        .wizard-step {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 25%;
            z-index: 2;
            text-align: center;
        }
        .wizard-step-circle {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background-color: #E2E8F0;
            color: #64748B;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            margin-bottom: 0.5rem;
            border: 2px solid #E2E8F0;
            transition: all 0.3s;
        }
        .wizard-step-active .wizard-step-circle {
            background-color: #0F2444;
            color: white;
            border-color: #0F2444;
            box-shadow: 0 0 0 4px rgba(15, 36, 68, 0.15);
        }
        .wizard-step-completed .wizard-step-circle {
            background-color: #16A34A;
            color: white;
            border-color: #16A34A;
        }
        .wizard-step-label {
            font-size: 0.8rem;
            font-weight: 500;
            color: #64748B;
        }
        .wizard-step-active .wizard-step-label {
            color: #0F2444;
            font-weight: 600;
        }
        .wizard-step-completed .wizard-step-label {
            color: #16A34A;
        }
        
        /* Centered landing page container */
        .landing-container {
            max-width: 700px;
            margin: auto;
            padding: 2.5rem;
            background-color: white;
            border-radius: 12px;
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05), 0 8px 10px -6px rgba(0,0,0,0.03);
            border: 1px solid #E2E8F0;
            margin-top: 3rem;
            text-align: center;
        }
        
        /* Sticky Header */
        .sticky-header {
            position: sticky;
            top: 0;
            padding: 1rem 0;
            z-index: 999;
            border-bottom: 2px solid #E2E8F0;
            margin-bottom: 1.5rem;
        }
        
        /* Responsive Mobile Check CSS Block */
        @media (max-width: 768px) {
            .desktop-only-content {
                display: none !important;
            }
            .mobile-warning-block {
                display: flex !important;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 80vh;
                text-align: center;
                padding: 2rem;
                background-color: white;
                border-radius: 8px;
                border: 2px dashed #F59E0B;
                margin: 2rem 1rem;
            }
        }
        @media (min-width: 769px) {
            .mobile-warning-block {
                display: none !important;
            }
        }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def render_mobile_warning():
    """Renders the mobile browser blockage warning overlay."""
    st.markdown(
        """
        <div class="mobile-warning-block">
            <span style="font-size: 3rem; margin-bottom: 1rem;">🖥️</span>
            <h3 style="color: #0F2444; margin-bottom: 0.5rem;">Desktop Interface Required</h3>
            <p style="color: #64748B; max-width: 320px;">
                The Reviewer Management Dashboard contains complex analytical evaluations. Please use a desktop browser.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
