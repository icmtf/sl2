import streamlit as st
from views.global_overview import global_overview
from views.device_details import device_details_view

# Configure page settings
st.set_page_config(
    layout="wide",
    page_title="Network Devices Dashboard",
    initial_sidebar_state="expanded"
)

# Initialize session state for callbacks
if 'callbacks_initialized' not in st.session_state:
    st.session_state.callbacks_initialized = False
    st.session_state.changed_hostname = None
    st.session_state.changed_value = False
    st.session_state.selected_devices = set()
    st.session_state.df = None
    st.session_state.sort_column = None
    st.session_state.sort_direction = None

def main():
    st.title('Network Devices Dashboard')
    
    # Navigation menu in sidebar
    menu = ["Device Details", "Global Overview"]
    choice = st.sidebar.radio("Navigation", menu)
    
    # Display appropriate view
    if choice == "Global Overview":
        global_overview()
    elif choice == "Device Details":
        device_details_view()

if __name__ == "__main__":
    main()