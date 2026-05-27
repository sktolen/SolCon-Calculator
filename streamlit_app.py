import os
import streamlit as st
from streamlit_navigation_bar import st_navbar
import pages as pg

st.set_page_config(
    page_title="SolCon",
    layout="wide",
    initial_sidebar_state="collapsed"
)

pages = ["Home", "Calculator", "How It Works", "About Us"]

parent_dir = os.path.dirname(os.path.abspath(__file__))
logo_path = os.path.join(parent_dir, "images/solcon_icon.svg")

styles = {
    "nav": {
        "background-color": "#f5f5f5",
        "display": "flex",
        "justify-content": "flex-start",
        "align-items": "center",
        "padding": "0 2rem",
        "height": "56px",
        "box-shadow": "0 1px 0 rgba(0,0,0,0.08)",
    },

    "img": {
        "height": "100px",
        "margin-right": "2rem",
    },

    "span": {
        "color": "#374151",
        "padding": "0.4rem 0.75rem",
        "border-radius": "6px",
        "font-size": "0.875rem",
        "font-weight": "400",
    },

    "active": {
        "background-color": "#DCFCE7",
        "color": "#166534",
        "font-weight": "600",
    },

    "hover": {
        "background-color": "#ebebeb",
    },
}

options = {
    "show_menu": False,
    "show_sidebar": False,
} 

# ── Track current page in session state so Home is highlighted on first load ──
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"

page = st_navbar(
    pages,
    selected=st.session_state.current_page,   # ← reflects active page, not hardcoded
    logo_path=logo_path,
    logo_page="SolCon",
    styles=styles,
    options=options,
)

# Update session state when user navigates
if page and page != "SolCon":
    st.session_state.current_page = page

functions = {
    "Home": pg.show_home,
    "Calculator": pg.show_calculator,
    "How It Works": pg.show_how_it_works,
    "About Us": pg.show_about_us,
    "SolCon": pg.show_home,
}

go_to = functions.get(page)
if go_to:
    go_to()