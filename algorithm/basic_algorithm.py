from dataclasses import dataclass
from typing import List, Dict, Any
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
#  Basic (Baseline) Algorithm
#
#  Logic (from the report):
#    - Targets a flat average load every 30-min slot, regardless of PV/SOC/time
#    - flat_load = daily_avg_kwh / 48 slots
#    - PV serves load first
#    - Battery covers remaining load (down to soc_floor)
#    - Grid covers any remaining shortfall
#    - Surplus PV charges battery, then exports
#    - Never charges battery from grid
#
#  Output columns are a strict superset of what _show_metrics, _show_charts,
#  _show_daily_summary, etc. expect — so basic results can be passed to any
#  existing display function unchanged.
# ─────────────────────────────────────────────────────────────────────────────

SLOT_HOURS = 0.5   # 30-min slots throughout


def simulate_basic(
    pv_data: pd.DataFrame,
    daily_kwh: dict,        # {date_str: total_pv_kwh} — same shape as solcon receives
    start_weekday: int,     # kept for API compatibility; not used by basic logic
    cfg,                    # SystemConfig from solcon_v51
) -> List[Dict[str, Any]]:
    """
    Baseline algorithm: flat load every slot, no load shedding, no TOU awareness.
    Grid absorbs whatever the battery cannot cover once it hits soc_floor.
    """

    # Flat load per slot = average daily consumption / 48 slots.
    # We derive "average daily consumption" from the system's full-load tiers,
    # which matches the report's 27.2 kWh / 48 = 0.5667 kWh/slot baseline.
    # Using cfg load tiers keeps it consistent with whatever the user configured.
    # cfg load tier fields are already in kWh/slot (not kW), so sum directly
    flat_load_per_slot = cfg.critical_load + cfg.essential_load + cfg.noncritical_load
    # = 0.200 + 0.350 + 0.250 = 0.800 kWh/slot = 38.4 kWh/day

    soc = cfg.initial_soc
    results = []
    dates = list(daily_kwh.keys())

    for i, row in pv_data.iterrows():
        current_date = row["date"]
        slot = row["slot"]
        pv_kw = row["pv_kw"]           # already efficiency-adjusted by prepare_weather_data

        day_index = dates.index(current_date) if current_date in dates else 0
        weekday = (start_weekday + day_index) % 7

        # pv_kw is already in post-efficiency kW; convert to kWh for this slot
        pv_kwh = pv_kw * SLOT_HOURS
        load_kwh = flat_load_per_slot

        # ── 1. PV serves load first ───────────────────────────────────────
        pv_to_load = min(pv_kwh, load_kwh)
        remaining_load = load_kwh - pv_to_load
        remaining_pv = pv_kwh - pv_to_load

        # ── 2. Battery serves remaining load (bounded by soc_floor) ──────
        available_battery = max(0.0, (soc - cfg.soc_floor) * cfg.battery_capacity)
        battery_to_load = min(remaining_load, available_battery)
        soc -= battery_to_load / cfg.battery_capacity
        remaining_load -= battery_to_load

        # ── 3. Grid serves anything left ──────────────────────────────────
        grid_to_load = remaining_load   # may be > 0 when battery is at floor

        # ── 4. Surplus PV charges battery ────────────────────────────────
        battery_headroom = max(0.0, (cfg.soc_max - soc) * cfg.battery_capacity)
        pv_to_battery = min(remaining_pv, battery_headroom)
        soc += pv_to_battery / cfg.battery_capacity

        # ── 5. Remaining PV is exported ───────────────────────────────────
        export_kwh = max(0.0, remaining_pv - pv_to_battery)

        # ── 6. No grid charging (basic never charges from grid) ───────────
        grid_to_battery = 0.0

        # SOC clamp
        soc = max(cfg.soc_floor, min(cfg.soc_max, soc))

        # ── Financials (flat import rate — no TOU awareness) ──────────────
        grid_cost = grid_to_load * cfg.import_rate
        export_credit = export_kwh * cfg.export_rate
        net_cost = grid_cost - export_credit

        results.append({
            # ── identity / time ──────────────────────────────────────────
            "time":             row["time"],
            "date":             current_date,
            "slot":             slot,
            "weekday":          weekday,

            # ── PV ───────────────────────────────────────────────────────
            "pv_kw":            pv_kw,
            "pv_kwh":           pv_kwh,
            "pv_state":         "BASIC",     # sentinel; not used by display fns
            "is_peak":          False,
            "forecast_tier":    "N/A",
            "outlook":          "N/A",

            # ── demand (decision layer — same field names as solcon) ──────
            "load_demand":      load_kwh,
            "battery_demand":   battery_to_load,
            "grid_demand":      grid_to_load,
            "grid_charge":      0.0,

            # ── actual energy flow (what _show_metrics / charts read) ─────
            "pv_to_load":       pv_to_load,
            "battery_load":     battery_to_load,   # ← _show_metrics key
            "grid_load":        grid_to_load,       # ← _show_metrics key
            "pv_to_battery":    pv_to_battery,
            "grid_to_battery":  grid_to_battery,    # ← _show_metrics key

            # ── battery & financial ───────────────────────────────────────
            "soc":              soc,
            "rate":             cfg.import_rate,
            "export_kwh":       export_kwh,
            "export_credit":    export_credit,
            "grid_cost":        grid_cost,
            "net_cost":         net_cost,
        })

    return results