import streamlit as st
import requests
import pandas as pd
from algorithm.solcon_v51 import SystemConfig, simulate_solcon
from algorithm.weather import get_weather_forecast, prepare_weather_data, aggregate_daily_pv
import datetime


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

    if run_btn:
        forecast_df = get_weather_forecast(
            cfg.latitude,
            cfg.longitude
        )

        forecast_df = prepare_weather_data(
            forecast_df,
            cfg
        )

        daily_kwh = aggregate_daily_pv(
            forecast_df
        )

        results = simulate_solcon(
            pv_data=forecast_df,
            daily_kwh=daily_kwh,
            start_weekday=0,
            cfg=cfg
        )

        results_df = pd.DataFrame(results)

        st.subheader("Simulation Results")

        # Tables
        total_cost = results_df["cost"].sum()
        total_grid_load = results_df["grid_load"].sum()
        total_grid_charge = results_df["grid_charge"].sum()
        total_battery_load = results_df["battery_load"].sum()
        min_soc = results_df["soc"].min() * 100
        max_soc = results_df["soc"].max() * 100

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric("Total Cost", f"PHP {total_cost:,.2f}")
        col2.metric("Grid Load", f"{total_grid_load:.2f} kWh")
        col3.metric("Grid Charge", f"{total_grid_charge:.2f} kWh")
        col4.metric("Battery Used", f"{total_battery_load:.2f} kWh")
        col5.metric("SOC Range", f"{min_soc:.1f}%–{max_soc:.1f}%")

        results_df["soc_percent"] = results_df["soc"] * 100
        results_df["datetime"] = pd.to_datetime(results_df["time"])
        results_df["time_label"] = (results_df["datetime"].dt.strftime("%A | %I:%M %p").str.replace("| 0", "| ", regex=False))

        # Battery SOC Over Time
        st.subheader("Battery SOC Over Time")
        st.line_chart(
            results_df.set_index("time_label")[["soc_percent"]]
        )
        
        # Energy Source Breakdown
        st.subheader("Energy Source Breakdown")
        energy_df = results_df[[
            "time_label",
            "battery_load",
            "grid_load",
            "grid_charge"
        ]].set_index("time_label")

        st.area_chart(energy_df)

        # Cost Over Time
        st.subheader("Cost Over Time")
        st.bar_chart(
            results_df.set_index("time_label")[["cost"]]
        )

        # Daily Sumamry
        st.subheader("Daily Summary")

        daily_summary = results_df.groupby("date").agg(
            total_cost=("cost", "sum"),
            grid_load=("grid_load", "sum"),
            grid_charge=("grid_charge", "sum"),
            battery_load=("battery_load", "sum"),
            min_soc=("soc", "min"),
            max_soc=("soc", "max"),
            avg_pv_kw=("pv_kw", "mean")
        ).reset_index()

        daily_summary["min_soc"] = daily_summary["min_soc"] * 100
        daily_summary["max_soc"] = daily_summary["max_soc"] * 100

        st.dataframe(daily_summary, use_container_width=True)

        # Full Details
        with st.expander("Full Slot-by-Slot Results"):
            display_df = results_df.copy()
            display_df["soc"] = (display_df["soc"] * 100).round(1).astype(str) + "%"
            st.dataframe(display_df, use_container_width=True)