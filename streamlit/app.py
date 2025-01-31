import streamlit as st

st.set_page_config(page_title="iNET Services", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def login():
    if st.button("Log in"):
        st.session_state.logged_in = True
        st.rerun()

def logout():
    if st.button("Log out"):
        st.session_state.logged_in = False
        st.rerun()

# Auth pages
login_page = st.Page(login, title="Log in", icon=":material/login:", url_path="login")
logout_page = st.Page(logout, title="Log out", icon=":material/logout:", url_path="logout")

# Global pages
from views.global_overview import show as global_overview_show

home_page = st.Page(global_overview_show, title="Global Overview", icon=":material/dashboard:", default=True, url_path="home")
device_details = st.Page("views/device_details.py", title="Device Details", icon=":material/devices:", url_path="devices")

# Compliance Status pages
backup_status = st.Page("views/backup_status/view.py", title="Backup Status", icon=":material/backup:", url_path="backup_status")
operational_status = st.Page("views/operational_status/view.py", title="Operational Status", icon=":material/check_circle:", url_path="operational_status")
validation_status = st.Page("views/validation_status/view.py", title="Validation Status", icon=":material/check_circle:", url_path="validation_status")
validation_cisco = st.Page("views/validation_status/cisco.py", title="Cisco", icon=":material/router:", url_path="validation_cisco")
validation_fortinet = st.Page("views/validation_status/fortinet.py", title="Fortinet", icon=":material/security:", url_path="validation_fortinet")

# Remote Access pages
from views.remote_access import page1, page2

remote_access_p1 = st.Page(page1.show, title="Remote Access P1", icon=":material/vpn_key:", url_path="remote_access_1")
remote_access_p2 = st.Page(page2.show, title="Remote Access P2", icon=":material/vpn_key:", url_path="remote_access_2")

if st.session_state.logged_in:
    pg = st.navigation(
        {
            "Home": [logout_page, home_page, device_details],
            "Compliance Status": [
                backup_status,
                operational_status,
                validation_status,
                validation_cisco,
                validation_fortinet
            ],
            "Remote Access": [
                remote_access_p1,
                remote_access_p2
            ],
        }
    )
else:
    pg = st.navigation(
        {
            "Home": [login_page, home_page]
        }
    )

pg.run()