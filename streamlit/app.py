import streamlit as st
import os

st.set_page_config(page_title="iNET Services", layout="wide")

# Załaduj styl CSS dla całej aplikacji
def load_css():
    css_file = os.path.join(os.path.dirname(__file__), "views/styles/main.css")
    with open(css_file, "r") as f:
        css = f.read()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# Zastosuj styl CSS
load_css()

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

# Home page
from views.home.view import main as home_main
home_page = st.Page(home_main, title="Home", icon=":material/home:", default=True, url_path="home")

# Testing pages
from views.testing.view import show as global_overview_show
global_overview = st.Page(global_overview_show, title="Global Overview", icon=":material/dashboard:", url_path="global_overview")
device_details = st.Page("views/testing/device_details.py", title="Device Details", icon=":material/devices:", url_path="devices")

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
            "": [logout_page, home_page],
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
            "Testing": [global_overview, device_details],
        }
    )
else:
    pg = st.navigation(
        {
            "": [login_page, home_page]
        }
    )

pg.run()