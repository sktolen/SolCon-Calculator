import streamlit as st
import pandas as pd
import datetime
from algorithm.basic_algorithm import simulate_basic
from algorithm.solcon_v51 import SystemConfig, simulate_solcon as simulate_solcon_v51
from algorithm.solcon_v52 import simulate_solcon as simulate_solcon_v52
from algorithm.weather import (
    get_weather_forecast,
    get_weather_weekly,
    get_weather_monthly,
    get_weather_annual,
    prepare_weather_data,
    aggregate_daily_pv,
)

# ─────────────────────────────────────────────
#  Page config & global styles
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="SolCon v5 · Energy Dispatch Calculator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,600;1,9..144,400&display=swap');

:root {
    --ink:    #0D1117;
    --ink2:   #161B22;
    --ink3:   #21262D;
    --border: #30363D;
    --text:   #E6EDF3;
    --text2:  #8B949E;
    --teal:   #39D353;
    --amber:  #E3B341;
    --blue:   #58A6FF;
    --orange: #F0883E;
    --red:    #F85149;
    --mono:   'JetBrains Mono', monospace;
    --serif:  'Fraunces', serif;
}

html, body, [class*="css"] {
    font-family: var(--mono) !important;
    background-color: var(--ink) !important;
    color: var(--text) !important;
}

.main .block-container {
    max-width: 1400px;
    padding: 2rem 2.5rem 4rem;
}

.solcon-title {
    font-family: var(--serif) !important;
    font-size: 3rem;
    font-weight: 600;
    line-height: 1;
    color: var(--text);
    letter-spacing: -0.02em;
    margin-bottom: 0.25rem;
}
.solcon-subtitle {
    font-family: var(--mono);
    font-size: 0.72rem;
    color: var(--text2);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 2rem;
}
.solcon-accent { color: var(--teal); }

.section-label {
    font-family: var(--mono);
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--text2);
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.4rem;
    margin-bottom: 1rem;
}

/* Insight banners — these stay class-based as they're simple enough */
.insight-warn {
    background: rgba(248,81,73,0.08);
    border: 1px solid rgba(248,81,73,0.35);
    border-left: 3px solid var(--red);
    border-radius: 5px;
    padding: 0.65rem 1rem;
    font-size: 0.78rem;
    color: var(--text);
    margin-bottom: 0.6rem;
}
.insight-ok {
    background: rgba(57,211,83,0.07);
    border: 1px solid rgba(57,211,83,0.25);
    border-left: 3px solid var(--teal);
    border-radius: 5px;
    padding: 0.65rem 1rem;
    font-size: 0.78rem;
    color: var(--text);
    margin-bottom: 0.6rem;
}
.insight-info {
    background: rgba(88,166,255,0.07);
    border: 1px solid rgba(88,166,255,0.25);
    border-left: 3px solid var(--blue);
    border-radius: 5px;
    padding: 0.65rem 1rem;
    font-size: 0.78rem;
    color: var(--text);
    margin-bottom: 0.6rem;
}

