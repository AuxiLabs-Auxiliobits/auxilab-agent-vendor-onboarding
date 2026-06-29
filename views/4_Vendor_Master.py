import os
import json
import streamlit as st
import pandas as pd
from datetime import datetime, date
from dotenv import load_dotenv
load_dotenv()
from utils.style_utils import inject_custom_css
from utils.data_manager import read_submissions

# Config from .env
SYSTEM_DATE_STR = os.getenv("SYSTEM_DATE", datetime.now().strftime("%Y-%m-%d"))
SYSTEM_DATE = datetime.strptime(SYSTEM_DATE_STR, "%Y-%m-%d").date()
APP_NAME = os.getenv("APP_NAME", "VendorGate")

st.set_page_config(
    page_title="VendorGate Approved Vendor Ledger",
    page_icon="🗄️",
    layout="wide"
)

inject_custom_css()

st.title("🗄️ Master Approved Vendor Ledger")
st.markdown("Analytical ledger of all corporate entities authorized for active purchasing.")

submissions = read_submissions()

# Filter for approved vendors only
approved_vendors = [s for s in submissions if s["status"] == "Approved"]

if not approved_vendors:
    st.info("No approved vendors currently exist in the ledger.")
else:
    # High-level stats
    expiring_soon_count = 0
    expired_count = 0
    total_rev = 0
    
    rows = []
    for v in approved_vendors:
        # Parse insurance expiration
        expiry_date_str = "N/A"
        expiry_warning = "🟢 Active"
        days_left = None
        
        try:
            extracted = json.loads(v["extracted_data"])
            coi_expiry = extracted.get("coi", {}).get("earliestExpiryDate")
            if coi_expiry:
                expiry_date_str = coi_expiry
                clean_date = coi_expiry.split("T")[0].strip()
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
                    try:
                        exp_date = datetime.strptime(clean_date, fmt).date()
                        days_left = (exp_date - SYSTEM_DATE).days
                        break
                    except ValueError:
                        continue
        except Exception:
            pass
            
        if days_left is not None:
            if days_left < 0:
                expiry_warning = f"🔴 Expired ({abs(days_left)} days ago)"
                expired_count += 1
            elif days_left <= 60:
                expiry_warning = f"⚠️ Warning ({days_left} days left)"
                expiring_soon_count += 1
            else:
                expiry_warning = f"🟢 Active ({days_left} days left)"
        
        # Calculate total revenue
        rev = v.get("annual_revenue_usd")
        if rev:
            total_rev += int(rev)
            
        rows.append({
            "ERP Key": v.get("erp_vendor_key", "PENDING"),
            "Vendor Legal Name": v["legal_name"],
            "Contact Person": f"{v['contact_name']} ({v['contact_email']})",
            "Annual Revenue": f"${int(v['annual_revenue_usd']):,}" if v.get("annual_revenue_usd") else "N/A",
            "Insurance Expiry": expiry_date_str,
            "Insurance Status": expiry_warning,
            "Onboarded Date": v["created_at"].split()[0]
        })
        
    df = pd.DataFrame(rows)
    
    # Render KPI Cards
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Approved Vendor Count", len(approved_vendors))
    kpi2.metric("Insurance Expiries (Under 60 Days)", expiring_soon_count + expired_count, help="Includes expired and expiring soon")
    kpi3.metric("Total Active Portfolio Revenue", f"${total_rev:,}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Search Filter Mechanism
    search_query = st.text_input("Search Approved Ledger (by Company, ERP Key, or Contact Email):").strip().lower()
    
    if search_query:
        df_filtered = df[
            df["Vendor Legal Name"].str.lower().str.contains(search_query) |
            df["ERP Key"].str.lower().str.contains(search_query) |
            df["Contact Person"].str.lower().str.contains(search_query)
        ]
    else:
        df_filtered = df
        
    st.markdown("##### Approved Ledger Records")
    st.dataframe(df_filtered, hide_index=True, use_container_width=True)
    
    # Custom download button to export approved vendors
    csv_data = df_filtered.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Export Ledger to CSV",
        data=csv_data,
        file_name="vendor_master_ledger.csv",
        mime="text/csv",
    )
