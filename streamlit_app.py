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
        "background-color": "#e9e9e9",
        "justify-content": "left",
        "align-items": "center",
        "padding": "0.75rem 5vw",
    },

    "img": {
        "height": "100px",
        "padding-right": "14px",
        "line-height": "1",
        "display": "inline-flex",
        "align-items": "center",
    },

    "span": {
        "color": "#111827",
        "padding": "0.55rem 1rem",
        "border-radius": "999px",
        "font-weight": "500",
        "line-height": "1",
        "display": "inline-flex",
        "align-items": "center",
        "height": "40px",
    },

    "active": {
        "background-color": "#DCFCE7",
        "color": "var(--text-color)",
        "font-weight": "700",
    },

    "hover": {
        "background-color": "#F3F4F6",
    },
}

options = {
    "show_menu": False,
    "show_sidebar": False,
}

page = st_navbar(
    pages,
    selected="Home",
    logo_path=logo_path,
    logo_page="SolCon",
    styles=styles,
    options=options,
)

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