div[data-testid="stNumberInput"] input,
div[data-testid="stSelectbox"] select,
div[data-testid="stTextInput"] input {
    background: var(--ink2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 4px !important;
    font-family: var(--mono) !important;
    font-size: 0.82rem !important;
}

button[data-baseweb="tab"] {
    font-family: var(--mono) !important;
    font-size: 0.72rem !important;
    letter-spacing: 0.05em !important;
}

hr { border-color: var(--border) !important; }
.stDataFrame { border: 1px solid var(--border) !important; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  Shared helpers
# ─────────────────────────────────────────────

def _run_basic_simulation(raw_df, cfg) -> pd.DataFrame:
    prepared = prepare_weather_data(raw_df, cfg)
    daily_kwh = aggregate_daily_pv(prepared)
    start_weekday = _start_weekday_for(prepared)
    results = simulate_basic(
        pv_data=prepared,
        daily_kwh=daily_kwh,
        start_weekday=start_weekday,
        cfg=cfg,
    )
    df = pd.DataFrame(results)
    df["soc_percent"] = df["soc"] * 100
    df["datetime"] = pd.to_datetime(df["time"])
    return df

def _start_weekday_for(df: pd.DataFrame) -> int:
    first_date = pd.to_datetime(df["date"].iloc[0])
    return first_date.weekday()

def _run_simulation(raw_df, cfg) -> pd.DataFrame:
    prepared = prepare_weather_data(raw_df, cfg)
    daily_kwh = aggregate_daily_pv(prepared)
    start_weekday = _start_weekday_for(prepared)

    if cfg.algorithm_mode == "SOLCON v5.2 - TOU + No Load Shedding":
        results = simulate_solcon_v52(
            pv_data=prepared,
            daily_kwh=daily_kwh,
            start_weekday=start_weekday,
            cfg=cfg,
        )
    else:
        results = simulate_solcon_v51(
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
    total_grid_cost     = results_df["grid_cost"].sum()
    total_export_credit = results_df["export_credit"].sum()
    total_net_cost      = results_df["net_cost"].sum()
    total_grid_load     = results_df["grid_load"].sum()
    total_grid_to_batt  = results_df["grid_to_battery"].sum()
    total_battery_load  = results_df["battery_load"].sum()
    total_pv_gen = results_df["pv_kw"].sum() * 0.5   # kW × 0.5 hr = kWh

    # FIX: all styles are fully inlined — no class lookups across st.markdown calls.
    # Streamlit scopes injected HTML and can't reliably resolve classes defined in a
    # separate st.markdown(<style>) block when rendering subsequent markdown blocks.
    GRADIENTS = [
        "linear-gradient(135deg,#1d4ed8 0%,#3b82f6 100%)",  # Grid Cost      — blue
        "linear-gradient(135deg,#6d28d9 0%,#8b5cf6 100%)",  # Export Revenue — purple
        "linear-gradient(135deg,#b45309 0%,#f59e0b 100%)",  # Net Cost       — amber
        "linear-gradient(135deg,#0e7490 0%,#22d3ee 100%)",  # Grid Load      — cyan
        "linear-gradient(135deg,#c2410c 0%,#fb923c 100%)",  # Grid→Battery   — orange
        "linear-gradient(135deg,#065f46 0%,#34d399 100%)",  # Battery Disc.  — green
        "linear-gradient(135deg,#1e3a5f 0%,#60a5fa 100%)",  # SOC Range      — steel
    ]

    cards = [
        ("Grid Cost",          f"PHP {total_grid_cost:,.2f}",      "Amount paid for grid energy consumed"),
        ("Export Revenue",     f"PHP {total_export_credit:,.2f}",  "Net metering amount earned"),
        ("Net Cost",           f"PHP {total_net_cost:,.2f}",       "Grid cost minus net metering"),
        ("Grid Load",          f"{total_grid_load:.2f} kWh",       "Drawn energy from grid to loads"),
        ("Grid to Battery",     f"{total_grid_to_batt:.2f} kWh",   "Grid energy used to charge battery"),
        ("Battery Discharged", f"{total_battery_load:.2f} kWh",    "Energy discharged to serve loads"),
        ("PV Generated",        f"{total_pv_gen:.2f} kWh",         "Total solar energy produced"),
    ]

    base   = ("border-radius:16px;padding:1.1rem 0.75rem;min-height:120px;"
              "display:flex;flex-direction:column;justify-content:center;align-items:center;"
              "text-align:center;box-shadow:0 4px 16px rgba(0,0,0,0.25);margin-bottom:0.5rem;")
    s_lbl  = ("color:rgba(255,255,255,0.85);font-size:0.7rem;font-weight:600;"
               "letter-spacing:0.06em;text-transform:uppercase;margin-bottom:0.5rem;line-height:1.2;")
    s_val  = ("color:#ffffff;font-size:1.15rem;font-weight:800;line-height:1.1;"
               "margin-bottom:0.3rem;font-family:'JetBrains Mono',monospace;")
    s_sub  = "color:rgba(255,255,255,0.65);font-size:0.65rem;line-height:1.2;"

    cols = st.columns(len(cards))
    for col, (label, value, sub), grad in zip(cols, cards, GRADIENTS):
        with col:
            st.markdown(
                f'<div style="{base}background:{grad};">'
                f'<div style="{s_lbl}">{label}</div>'
                f'<div style="{s_val}">{value}</div>'
                f'<div style="{s_sub}">{sub}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────────
#  Simulation insights
# ─────────────────────────────────────────────

def _show_simulation_insights(results_df: pd.DataFrame, cfg: SystemConfig):
    total_export = results_df["export_kwh"].sum()
    min_soc      = results_df["soc"].min() * 100
    floor_pct    = cfg.soc_floor * 100

    # SOC floor breach
    if min_soc <= floor_pct:
        st.markdown(
            f'<div class="insight-warn">⚠️ Battery hit the SOC floor ({floor_pct:.0f}%) during the simulation. '
            f'Lowest recorded SOC: <strong>{min_soc:.1f}%</strong>. '
            f'Consider increasing the grid-charge target or reducing non-critical loads.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="insight-ok">✓ Battery stayed above the SOC floor ({floor_pct:.0f}%) throughout. '
            f'Lowest SOC recorded: <strong>{min_soc:.1f}%</strong>.</div>',
            unsafe_allow_html=True,
        )

    # Export
    if total_export <= 0:
        st.markdown(
            '<div class="insight-info">ℹ️ No surplus solar was exported to the grid — all generation was '
            'consumed internally or stored in the battery.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="insight-info">ℹ️ <strong>{total_export:.2f} kWh</strong> exported to Meralco grid '
            f'(PHP {results_df["export_credit"].sum():,.2f} in net-metering credits).</div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────
#  Charts (slot-level — daily & weekly)
# ─────────────────────────────────────────────

def _show_charts(results_df: pd.DataFrame, basic_df: pd.DataFrame = None, index_col: str = "time_label", soc_resolution: str = "hourly"):
    def _hourly(df):
        return (
            df.copy()
            .assign(hour=pd.to_datetime(df["time"]).dt.floor("h"))
            .groupby("hour")
            .agg(
                soc_percent=("soc_percent", "mean"),
                battery_load=("battery_load", "sum"),
                grid_load=("grid_load", "sum"),
                grid_to_battery=("grid_to_battery", "sum"),
                net_cost=("net_cost", "sum"),
            )
        )

    hourly = _hourly(results_df)

    # ── SOC ───────────────────────────────────────────────────────────────
    st.markdown('')
    st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Battery State of Charge (hourly avg)</div>', unsafe_allow_html=True)
    if basic_df is not None:
        soc_compare = pd.DataFrame({
            "SOLCON": _hourly(basic_df)["soc_percent"],   # basic first so SOLCON draws on top
            "Basic":  hourly["soc_percent"],
        }).rename(columns={"SOLCON": "Basic", "Basic": "SOLCON"})  # swap back
        soc_data = pd.DataFrame({
            "SOLCON": hourly["soc_percent"],
            "Basic":  _hourly(basic_df)["soc_percent"],
        })
        st.line_chart(soc_data, color=["#39D353", "#58A6FF"])
        st.caption("Green = SOLCON · Blue = Basic")
    else:
        st.line_chart(hourly[["soc_percent"]], color=["#39D353"])

    # ── Energy source breakdown ───────────────────────────────────────────
    st.markdown('')
    st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Energy Source Breakdown (kWh per hour)</div>', unsafe_allow_html=True)
    st.area_chart(hourly[["battery_load", "grid_load", "grid_to_battery"]], color=["#58A6FF", "#F85149", "#F0883E"])

    # ── Grid load comparison ──────────────────────────────────────────────
    if basic_df is not None:
        st.markdown('')
        st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Grid Draw Comparison (kWh per hour)</div>', unsafe_allow_html=True)
        grid_data = pd.DataFrame({
            "Basic":  _hourly(basic_df)["grid_load"],
            "SolCon": hourly["grid_load"],
        })
        st.bar_chart(grid_data, color=["#F85149", "#39D353"], stack=False)
        st.caption("Green = SOLCON · Red = Basic")

    # ── Net cost ──────────────────────────────────────────────────────────
    st.markdown('')
    st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">SOLCON — Net Cost per Hour (PHP)</div>', unsafe_allow_html=True)
    hourly_bill = (
        results_df.copy()
        .assign(hour=pd.to_datetime(results_df["time"]).dt.floor("h"))
        .groupby("hour")
        .agg(grid_cost=("grid_cost", "sum"), export_credit=("export_credit", "sum"))
    )
    hourly_bill["export_credit"] = -hourly_bill["export_credit"]
    st.bar_chart(hourly_bill[["grid_cost", "export_credit"]], color=["#F85149", "#39D353"])
    st.caption("Red = grid cost · Green = export credit (negative = earned)")

    if basic_df is not None:
        st.markdown('')
        st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Basic — Net Cost per Hour (PHP)</div>', unsafe_allow_html=True)
        basic_hourly_bill = (
            basic_df.copy()
            .assign(hour=pd.to_datetime(basic_df["time"]).dt.floor("h"))
            .groupby("hour")
            .agg(grid_cost=("grid_cost", "sum"), export_credit=("export_credit", "sum"))
        )
        basic_hourly_bill["export_credit"] = -basic_hourly_bill["export_credit"]
        st.bar_chart(basic_hourly_bill[["grid_cost", "export_credit"]], color=["#F85149", "#39D353"])
        st.caption("Red = grid cost · Green = export credit (negative = earned)")

        st.markdown('')
        st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Net Cost Comparison — SOLCON vs Basic (PHP per hour)</div>', unsafe_allow_html=True)
        net_compare = pd.DataFrame({
            "SOLCON": results_df.copy().assign(hour=pd.to_datetime(results_df["time"]).dt.floor("h")).groupby("hour")["net_cost"].sum(),
            "Basic":  basic_df.copy().assign(hour=pd.to_datetime(basic_df["time"]).dt.floor("h")).groupby("hour")["net_cost"].sum(),
        })
        st.line_chart(net_compare, color=["#39D353", "#F85149"])
        st.caption("Green = SOLCON · Red = Basic — lower is better")


# ─────────────────────────────────────────────
#  Charts (day-aggregated — monthly)
# ─────────────────────────────────────────────

def _show_charts_daily_agg(results_df: pd.DataFrame, basic_df: pd.DataFrame = None):
    st.markdown('')
    st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Battery SOC Over Time (avg per slot)</div>', unsafe_allow_html=True)
    if basic_df is not None:
        soc_data = pd.DataFrame({
            "SOLCON": results_df.set_index("datetime")["soc_percent"],
            "Basic":  basic_df.set_index("datetime")["soc_percent"],
        })
        st.line_chart(soc_data, color=["#39D353", "#58A6FF"])
        st.caption("Green = SOLCON · Blue = Basic")
    else:
        st.line_chart(results_df.set_index("datetime")[["soc_percent"]], color=["#39D353"])

    st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Daily Energy Source Breakdown (kWh)</div>', unsafe_allow_html=True)
    daily_energy = results_df.groupby("date")[["battery_load", "grid_load", "grid_to_battery"]].sum()
    st.area_chart(daily_energy, color=["#58A6FF", "#F85149", "#F0883E"])

    if basic_df is not None:
        st.markdown('')
        st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Daily Grid Draw Comparison (kWh)</div>', unsafe_allow_html=True)
        grid_data = pd.DataFrame({
            "SOLCON": results_df.groupby("date")["grid_load"].sum(),
            "Basic":  basic_df.groupby("date")["grid_load"].sum(),
        })
        st.bar_chart(grid_data, color=["#39D353", "#F85149"], stack=False)
        st.caption("Green = SOLCON · Red = Basic")

    _show_net_bill_chart(results_df, period="daily")

# ─────────────────────────────────────────────
#  Daily summary table
# ─────────────────────────────────────────────

def _show_daily_summary(results_df: pd.DataFrame):
    st.markdown('')
    st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Daily Summary</div>', unsafe_allow_html=True)
    daily = (
        results_df.groupby("date")
        .agg(
            grid_cost=("grid_cost", "sum"),
            export_credit=("export_credit", "sum"),
            net_cost=("net_cost", "sum"),
            grid_load=("grid_load", "sum"),
            grid_to_battery=("grid_to_battery", "sum"),
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
#  Monthly breakdown (Annual tab)
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
            grid_to_battery=("grid_to_battery", "sum"),
            battery_load=("battery_load", "sum"),
            export_kwh=("export_kwh", "sum"),
            avg_pv_kw=("pv_kw", "mean"),
        )
        .reset_index()
    )

    st.markdown('<div class="section-label">Monthly Breakdown</div>', unsafe_allow_html=True)
    st.dataframe(monthly, use_container_width=True)

    _show_net_bill_chart(results_df, period="monthly")

    st.markdown('<div class="section-label">Monthly Energy Sources (kWh)</div>', unsafe_allow_html=True)
    st.area_chart(
        monthly.set_index("month")[["battery_load", "grid_load", "grid_to_battery"]],
        color=["#58A6FF", "#F85149", "#F0883E"],
    )


# ─────────────────────────────────────────────
#  Net bill chart (shared)
# ─────────────────────────────────────────────

def _show_net_bill_chart(results_df: pd.DataFrame, period: str = "daily"):
    df = results_df.copy()
    if "datetime" not in df.columns:
        df["datetime"] = pd.to_datetime(df["time"])

    if period == "daily":
        df["period"] = df["datetime"].dt.strftime("%b %d")
        title = "Daily Net Bill — Grid Cost vs Export Revenue"
    else:
        df["period"] = df["datetime"].dt.to_period("M").astype(str)
        title = "Monthly Net Bill — Grid Cost vs Export Revenue"

    bill = (
        df.groupby("period")
        .agg(
            grid_cost=("grid_cost", "sum"),
            export_credit=("export_credit", "sum"),
        )
        .reset_index()
    )
    bill["grid_cost"]     = bill["grid_cost"].round(2)
    bill["export_credit"] = -bill["export_credit"].round(2)

    st.markdown(f'<div class="section-label">{title}</div>', unsafe_allow_html=True)
    st.bar_chart(
        bill.set_index("period")[["grid_cost", "export_credit"]],
        color=["#F85149", "#39D353"],
    )
    st.caption("Red = grid cost · Green = export credit (negative = earned)")


# ─────────────────────────────────────────────
#  Per-tab simulation runners
# ─────────────────────────────────────────────

def _tab_daily(cfg: SystemConfig):
    st.caption("3-day forecast starting today.")
    if not st.button("▶ Run 3-Day Simulation", type="primary", key="run_daily"):
        return

    with st.spinner("Fetching 3-day forecast…"):
        raw_df = get_weather_forecast(cfg.latitude, cfg.longitude, forecast_days=3)

    with st.spinner("Running simulation…"):
        results_df = _run_simulation(raw_df, cfg)
        basic_df   = _run_basic_simulation(raw_df, cfg)

    st.divider()
    st.subheader("Summary")

    _show_metrics(results_df)
    _show_simulation_insights(results_df, cfg)
    _show_charts(results_df, basic_df=basic_df)   # ← add basic_df
    _show_daily_summary(results_df)

    with st.expander("Full Slot-by-Slot Results"):
        display = results_df.copy()
        display["soc"] = (display["soc"] * 100).round(1).astype(str) + "%"
        st.dataframe(display, use_container_width=True)


def _tab_weekly(cfg: SystemConfig):
    today  = datetime.date.today()
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
        basic_df   = _run_basic_simulation(raw_df, cfg)

    st.divider()
    st.subheader("Summary")

    _show_metrics(results_df)
    _show_simulation_insights(results_df, cfg)
    _show_charts(results_df, basic_df=basic_df)
    _show_daily_summary(results_df)

    with st.expander("Full Slot-by-Slot Results"):
        display = results_df.copy()
        display["soc"] = (display["soc"] * 100).round(1).astype(str) + "%"
        st.dataframe(display, use_container_width=True)


def _tab_monthly(cfg: SystemConfig):
    col1, col2 = st.columns(2)
    with col1:
        month = st.selectbox(
            "Month",
            list(range(1, 13)),
            index=datetime.date.today().month - 1,
            format_func=lambda m: datetime.date(2000, m, 1).strftime("%B"),
        )
    with col2:
        year = st.number_input("Year", min_value=2020, max_value=2030,
                               value=datetime.date.today().year, step=1)

    st.caption(f"Historical + forecast data for {datetime.date(year, month, 1).strftime('%B %Y')}.")

    if not st.button("▶ Run Monthly Simulation", type="primary", key="run_monthly"):
        return

    with st.spinner(f"Fetching data for {datetime.date(year, month, 1).strftime('%B %Y')}…"):
        raw_df = get_weather_monthly(cfg.latitude, cfg.longitude, month=month, year=year)

    with st.spinner("Running simulation…"):
        monthly_cfg = SystemConfig(
            battery_capacity=cfg.battery_capacity,
            soc_floor=cfg.soc_floor,
            pv_capacity=cfg.pv_capacity,
            soc_max=cfg.soc_max,
            system_efficiency=cfg.system_efficiency,
            import_rate=cfg.import_rate,
            export_rate=cfg.export_rate,
            peak_rate=17.47 if month <= 6 else 17.27,
            offpeak_rate=cfg.offpeak_rate,
            algorithm_mode=cfg.algorithm_mode,
            latitude=cfg.latitude,
            longitude=cfg.longitude,
        )
        results_df = _run_simulation(raw_df, monthly_cfg)
        basic_df   = _run_basic_simulation(raw_df, monthly_cfg)

    st.divider()
    st.subheader("Summary")
    _show_metrics(results_df)
    _show_simulation_insights(results_df, monthly_cfg)
    _show_charts_daily_agg(results_df, basic_df=basic_df)
    _show_daily_summary(results_df)

    with st.expander("Full Slot-by-Slot Results"):
        display = results_df.copy()
        display["soc"] = (display["soc"] * 100).round(1).astype(str) + "%"
        st.dataframe(display, use_container_width=True)


def _tab_annual(cfg: SystemConfig):
    prev_year = datetime.date.today().year - 1
    st.caption(
        f"Historical data for the full year {prev_year} (Jan 1 – Dec 31)."
    )
    if not st.button("▶ Run Annual Simulation", type="primary", key="run_annual"):
        return

    with st.spinner(f"Fetching historical data for {prev_year}… (this may take ~10–20 s)"):
        raw_df = get_weather_annual(cfg.latitude, cfg.longitude)

    with st.spinner("Running simulation (365 days)…"):
        results_df = _run_simulation(raw_df, cfg)
        basic_df   = _run_basic_simulation(raw_df, cfg)

    st.divider()
    st.subheader("Summary")

    _show_metrics(results_df)
    _show_simulation_insights(results_df, cfg)
    _show_monthly_breakdown(results_df)

    st.markdown('<div class="section-label">Daily Average SOC Over the Year</div>', unsafe_allow_html=True)
    soc_annual = pd.DataFrame({
        "SOLCON": results_df.groupby("date")["soc_percent"].mean(),
        "Basic":  basic_df.groupby("date")["soc_percent"].mean(),
    })
    st.line_chart(soc_annual, color=["#39D353", "#58A6FF"])
    st.caption("Green = SOLCON · Blue = Basic")

    _show_daily_summary(results_df)

    with st.expander("Full Slot-by-Slot Results (large dataset)"):
        display = results_df.copy()
        display["soc"] = (display["soc"] * 100).round(1).astype(str) + "%"
        st.dataframe(display, use_container_width=True)


# ─────────────────────────────────────────────
#  Main entry point
# ─────────────────────────────────────────────

_STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,600;1,9..144,400&display=swap');

:root {
    --ink:    #0D1117;
    --ink2:   #161B22;
    --ink3:   #21262D;
    --border: #30363D;
    --text:   #E6EDF3;
    --text2:  #8B949E;
    --teal:   #39D353;
    --amber:  #E3B341;
    --blue:   #58A6FF;
    --orange: #F0883E;
    --red:    #F85149;
    --mono:   'JetBrains Mono', monospace;
    --serif:  'Fraunces', serif;
}

html, body, [class*="css"] {
    font-family: var(--mono) !important;
    background-color: var(--ink) !important;
    color: var(--text) !important;
}

.main .block-container {
    max-width: 1100px;
    padding: 2rem 2.5rem 4rem;
}
</style>
"""

def show_calculator():
    st.markdown(_STYLES, unsafe_allow_html=True)

    st.markdown("""
    <div style="font-family:'Fraunces',serif;font-size:2.6rem;font-weight:600; letter-spacing:-0.02em;color:#E6EDF3;line-height:1;margin-bottom:0.25rem;">
        <span style="color:#39D353;">Energy Calculator</span>
    </div>
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#8B949E;
                letter-spacing:0.14em;text-transform:uppercase;margin-bottom:2.5rem;">
        Smart SolCon · Off-Grid PV-BESS Load Controller
    </div>
    """, unsafe_allow_html=True)

    st.markdown('')

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Hardware</div>',unsafe_allow_html=True)
        battery_capacity  = st.number_input("Battery Capacity (kWh)",   min_value=0.1, value=16.59, step=0.01)
        soc_floor         = st.number_input("Min SOC Floor (%)",        min_value=0,   max_value=100, value=20)
        pv_capacity       = st.number_input("PV System Capacity (kWp)", min_value=0.1, value=8.0, step=0.1)
        soc_max           = st.number_input("Maximum SOC (%)",          min_value=0,   max_value=100, value=100)
        system_efficiency = st.slider(
            "System Performance Ratio",
            min_value=0.50, max_value=1.00, value=0.80, step=0.01,
            help="Accounts for heat, wiring, and inverter losses. 0.80 = 80% efficient.",
        )

    with col2:
        st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Electricity Rates (PHP / kWh)</div>',unsafe_allow_html=True)
        import_rate  = st.number_input("Import / Flat Rate",       min_value=0.0, value=15.68, step=0.01,
                                       help="Meralco standard flat tariff.")
        peak_rate    = st.number_input("TOU Peak Rate",            min_value=0.0, value=17.27, step=0.01,
                                       help="Rate during peak hours (08:00–21:00 Mon–Sat, 18:00–20:00 Sun).")
        offpeak_rate = st.number_input("TOU Off-Peak Rate",        min_value=0.0, value=13.54, step=0.01,
                                       help="Rate during all other hours.")
        export_rate  = st.number_input("Net Metering Export Rate", min_value=0.0, value=8.80,  step=0.01,
                                       help="PHP/kWh credited when surplus solar is exported to Meralco.")

    with col3:
        st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Algorithm & Location</div>', unsafe_allow_html=True)
        algorithm_mode = st.selectbox(
            "Algorithm Mode",
            [
                "SOLCON v5.1 - TOU + Load Shedding",
                "SOLCON v5.2 - TOU + No Load Shedding",
            ],
        )
        latitude  = st.number_input("Latitude",  value=14.6760, format="%.4f",
                                    help="Latitude of the location for weather data.")
        longitude = st.number_input("Longitude", value=121.0437, format="%.4f",
                                    help="Longitude of the location for weather data.")

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

    tab_daily, tab_weekly, tab_monthly, tab_annual = st.tabs([
        "Biweekly",
        "Weekly",
        "Monthly",
        "Annual",
    ])

    with tab_daily:
        _tab_daily(cfg)

    with tab_weekly:
        _tab_weekly(cfg)

    with tab_monthly:
        _tab_monthly(cfg)

    with tab_annual:
        _tab_annual(cfg)