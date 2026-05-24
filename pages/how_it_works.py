import streamlit as st

# ─────────────────────────────────────────────
#  Shared style block — Light Mode
# ─────────────────────────────────────────────

_STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,600;1,9..144,400&display=swap');

:root {
    --background: #F6F8FA;
    --surface:    #FFFFFF;
    --surface2:   #EFF1F3;
    --border:     #D0D7DE;
    --border2:    #C6CDD5;
    --ink:        #1F2328;
    --ink2:       #3D444D;
    --muted:      #656D76;
    --teal:       #1A7F37;
    --amber:      #9A6700;
    --blue:       #0969DA;
    --orange:     #BC4C00;
    --red:        #CF222E;
    --mono:       'JetBrains Mono', monospace;
    --serif:      'Fraunces', serif;
}

html, body, [class*="css"] {
    font-family: var(--mono) !important;
    background-color: var(--background) !important;
    color: var(--ink2) !important;
}

.main .block-container {
    max-width: 1100px;
    padding: 2rem 2.5rem 4rem;
}

/* Override Streamlit's default dark inputs / widgets */
.stTextInput > div > div,
.stSelectbox > div > div,
.stNumberInput > div > div {
    background-color: var(--surface) !important;
    border-color: var(--border) !important;
    color: var(--ink) !important;
}

/* ── Card hover effects ── */
.sc-card {
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
    cursor: default;
}
.sc-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(31, 35, 40, 0.12) !important;
    border-color: var(--border2) !important;
}

