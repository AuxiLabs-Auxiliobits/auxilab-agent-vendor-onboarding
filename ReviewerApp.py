import streamlit as st

pg = st.navigation([
    st.Page("views/3_Dashboard.py", title="Admin Dashboard", icon="📊"),
    st.Page("views/4_Vendor_Master.py", title="Vendor Master", icon="📋")
])
pg.run()
