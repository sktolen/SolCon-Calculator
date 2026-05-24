import streamlit as st
import pandas as pd
import datetime
from algorithm.solcon_v51 import SystemConfig, simulate_solcon
from algorithm.weather import (
    get_weather_forecast,
    get_weather_weekly,
    get_weather_monthly,
    get_weather_annual,
    prepare_weather_data,
    aggregate_daily_pv,
)


# ─────────────────────────────────────────────
#  Shared helpers
# ─────────────────────────────────────────────

def _start_weekday_for(df: pd.DataFrame) -> int:
    first_date = pd.to_datetime(df["date"].iloc[0])
    return first_date.weekday()


def _run_simulation(raw_df, cfg) -> pd.DataFrame:
    prepared = prepare_weather_data(raw_df, cfg)
    daily_kwh = aggregate_daily_pv(prepared)
    start_weekday = _start_weekday_for(prepared)
    results = simulate_solcon(
        pv_data=prepared,
        daily_kwh=daily_kwh,
        start_weekday=start_weekday,
        cfg=cfg,
    )
    df = pd.DataFrame(results)
    df["soc_percent"] = df["soc"] * 100
    df["datetime"] = pd.to_datetime(df["time"])
    df["time_label"] = (
        df["datetime"]
        .dt.strftime("%a %b %d | %I:%M %p")
        .str.replace("| 0", "| ", regex=False)
    )
    return df


# ─────────────────────────────────────────────
#  Summary metrics row
# ─────────────────────────────────────────────

def _show_metrics(results_df: pd.DataFrame):
    total_grid_cost = results_df["grid_cost"].sum()
    total_export_credit = results_df["export_credit"].sum()
    total_net_cost = results_df["net_cost"].sum()
    total_grid_load = results_df["grid_load"].sum()
    total_grid_charge = results_df["grid_charge"].sum()
    total_battery_load = results_df["battery_load"].sum()
    min_soc = results_df["soc"].min() * 100
    max_soc = results_df["soc"].max() * 100

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Grid Cost", f"PHP {total_grid_cost:,.2f}")
    c2.metric("Export Credit", f"PHP {total_export_credit:,.2f}")
    c3.metric("Net Cost", f"PHP {total_net_cost:,.2f}")
    c4.metric("Grid Load", f"{total_grid_load:.2f} kWh")
    c5.metric("Grid Charge", f"{total_grid_charge:.2f} kWh")
    c6.metric("Battery Used", f"{total_battery_load:.2f} kWh")
    c7.metric("SOC Range", f"{min_soc:.1f}%–{max_soc:.1f}%")


# ─────────────────────────────────────────────
#  Charts (slot-level — daily & weekly)
# ─────────────────────────────────────────────

def _show_charts(results_df: pd.DataFrame, index_col: str = "time_label"):
    idx = results_df.set_index(index_col)

    st.subheader("Battery SOC Over Time")
    st.line_chart(idx[["soc_percent"]])

    st.subheader("Energy Source Breakdown")
    st.area_chart(idx[["battery_load", "grid_load", "grid_charge"]])

    st.subheader("Cost Over Time")
    st.bar_chart(idx[["net_cost"]])


# ─────────────────────────────────────────────
#  Charts (day-aggregated — monthly)
# ─────────────────────────────────────────────

def _show_charts_daily_agg(results_df: pd.DataFrame):
    st.subheader("Battery SOC Over Time")
    st.line_chart(results_df.set_index("datetime")[["soc_percent"]])

    st.subheader("Daily Energy Source Breakdown")
    daily_energy = (
        results_df.groupby("date")[["battery_load", "grid_load", "grid_charge"]]
        .sum()
    )
    st.area_chart(daily_energy)

    st.subheader("Daily Cost")
    daily_cost = results_df.groupby("date")[["net_cost"]].sum()
    st.bar_chart(daily_cost)


# ─────────────────────────────────────────────
#  Daily summary table (used by all tabs)
# ─────────────────────────────────────────────

