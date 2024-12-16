import streamlit as st
from streamlit_option_menu import option_menu
from views.backup_status.view import backup_status_view
from views.compliance_status.view import compliance_status_view
from views.device_details import device_details_view
from views.global_overview import global_overview

def main():
    # Set page config
    st.set_page_config(page_title="CodeHorizon", layout="wide")
    
    # Initialize session state if doesn't exist
    if 'current_menu' not in st.session_state:
        st.session_state['current_menu'] = 'Compliance Status'
    
    # Horizontal menu using streamlit-option-menu
    selected_menu = option_menu(
        menu_title=None,
        options=["Compliance Status", "Remote Access Status"],
        icons=["shield-check", "pc-display"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "#1e1e1e"},
            "icon": {"color": "#2196F3", "font-size": "25px"},
            "nav-link": {
                "font-size": "25px",
                "text-align": "center",
                "margin": "0px",
                "--hover-color": "#333",
                "color": "#666",
            },
            "nav-link-selected": {
                "background-color": "#1A1A1A",  # Ciemniejszy kolor tła dla aktywnego elementu
                "color": "#2196F3",  # Ten sam niebieski co ikony
            }
        }
    )
    
    # Update current menu in session state
    st.session_state['current_menu'] = selected_menu
    
    # Sidebar menu based on main selection using streamlit-option-menu
    if st.session_state['current_menu'] == "Compliance Status":
        with st.sidebar:
            compliance_menu = option_menu(
                menu_title="Compliance Views",
                options=["Backup Status", "Compliance Status"],
                icons=["hdd", "shield"],
                default_index=0,
                styles={
                    "container": {"padding": "5!important", "background-color": "#1e1e1e"},
                    "icon": {"color": "#2196F3", "font-size": "15px"},
                    "nav-link": {
                        "font-size": "16px",
                        "text-align": "left",
                        "margin": "0px",
                        "--hover-color": "#333",
                        "color": "#666",
                    },
                    "nav-link-selected": {
                        "background-color": "#1A1A1A",  # Ciemniejszy kolor tła dla aktywnego elementu
                        "color": "#2196F3",  # Ten sam niebieski co ikony
                    }
                }
            )
            
        # Content for compliance views
        if compliance_menu == "Backup Status":
            backup_status_view()
        elif compliance_menu == "Compliance Status":
            compliance_status_view()
            
    else:  # Remote Access Status menu
        with st.sidebar:
            remote_menu = option_menu(
                menu_title="Remote Access Views",
                options=["Global Overview", "Device Details"],
                icons=["globe", "pc"],
                default_index=0,
                styles={
                    "container": {"padding": "5!important", "background-color": "#1e1e1e"},
                    "icon": {"color": "#2196F3", "font-size": "15px"},
                    "nav-link": {
                        "font-size": "16px",
                        "text-align": "left",
                        "margin": "0px",
                        "--hover-color": "#333",
                        "color": "#666",
                    },
                    "nav-link-selected": {
                        "background-color": "#1A1A1A",  # Ciemniejszy kolor tła dla aktywnego elementu
                        "color": "#2196F3",  # Ten sam niebieski co ikony
                    }
                }
            )
        
        # Content for remote access views
        if remote_menu == "Global Overview":
            global_overview()
        elif remote_menu == "Device Details":
            device_details_view()

if __name__ == "__main__":
    main()