"""
SOLCON v5 — Battery Dispatch Algorithm
Implements v5.1 (TOU + Load Shedding) and v5.2 (TOU + No Load Shedding)

Rates are simplified to three user-facing inputs:
  import_rate  — what you pay Meralco (flat baseline, also used as export credit)
  peak_rate    — what you pay during peak hours (TOU/POP enrolled)
  offpeak_rate — what you pay during off-peak hours (TOU/POP enrolled)
"""

from dataclasses import dataclass
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# STEP 0 — System config (all overridable from Streamlit UI)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SystemConfig:
    # Hardware
    battery_cap: float   = 16.59   # kWh nominal capacity
    battery_min: float   = 0.20    # SOC floor — never discharge below this
    lfp_rt_eff: float    = 0.96    # LFP round-trip charge efficiency
    pv_rated_kw: float   = 8.0     # kWp installed
    slot_h: float        = 0.5     # hours per slot (30 min)
    max_gc: float        = 2.5     # max grid draw per slot for charging (kWh)

    # v5.1 load tiers (kWh per 30-min slot)
    load_c: float        = 0.200   # Critical: medical, essential lights
    load_e: float        = 0.350   # Essential: fridge, fans
    load_n: float        = 0.250   # Non-critical: aircon, TV

    # v5.2 full load per slot (= 27.2 kWh/day ÷ 48 slots)
    load_full: float     = 0.5667

    # Grid-charge SOC targets
    gc_mixed_tgt: float  = 0.75    # charge to 75% on MIXED_WEEK
    gc_cloudy_tgt: float = 0.85    # charge to 85% on CLOUDY_WEEK
    min_soc_gap: float   = 0.10    # min SOC gap below target to fire gate

    # Simplified tariff rates (PHP/kWh) — set from UI
    peak_rate: float     = 17.27   # peak hour rate (user's current season)
    offpeak_rate: float  = 13.54   # off-peak rate
    import_rate: float   = 15.68   # flat/import rate; also used as export credit
    rate_export: float   = 8.80    # net metering export credit (PHP/kWh)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Time slot helpers
# ─────────────────────────────────────────────────────────────────────────────

def is_peak(slot: int, weekday: int) -> bool:
    """
    Mon–Sat peak: slots 16–41  (08:00–21:00)
    Sunday peak:  slots 36–39  (18:00–20:00) — only 4 slots!
    weekday: 0=Mon … 6=Sun
    """
    if weekday == 6:
        return 36 <= slot <= 39
    return 16 <= slot <= 41


def get_rate(slot: int, weekday: int, cfg: SystemConfig) -> float:
    """Returns PHP/kWh tariff for this slot using simplified peak/offpeak rates."""
    return cfg.peak_rate if is_peak(slot, weekday) else cfg.offpeak_rate


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — PV state classification
# ─────────────────────────────────────────────────────────────────────────────

def classify_pv(pv_kw: float, cfg: SystemConfig) -> str:
    """
    CHARGE  > 80% of rated  (e.g. > 6.4 kW on 8 kWp)
    SUNNY   > 40% of rated  (3.2–6.4 kW)
    CLOUDY  > 10% of rated  (0.8–3.2 kW)
    NIGHT   ≤ 10% of rated  (≤ 0.8 kW — night OR heavy overcast)
    """
    ratio = pv_kw / cfg.pv_rated_kw
    if   ratio > 0.80: return "CHARGE"
    elif ratio > 0.40: return "SUNNY"
    elif ratio > 0.10: return "CLOUDY"
    else:              return "NIGHT"


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Forecast tier and 3-day week outlook
# ─────────────────────────────────────────────────────────────────────────────

def forecast_tier(kwh: float) -> str:
    """
    HIGH   > 20 kWh/day  — clear sky
    MEDIUM 10–20 kWh/day — partly cloudy
    LOW    < 10 kWh/day  — overcast / rainy
    kwh is the TOTAL predicted PV generation for that day (not raw weather metrics).
    """
    if   kwh > 20.0:  return "HIGH"
    elif kwh >= 10.0: return "MEDIUM"
    else:             return "LOW"


def week_outlook(day: int, daily_kwh: dict) -> str:
    """
    Looks at next 3 days of forecast to classify upcoming week:
    SUNNY_WEEK   — all 3 next days HIGH (> 20 kWh)
    CLOUDY_WEEK  — 2+ LOW days (< 10 kWh) in next 3
    MIXED_WEEK   — everything else
    Falls back to today's value for missing future days.
    """
    low = med = 0
    for i in range(1, 4):
        kwh  = daily_kwh.get(day + i, daily_kwh[day])
        tier = forecast_tier(kwh)
        if   tier == "LOW":    low += 1
        elif tier == "MEDIUM": med += 1
    if   low == 0 and med == 0: return "SUNNY_WEEK"
    elif low >= 2:              return "CLOUDY_WEEK"
    else:                       return "MIXED_WEEK"


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Grid-charging profitability gate
# ─────────────────────────────────────────────────────────────────────────────

