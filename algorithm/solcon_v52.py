from dataclasses import dataclass
from algorithm.weather import get_weather_forecast, prepare_weather_data, aggregate_daily_pv
import pandas as pd


# Key flow of SolCon v5.2:
# 1 PV serves load first
# 2 Battery covers remaining load
# 3 Grid covers anything left
# 4 Excess PV charges battery
# 5 Any remaining PV is exported
# 6 Optional grid charging on top
#
# v5.2 vs v5.1 difference:
# No load shedding. Every slot uses LOAD_FULL instead of C, C+E, or C+E+N splits


# import user inputs from calculator (values are defaults but will be changed when pressing submit)
@dataclass
class SystemConfig:
    battery_capacity: float
    soc_floor: float
    pv_capacity: float
    soc_max: float
    system_efficiency: float

    import_rate: float
    export_rate: float
    peak_rate: float
    offpeak_rate: float

    algorithm_mode: str
    latitude: float
    longitude: float

    # Hardcoded inputs (can be made dynamic in the future)
    critical_load: float = 0.200
    essential_load: float = 0.350
    noncritical_load: float = 0.250
    max_grid_charge: float = 2.5
    initial_soc: float = 0.50
    daily_load_kwh: float = 27.2  # kWh consumed per day across all loads


# Check PV state based on current generation and PV capacity
def check_pv_state(pv_kw, cfg):
    if cfg.pv_capacity <= 0:
        return "NIGHT"
 
    ratio = pv_kw / cfg.pv_capacity
 
    if ratio > 0.80:
        return "CHARGE"
    elif ratio > 0.40:
        return "SUNNY"
    elif ratio > 0.10:
        return "CLOUDY"
    else:
        return "NIGHT"


# Returns TRUE if current day and time slot is in peak hours, FALSE otherwise
def check_peak_offpeak(slot, weekday):
    # weekday: 0-6 (Mon-Sun)
    # slot: 0-47 (30-min intervals of the day)
 
    # Peak on sunday is 6PM to 8PM (2 hours)
    if weekday == 6:
        return 36 <= slot <= 39
 
    # Peak on other days is 8AM to 9PM (13 hours)
    return 16 <= slot <= 41
 
 
# Check forecast tier based on daily kWh
def check_forecast_tier(day_kwh, cfg):
    high_threshold   = cfg.pv_capacity * 4.5 * cfg.system_efficiency
    medium_threshold = cfg.pv_capacity * 2.0 * cfg.system_efficiency

    if day_kwh >= high_threshold:
        return "HIGH"
    elif day_kwh >= medium_threshold:
        return "MEDIUM"
    else:
        return "LOW"

# Check outlook for the next ays based on forecast tiers
def check_outlook(current_date, daily_kwh, cfg):
    dates = list(daily_kwh.keys())
    current_index = dates.index(current_date)
 
    low_count = 0
    medium_count = 0
 
    for i in range(1, 4):
        future_index = current_index + i
 
        if future_index < len(dates):
            future_date = dates[future_index]
        else:
            future_date = current_date
 
        future_kwh = daily_kwh[future_date]
        tier = check_forecast_tier(future_kwh, cfg)
 
        if tier == "LOW":
            low_count += 1
        elif tier == "MEDIUM":
            medium_count += 1
 
    if low_count == 0 and medium_count == 0:
        return "SUNNY_WEEK"
    elif low_count >= 2:
        return "CLOUDY_WEEK"
    else:
        return "MIXED_WEEK"


