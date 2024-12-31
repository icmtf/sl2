import streamlit as st

def validation_status_view():
    st.title("Validation Status")
    st.write("Select an option from the left menu to see detailed information.")
    
    st.header("Available validation options:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Schema Validation")
        st.write("Checking configuration schema validity.")
        
    with col2:
        st.subheader("Config Validation")
        st.write("Validation of configuration files.")