def _show_daily_summary(results_df: pd.DataFrame):
    st.subheader("Daily Summary")
    daily = (
        results_df.groupby("date")
        .agg(
            grid_cost=("grid_cost", "sum"),
            export_credit=("export_credit", "sum"),
            net_cost=("net_cost", "sum"),
            grid_load=("grid_load", "sum"),
            grid_charge=("grid_charge", "sum"),
            battery_load=("battery_load", "sum"),
            export_kwh=("export_kwh", "sum"),
            min_soc=("soc", "min"),
            max_soc=("soc", "max"),
            avg_pv_kw=("pv_kw", "mean"),
        )
        .reset_index()
    )
    daily["min_soc"] = (daily["min_soc"] * 100).round(1)
    daily["max_soc"] = (daily["max_soc"] * 100).round(1)
    st.dataframe(daily, use_container_width=True)


# ─────────────────────────────────────────────
#  Monthly breakdown (used in Annual tab)
# ─────────────────────────────────────────────

def _show_monthly_breakdown(results_df: pd.DataFrame):
    results_df = results_df.copy()
    results_df["month"] = pd.to_datetime(results_df["date"]).dt.to_period("M").astype(str)

    monthly = (
        results_df.groupby("month")
        .agg(
            grid_cost=("grid_cost", "sum"),
            export_credit=("export_credit", "sum"),
            net_cost=("net_cost", "sum"),
            grid_load=("grid_load", "sum"),
            grid_charge=("grid_charge", "sum"),
            battery_load=("battery_load", "sum"),
            export_kwh=("export_kwh", "sum"),
            avg_pv_kw=("pv_kw", "mean"),
        )
        .reset_index()
    )

    st.subheader("Monthly Breakdown")
    st.dataframe(monthly, use_container_width=True)

    st.subheader("Monthly Net Cost")
    st.bar_chart(monthly.set_index("month")[["net_cost"]])

    st.subheader("Monthly Energy Sources")
    st.area_chart(monthly.set_index("month")[["battery_load", "grid_load", "grid_charge"]])


# ─────────────────────────────────────────────
#  Per-tab simulation runners
# ─────────────────────────────────────────────

def _tab_daily(cfg: SystemConfig):
    st.caption("3-day forecast starting today.")
    if not st.button("▶ Run Daily Simulation", type="primary", key="run_daily"):
        return

    with st.spinner("Fetching 3-day forecast…"):
        raw_df = get_weather_forecast(cfg.latitude, cfg.longitude, forecast_days=3)

    with st.spinner("Running simulation…"):
        results_df = _run_simulation(raw_df, cfg)

    st.subheader("Simulation Results")
    _show_metrics(results_df)
    _show_charts(results_df)
    _show_daily_summary(results_df)

    with st.expander("Full Slot-by-Slot Results"):
        display = results_df.copy()
        display["soc"] = (display["soc"] * 100).round(1).astype(str) + "%"
        st.dataframe(display, use_container_width=True)


def _tab_weekly(cfg: SystemConfig):
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    sunday = monday + datetime.timedelta(days=6)
    st.caption(
        f"Historical data from Monday {monday.strftime('%b %d')} through yesterday, "
        f"plus forecast through Sunday {sunday.strftime('%b %d')}."
    )
    if not st.button("▶ Run Weekly Simulation", type="primary", key="run_weekly"):
        return

    with st.spinner("Fetching this week's data…"):
        raw_df = get_weather_weekly(cfg.latitude, cfg.longitude)

    with st.spinner("Running simulation…"):
        results_df = _run_simulation(raw_df, cfg)

    st.subheader("Simulation Results")
    _show_metrics(results_df)
    _show_charts(results_df)
    _show_daily_summary(results_df)

    with st.expander("Full Slot-by-Slot Results"):
        display = results_df.copy()
        display["soc"] = (display["soc"] * 100).round(1).astype(str) + "%"
        st.dataframe(display, use_container_width=True)


def _tab_monthly(cfg: SystemConfig):
    today = datetime.date.today()
    month_name = today.strftime("%B %Y")
    st.caption(
        f"Historical data from the 1st of {month_name} through yesterday, "
        f"plus forecast for the remaining days of this month."
    )
    if not st.button("▶ Run Monthly Simulation", type="primary", key="run_monthly"):
        return

    with st.spinner(f"Fetching data for {month_name}…"):
        raw_df = get_weather_monthly(cfg.latitude, cfg.longitude)

    with st.spinner("Running simulation…"):
        results_df = _run_simulation(raw_df, cfg)

    st.subheader("Simulation Results")
    _show_metrics(results_df)
    _show_charts_daily_agg(results_df)
    _show_daily_summary(results_df)

    with st.expander("Full Slot-by-Slot Results"):
        display = results_df.copy()
        display["soc"] = (display["soc"] * 100).round(1).astype(str) + "%"
        st.dataframe(display, use_container_width=True)


