import streamlit as st
from views.global_overview import global_overview
from views.device_details import device_details_view

# Konfiguracja szerokości strony
st.set_page_config(layout="wide")

def main():
    st.title('Network Devices Dashboard')
    
    # Menu nawigacyjne w pasku bocznym
    menu = ["Device Details", "Global Overview"]
    choice = st.sidebar.radio("Navigation", menu)
    
    # Wyświetlanie odpowiedniego widoku
    if choice == "Global Overview":
        global_overview()
    elif choice == "Device Details":
        device_details_view()

if __name__ == "__main__":
    main()