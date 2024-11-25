import streamlit as st
from views.global_overview import global_overview
from views.device_details import device_details_view
from views.backup_status.view import backup_status_view
from views.compliance_status.view import compliance_status_view

# Konfiguracja szerokości strony
st.set_page_config(layout="wide")

def main():
    st.title('CodeHorizon')
    
    # Menu nawigacyjne w pasku bocznym
    menu = ["Backup Status", "Device Details", "Global Overview", "Compliance Status"]
    choice = st.sidebar.radio("Navigation", menu)
    
    # Wyświetlanie odpowiedniego widoku
    if choice == "Global Overview":
        global_overview()
    elif choice == "Device Details":
        device_details_view()
    elif choice == "Backup Status":
        backup_status_view()
    elif choice == "Compliance Status":
        compliance_status_view()

if __name__ == "__main__":
    main()