def should_grid_charge(outlook: str, t_kwh: float, soc: float,
                        cfg: SystemConfig) -> Optional[float]:
    """
    Called ONLY during NIGHT + OFF-PEAK slots.
    Returns target SOC if charging is profitable, None otherwise.

    SUNNY_WEEK  → never charge (PV refills naturally)
    MIXED_WEEK  → charge only if tomorrow is LOW (<10 kWh) AND gap ≥ 10%
    CLOUDY_WEEK → charge if gap ≥ 10%
    """
    if outlook == "SUNNY_WEEK":
        return None
    target = cfg.gc_mixed_tgt if outlook == "MIXED_WEEK" else cfg.gc_cloudy_tgt
    if outlook == "MIXED_WEEK" and t_kwh >= 10.0:
        return None  # tomorrow is MEDIUM/HIGH — PV handles it
    if soc >= target - cfg.min_soc_gap:
        return None  # already close enough to target
    return target


def calc_grid_charge(target: float, soc: float, cfg: SystemConfig) -> float:
    """
    kWh to DRAW from grid for charging (capped at MAX_GC).
    Actual stored = gc × LFP_RT_EFF, applied in energy_balance.
    """
    gap_kwh = (target - soc) * cfg.battery_cap
    return min(gap_kwh, cfg.max_gc)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5a — v5.1 dispatch (TOU + Load Shedding)
# ─────────────────────────────────────────────────────────────────────────────

def dispatch_v51(pv_state: str, soc: float, t_tier: str,
                 slot: int, weekday: int, t_kwh: float,
                 outlook: str, cfg: SystemConfig) -> tuple:
    """
    Returns (bl, gl, gc):
      bl = kWh battery → loads
      gl = kWh grid → loads directly
      gc = kWh grid → battery (charging)
    gc is always 0 during daytime (CHARGE/SUNNY/CLOUDY).
    """
    C, E, N = cfg.load_c, cfg.load_e, cfg.load_n

    # ── DAYTIME ──────────────────────────────────────────────────────────────
    if pv_state == "CHARGE":
        return (C + E + N, 0.0, 0.0)          # strong sun — run everything

    elif pv_state == "SUNNY":
        if soc >= 0.61:
            return (C + E + N, 0.0, 0.0)      # battery healthy — all loads
        else:
            return (C + E, 0.0, 0.0)           # battery low — shed N (aircon/TV)

    elif pv_state == "CLOUDY":
        if is_peak(slot, weekday):
            return (C + E, 0.0, 0.0)           # cloudy + peak — shed N, no grid
        else:
            if soc >= 0.61:
                return (C + E, 0.0, 0.0)
            else:
                return (C, E, 0.0)             # split: battery=C, grid=E (cheap offpeak)

    # ── NIGHT ────────────────────────────────────────────────────────────────
    else:
        if is_peak(slot, weekday):
            # Never charge during peak — gc always 0
            if soc > cfg.battery_min:
                return (C + E, 0.0, 0.0)
            else:
                return (0.0, C + E, 0.0)       # floor hit — forced peak grid draw

        else:
            # OFF-PEAK night: run gate, then pick load source
            gc_target = should_grid_charge(outlook, t_kwh, soc, cfg)
            gc = calc_grid_charge(gc_target, soc, cfg) if gc_target else 0.0

            if outlook == "SUNNY_WEEK":
                if soc > cfg.battery_min:
                    bl, gl = C + E, 0.0
                else:
                    bl, gl = 0.0, C + E

            elif soc >= 0.61:
                bl, gl = C + E, 0.0            # high SOC — battery covers all

            elif soc > cfg.battery_min:         # mid-range 21%–60%
                if outlook == "MIXED_WEEK":
                    if t_tier == "HIGH":
                        bl, gl = C + E, 0.0
                    elif t_tier == "MEDIUM":
                        bl, gl = (C + E, 0.0) if soc > 0.35 else (C, E)
                    else:  # LOW
                        bl, gl = (C + E, 0.0) if soc > 0.45 else (C, E)
                else:  # CLOUDY_WEEK — more protective
                    if t_tier == "HIGH":
                        bl, gl = C + E, 0.0
                    elif t_tier == "MEDIUM":
                        bl, gl = (C + E, 0.0) if soc > 0.40 else (C, E)
                    else:  # LOW
                        bl, gl = (C + E, 0.0) if soc > 0.55 else (C, E)
            else:
                bl, gl = 0.0, C + E            # floor hit

            return (bl, gl, gc)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5b — v5.2 dispatch (TOU + No Load Shedding)
