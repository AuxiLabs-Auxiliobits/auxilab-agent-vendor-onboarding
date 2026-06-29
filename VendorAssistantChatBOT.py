"""
VendorGate AI Assistant — Standalone Bot
Run with:  streamlit run VendorAssistantChatBOT.py
"""

import os
import sys
import json
import re
from datetime import datetime

# ── Ensure project root is on the path so utils/ can be imported ───────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import streamlit as st
from utils.data_manager import get_submission_by_id

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="VendorGate ChatBOT",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════════════════════
# CSS — Full premium dark-themed standalone design
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"], .stApp {
        font-family: 'Outfit', sans-serif;
        background-color: #0D1B2E;
    }

    header { visibility: hidden; }
    footer  { visibility: hidden; }

    /* All headings white in this app */
    h1, h2, h3, h4, h5, h6 {
        color: white !important;
        font-weight: 600 !important;
    }

    /* Streamlit section labels / small text */
    label, .stTextInput label, .stForm label {
        color: #CBD5E1 !important;
    }

    /* Inputs */
    .stTextInput input {
        background: #1E2D45 !important;
        color: #F1F5F9 !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
    .stTextInput input::placeholder {
        color: #64748B !important;
    }
    .stTextInput input:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.2) !important;
    }

    /* Buttons */
    div.stButton > button {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 1.5rem !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 8px rgba(99,102,241,0.3) !important;
    }
    div.stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 16px rgba(99,102,241,0.4) !important;
        background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
    }

    /* Form submit */
    div.stFormSubmitButton > button {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    div.stFormSubmitButton > button:hover {
        background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
        transform: translateY(-1px) !important;
    }

    /* Scrollable containers */
    [data-testid="stVerticalBlock"] {
        scrollbar-width: thin;
        scrollbar-color: #334155 #1E2D45;
    }

    /* ── Hero ───────────────────────────────────────────────────────────────── */
    .bot-hero {
        background: linear-gradient(135deg, #0F2444 0%, #1a1f3a 50%, #0d1b2e 100%);
        border-bottom: 1px solid #1E3A5F;
        padding: 1.8rem 2.5rem;
        display: flex;
        align-items: center;
        gap: 1.5rem;
        margin-bottom: 1.5rem;
        border-radius: 12px;
        position: relative;
        overflow: hidden;
    }
    .bot-hero::after {
        content: '';
        position: absolute;
        right: -60px; top: -60px;
        width: 240px; height: 240px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(99,102,241,0.12), transparent 70%);
    }
    .bot-hero::before {
        content: '';
        position: absolute;
        left: 40%; bottom: -80px;
        width: 300px; height: 300px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(139,92,246,0.07), transparent 70%);
    }
    .bot-hero-icon {
        width: 60px; height: 60px;
        border-radius: 16px;
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        display: flex; align-items: center; justify-content: center;
        font-size: 1.8rem;
        flex-shrink: 0;
        box-shadow: 0 8px 20px rgba(99,102,241,0.4);
        z-index: 1;
    }
    .bot-hero-text { z-index: 1; }
    .bot-hero-title {
        color: white !important;
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0 0 0.2rem 0;
        line-height: 1.2;
    }
    .bot-hero-sub {
        color: rgba(255,255,255,0.55);
        font-size: 0.88rem;
        margin: 0;
    }
    .bot-live-badge {
        margin-left: auto;
        background: rgba(74,222,128,0.15);
        border: 1px solid rgba(74,222,128,0.3);
        color: #4ade80;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        display: flex;
        align-items: center;
        gap: 0.4rem;
        z-index: 1;
        flex-shrink: 0;
    }
    .live-dot {
        width: 7px; height: 7px;
        border-radius: 50%;
        background: #4ade80;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(0.85); }
    }

    /* ── Status Card (left panel) ───────────────────────────────────────────── */
    .sc-card {
        background: #1E2D45;
        border: 1px solid #2D4A6B;
        border-radius: 12px;
        overflow: hidden;
        margin-bottom: 1rem;
    }
    .sc-header {
        background: linear-gradient(135deg, #0F2444, #1e3a60);
        padding: 1rem 1.25rem;
        border-bottom: 1px solid #2D4A6B;
    }
    .sc-body { padding: 1rem 1.25rem; }
    .sc-label { color: #64748B; font-size: 0.78rem; }
    .sc-value { color: #F1F5F9; font-size: 0.88rem; font-weight: 500; }

    /* Status pills */
    .pill {
        display: inline-flex; align-items: center; gap: 0.3rem;
        padding: 0.25rem 0.75rem;
        border-radius: 20px; font-size: 0.78rem; font-weight: 600;
    }
    .pill-approved   { background: rgba(22,163,74,0.2);  color: #4ade80; border: 1px solid rgba(22,163,74,0.3); }
    .pill-awaiting   { background: rgba(234,179,8,0.15); color: #fbbf24; border: 1px solid rgba(234,179,8,0.3); }
    .pill-action     { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
    .pill-processing { background: rgba(59,130,246,0.15); color: #60a5fa; border: 1px solid rgba(59,130,246,0.3); }
    .pill-rejected   { background: rgba(239,68,68,0.2);  color: #f87171; border: 1px solid rgba(239,68,68,0.35); }

    /* Score bar track */
    .score-track {
        height: 6px; background: #1a2d45;
        border-radius: 4px; overflow: hidden; margin-top: 0.4rem;
    }

    /* Doc rows */
    .doc-row {
        display: flex; align-items: center; gap: 0.6rem;
        padding: 0.45rem 0;
        border-bottom: 1px solid #1a2d45;
        font-size: 0.83rem; color: #CBD5E1;
    }
    .doc-row:last-child { border-bottom: none; }

    /* ── Chat panel ─────────────────────────────────────────────────────────── */
    .chat-panel {
        background: #1E2D45;
        border: 1px solid #2D4A6B;
        border-radius: 12px;
        overflow: hidden;
    }
    .chat-top-bar {
        background: linear-gradient(90deg, #0F2444, #1e3a60);
        padding: 1rem 1.5rem;
        display: flex; align-items: center; gap: 0.8rem;
        border-bottom: 1px solid #2D4A6B;
    }
    .chat-bot-avatar {
        width: 36px; height: 36px; border-radius: 50%;
        background: linear-gradient(135deg,#6366f1,#8b5cf6);
        display: flex; align-items: center; justify-content: center;
        font-size: 1rem; flex-shrink: 0;
    }

    /* Messages */
    .msg-user {
        display: flex; justify-content: flex-end; margin-bottom: 1rem;
    }
    .msg-user-bubble {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: white;
        padding: 0.7rem 1.05rem;
        border-radius: 18px 18px 4px 18px;
        max-width: 75%; font-size: 0.9rem; line-height: 1.5;
        box-shadow: 0 2px 10px rgba(99,102,241,0.3);
    }
    .msg-bot {
        display: flex; justify-content: flex-start;
        align-items: flex-start; gap: 0.55rem; margin-bottom: 1rem;
    }
    .msg-bot-av {
        width: 30px; height: 30px; border-radius: 50%;
        background: linear-gradient(135deg,#6366f1,#8b5cf6);
        display: flex; align-items: center; justify-content: center;
        font-size: 0.8rem; flex-shrink: 0; margin-top: 3px;
    }
    .msg-bot-bubble {
        background: #243850;
        color: #E2E8F0;
        padding: 0.7rem 1.05rem;
        border-radius: 18px 18px 18px 4px;
        max-width: 80%; font-size: 0.9rem; line-height: 1.6;
        border: 1px solid #2D4A6B;
    }
    .msg-ts {
        font-size: 0.66rem; color: #475569; margin-top: 0.2rem;
    }
    .msg-ts-r { text-align: right; }

    /* Empty state */
    .empty-state {
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; padding: 3.5rem 1rem; text-align: center;
    }
    .empty-icon { font-size: 3rem; margin-bottom: 1rem; opacity: 0.4; }

    /* Quick chips */
    .chip-label {
        font-size: 0.75rem; color: #475569;
        font-weight: 500; margin-bottom: 0.4rem;
    }

    /* Link form card */
    .link-card {
        background: #1E2D45;
        border: 1px solid #2D4A6B;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }

    /* Section labels */
    .section-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #4B6A8B;
        font-weight: 600;
        margin-bottom: 0.6rem;
    }

    /* Footer */
    .bot-footer {
        text-align: center;
        color: #334155;
        font-size: 0.75rem;
        padding: 1.5rem 0 0.5rem;
        border-top: 1px solid #1E2D45;
        margin-top: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def get_gemini_key() -> str | None:
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    # Read from agent/.env relative to project root
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("GEMINI_API_KEY"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        return parts[1].strip().strip('"').strip("'")
    return None


def build_context(sub: dict) -> str:
    lines = [
        "=== VENDOR APPLICATION CONTEXT ===",
        f"Submission ID   : {sub.get('submission_id','N/A')}",
        f"Legal Name      : {sub.get('legal_name','N/A')}",
        f"DBA Name        : {sub.get('dba_name','N/A')}",
        f"Website URL     : {sub.get('website','N/A')}",
        f"DUNS            : {sub.get('duns','N/A')}",
        f"FEIN Number     : {sub.get('fein','N/A')}",
        f"Tax Classific.  : {sub.get('tax_classification','N/A')}",
        f"State of Inc.   : {sub.get('state_of_incorporation','N/A')}",
        f"Backup Withhold.: {'Yes' if sub.get('backup_withholding') else 'No'}",
        f"1099 Eligible   : {'Yes' if sub.get('is_1099_eligible') else 'No'}",
        f"Contact         : {sub.get('contact_name','N/A')} <{sub.get('contact_email','N/A')}> ({sub.get('contact_phone','N/A')})",
        f"AP Contact      : {sub.get('ap_contact_name','N/A')} <{sub.get('ap_contact_email','N/A')}> ({sub.get('ap_contact_phone','N/A')})",
        f"HQ Address      : {sub.get('company_street','N/A')}, {sub.get('company_city','N/A')}, {sub.get('company_state','N/A')} {sub.get('company_zip','N/A')}",
        f"Billing Address : {sub.get('billing_street','N/A')}, {sub.get('billing_city','N/A')}, {sub.get('billing_state','N/A')} {sub.get('billing_zip','N/A')}" if sub.get('billing_street') else f"Billing Address : {sub.get('company_address','N/A')}",
        f"Years in Biz    : {sub.get('years_in_business','N/A')}",
        f"Annual Revenue  : ${int(sub['annual_revenue_usd']):,}" if sub.get('annual_revenue_usd') else "Annual Revenue  : N/A",
        f"Employees       : {sub.get('employee_count','N/A')}",
        f"Payment Terms   : {sub.get('payment_terms','N/A')}",
        f"Conflict of Int.: {sub.get('conflict_of_interest','N/A')}",
        f"References      : {sub.get('references_count','N/A')}",
        f"Current Status  : {sub.get('status','N/A')}",
        f"Compliance Score: {sub.get('overall_score','N/A')}%",
        f"Risk Rec.       : {sub.get('risk_recommendation','N/A')}",
        f"Bank Beneficiary: {sub.get('bank_beneficiary_name','N/A')}",
        f"SWIFT/BIC Code  : {sub.get('swift_bic','N/A')}",
        f"Submitted       : {sub.get('created_at','N/A')}",
        f"Last Updated    : {sub.get('updated_at','N/A')}",
        f"ERP Vendor Key  : {sub.get('erp_vendor_key','Not yet assigned')}",
        "",
        "--- UPLOADED DOCUMENTS ---",
        f"W-9 Form        : {'✓ ' + sub['w9_filename'] if sub.get('w9_filename') else '✗ MISSING'}",
        f"COI             : {'✓ ' + sub['coi_filename'] if sub.get('coi_filename') else '✗ MISSING'}",
        f"Bank Letter     : {'✓ ' + sub['bank_letter_filename'] if sub.get('bank_letter_filename') else '✗ MISSING'}",
        f"Questionnaire   : {'✓ ' + sub['questionnaire_filename'] if sub.get('questionnaire_filename') else '✗ MISSING'}",
        f"Company Reg     : {'✓ ' + sub['company_reg_filename'] if sub.get('company_reg_filename') else '✗ MISSING'}",
    ]
    try:
        rf = json.loads(sub.get("risk_flags", "{}"))
        high, med = rf.get("high", []), rf.get("medium", [])
        lines += ["", "--- RISK FLAGS ---",
                  f"HIGH ({len(high)}): " + ("; ".join(high) if high else "None"),
                  f"MEDIUM ({len(med)}): " + ("; ".join(med) if med else "None")]
    except Exception:
        pass
    try:
        checks = json.loads(sub.get("consistency_checks", "[]"))
        lines += ["", "--- CONSISTENCY CHECKS ---"]
        for c in checks:
            lines.append(f"{'✓ PASS' if c.get('passed') else '✗ FAIL'} | {c.get('rule','')}: {c.get('details','')}")
    except Exception:
        pass
    if sub.get("reviewer_comments"):
        lines += ["", "--- REVIEWER NOTES ---", sub["reviewer_comments"]]
    lines += ["", "==================================="]
    return "\n".join(lines)


def ask_gemini(api_key: str, system_prompt: str, history: list, user_msg: str) -> str:
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        contents = []
        for m in history:
            role = "user" if m["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=user_msg)]))

        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.4,
                max_output_tokens=1024
            )
        )
        return resp.text.strip()
    except Exception as e:
        return f"⚠️ Could not reach AI service. Please try again. (Detail: {str(e)[:120]})"


def pill(status: str) -> str:
    cfg = {
        "Approved":            ("pill-approved",   "✅"),
        "Awaiting human review":("pill-awaiting",  "⏳"),
        "Action Required":     ("pill-action",     "⚠️"),
        "Processing":          ("pill-processing", "🔄"),
        "Rejected":            ("pill-rejected",   "❌"),
    }
    cls, icon = cfg.get(status, ("pill-awaiting", "•"))
    return f'<span class="pill {cls}">{icon} {status}</span>'


def fmt_md(text: str) -> str:
    """Convert **bold** and `code` to inline HTML for safe rendering."""
    out = text.replace("\n", "<br>")
    out = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', out)
    out = re.sub(r'`(.*?)`', r'<code style="background:#1a2d45;padding:1px 5px;border-radius:4px;font-size:0.85em;color:#a5b4fc;">\1</code>', out)
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════════════════════
for k, v in [("bot_msgs", []), ("bot_sub_id", ""), ("bot_sub", None), ("bot_linked", False)]:
    if k not in st.session_state:
        st.session_state[k] = v


# ═══════════════════════════════════════════════════════════════════════════════
# HERO HEADER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="bot-hero" >
    <div class="bot-hero-icon">🤖</div>
    <div class="bot-hero-text">
        <div class="bot-hero-title">VendorGate AI Assistant</div>
        <div class="bot-hero-sub">Natural language queries about your vendor onboarding application · Powered by Gemini</div>
    </div>
    <div class="bot-live-badge">
        <div class="live-dot"></div>
        Live
    </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TWO-COLUMN LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════
left, right = st.columns([1, 1.85], gap="large")


# ──────────────────────────────────────────────────────────────────────────────
# LEFT — Application Lookup + Status Card
# ──────────────────────────────────────────────────────────────────────────────
with left:
    st.markdown('<div class="section-label">🔗 Link Your Application</div>', unsafe_allow_html=True)

    with st.form("link_form", clear_on_submit=False):
        ref_input = st.text_input(
            "Reference Code",
            value=st.session_state.bot_sub_id,
            placeholder="e.g. VND-2026-00001"
        )
        submitted = st.form_submit_button("Link Application →", use_container_width=True)

    if submitted and ref_input.strip():
        sub = get_submission_by_id(ref_input.strip())
        if sub:
            st.session_state.bot_sub_id = ref_input.strip()
            st.session_state.bot_sub    = sub
            st.session_state.bot_linked = True
            welcome = (
                f"👋 Hello, **{sub.get('contact_name','there')}**! "
                f"I've loaded your application for **{sub.get('legal_name','your company')}** "
                f"(Ref: `{sub['submission_id']}`).\n\n"
                f"Your current status is **{sub.get('status','N/A')}** with a compliance score of "
                f"**{sub.get('overall_score','N/A')}%**.\n\n"
                f"Ask me anything about your submission — documents, checks, risk flags, or next steps! 🚀"
            )
            st.session_state.bot_msgs = [{"role": "assistant", "content": welcome, "ts": datetime.now().strftime("%H:%M")}]
            st.rerun()
        else:
            st.error(f"❌ Reference `{ref_input.strip()}` not found. Please check and try again.")

    # Status card
    if st.session_state.bot_linked and st.session_state.bot_sub:
        sub = get_submission_by_id(st.session_state.bot_sub["submission_id"]) or st.session_state.bot_sub
        st.session_state.bot_sub = sub

        score = float(sub.get("overall_score", 0) or 0)
        bar_color = "#4ade80" if score >= 80 else "#fbbf24" if score >= 50 else "#f87171"

        st.markdown(f"""
        <div class="sc-card">
            <div class="sc-header">
                <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.1em;color:rgba(255,255,255,0.4);margin-bottom:0.25rem;">Linked Application</div>
                <div style="font-size:1rem;font-weight:700;color:white;margin-bottom:0.1rem;">{sub.get('legal_name','N/A')}</div>
                <div style="font-family:monospace;font-size:0.75rem;color:rgba(255,255,255,0.45);">{sub.get('submission_id','')}</div>
            </div>
            <div class="sc-body">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.8rem;">
                    <span class="sc-label">Status</span>
                    {pill(sub.get('status',''))}
                </div>
                <div style="margin-bottom:0.8rem;">
                    <div style="display:flex;justify-content:space-between;">
                        <span class="sc-label">Compliance Score</span>
                        <span style="color:#a5b4fc;font-weight:700;font-size:0.85rem;">{score:.1f}%</span>
                    </div>
                    <div class="score-track">
                        <div style="height:100%;width:{score}%;background:{bar_color};border-radius:4px;"></div>
                    </div>
                </div>
                <div style="font-size:0.78rem;font-weight:600;color:#6366f1;margin-bottom:0.5rem;margin-top:0.8rem;">📎 Documents</div>
        """, unsafe_allow_html=True)

        docs = [
            ("W-9 Tax Form",       sub.get("w9_filename")),
            ("Certificate of Ins.",sub.get("coi_filename")),
            ("Bank Letter",        sub.get("bank_letter_filename")),
            ("Questionnaire",      sub.get("questionnaire_filename")),
        ]
        rows = ""
        for label, fname in docs:
            icon  = "✅" if fname else "❌"
            color = "#4ade80" if fname else "#f87171"
            rows += f'<div class="doc-row"><span style="color:{color}">{icon}</span><span>{label}</span></div>'

        st.markdown(f"""
                {rows}
                <div style="height:1px;background:#1a2d45;margin:0.8rem 0;"></div>
                <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;">
                    <span class="sc-label">Submitted</span>
                    <span class="sc-value">{str(sub.get('created_at',''))[:10]}</span>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span class="sc-label">Last Updated</span>
                    <span class="sc-value">{str(sub.get('updated_at',''))[:16]}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Risk banner
        try:
            rf = json.loads(sub.get("risk_flags", "{}"))
            high, med = rf.get("high", []), rf.get("medium", [])
            total = len(high) + len(med)
            if total:
                st.markdown(f"""
                <div style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.25);border-left:4px solid #f59e0b;border-radius:8px;padding:0.7rem 1rem;margin-top:0.6rem;">
                    <div style="font-weight:600;color:#fbbf24;font-size:0.83rem;margin-bottom:0.15rem;">⚠️ {total} Issue{'s' if total>1 else ''} Found</div>
                    <div style="color:#92400e;font-size:0.77rem;color:#d97706;">{len(high)} high-risk · {len(med)} medium-risk</div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="background:rgba(74,222,128,0.1);border:1px solid rgba(74,222,128,0.25);border-left:4px solid #4ade80;border-radius:8px;padding:0.7rem 1rem;margin-top:0.6rem;">
                    <div style="font-weight:600;color:#4ade80;font-size:0.83rem;">✅ No Risk Flags</div>
                    <div style="color:#86efac;font-size:0.77rem;">All automated checks passed.</div>
                </div>""", unsafe_allow_html=True)
        except Exception:
            pass

        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 Refresh", use_container_width=True):
                fresh = get_submission_by_id(sub["submission_id"])
                if fresh:
                    st.session_state.bot_sub = fresh
                st.rerun()
        with c2:
            if st.button("🔓 Unlink", use_container_width=True):
                for k in ["bot_linked", "bot_sub", "bot_sub_id", "bot_msgs"]:
                    st.session_state[k] = False if k == "bot_linked" else (None if k == "bot_sub" else ("" if k == "bot_sub_id" else []))
                st.rerun()
    else:
        st.markdown("""
        <div style="background:#1E2D45;border:2px dashed #2D4A6B;border-radius:12px;padding:2rem;text-align:center;margin-top:0.5rem;">
            <div style="font-size:2rem;margin-bottom:0.6rem;opacity:0.4;">📋</div>
            <div style="color:#64748B;font-size:0.85rem;font-weight:500;">No application linked</div>
            <div style="color:#334155;font-size:0.77rem;margin-top:0.3rem;">Enter your reference code above</div>
        </div>
        """, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# RIGHT — Chat Interface
# ──────────────────────────────────────────────────────────────────────────────
with right:
    st.markdown('<div class="section-label">💬 AI Assistant Chat</div>', unsafe_allow_html=True)

    # Chat top bar
    if st.session_state.bot_linked and st.session_state.bot_sub:
        ctx_label = f"Context loaded: {st.session_state.bot_sub.get('legal_name','your application')}"
    else:
        ctx_label = "Link an application to enable AI responses"

    st.markdown(f"""
    <div class="chat-top-bar">
        <div class="chat-bot-avatar">🤖</div>
        <div>
            <div style="color:white;font-weight:600;font-size:0.95rem;">
                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#4ade80;margin-right:6px;box-shadow:0 0 0 3px rgba(74,222,128,0.2);"></span>
                VendorGate Assistant
            </div>
            <div style="color:rgba(255,255,255,0.45);font-size:0.76rem;">{ctx_label}</div>
        </div>
        <div style="margin-left:auto;font-size:0.7rem;color:rgba(255,255,255,0.3);">AI Powered Chat BOT</div>
    </div>
    """, unsafe_allow_html=True)

    # Message display
    msg_area = st.container(height=440)
    with msg_area:
        if not st.session_state.bot_msgs:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-icon">💬</div>
                <div style="color:#475569;font-size:0.93rem;font-weight:600;margin-bottom:0.4rem;">No messages yet</div>
                <div style="color:#334155;font-size:0.8rem;max-width:260px;line-height:1.5;">
                    Link your application on the left, then ask me anything about your onboarding status.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for m in st.session_state.bot_msgs:
                ts = m.get("ts", "")
                if m["role"] == "user":
                    st.markdown(f"""
                    <div class="msg-user">
                        <div>
                            <div class="msg-user-bubble">{m["content"]}</div>
                            <div class="msg-ts msg-ts-r">{ts}</div>
                        </div>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="msg-bot">
                        <div class="msg-bot-av">🤖</div>
                        <div>
                            <div class="msg-bot-bubble">{fmt_md(m["content"])}</div>
                            <div class="msg-ts">{ts}</div>
                        </div>
                    </div>""", unsafe_allow_html=True)

    # Quick question chips
    quick_trigger = None
    if st.session_state.bot_linked:
        st.markdown('<div class="chip-label">💡 Quick questions</div>', unsafe_allow_html=True)
        chips = [
            "What is my current status?",
            "What documents are missing?",
            "What checks failed?",
            "What are my next steps?",
            "Explain my compliance score",
            "Are there any risk flags?",
        ]
        cols = st.columns(3)
        for i, col in enumerate(cols):
            for j in range(2):
                idx = i * 2 + j
                if idx < len(chips):
                    with col:
                        if st.button(chips[idx], key=f"chip_{idx}", use_container_width=True):
                            quick_trigger = chips[idx]

    # Input form
    disabled = not st.session_state.bot_linked
    ph = "Type your question..." if st.session_state.bot_linked else "Link your application first..."
    with st.form("chat_form", clear_on_submit=True):
        ic1, ic2 = st.columns([5, 1])
        with ic1:
            user_input = st.text_input("msg", label_visibility="collapsed", placeholder=ph, disabled=disabled)
        with ic2:
            send = st.form_submit_button("Send ➤", use_container_width=True, disabled=disabled)

    # Process
    final_msg = (user_input.strip() if send and user_input and user_input.strip() else None) or quick_trigger

    if final_msg and st.session_state.bot_linked and st.session_state.bot_sub:
        api_key = get_gemini_key()
        ts_now  = datetime.now().strftime("%H:%M")

        st.session_state.bot_msgs.append({"role": "user", "content": final_msg, "ts": ts_now})

        if not api_key:
            reply = (
                "⚠️ **No Gemini API key found.** Please set `GEMINI_API_KEY` in your environment "
                "or in `agent/.env` and restart the app."
            )
        else:
            sub     = st.session_state.bot_sub
            context = build_context(sub)
            sys_prompt = (
                "You are VendorGate AI Assistant, a professional and empathetic chatbot embedded in an "
                "enterprise vendor onboarding portal.\n\n"
                "RULES:\n"
                "- Only use data from the provided context. Never fabricate scores, dates, or statuses.\n"
                "- Be concise (under 200 words unless detail is requested). Use bullet points and bold.\n"
                "- If the question is outside your context, say so and suggest contacting the procurement team.\n"
                "- Be warm and helpful — the vendor is trying to complete their registration.\n"
                f"- Today's date: {datetime.now().strftime('%Y-%m-%d')}.\n\n"
                f"{context}"
            )
            history = [{"role": m["role"], "content": m["content"]}
                       for m in st.session_state.bot_msgs[:-1][-20:]]
            reply = ask_gemini(api_key, sys_prompt, history, final_msg)

        st.session_state.bot_msgs.append({"role": "assistant", "content": reply, "ts": datetime.now().strftime("%H:%M")})
        st.rerun()

    # Clear chat
    if st.session_state.bot_msgs:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑️ Clear Chat", use_container_width=False):
            st.session_state.bot_msgs = []
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="bot-footer">
    🔒 Your data is processed securely · Powered by Gemini 2.5 Flash ·
    For urgent matters contact your procurement coordinator
</div>
""", unsafe_allow_html=True)