/* Step cards (left-accent) */
.sc-card-step {
    transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.sc-card-step:hover {
    transform: translateX(3px);
    box-shadow: 0 4px 14px rgba(31, 35, 40, 0.10) !important;
}

/* Outlook rows */
.sc-card-row {
    transition: background 0.15s ease, box-shadow 0.15s ease;
}
.sc-card-row:hover {
    background: #F0F6FF !important;
    box-shadow: 0 2px 8px rgba(9, 105, 218, 0.08) !important;
}
</style>
"""

# ─────────────────────────────────────────────
#  How It Works
# ─────────────────────────────────────────────

def show_how_it_works():
    st.markdown(_STYLES, unsafe_allow_html=True)

    st.markdown("""
    <div style="font-family:'Fraunces',serif;font-size:2.6rem;font-weight:600;
                letter-spacing:-0.02em;color:#1F2328;line-height:1;margin-bottom:0.25rem;">
        <span style="color:#1A7F37;">How It Works</span>
    </div>
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#656D76;
                letter-spacing:0.14em;text-transform:uppercase;margin-bottom:2.5rem;">
        Smart SolCon · Off-Grid PV-BESS Load Controller
    </div>
    """, unsafe_allow_html=True)

    # ── Overview blurb ──
    st.markdown("""
    <p style="font-size:0.88rem;color:#656D76;line-height:1.75;max-width:680px;margin-bottom:2rem;">
        SolCon simulates a <strong style="color:#1F2328;">PV + Battery Energy Storage System (BESS)</strong>
        against real weather data from Open-Meteo. Every 30-minute slot, the algorithm decides
        how much load to draw from solar, battery, or grid — and whether to pre-charge the battery
        from cheap off-peak grid power to survive upcoming cloudy days.
    </p>
    """, unsafe_allow_html=True)

    # ── Energy dispatch pipeline ──
    st.markdown("""
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;font-weight:600;
                letter-spacing:0.15em;text-transform:uppercase;color:#656D76;
                border-bottom:1px solid #D0D7DE;padding-bottom:0.4rem;margin-bottom:1.4rem;">
        Energy dispatch order — per 30-min slot
    </div>
    """, unsafe_allow_html=True)

    steps = [
        ("#1A7F37", "01", "PV Serves Load First",
         "Solar generation is applied directly to the total load demand. "
         "Avoids drawing from battery or grid while the sun is shining."),
        ("#0969DA", "02", "Battery Covers Remaining Load",
         "Any load not met by PV is drawn from the battery, down to the configured "
         "SOC floor. The floor protects battery longevity and reserves capacity for peak hours."),
        ("#CF222E", "03", "Grid Covers the Rest",
         "If both PV and battery are insufficient, the remainder is pulled from the grid. "
         "TOU pricing applies — peak hours (Mon–Sat 08:00–21:00) cost more."),
        ("#1A7F37", "04", "Excess PV Charges Battery",
         "After serving all loads, leftover solar charges the battery up to the maximum SOC. "
         "Round-trip efficiency (system performance ratio) is applied here."),
        ("#9A6700", "05", "Surplus PV is Exported",
         "If the battery is full and PV is still generating, the excess is exported to the "
         "Meralco grid and earns net-metering credits at the configured export rate."),
        ("#BC4C00", "06", "Optional Grid Pre-Charging",
         "During off-peak hours, if the 3-day outlook is cloudy and SOC is low, "
         "the algorithm charges from cheap grid power to prepare for days with poor solar yield."),
    ]

    for color, num, title, desc in steps:
        st.markdown(f"""
        <div class="sc-card-step" style="display:flex;gap:1.25rem;align-items:flex-start;
                    margin-bottom:1rem;padding:1rem 1.25rem;
                    background:#FFFFFF;border:1px solid #D0D7DE;
                    border-left:3px solid {color};border-radius:6px;
                    box-shadow:0 1px 3px rgba(31,35,40,0.06);">
            <div style="font-family:'Fraunces',serif;font-size:1.6rem;font-weight:600;
                        color:{color};opacity:0.45;line-height:1;min-width:2rem;">{num}</div>
            <div>
                <div style="font-size:0.82rem;font-weight:600;color:#1F2328;
                            margin-bottom:0.3rem;">{title}</div>
                <div style="font-size:0.78rem;color:#656D76;line-height:1.65;">{desc}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── PV State logic ──
    st.markdown("""
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;font-weight:600;
                letter-spacing:0.15em;text-transform:uppercase;color:#656D76;
                border-bottom:1px solid #D0D7DE;padding-bottom:0.4rem;margin-bottom:1.4rem;">
        PV State Classification
    </div>
    """, unsafe_allow_html=True)

    pv_states = [
        ("#9A6700", "CHARGE",  "> 80% of peak capacity",  "Run all loads from battery. Maximum solar surplus expected."),
        ("#1A7F37", "SUNNY",   "40 – 80% of peak",        "Run all loads from battery if SOC ≥ 61%, otherwise critical + essential only."),
        ("#0969DA", "CLOUDY",  "10 – 40% of peak",        "Prioritise battery during peak hours. Shift some load to grid off-peak if SOC is low."),
        ("#656D76", "NIGHT",   "< 10% of peak",           "Minimise battery drain. Let grid serve loads during off-peak; battery defends peak hours."),
    ]

    cols = st.columns(4)
    for col, (color, state, threshold, note) in zip(cols, pv_states):
        with col:
            st.markdown(f"""
            <div style="background:#FFFFFF;border:1px solid #D0D7DE;
                        border-top:3px solid {color};border-radius:6px;
                        padding:1rem;min-height:140px;
                        box-shadow:0 1px 3px rgba(31,35,40,0.06);">
                <div style="font-size:0.65rem;font-weight:600;letter-spacing:0.1em;
                            color:{color};margin-bottom:0.4rem;">{state}</div>
                <div style="font-size:0.7rem;color:#1F2328;margin-bottom:0.5rem;
                            font-weight:600;">{threshold}</div>
                <div style="font-size:0.72rem;color:#656D76;line-height:1.6;">{note}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Forecast outlook ──
    st.markdown("""
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;font-weight:600;
                letter-spacing:0.15em;text-transform:uppercase;color:#656D76;
                border-bottom:1px solid #D0D7DE;padding-bottom:0.4rem;margin-bottom:1.4rem;">
        3-Day Forecast Outlook
    </div>
    """, unsafe_allow_html=True)

    outlooks = [
        ("#1A7F37", "SUNNY_WEEK",  "No cloudy days ahead",      "No grid pre-charging. Let solar handle it."),
        ("#9A6700", "MIXED_WEEK",  "1 cloudy day in next 3",    "Grid-charges to 75% SOC only on LOW forecast days."),
        ("#CF222E", "CLOUDY_WEEK", "2+ cloudy days in next 3",  "Aggressive grid pre-charge to 90% SOC overnight."),
    ]

    for color, label, condition, action in outlooks:
        st.markdown(f"""
        <div style="display:flex;gap:1rem;align-items:center;
                    margin-bottom:0.6rem;padding:0.8rem 1.1rem;
                    background:#FFFFFF;border:1px solid #D0D7DE;
                    border-radius:6px;box-shadow:0 1px 3px rgba(31,35,40,0.06);">
            <div style="min-width:110px;font-size:0.65rem;font-weight:600;
                        letter-spacing:0.08em;color:{color};">{label}</div>
            <div style="min-width:200px;font-size:0.75rem;color:#656D76;">{condition}</div>
            <div style="font-size:0.75rem;color:#1F2328;">{action}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Weather data note ──
    st.markdown("""
    <div style="background:#FFFFFF;border:1px solid #D0D7DE;border-left:3px solid #0969DA;
                border-radius:6px;padding:1rem 1.25rem;font-size:0.78rem;color:#656D76;
                line-height:1.7;max-width:760px;box-shadow:0 1px 3px rgba(31,35,40,0.06);">
        <strong style="color:#0969DA;">Weather Data</strong> — SolCon fetches 15-minute interval irradiance,
        cloud cover, precipitation, and temperature from
        <span style="color:#1F2328;">Open-Meteo</span> (forecast API for upcoming days,
        archive API for historical data). Irradiance is converted to PV output using:
        <br><br>
        <code style="color:#1A7F37;background:#DAFBE1;padding:0.15rem 0.4rem;border-radius:4px;">pv_kw = pv_capacity × (irradiance / 1000) × system_efficiency</code>
        <br><br>
        Data is resampled to 30-minute slots before simulation.
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  About Us
# ─────────────────────────────────────────────

def show_about_us():
    st.markdown(_STYLES, unsafe_allow_html=True)

    st.markdown("""
    <div style="font-family:'Fraunces',serif;font-size:2.6rem;font-weight:600;
                letter-spacing:-0.02em;color:#1F2328;line-height:1;margin-bottom:0.25rem;">
        ABOUT <span style="color:#1A7F37;">US</span>
    </div>
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#656D76;
                letter-spacing:0.14em;text-transform:uppercase;margin-bottom:2.5rem;">
        Smart SolCon · PV-BESS Dispatch Research
    </div>
    """, unsafe_allow_html=True)

    # ── Mission ──
    st.markdown("""
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;font-weight:600;
                letter-spacing:0.15em;text-transform:uppercase;color:#656D76;
                border-bottom:1px solid #D0D7DE;padding-bottom:0.4rem;margin-bottom:1.4rem;">
        Mission
    </div>
    <p style="font-size:0.88rem;color:#656D76;line-height:1.8;max-width:720px;margin-bottom:2rem;">
        <strong style="color:#1F2328;">Smart SolCon</strong> is a solar energy dispatch simulator
        built for Philippine households and small businesses on Meralco's grid.
        Our goal is to make it easy to understand how a rooftop solar + battery system
        actually behaves — hour by hour, peso by peso — before committing to an installation.
    </p>
    """, unsafe_allow_html=True)

    # ── What we built ──
    st.markdown("""
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;font-weight:600;
                letter-spacing:0.15em;text-transform:uppercase;color:#656D76;
                border-bottom:1px solid #D0D7DE;padding-bottom:0.4rem;margin-bottom:1.4rem;">
        What We Built
    </div>
    """, unsafe_allow_html=True)

    features = [
        ("#1A7F37", "Real Weather Data",
         "Pulls live 15-min irradiance and cloud cover from Open-Meteo for any GPS coordinate in the Philippines. "
         "No synthetic profiles — every simulation reflects actual sky conditions."),
        ("#0969DA", "TOU-Aware Dispatch",
         "Models Meralco's Time-of-Use tariff structure. The algorithm protects battery charge "
         "specifically for peak-hour periods (Mon–Sat 08:00–21:00) where grid rates are highest."),
        ("#9A6700", "Predictive Grid Charging",
         "Looks 3 days ahead at the forecast. If a cloudy stretch is coming, SolCon pre-charges "
         "the battery from cheap off-peak grid power the night before — so you're not caught short."),
        ("#BC4C00", "Net Metering Accounting",
         "Tracks every kWh exported to the grid and credits it at your configured export rate. "
         "Bills reflect actual net metering offsets, not just gross grid consumption."),
        ("#CF222E", "Load Shedding Mode",
         "v5.1 includes a load-shedding dispatch mode that prioritises critical and essential loads "
         "during brownouts or grid instability, dropping non-critical loads to protect battery reserves."),
        ("#656D76", "Multiple Timeframes",
         "Run simulations over 3 days, a full week, the current month, or the entire previous year. "
         "Each timeframe blends historical archive data with short-range forecast data seamlessly."),
    ]

    col1, col2 = st.columns(2)
    for i, (color, title, desc) in enumerate(features):
        col = col1 if i % 2 == 0 else col2
        with col:
            st.markdown(f"""
            <div style="background:#FFFFFF;border:1px solid #D0D7DE;
                        border-left:3px solid {color};border-radius:6px;
                        padding:1rem 1.25rem;margin-bottom:1rem;min-height:110px;
                        box-shadow:0 1px 3px rgba(31,35,40,0.06);">
                <div style="font-size:0.8rem;font-weight:600;color:#1F2328;
                            margin-bottom:0.4rem;">{title}</div>
                <div style="font-size:0.76rem;color:#656D76;line-height:1.65;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tech stack ──
    st.markdown("""
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;font-weight:600;
                letter-spacing:0.15em;text-transform:uppercase;color:#656D76;
                border-bottom:1px solid #D0D7DE;padding-bottom:0.4rem;margin-bottom:1.4rem;">
        Built With
    </div>
    """, unsafe_allow_html=True)

    stack = [
        ("Python 3.11",    "Core simulation engine"),
        ("Streamlit",      "Web interface & interactive calculator"),
        ("Open-Meteo",     "Free weather & solar irradiance API"),
        ("Pandas",         "Data wrangling & time-series aggregation"),
        ("JetBrains Mono", "Interface typography"),
        ("Fraunces",       "Display typography"),
    ]

    cols = st.columns(3)
    for i, (tech, role) in enumerate(stack):
        with cols[i % 3]:
            st.markdown(f"""
            <div style="background:#FFFFFF;border:1px solid #D0D7DE;border-radius:6px;
                        padding:0.75rem 1rem;margin-bottom:0.75rem;
                        box-shadow:0 1px 3px rgba(31,35,40,0.06);">
                <div style="font-size:0.78rem;font-weight:600;color:#1A7F37;">{tech}</div>
                <div style="font-size:0.7rem;color:#656D76;margin-top:0.2rem;">{role}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Disclaimer ──
    st.markdown("""
    <div style="background:#FFFFFF;border:1px solid #D0D7DE;border-left:3px solid #656D76;
                border-radius:6px;padding:1rem 1.25rem;font-size:0.75rem;color:#656D76;
                line-height:1.7;max-width:760px;box-shadow:0 1px 3px rgba(31,35,40,0.06);">
        <strong style="color:#1F2328;">Disclaimer</strong> — SolCon is a simulation tool intended
        for educational and planning purposes. Results are based on weather model data and
        simplified load assumptions. Actual system performance will vary based on equipment
        specifications, installation quality, shading, and grid conditions.
        Always consult a licensed solar installer before making purchasing decisions.
    </div>
    """, unsafe_allow_html=True)