import streamlit as st
import altair as alt
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
        "linear-gradient(135deg,#6d28d9 0%,#8b5cf6 100%)",  # Net Metering   — purple
        "linear-gradient(135deg,#b45309 0%,#f59e0b 100%)",  # Net Bill       — amber
        "linear-gradient(135deg,#0e7490 0%,#22d3ee 100%)",  # Grid Load      — cyan
        "linear-gradient(135deg,#c2410c 0%,#fb923c 100%)",  # Grid→Battery   — orange
        "linear-gradient(135deg,#065f46 0%,#34d399 100%)",  # Battery Disc.  — green
        "linear-gradient(135deg,#1e3a5f 0%,#60a5fa 100%)",  # SOC Range      — steel
    ]

    cards = [
        ("Grid Cost",          f"PHP {total_grid_cost:,.2f}",      "Amount paid for grid energy consumed"),
        ("Net Metering",     f"PHP {total_export_credit:,.2f}",  "Net metering amount earned"),
        ("Net Bill",           f"PHP {total_net_cost:,.2f}",       "Grid cost minus net metering"),
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

def _show_comparison_metrics(results_df: pd.DataFrame, basic_df: pd.DataFrame):
    """Shows SOLCON and Basic metrics side by side for comparison — horizontal layout."""

    def _extract(df):
        return {
            "grid_cost":     df["grid_cost"].sum(),
            "export_credit": df["export_credit"].sum(),
            "net_cost":      df["net_cost"].sum(),
            "grid_load":     df["grid_load"].sum(),
            "grid_to_batt":  df["grid_to_battery"].sum(),
            "battery_load":  df["battery_load"].sum(),
            "pv_gen":        df["pv_kw"].sum() * 0.5,
        }

    s = _extract(results_df)
    b = _extract(basic_df)

    METRICS = [
        ("Net Bill",           f"PHP {s['net_cost']:,.2f}",      f"PHP {b['net_cost']:,.2f}",
         s['net_cost'] - b['net_cost'], "PHP", True),
        ("Grid Cost",          f"PHP {s['grid_cost']:,.2f}",     f"PHP {b['grid_cost']:,.2f}",
         s['grid_cost'] - b['grid_cost'], "PHP", True),
        ("Net Metering",     f"PHP {s['export_credit']:,.2f}", f"PHP {b['export_credit']:,.2f}",
         s['export_credit'] - b['export_credit'], "PHP", False),
        ("Grid Load",          f"{s['grid_load']:.2f} kWh",      f"{b['grid_load']:.2f} kWh",
         s['grid_load'] - b['grid_load'], "kWh", True),
        ("Grid to Battery",     f"{s['grid_to_batt']:.2f} kWh",   f"{b['grid_to_batt']:.2f} kWh",
         None, None, None),
        ("Battery Discharged", f"{s['battery_load']:.2f} kWh",   f"{b['battery_load']:.2f} kWh",
         None, None, None),
        ("PV Generated",       f"{s['pv_gen']:.2f} kWh",         f"{b['pv_gen']:.2f} kWh",
         None, None, None),
    ]

    SOLCON_GRAD = "linear-gradient(135deg,#065f46 0%,#34d399 100%)"
    BASIC_GRAD  = "linear-gradient(135deg,#1e3a5f 0%,#60a5fa 100%)"

    s_lbl       = ("color:rgba(255,255,255,0.75);font-size:0.58rem;font-weight:600;"
                   "letter-spacing:0.07em;text-transform:uppercase;margin-bottom:0.25rem;line-height:1.2;")
    s_val       = ("color:#ffffff;font-size:0.88rem;font-weight:800;line-height:1.1;"
                   "font-family:'JetBrains Mono',monospace;")
    s_diff_good = ("color:#39D353;font-size:0.62rem;font-weight:700;"
                   "margin-top:0.3rem;line-height:1.2;")
    s_diff_bad  = ("color:#F85149;font-size:0.62rem;font-weight:700;"
                   "margin-top:0.3rem;line-height:1.2;")
    s_metric_label = ("font-family:JetBrains Mono,monospace;font-size:0.62rem;font-weight:600;"
                      "color:#8B949E;text-transform:uppercase;letter-spacing:0.06em;"
                      "text-align:center;margin-bottom:0.35rem;")

    # Fixed height + top-aligned for both card types
    card  = ("border-radius:10px;padding:0.75rem 0.6rem;"
                   "display:flex;flex-direction:column;align-items:center;"
                   "text-align:center;margin-bottom:0.2rem;"
                   "min-height:70px;justify-content:flex-start;")

    cols = st.columns(len(METRICS))
    for col, (label, s_val_str, b_val_str, diff, unit, lower_is_better) in zip(cols, METRICS):
        with col:
            st.markdown(
                f'<div style="{s_metric_label}">{label}</div>',
                unsafe_allow_html=True,
            )

            if diff is not None:
                better = (diff < 0 and lower_is_better) or (diff > 0 and not lower_is_better)
                arrow = "↓" if diff < 0 else "↑"
                diff_str = f"{arrow} {unit} {abs(diff):,.2f} vs Basic"
                diff_style = s_diff_good if better else s_diff_bad
                diff_html = f'<div style="{diff_style}">{diff_str}</div>'
            else:
                diff_html = ""

            # SOLCON card — fixed min-height, top-aligned, diff inside
            st.markdown(
                f'<div style="{card}background:{SOLCON_GRAD};">'
                f'<div style="{s_lbl}">SOLCON</div>'
                f'<div style="{s_val}">{s_val_str}</div>'
                f'{diff_html}'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Basic card — fixed min-height, top-aligned
            st.markdown(
                f'<div style="{card}background:{BASIC_GRAD};">'
                f'<div style="{s_lbl}">Basic</div>'
                f'<div style="{s_val}">{b_val_str}</div>'
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

def _show_charts(results_df: pd.DataFrame, basic_df: pd.DataFrame = None, index_col: str = "time_label", soc_resolution: str = "hourly", grid_interval_hours: int = 3):

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
            .reset_index()
        )

    def _nhourly(df, n):
        d = _hourly(df).copy()
        d["hour"] = pd.to_datetime(d["hour"])
        d["bucket"] = d["hour"].dt.floor(f"{n}h")
        d = d.groupby("bucket")["grid_load"].sum().reset_index()
        d["hour_label"] = d["bucket"].dt.strftime("%b %d %I %p")
        return d

    hourly = _hourly(results_df)

    # ── SOC ───────────────────────────────────────────────────────────────
    st.markdown('')
    st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Battery State of Charge (%)</div>', unsafe_allow_html=True)

    if basic_df is not None:
        soc_solcon = hourly[["hour", "soc_percent"]].copy()
        soc_solcon["algorithm"] = "SOLCON"
        soc_basic = _hourly(basic_df)[["hour", "soc_percent"]].copy()
        soc_basic["algorithm"] = "Basic"
        soc_combined = pd.concat([soc_solcon, soc_basic], ignore_index=True)

        soc_chart = (
            alt.Chart(soc_combined)
            .mark_line()
            .encode(
                x=alt.X("hour:T", title="Time"),
                y=alt.Y("soc_percent:Q", title="SOC (%)", scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("algorithm:N",
                                scale=alt.Scale(domain=["SOLCON", "Basic"],
                                                range=["#39D353", "#58A6FF"]),
                                legend=alt.Legend(title="Algorithm")),
                tooltip=[
                    alt.Tooltip("hour:T", title="Time", format="%b %d %I:%M %p"),
                    alt.Tooltip("algorithm:N", title="Algorithm"),
                    alt.Tooltip("soc_percent:Q", title="SOC (%)", format=".1f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(soc_chart, use_container_width=True)
    else:
        soc_chart = (
            alt.Chart(hourly)
            .mark_line(color="#39D353")
            .encode(
                x=alt.X("hour:T", title="Time"),
                y=alt.Y("soc_percent:Q", title="SOC (%)", scale=alt.Scale(domain=[0, 100])),
                tooltip=[
                    alt.Tooltip("hour:T", title="Time", format="%b %d %I:%M %p"),
                    alt.Tooltip("soc_percent:Q", title="SOC (%)", format=".1f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(soc_chart, use_container_width=True)

    # ── Energy source breakdown ───────────────────────────────────────────
    st.markdown('')
    st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Energy Source Breakdown (kWh)</div>', unsafe_allow_html=True)

    energy_long = hourly[["hour", "battery_load", "grid_load", "grid_to_battery"]].melt(
        id_vars="hour", var_name="source", value_name="kwh"
    )
    source_labels = {
        "battery_load": "Battery",
        "grid_load": "Grid",
        "grid_to_battery": "Grid → Battery",
    }
    energy_long["source"] = energy_long["source"].map(source_labels)

    energy_chart = (
        alt.Chart(energy_long)
        .mark_area()
        .encode(
            x=alt.X("hour:T", title="Time"),
            y=alt.Y("kwh:Q", title="kWh", stack="zero"),
            color=alt.Color("source:N",
                            scale=alt.Scale(domain=["Battery", "Grid", "Grid → Battery"],
                                            range=["#58A6FF", "#F85149", "#F0883E"]),
                            legend=alt.Legend(title="Source")),
            tooltip=[
                alt.Tooltip("hour:T", title="Time", format="%b %d %I:%M %p"),
                alt.Tooltip("source:N", title="Source"),
                alt.Tooltip("kwh:Q", title="kWh", format=".3f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(energy_chart, use_container_width=True)

    # ── Grid draw comparison ──────────────────────────────────────────────
    if basic_df is not None:
        st.markdown('')
        st.markdown(f'<div style="font-weight:bold; color:gray; text-transform:uppercase;">Grid Draw Comparison (kWh)</div>', unsafe_allow_html=True)

        grid_solcon = _nhourly(results_df, grid_interval_hours)[["hour_label", "grid_load"]].copy()
        grid_solcon["algorithm"] = "SOLCON"
        grid_basic = _nhourly(basic_df, grid_interval_hours)[["hour_label", "grid_load"]].copy()
        grid_basic["algorithm"] = "Basic"
        grid_combined = pd.concat([grid_solcon, grid_basic], ignore_index=True)

        grid_chart = (
            alt.Chart(grid_combined)
            .mark_bar()
            .encode(
                x=alt.X("hour_label:O", title="Time", sort=None),
                y=alt.Y("grid_load:Q", title="kWh"),
                color=alt.Color("algorithm:N",
                                scale=alt.Scale(domain=["SOLCON", "Basic"],
                                                range=["#39D353", "#58A6FF"]),
                                legend=alt.Legend(title="Algorithm")),
                xOffset="algorithm:N",
                tooltip=[
                    alt.Tooltip("hour_label:O", title="Time"),
                    alt.Tooltip("algorithm:N", title="Algorithm"),
                    alt.Tooltip("grid_load:Q", title="kWh", format=".3f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(grid_chart, use_container_width=True)

    # ── Net Bill Comparison — daily ───────────────────────────────────────
    if basic_df is not None:
        st.markdown('')
        st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Net Bill Comparison (PhP)</div>', unsafe_allow_html=True)

        def _daily_net(df, label):
            d = df.copy()
            d["period"] = pd.to_datetime(d["time"]).dt.strftime("%b %d")
            result = d.groupby("period")["net_cost"].sum().reset_index()
            result["algorithm"] = label
            result = result.rename(columns={"net_cost": "net"})
            return result

        combined = pd.concat([
            _daily_net(results_df, "SOLCON"),
            _daily_net(basic_df, "Basic"),
        ], ignore_index=True)

        net_chart = (
            alt.Chart(combined)
            .mark_bar()
            .encode(
                x=alt.X("period:O", title="Date", sort=None),
                y=alt.Y("net:Q", title="Net Bill (PHP)",
                        axis=alt.Axis(labelExpr="'PHP ' + datum.value")),
                color=alt.Color("algorithm:N",
                                scale=alt.Scale(domain=["SOLCON", "Basic"],
                                                range=["#39D353", "#58A6FF"]),
                                legend=alt.Legend(title="Algorithm")),
                xOffset="algorithm:N",
                tooltip=[
                    alt.Tooltip("period:O", title="Date"),
                    alt.Tooltip("algorithm:N", title="Algorithm"),
                    alt.Tooltip("net:Q", title="Net Bill (PHP)", format=",.2f"),
                ],
            )
            .properties(height=350)
        )
        st.altair_chart(net_chart, use_container_width=True)

# ─────────────────────────────────────────────
#  Charts (day-aggregated — monthly)
# ─────────────────────────────────────────────

def _show_charts_daily_agg(results_df: pd.DataFrame, basic_df: pd.DataFrame = None):

    def _daily(df):
        return (
            df.copy()
            .assign(date=pd.to_datetime(df["date"]))
            .groupby("date")
            .agg(
                soc_percent=("soc_percent", "mean"),
                battery_load=("battery_load", "sum"),
                grid_load=("grid_load", "sum"),
                grid_to_battery=("grid_to_battery", "sum"),
                net_cost=("net_cost", "sum"),
            )
            .reset_index()
        )

    daily = _daily(results_df)

    # ── SOC ───────────────────────────────────────────────────────────────
    st.markdown('')
    st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Battery SOC Over Time (%)</div>', unsafe_allow_html=True)

    if basic_df is not None:
        soc_solcon = daily[["date", "soc_percent"]].copy()
        soc_solcon["algorithm"] = "SOLCON"
        soc_basic = _daily(basic_df)[["date", "soc_percent"]].copy()
        soc_basic["algorithm"] = "Basic"
        soc_combined = pd.concat([soc_solcon, soc_basic], ignore_index=True)

        soc_chart = (
            alt.Chart(soc_combined)
            .mark_line()
            .encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("soc_percent:Q", title="SOC (%)", scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("algorithm:N",
                                scale=alt.Scale(domain=["SOLCON", "Basic"],
                                                range=["#39D353", "#58A6FF"]),
                                legend=alt.Legend(title="Algorithm")),
                tooltip=[
                    alt.Tooltip("date:T", title="Date", format="%b %d"),
                    alt.Tooltip("algorithm:N", title="Algorithm"),
                    alt.Tooltip("soc_percent:Q", title="SOC (%)", format=".1f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(soc_chart, use_container_width=True)
    else:
        soc_chart = (
            alt.Chart(daily)
            .mark_line(color="#39D353")
            .encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("soc_percent:Q", title="SOC (%)", scale=alt.Scale(domain=[0, 100])),
                tooltip=[
                    alt.Tooltip("date:T", title="Date", format="%b %d"),
                    alt.Tooltip("soc_percent:Q", title="SOC (%)", format=".1f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(soc_chart, use_container_width=True)

    # ── Energy source breakdown ───────────────────────────────────────────
    st.markdown('')
    st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Daily Energy Source Breakdown (kWh)</div>', unsafe_allow_html=True)

    energy_long = daily[["date", "battery_load", "grid_load", "grid_to_battery"]].melt(
        id_vars="date", var_name="source", value_name="kwh"
    )
    source_labels = {
        "battery_load": "Battery",
        "grid_load": "Grid",
        "grid_to_battery": "Grid → Battery",
    }
    energy_long["source"] = energy_long["source"].map(source_labels)

    energy_chart = (
        alt.Chart(energy_long)
        .mark_area()
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("kwh:Q", title="kWh", stack="zero"),
            color=alt.Color("source:N",
                            scale=alt.Scale(domain=["Battery", "Grid", "Grid → Battery"],
                                            range=["#58A6FF", "#F85149", "#F0883E"]),
                            legend=alt.Legend(title="Source")),
            tooltip=[
                alt.Tooltip("date:T", title="Date", format="%b %d"),
                alt.Tooltip("source:N", title="Source"),
                alt.Tooltip("kwh:Q", title="kWh", format=".2f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(energy_chart, use_container_width=True)

    # ── Grid draw comparison ──────────────────────────────────────────────
    if basic_df is not None:
        st.markdown('')
        st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Daily Grid Draw Comparison (kWh)</div>', unsafe_allow_html=True)

        grid_solcon = daily[["date", "grid_load"]].copy()
        grid_solcon["algorithm"] = "SOLCON"
        grid_basic = _daily(basic_df)[["date", "grid_load"]].copy()
        grid_basic["algorithm"] = "Basic"
        grid_combined = pd.concat([grid_solcon, grid_basic], ignore_index=True)
        grid_combined["date_label"] = pd.to_datetime(grid_combined["date"]).dt.strftime("%b %d")

        grid_chart = (
            alt.Chart(grid_combined)
            .mark_bar()
            .encode(
                x=alt.X("date_label:O", title="Date", sort=None),
                y=alt.Y("grid_load:Q", title="kWh"),
                color=alt.Color("algorithm:N",
                                scale=alt.Scale(domain=["SOLCON", "Basic"],
                                                range=["#39D353", "#58A6FF"]),
                                legend=alt.Legend(title="Algorithm")),
                xOffset="algorithm:N",
                tooltip=[
                    alt.Tooltip("date_label:O", title="Date"),
                    alt.Tooltip("algorithm:N", title="Algorithm"),
                    alt.Tooltip("grid_load:Q", title="kWh", format=".2f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(grid_chart, use_container_width=True)

    # ── Net Bill Comparison ───────────────────────────────────────────────
    _show_net_bill_chart(results_df, period="daily", basic_df=basic_df)

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

def _show_monthly_breakdown(results_df: pd.DataFrame, basic_df: pd.DataFrame = None):
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

    st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Monthly Breakdown</div>', unsafe_allow_html=True)
    st.dataframe(monthly, use_container_width=True)

    _show_net_bill_chart(results_df, period="monthly", basic_df=basic_df)

    # ── Monthly Energy Sources ────────────────────────────────────────────
    st.markdown('')
    st.markdown('<div style="font-weight:bold; color:gray; text-transform:uppercase;">Monthly Energy Sources (kWh)</div>', unsafe_allow_html=True)

    energy_long = monthly[["month", "battery_load", "grid_load", "grid_to_battery"]].melt(
        id_vars="month", var_name="source", value_name="kwh"
    )
    source_labels = {
        "battery_load": "Battery",
        "grid_load": "Grid",
        "grid_to_battery": "Grid → Battery",
    }
    energy_long["source"] = energy_long["source"].map(source_labels)

    energy_chart = (
        alt.Chart(energy_long)
        .mark_area()
        .encode(
            x=alt.X("month:O", title="Month", sort=None),
            y=alt.Y("kwh:Q", title="kWh", stack="zero"),
            color=alt.Color(
                "source:N",
                scale=alt.Scale(
                    domain=["Battery", "Grid", "Grid → Battery"],
                    range=["#58A6FF", "#F85149", "#F0883E"],
                ),
                legend=alt.Legend(title="Source"),
            ),
            tooltip=[
                alt.Tooltip("month:O", title="Month"),
                alt.Tooltip("source:N", title="Source"),
                alt.Tooltip("kwh:Q", title="kWh", format=".2f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(energy_chart, use_container_width=True)

# ─────────────────────────────────────────────
#  Net bill chart (shared)
# ─────────────────────────────────────────────

def _show_net_bill_chart(results_df: pd.DataFrame, period: str = "daily", basic_df: pd.DataFrame = None):
    df = results_df.copy()
    if "datetime" not in df.columns:
        df["datetime"] = pd.to_datetime(df["time"])

    if period == "daily":
        df["period"] = df["datetime"].dt.strftime("%b %d")
        title = "Net Bill Comparison (PhP)"
    else:
        df["period"] = df["datetime"].dt.to_period("M").astype(str)
        title = "Net Bill Comparison (PhP)"

    solcon_bill = (
        df.groupby("period")
        .agg(grid_cost=("grid_cost", "sum"), export_credit=("export_credit", "sum"))
        .reset_index()
    )
    solcon_bill["net"] = (solcon_bill["grid_cost"] - solcon_bill["export_credit"]).round(2)

    st.markdown(f'<div style="font-weight:bold; color:gray; text-transform:uppercase;">{title}</div>', unsafe_allow_html=True)

    if basic_df is not None:
        b = basic_df.copy()
        if "datetime" not in b.columns:
            b["datetime"] = pd.to_datetime(b["time"])
        if period == "daily":
            b["period"] = b["datetime"].dt.strftime("%b %d")
        else:
            b["period"] = b["datetime"].dt.to_period("M").astype(str)

        basic_bill = (
            b.groupby("period")
            .agg(grid_cost=("grid_cost", "sum"), export_credit=("export_credit", "sum"))
            .reset_index()
        )
        basic_bill["net"] = (basic_bill["grid_cost"] - basic_bill["export_credit"]).round(2)

        # Merge into long format for Altair
        solcon_long = solcon_bill[["period", "net"]].copy()
        solcon_long["algorithm"] = "SOLCON"
        basic_long = basic_bill[["period", "net"]].copy()
        basic_long["algorithm"] = "Basic"
        combined = pd.concat([solcon_long, basic_long], ignore_index=True)

        chart = (
            alt.Chart(combined)
            .mark_bar()
            .encode(
                x=alt.X("period:O", title="Date", sort=None),
                y=alt.Y("net:Q", title="Net Bill (PHP)",
                        axis=alt.Axis(labelExpr="'PHP ' + datum.value")),
                color=alt.Color("algorithm:N",
                                scale=alt.Scale(
                                    domain=["SOLCON", "Basic"],
                                    range=["#39D353", "#58A6FF"]
                                ),
                                legend=alt.Legend(title="Algorithm")),
                xOffset="algorithm:N",
                tooltip=[
                    alt.Tooltip("period:O", title="Date"),
                    alt.Tooltip("algorithm:N", title="Algorithm"),
                    alt.Tooltip("net:Q", title="Net Bill (PHP)", format=",.2f"),
                ],
            )
            .properties(height=350)
        )
        st.altair_chart(chart, use_container_width=True)

    else:
        solcon_long = solcon_bill[["period", "net"]].copy()
        solcon_long["algorithm"] = "SOLCON"

        chart = (
            alt.Chart(solcon_long)
            .mark_bar(color="#39D353")
            .encode(
                x=alt.X("period:O", title="Date", sort=None),
                y=alt.Y("net:Q", title="Net Bill (PHP)",
                        axis=alt.Axis(labelExpr="'PHP ' + datum.value")),
                tooltip=[
                    alt.Tooltip("period:O", title="Date"),
                    alt.Tooltip("net:Q", title="Net Bill (PHP)", format=",.2f"),
                ],
            )
            .properties(height=350)
        )
        st.altair_chart(chart, use_container_width=True)

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

    _show_comparison_metrics(results_df, basic_df)
    _show_simulation_insights(results_df, cfg)
    _show_charts(results_df, basic_df=basic_df, grid_interval_hours=3) # ← add basic_df
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

    _show_comparison_metrics(results_df, basic_df)
    _show_simulation_insights(results_df, cfg)
    _show_charts(results_df, basic_df=basic_df, grid_interval_hours=6)
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
    _show_comparison_metrics(results_df, basic_df)
    _show_simulation_insights(results_df, monthly_cfg)
    _show_charts_daily_agg(results_df, basic_df=basic_df)
    _show_daily_summary(results_df)

    with st.expander("Full Slot-by-Slot Results"):
        display = results_df.copy()
        display["soc"] = (display["soc"] * 100).round(1).astype(str) + "%"
        st.dataframe(display, use_container_width=True)


def _tab_annual(cfg: SystemConfig):
    prev_year = datetime.date.today().year - 1
    st.caption(f"Historical data for the full year {prev_year} (Jan 1 – Dec 31).")
    if not st.button("▶ Run Annual Simulation", type="primary", key="run_annual"):
        return

    with st.spinner(f"Fetching historical data for {prev_year}… (this may take ~10–20 s)"):
        raw_df = get_weather_annual(cfg.latitude, cfg.longitude)

    with st.spinner("Running simulation (365 days)…"):
        results_df = _run_simulation(raw_df, cfg)
        basic_df   = _run_basic_simulation(raw_df, cfg)

    st.divider()
    st.subheader("Summary")

    _show_comparison_metrics(results_df, basic_df)
    _show_simulation_insights(results_df, cfg)
    _show_monthly_breakdown(results_df, basic_df=basic_df)

    # ── Daily Average SOC Over the Year ──────────────────────────────────
    st.markdown('<div class="section-label">Daily Average SOC Over the Year</div>', unsafe_allow_html=True)

    soc_solcon = results_df.groupby("date")["soc_percent"].mean().reset_index()
    soc_solcon["algorithm"] = "SOLCON"
    soc_basic  = basic_df.groupby("date")["soc_percent"].mean().reset_index()
    soc_basic["algorithm"] = "Basic"
    soc_annual = pd.concat([soc_solcon, soc_basic], ignore_index=True)
    soc_annual["date"] = pd.to_datetime(soc_annual["date"])

    soc_chart = (
        alt.Chart(soc_annual)
        .mark_line()
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("soc_percent:Q", title="SOC (%)", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color(
                "algorithm:N",
                scale=alt.Scale(domain=["SOLCON", "Basic"], range=["#39D353", "#58A6FF"]),
                legend=alt.Legend(title="Algorithm"),
            ),
            tooltip=[
                alt.Tooltip("date:T", title="Date", format="%b %d"),
                alt.Tooltip("algorithm:N", title="Algorithm"),
                alt.Tooltip("soc_percent:Q", title="SOC (%)", format=".1f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(soc_chart, use_container_width=True)

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
            min_value=0.50, max_value=1.00, value=0.96, step=0.01,
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