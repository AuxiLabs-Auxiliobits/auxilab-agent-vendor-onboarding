import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

# ── All config from .env ──────────────────────────────────────────
SMTP_SERVER           = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT             = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER             = os.getenv("SMTP_USER", "")
SMTP_PASSWORD         = os.getenv("SMTP_PASSWORD", "")
SENDER_EMAIL          = os.getenv("SENDER_EMAIL", "noreply@vendorgate.com")
SENIOR_AUDITOR_EMAIL  = os.getenv("SENIOR_AUDITOR_EMAIL", "senior.auditor@company.com")
REVIEWER_EMAIL        = os.getenv("REVIEWER_EMAIL", "reviewer@company.com")
APP_NAME              = os.getenv("APP_NAME", "VendorGate")
APP_SLA_HOURS         = int(os.getenv("APP_SLA_HOURS", "1"))


def log_simulated_email(subject, to_email, body):
    """
    Log email details to console and store them in Streamlit session state
    for visual testing inside the dashboard and submission screens.
    """
    print(f"\n================ [SIMULATED EMAIL SENT] ================")
    print(f"To: {to_email}")
    print(f"Subject: {subject}")
    print(f"Body:\n{body}")
    print(f"========================================================\n")
    
    # Store in session state for UI alerts
    if "email_inbox" not in st.session_state:
        st.session_state["email_inbox"] = []
    
    st.session_state["email_inbox"].append({
        "to": to_email,
        "subject": subject,
        "body": body
    })
    
    # Show toast in Streamlit if possible
    try:
        st.toast(f"📧 Notification email sent to {to_email}: {subject}")
    except Exception:
        pass

def send_email(to_email, subject, body_html, body_text):
    """Sends email via smtplib. Falls back to simulation if configuration is missing."""
    if not SMTP_USER or not SMTP_PASSWORD:
        # Fall back to simulation/logging if credentials are not configured
        log_simulated_email(subject, to_email, body_text)
        return True
        
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        
        part1 = MIMEText(body_text, "plain")
        part2 = MIMEText(body_html, "html")
        msg.attach(part1)
        msg.attach(part2)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        # Fall back to logging on error
        log_simulated_email(f"[ERROR-FALLBACK] {subject}", to_email, body_text)
        return False

def send_submission_received_email(to_email, submission_id, company_name):
    """Notify vendor that their submission was received."""
    subject = f"VendorGate Onboarding Received: {submission_id} - {company_name}"
    
    body_text = f"""Dear {company_name} team,

Your vendor onboarding packet has been successfully submitted to VendorGate.

Tracking Reference: {submission_id}
Estimated SLA: Under 1 Minute for automated review and reviewer assignment.

You can check the status of your packet at any time using the Tracking Lookup tool with your reference code.

Best regards,
Vendor Onboarding Team
VendorGate Portal
"""
    
    body_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
          <h2 style="color: #0F2444; border-bottom: 2px solid #0F2444; padding-bottom: 10px;">Submission Received</h2>
          <p>Dear {company_name} Team,</p>
          <p>Your vendor onboarding packet has been successfully submitted to VendorGate.</p>
          <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 5px 0;"><strong>Tracking Reference:</strong> <span style="font-family: monospace; font-size: 16px; color: #0F2444;">{submission_id}</span></p>
            <p style="margin: 5px 0;"><strong>Estimated Review SLA:</strong> Under 1 hour</p>
          </div>
          <p>You can check the status of your packet at any time using our status lookup page.</p>
          <br>
          <p style="font-size: 12px; color: #777; border-top: 1px solid #eee; padding-top: 10px;">
            This is an automated notification from VendorGate. Please do not reply directly to this email.
          </p>
        </div>
      </body>
    </html>
    """
    return send_email(to_email, subject, body_html, body_text)

def send_approved_email(to_email, submission_id, company_name, erp_vendor_key):
    """Notify vendor that their onboarding is approved and active in ERP."""
    subject = f"VendorGate Onboarding APPROVED: {company_name} (Ref: {submission_id})"
    
    body_text = f"""Dear {company_name} team,

We are pleased to inform you that your vendor onboarding packet has been approved.

Submission Reference: {submission_id}
Assigned ERP Vendor Key: {erp_vendor_key}

Your company is now active in our corporate ledger and eligible to receive purchase orders and process invoice payments.

Best regards,
Corporate Procurement
VendorGate Portal
"""
    
    body_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
          <h2 style="color: #2e7d32; border-bottom: 2px solid #2e7d32; padding-bottom: 10px;">Onboarding Approved</h2>
          <p>Dear {company_name} Team,</p>
          <p>We are pleased to inform you that your vendor onboarding packet has been approved.</p>
          <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 5px solid #2e7d32;">
            <p style="margin: 5px 0;"><strong>Submission Reference:</strong> <span style="font-family: monospace;">{submission_id}</span></p>
            <p style="margin: 5px 0;"><strong>ERP Vendor Key:</strong> <span style="font-family: monospace; font-weight: bold; color: #2e7d32;">{erp_vendor_key}</span></p>
          </div>
          <p>Your company is now active in our corporate ledger and eligible to receive purchase orders and process invoice payments.</p>
          <br>
          <p style="font-size: 12px; color: #777; border-top: 1px solid #eee; padding-top: 10px;">
            This is an automated notification from VendorGate. Please do not reply directly to this email.
          </p>
        </div>
      </body>
    </html>
    """
    return send_email(to_email, subject, body_html, body_text)

def send_action_required_email(to_email, submission_id, company_name, items_needed):
    """Notify vendor that revisions are required to proceed with onboarding."""
    subject = f"ACTION REQUIRED: VendorGate Onboarding Deficiencies - {company_name} ({submission_id})"
    
    bullets = "\n".join([f"- {item}" for item in items_needed])
    
    body_text = f"""Dear {company_name} team,

During the review of your vendor onboarding packet ({submission_id}), our reviewers flagged several deficiencies that require your attention:

{bullets}

Please log in to the status tracking portal using your reference code and upload the corrected documents or update the requested fields to resume processing.

Best regards,
Vendor Review Board
VendorGate Portal
"""
    
    html_bullets = "".join([f"<li style='margin-bottom: 8px;'>{item}</li>" for item in items_needed])
    body_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
          <h2 style="color: #F59E0B; border-bottom: 2px solid #F59E0B; padding-bottom: 10px;">Action Required</h2>
          <p>Dear {company_name} Team,</p>
          <p>During the review of your vendor onboarding packet (<strong>{submission_id}</strong>), our reviewers flagged deficiencies that require your attention:</p>
          
          <div style="background-color: #fffbeb; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 5px solid #F59E0B;">
            <p style="margin-top: 0; font-weight: bold; color: #B45309;">Please address the following items:</p>
            <ul style="padding-left: 20px; color: #78350F;">
              {html_bullets}
            </ul>
          </div>
          
          <p>Please log in to the status tracking portal using your reference code to resubmit or make adjustments.</p>
          <br>
          <p style="font-size: 12px; color: #777; border-top: 1px solid #eee; padding-top: 10px;">
            This is an automated notification from VendorGate. Please do not reply directly to this email.
          </p>
        </div>
      </body>
    </html>
    """
    return send_email(to_email, subject, body_html, body_text)