def _tab_annual(cfg: SystemConfig):
    prev_year = datetime.date.today().year - 1
    st.caption(
        f"Historical data for the full year {prev_year} "
        f"(Jan 1 – Dec 31). This may take a moment to fetch."
    )
    if not st.button("▶ Run Annual Simulation", type="primary", key="run_annual"):
        return

    with st.spinner(f"Fetching historical data for {prev_year}… (this may take ~10–20 s)"):
        raw_df = get_weather_annual(cfg.latitude, cfg.longitude)

    with st.spinner("Running simulation (365 days)…"):
        results_df = _run_simulation(raw_df, cfg)

    st.subheader("Simulation Results")
    _show_metrics(results_df)
    _show_monthly_breakdown(results_df)

    st.subheader("Daily SOC Over Time")
    daily_soc = results_df.groupby("date")["soc_percent"].mean()
    st.line_chart(daily_soc)

    _show_daily_summary(results_df)

    with st.expander("Full Slot-by-Slot Results (large dataset)"):
        display = results_df.copy()
        display["soc"] = (display["soc"] * 100).round(1).astype(str) + "%"
        st.dataframe(display, use_container_width=True)


# ─────────────────────────────────────────────
#  Main entry point
# ─────────────────────────────────────────────

def show_calculator():
    st.header("Calculator")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            '<div style="font-weight:bold; color:gray; text-transform:uppercase;">Hardware</div>',
            unsafe_allow_html=True,
        )
        battery_capacity = st.number_input("Battery Capacity (kWh)", min_value=0.1, value=16.59, step=0.01)
        soc_floor = st.number_input("Min SOC Floor (%)", min_value=0, max_value=100, value=20)
        pv_capacity = st.number_input("PV System Capacity (kWp)", min_value=0.1, value=8.0, step=0.1)
        soc_max = st.number_input("Maximum SOC (%)", min_value=0, max_value=100, value=100)
        system_efficiency = st.slider(
            "System Performance Ratio",
            min_value=0.50, max_value=1.00, value=0.80, step=0.01,
            help="Accounts for heat, wiring, inverter losses. 0.80 = 80% efficient.",
        )

    with col2:
        st.markdown(
            '<div style="font-weight:bold; color:gray; text-transform:uppercase;">Electricity Rates (PHP / kWh)</div>',
            unsafe_allow_html=True,
        )
        import_rate = st.number_input("Import / Flat Rate", min_value=0.0, value=15.68, step=0.01,
                                      help="What Meralco charges you on a standard flat tariff.")
        peak_rate = st.number_input("TOU Peak Rate", min_value=0.0, value=17.27, step=0.01,
                                    help="Rate during peak hours.")
        offpeak_rate = st.number_input("TOU Off-Peak Rate", min_value=0.0, value=13.54, step=0.01,
                                       help="Rate during all other hours.")
        export_rate = st.number_input("Net Metering Export Rate", min_value=0.0, value=8.80, step=0.01,
                                      help="PHP/kWh credited when surplus solar is exported.")

    with col3:
        st.markdown(
            '<div style="font-weight:bold; color:gray; text-transform:uppercase;">Algorithm & Location</div>',
            unsafe_allow_html=True,
        )
        algorithm_mode = st.selectbox(
            "Algorithm Mode",
            ["SOLCON v5.1 - TOU + Load Shedding", "SOLCON v5.2 - TOU + No Load Shedding"],
        )
        latitude = st.number_input("Latitude", value=14.6760, format="%.4f")
        longitude = st.number_input("Longitude", value=121.0437, format="%.4f")

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
        longitude=longitude,
    )

    st.divider()

    tab_daily, tab_weekly, tab_monthly, tab_annual = st.tabs(
        ["📅 Daily (3 days)", "📆 Weekly (Mon–Sun)", "🗓️ Monthly", "📊 Annual"]
    )

    with tab_daily:
        _tab_daily(cfg)

    with tab_weekly:
        _tab_weekly(cfg)

    with tab_monthly:
        _tab_monthly(cfg)

    with tab_annual:
        _tab_annual(cfg)