# ─────────────────────────────────────────────────────────────────────────────

def dispatch_v52(pv_state: str, soc: float, slot: int, weekday: int,
                 t_kwh: float, outlook: str, cfg: SystemConfig) -> tuple:
    """
    Always serves LOAD_FULL — no shedding ever.
    Simpler SOC thresholds vs v5.1. Gate logic identical.
    """
    FL = cfg.load_full

    if pv_state != "NIGHT":
        return (FL, 0.0, 0.0)                  # daytime — always full load, no grid

    elif is_peak(slot, weekday):
        if soc > cfg.battery_min:
            return (FL, 0.0, 0.0)
        else:
            return (0.0, FL, 0.0)              # floor hit during peak

    else:  # NIGHT + OFF-PEAK
        gc_target = should_grid_charge(outlook, t_kwh, soc, cfg)
        gc = calc_grid_charge(gc_target, soc, cfg) if gc_target else 0.0

        if outlook == "SUNNY_WEEK":
            bl, gl = (FL, 0.0) if soc > cfg.battery_min else (0.0, FL)
        elif outlook == "MIXED_WEEK":
            bl, gl = (FL, 0.0) if soc > 0.35 else (0.0, FL)
        else:  # CLOUDY_WEEK
            bl, gl = (FL, 0.0) if soc > 0.50 else (0.0, FL)

        return (bl, gl, gc)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — Energy balance and SOC update (shared)
# ─────────────────────────────────────────────────────────────────────────────

def energy_balance(pv_kwh: float, bl: float, gc: float,
                   soc: float, cfg: SystemConfig) -> tuple:
    """
    Returns (new_soc, ge, exported).
      ge       — emergency grid bridge (battery couldn't cover bl)
      exported — solar surplus sent to Meralco (never stored grid energy)
    """
    net = pv_kwh - bl

    if net >= 0:
        headroom = (1.0 - soc) * cfg.battery_cap
        charged  = min(net, headroom)
        soc     += charged / cfg.battery_cap
        exported = net - charged
        ge       = 0.0
    else:
        needed    = -net
        avail     = max(0.0, (soc - cfg.battery_min)) * cfg.battery_cap
        from_batt = min(needed, avail)
        soc      -= from_batt / cfg.battery_cap
        ge        = max(0.0, needed - from_batt)
        exported  = 0.0

    if gc > 0:
        headroom = (1.0 - soc) * cfg.battery_cap
        actual   = min(gc * cfg.lfp_rt_eff, headroom)
        soc     += actual / cfg.battery_cap

    soc = max(cfg.battery_min, min(1.0, soc))
    return soc, ge, exported


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — Per-slot runner
# ─────────────────────────────────────────────────────────────────────────────