# Determine how much load to run and whether to charge from grid based on all factors
# Returns (bl, gl, cl) -> battery load, grid load, grid charge
# Battery load -> how much energy to draw from the battery
# Grid load -> how much energy to draw from the grid
# Grid charge -> how much energy to use for charging the battery (can be 0 if not charging)
def determine_action(pv_state, is_peak, soc, forecast_tier, outlook, cfg):
    LOAD_FULL = cfg.daily_load_kwh / 48

    # DAYTIME — always serve full load from battery, no shedding
    if pv_state != "NIGHT":
        return LOAD_FULL, 0.0, 0.0

    # NIGHT + PEAK — deploy battery to avoid peak rate
    if is_peak:
        if soc > cfg.soc_floor:
            return LOAD_FULL, 0.0, 0.0
        else:
            return 0.0, LOAD_FULL, 0.0

    # NIGHT + OFF-PEAK
    target_soc = should_grid_charge(outlook, forecast_tier, soc, pv_state, cfg)
    gc = calculate_grid_charge(target_soc, soc, cfg) if target_soc is not None else 0.0

    if soc <= cfg.soc_floor:
        return 0.0, LOAD_FULL, gc

    if outlook == "SUNNY_WEEK":
        return LOAD_FULL, 0.0, gc

    if soc >= 0.61:
        return LOAD_FULL, 0.0, gc

    if outlook == "MIXED_WEEK":
        return (LOAD_FULL, 0.0, gc) if soc > 0.35 else (0.0, LOAD_FULL, gc)

    if outlook == "CLOUDY_WEEK":
        return (LOAD_FULL, 0.0, gc) if soc > 0.50 else (0.0, LOAD_FULL, gc)

    return 0.0, LOAD_FULL, gc


def should_grid_charge(outlook, forecast_tier, soc, pv_state, cfg):
    if pv_state in ("CHARGE", "SUNNY"):
        return None

    if outlook == "SUNNY_WEEK":
        return None

    if outlook == "MIXED_WEEK":
        if forecast_tier != "LOW":
            return None
        target_soc = 0.75
        if soc >= target_soc - 0.10:
            return None
        return target_soc

    if outlook == "CLOUDY_WEEK":
        target_soc = 0.85
        if soc >= target_soc - 0.10:
            return None
        return target_soc

    return None


# Calculate how much grid energy to use for charging
def calculate_grid_charge(target_soc, soc, cfg):
    soc_gap = target_soc - soc
    energy_needed = soc_gap * cfg.battery_capacity
    max_grid_charge = cfg.max_grid_charge
 
    return min(energy_needed, max_grid_charge)
 
 
# Apply PV generation to load, battery charging, and export in that order
def apply_energy_flow(soc, pv_kwh, battery_demand, grid_demand, grid_charge_request, cfg):
    # 1. PV offsets battery-side load only (slide 14)
    pv_to_load = min(pv_kwh, battery_demand)
    remaining_pv = pv_kwh - pv_to_load
    bl_deficit = battery_demand - pv_to_load  # what PV didn't cover on battery side

    # 2. Battery covers its deficit
    available_battery_kwh = max(0, (soc - cfg.soc_floor) * cfg.battery_capacity)
    battery_to_load = min(bl_deficit, available_battery_kwh)
    soc -= battery_to_load / cfg.battery_capacity

    # 3. Grid bridge (ge): battery couldn't fully cover bl deficit
    ge = bl_deficit - battery_to_load

    # 4. Total grid draw: gl (dispatch decision, always billed) + ge (bridge)
    grid_to_load = grid_demand + ge

    # 5. Excess PV charges battery
    battery_headroom_kwh = max(0, (cfg.soc_max - soc) * cfg.battery_capacity)
    pv_to_battery = min(remaining_pv * cfg.system_efficiency, battery_headroom_kwh)
    soc += pv_to_battery / cfg.battery_capacity

    pv_used_for_battery = (
        pv_to_battery / cfg.system_efficiency
        if cfg.system_efficiency > 0
        else 0
    )

    # 6. Remaining PV is exported
    export_kwh = max(0, remaining_pv - pv_used_for_battery)

    # 7. Optional grid charging
    battery_headroom_kwh = max(0, (cfg.soc_max - soc) * cfg.battery_capacity)
    grid_to_battery = min(
        grid_charge_request * cfg.system_efficiency,
        battery_headroom_kwh
    )
    soc += grid_to_battery / cfg.battery_capacity

    soc = max(cfg.soc_floor, min(cfg.soc_max, soc))

    return {
        "soc": soc,
        "pv_to_load": pv_to_load,
        "battery_to_load": battery_to_load,
        "grid_to_load": grid_to_load,
        "pv_to_battery": pv_to_battery,
        "grid_to_battery": grid_to_battery,
        "export_kwh": export_kwh,
        "ge": ge,  # expose ge so simulate_solcon can bill it correctly
    }

 
