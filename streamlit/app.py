import streamlit as st
from streamlit_option_menu import option_menu
from views.backup_status.view import backup_status_view
from views.operational_status.view import compliance_status_view as operational_status_view
from views.validation_status.view import validation_status_view
from views.validation_status.cisco import cisco_validation_status_view
from views.validation_status.fortinet import fortinet_validation_status_view
from views.remote_access.page1 import remote_access_page1
from views.remote_access.page2 import remote_access_page2
from views.global_overview import global_overview

def main():
    st.set_page_config(page_title="CodeHorizon", layout="wide")
    
    # Main horizontal menu
    main_selected = option_menu(
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
                "background-color": "#1A1A1A",
                "color": "#2196F3",
            }
        }
    )
    
    if main_selected == "Compliance Status":
        with st.sidebar:
            # CSS for side menu
            st.markdown("""
                <style>
                div[data-testid="stVerticalBlock"] div:has(div.stButton) {padding: 0;}
                </style>
            """, unsafe_allow_html=True)

            # Main side menu
            compliance_selected = option_menu(
                menu_title="Compliance Views",
                options=["Backup Status", "Operational Status", "Validation Status", "Global Overview [WiP]"],
                icons=["hdd", "shield", "check-circle", "globe"],
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
                        "background-color": "#1A1A1A",
                        "color": "#2196F3",
                    }
                }
            )

            # Submenu for Validation Status
            validation_selected = None
            if compliance_selected == "Validation Status":
                validation_selected = option_menu(
                    menu_title=None,
                    options=["Overview", "Cisco", "Fortinet"],
                    icons=["house", "1-circle", "2-circle"],
                    default_index=0,
                    styles={
                        "container": {
                            "padding": "0!important", 
                            "background-color": "transparent",
                            "margin-left": "1rem"
                        },
                        "icon": {"color": "#2196F3", "font-size": "13px"},
                        "nav-link": {
                            "font-size": "14px",
                            "text-align": "left",
                            "margin": "0px",
                            "--hover-color": "#333",
                            "color": "#666",
                            "padding": "0.5rem 1rem",
                        },
                        "nav-link-selected": {
                            "background-color": "#1A1A1A",
                            "color": "#2196F3",
                        }
                    }
                )
        
        # Rendering appropriate views
        if compliance_selected == "Backup Status":
            backup_status_view()
        elif compliance_selected == "Operational Status":
            operational_status_view()
        elif compliance_selected == "Validation Status":
            if not validation_selected or validation_selected == "Overview":
                validation_status_view()
            elif validation_selected == "Cisco":
                cisco_validation_status_view()
            elif validation_selected == "Fortinet":
                fortinet_validation_status_view()
        elif compliance_selected == "Global Overview [WiP]":
            global_overview()
            
    else:  # Remote Access Status
        with st.sidebar:
            remote_selected = option_menu(
                menu_title="Remote Access Views",
                options=["Page 1", "Page 2"],
                icons=["1-circle", "2-circle"],
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
                        "background-color": "#1A1A1A",
                        "color": "#2196F3",
                    }
                }
            )
        
        if remote_selected == "Page 1":
            remote_access_page1()
        else:
            remote_access_page2()

if __name__ == "__main__":
    main()