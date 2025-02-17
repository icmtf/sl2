import streamlit as st

light_theme = '''
<style>
    .stApp {
        background-color: #ffffff;
        color: #000000;
    }
    .stButton button {
        background-color: #00915a !important;
        color: white !important;
    }
    .stSidebar {
        background-color: #00915a !important;
    }
    .stProgress > div > div {
        background-color: #8fd429 !important;
    }
    .stTextInput label, .stTextInput p {
        color: #000000 !important;
    }
    .stSearchBox input {
        color: #000000 !important;
    }
    .legendtext {
        fill: #00915a !important;
    }
    text.gtitle, 
    text.gtitle tspan {
        fill: #000 !important;
    }
    div[data-testid="stDataFrameGlideDataEditor"] div[role="cell"] {
        background-color: #fff3e0 !important;
    }
</style>
'''

dark_theme = '''
<style>
    .stApp {
        background-color: black;
        color: #ffffff;
    }
    .stButton button {
        background-color: #fff !important;
        color: black !important;
    }
    .stSidebar {
        background-color: #00915a !important;
    }
    .stProgress > div > div {
        background-color: #8fd429 !important;
    }
    text.gtitle, 
    text.gtitle tspan {
        fill: #fff !important;
    }
</style>
'''
def initialize_theme():
    if "theme" not in st.session_state:
        st.session_state.theme = "light"

def toggle_theme():
    if st.session_state.theme == "light":
        st.session_state.theme = "dark"
    else:
        st.session_state.theme = "light"

def apply_theme():
    initialize_theme()
    
    # Dodaj przycisk przełączania w sidebarze
    with st.sidebar:
        st.write("##")  # Dodaj przestrzeń
        if st.button("🌓 Toggle Theme"):
            toggle_theme()
            st.rerun()
    
    # Zastosuj odpowiedni motyw
    if st.session_state.theme == "dark":
        st.markdown(dark_theme, unsafe_allow_html=True)
    else:
        st.markdown(light_theme, unsafe_allow_html=True)