# Simulate SolCon algorithm over the forecast period
def simulate_solcon(pv_data, daily_kwh, start_weekday, cfg):
    results = []
    soc = cfg.initial_soc
    dates = list(daily_kwh.keys())
 
    for i, row in pv_data.iterrows():
        current_date = row["date"]
        slot = row["slot"]
        pv_kw = row["pv_kw"]
 
        day_index = dates.index(current_date)
        weekday = (start_weekday + day_index) % 7
 
        pv_state = check_pv_state(pv_kw, cfg)
        is_peak = check_peak_offpeak(slot, weekday)
        outlook = check_outlook(current_date, daily_kwh, cfg)
 
        if day_index + 1 < len(dates):
            tomorrow_date = dates[day_index + 1]
        else:
            tomorrow_date = current_date
 
        tomorrow_kwh = daily_kwh[tomorrow_date]
        forecast_tier = check_forecast_tier(tomorrow_kwh, cfg)
 
        bl, gl, gc = determine_action(
            pv_state=pv_state,
            is_peak=is_peak,
            soc=soc,
            forecast_tier=forecast_tier,
            outlook=outlook,
            cfg=cfg,
        )
 
        # PV power converted to energy for a 30-minute slot
        pv_kwh = pv_kw * 0.5
 
        flow = apply_energy_flow(
            soc=soc,
            pv_kwh=pv_kwh,
            battery_demand=bl,
            grid_demand=gl,
            grid_charge_request=gc,
            cfg=cfg,
        )
 
        
        # After:
        soc = flow["soc"]
        pv_to_load = flow["pv_to_load"]
        battery_to_load = flow["battery_to_load"]
        grid_to_load = flow["grid_to_load"]
        pv_to_battery = flow["pv_to_battery"]
        grid_to_battery = flow["grid_to_battery"]
        export_kwh = flow["export_kwh"]
        ge = flow["ge"]

        rate = cfg.peak_rate if is_peak else cfg.offpeak_rate

        actual_gc_grid_draw = (
            grid_to_battery / cfg.system_efficiency
            if cfg.system_efficiency > 0
            else 0
        )
        grid_cost = (gl + ge + actual_gc_grid_draw) * rate

        export_credit = export_kwh * cfg.export_rate
        net_cost = grid_cost - export_credit
 
        results.append({
            "time": row["time"],
            "date": current_date,
            "slot": slot,
            "weekday": weekday,
            "pv_kw": pv_kw,
            "pv_kwh": pv_kwh,
            "pv_state": pv_state,
            "is_peak": is_peak,
            "forecast_tier": forecast_tier,
            "outlook": outlook,
 
            # intended demand from decision table
            "load_demand": bl + gl,
            "battery_demand": bl,
            "grid_demand": gl,
            "grid_charge": gc,
 
            # actual energy flow
            "pv_to_load": pv_to_load,
            "battery_load": battery_to_load,
            "grid_load": grid_to_load,
            "pv_to_battery": pv_to_battery,
            "grid_to_battery": grid_to_battery,
            "ge": ge,
 
            # battery + financial results
            "soc": soc,
            "rate": rate,
            "export_kwh": export_kwh,
            "export_credit": export_credit,
            "grid_cost": grid_cost,
            "net_cost": net_cost,
        })
 
    return results