import streamlit as st
import requests
import pandas as pd
from algorithm.solcon_v51 import SystemConfig


def show_calculator():
    st.header("Calculator")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            '<div style="font-weight:bold; color:gray; text-transform:uppercase;">Hardware</div>',
            unsafe_allow_html=True
        )
        battery_capacity = st.number_input(
            "Battery Capacity (kWh)",
            min_value=0.1,
            value=16.59,
            step=0.01
        )

        soc_floor = st.number_input(
            "Min SOC Floor (%)",
            min_value=0,
            max_value=100,
            value=20
        )

        pv_capacity = st.number_input(
            "PV System Capacity (kWp)",
            min_value=0.1,
            value=8.0,
            step=0.1
        )

        soc_max = st.number_input(
            "Maximum SOC (%)",
            min_value=0,
            max_value=100,
            value=100
        )

        system_efficiency = st.slider(
            "System Performance Ratio",
            min_value=0.50,
            max_value=1.00,
            value=0.80,
            step=0.01,
            help="Accounts for heat, wiring, inverter losses. 0.80 = 80% efficient."
        )

    with col2:
        st.markdown(
            '<div style="font-weight:bold; color:gray; text-transform:uppercase;">Electricity Rates (PHP / kWh)</div>',
            unsafe_allow_html=True
        )
        import_rate = st.number_input(
            "Import / Flat Rate",
            min_value=0.0,
            value=15.68,
            step=0.01,
            help="What Meralco charges you on a standard flat tariff."
        )

        peak_rate = st.number_input(
            "TOU Peak Rate",
            min_value=0.0,
            value=17.27,
            step=0.01,
            help="Rate during peak hours."
        )

        offpeak_rate = st.number_input(
            "TOU Off-Peak Rate",
            min_value=0.0,
            value=13.54,
            step=0.01,
            help="Rate during all other hours."
        )

        export_rate = st.number_input(
            "Net Metering Export Rate",
            min_value=0.0,
            value=8.80,
            step=0.01,
            help="PHP/kWh credited when surplus solar is exported."
        )

    with col3:
        st.markdown(
            '<div style="font-weight:bold; color:gray; text-transform:uppercase;">Algorithm & Location</div>',
            unsafe_allow_html=True
        )
        algorithm_mode = st.selectbox(
            "Algorithm Mode",
            [
                "SOLCON v5.1 - TOU + Load Shedding",
                "SOLCON v5.2 - TOU + No Load Shedding",
            ]
        )

        latitude = st.number_input(
            "Latitude",
            value=14.6760,
            format="%.4f"
        )

        longitude = st.number_input(
            "Longitude",
            value=121.0437,
            format="%.4f"
        )

    run_btn = st.button(
        "▶ Run Simulation",
        type="primary",
    )

    # Place inputs in config dataclass
    cfg = SystemConfig(
        battery_capacity=battery_capacity,
        soc_floor=soc_floor / 100,
        pv_capacity=pv_capacity,
        soc_max=soc_max / 100,
        system_efficiency=system_efficiency,

        import_rate=import_rate,
        export_rate=export_rate,
        peak_rate=peak_rate,
        offpeak_rate=offpeak_rate,

        algorithm_mode=algorithm_mode,
        latitude=latitude,
        longitude =longitude
    )