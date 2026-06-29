import streamlit as st

pg = st.navigation([
    st.Page("views/0_Home.py", title="Home", icon="🏠"),
    st.Page("views/1_Submit_Form.py", title="Submit Form", icon="📝"),
    st.Page("views/2_Track_Status.py", title="Track Status", icon="🔍")
])
pg.run()