def run_slot(slot: int, day: int, pv_kw: float, soc_in: float,
             weekday: int, daily_kwh: dict,
             version: str, cfg: SystemConfig) -> tuple:
    """Runs one 30-min slot. Returns (new_soc, result_dict)."""
    pv_kwh   = pv_kw * cfg.slot_h
    pv_state = classify_pv(pv_kw, cfg)
    t_kwh    = daily_kwh.get(day + 1, daily_kwh[day])
    t_tier   = forecast_tier(t_kwh)
    outlook  = week_outlook(day, daily_kwh)
    peak     = is_peak(slot, weekday)
    rate     = get_rate(slot, weekday, cfg)

    if version == "v51":
        bl, gl, gc = dispatch_v51(pv_state, soc_in, t_tier,
                                   slot, weekday, t_kwh, outlook, cfg)
    else:
        bl, gl, gc = dispatch_v52(pv_state, soc_in,
                                   slot, weekday, t_kwh, outlook, cfg)

    soc_out, ge, exported = energy_balance(pv_kwh, bl, gc, soc_in, cfg)

    total_grid = gl + ge + gc
    grid_cost  = total_grid * rate
    export_rev = exported   * cfg.rate_export
    net_cost   = grid_cost  - export_rev

    return soc_out, {
        "day": day, "slot": slot,
        "time": f"{slot // 2:02d}:{(slot % 2) * 30:02d}",
        "weekday": weekday, "peak": peak, "rate": rate,
        "pv_kw": pv_kw, "pv_kwh": pv_kwh, "pv_state": pv_state,
        "outlook": outlook, "t_tier": t_tier,
        "soc_start": soc_in, "soc_end": soc_out,
        "bl": bl, "gl": gl, "gc": gc, "ge": ge,
        "exported": exported, "total_grid": total_grid,
        "grid_cost": grid_cost, "export_rev": export_rev, "net_cost": net_cost,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — Simulation loop
# ─────────────────────────────────────────────────────────────────────────────

def run_simulation(profiles: list, daily_kwh: dict,
                   version: str,
                   start_weekday: int = 1,
                   soc_init: float = 0.50,
                   cfg: SystemConfig = None) -> list:
    """
    profiles      — list of {day, slot, pv_kw}, sorted by (day, slot)
    daily_kwh     — {day: total_pv_kwh} used for gate and outlook
    version       — "v51" or "v52"
    start_weekday — 0=Mon … 6=Sun for day 1
    soc_init      — starting SOC (fixed at 0.50 = 50%)
    cfg           — SystemConfig; uses defaults if None
    """
    if cfg is None:
        cfg = SystemConfig()
    soc     = soc_init
    results = []
    for entry in profiles:
        day     = entry["day"]
        slot    = entry["slot"]
        pv_kw   = entry["pv_kw"]
        weekday = (start_weekday + day - 1) % 7
        soc, result = run_slot(slot, day, pv_kw, soc,
                               weekday, daily_kwh, version, cfg)
        results.append(result)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# STEP 9 — Aggregation
# ─────────────────────────────────────────────────────────────────────────────

def aggregate_daily(results: list) -> dict:
    daily = {}
    for r in results:
        d = r["day"]
        if d not in daily:
            daily[d] = dict(grid_kwh=0.0, pv_kwh=0.0, exported=0.0, gc_kwh=0.0,
                            grid_cost=0.0, export_rev=0.0, net_cost=0.0,
                            peak_grid=0.0, min_soc=1.0, max_soc=0.0)
        d_ = daily[d]
        d_["grid_kwh"]   += r["total_grid"]
        d_["pv_kwh"]     += r["pv_kwh"]
        d_["exported"]   += r["exported"]
        d_["gc_kwh"]     += r["gc"]
        d_["grid_cost"]  += r["grid_cost"]
        d_["export_rev"] += r["export_rev"]
        d_["net_cost"]   += r["net_cost"]
        if r["peak"]:
            d_["peak_grid"] += r["gl"] + r["ge"]
        d_["min_soc"] = min(d_["min_soc"], r["soc_end"])
        d_["max_soc"] = max(d_["max_soc"], r["soc_end"])
    return daily


def aggregate_monthly(daily: dict) -> dict:
    keys = ["grid_kwh", "pv_kwh", "exported", "gc_kwh",
            "grid_cost", "export_rev", "net_cost", "peak_grid"]
    return {k: sum(d[k] for d in daily.values()) for k in keys}


# ─────────────────────────────────────────────────────────────────────────────
# WEATHER HELPER — open-meteo shortwave_radiation → pv_kw → profiles/daily_kwh
# ─────────────────────────────────────────────────────────────────────────────

def pv_kw_from_radiation(shortwave_wm2: float, pv_rated_kw: float,
                          system_losses: float = 0.80) -> float:
    """
    Converts shortwave irradiance (W/m²) to estimated PV output (kW).

    Formula:  pv_kw = pv_rated_kw × (irradiance / 1000) × system_losses

    1000 W/m² = Standard Test Condition (full bright sun).
    system_losses (~0.80) accounts for heat, wiring, and inverter efficiency.
    """
    return pv_rated_kw * (shortwave_wm2 / 1000.0) * system_losses


def prepare_inputs_from_forecast(forecast_df, pv_rated_kw: float,
                                  system_losses: float = 0.80) -> tuple:
    """
    Converts an open-meteo hourly DataFrame into (profiles, daily_kwh).

    forecast_df must have columns:
      time                 — datetime (hourly)
      shortwave_radiation  — W/m²

    Each hourly reading is expanded into 2 half-hour slots (open-meteo is hourly).
    Returns:
      profiles   — list of {day, slot, pv_kw}, 48 entries per day
      daily_kwh  — dict {day_number: total_pv_kwh_that_day}
    """
    import pandas as pd
    df = forecast_df.copy()
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)
    df["date"] = df["time"].dt.date

    profiles  = []
    daily_kwh = {}
    day_num   = 1

    for date, group in df.groupby("date"):
        group      = group.reset_index(drop=True)
        slot       = 0
        day_pv_kwh = 0.0
        for _, row in group.iterrows():
            pv_kw = pv_kw_from_radiation(
                row["shortwave_radiation"], pv_rated_kw, system_losses
            )
            for _ in range(2):          # each hour → 2 × 30-min slots
                if slot < 48:
                    profiles.append({"day": day_num, "slot": slot, "pv_kw": pv_kw})
                    day_pv_kwh += pv_kw * 0.5
                    slot += 1
        daily_kwh[day_num] = day_pv_kwh
        day_num += 1

    return profiles, daily_kwh
