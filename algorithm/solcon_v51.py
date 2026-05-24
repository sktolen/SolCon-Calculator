from dataclasses import dataclass
from algorithm.weather import get_weather_forecast, prepare_weather_data, aggregate_daily_pv
import pandas as pd


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
def check_forecast_tier(day_kwh):
    if day_kwh > 20:
        return "HIGH"
    elif day_kwh >= 10:
        return "MEDIUM"
    else:
        return "LOW"


# Check forecast tier based on daily kWh
def check_forecast_tier(day_kwh):
    if day_kwh > 20:
        return "HIGH"
    elif day_kwh >= 10:
        return "MEDIUM"
    else:
        return "LOW"


# Check outlook for the next 3 days based on forecast tiers
def check_outlook(current_date, daily_kwh):
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
        tier = check_forecast_tier(future_kwh)
 
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
    C = cfg.critical_load
    E = cfg.essential_load
    N = cfg.noncritical_load
 
    # CHARGE
    # run all loads directly from battery
    if pv_state == "CHARGE":
        return C + E + N, 0.0, 0.0
 
    # SUNNY
    # if SOC is high, run all loads from battery
    # else, run critical + essential from battery
    if pv_state == "SUNNY":
        if soc >= 0.61:
            return C + E + N, 0.0, 0.0
        else:
            return C + E, 0.0, 0.0
 
    # CLOUDY
    # If peak hours, run critical + essential from battery to avoid high grid rates
    # If off-peak, run critical and essential from battery only if battery is high enough, else run critical from battery and essential from grid
    if pv_state == "CLOUDY":
        if is_peak:
            return C + E, 0.0, 0.0
        else:
            if soc >= 0.61:
                return C + E, 0.0, 0.0
            else:
                return C, E, 0.0
 
    # NIGHT
    if pv_state == "NIGHT":
        # NIGHT + PEAK
        # if peak hours, run critical + essential from battery if SOC is sufficient
        # else run critical from battery and essential from grid
        if is_peak:
            if soc > cfg.soc_floor:
                return C + E, 0.0, 0.0
            else:
                return 0.0, C + E, 0.0
 
        # NIGHT + OFFPEAK
        # if off-peak hours, run critical + essential from grid to save battery for peak hours, unless SOC is very high in which case run from battery
        # also consider forecast and outlook - if forecast is bad and SOC is not high, charge from grid to prepare for next days
        target_soc = should_grid_charge(outlook, forecast_tier, soc)
        if target_soc is not None:
            gc = calculate_grid_charge(target_soc, soc, cfg)
        else:
            gc = 0.0
 
        # FIX: explicit SOC floor guard at the top level, matching the reference's
        # "Any SOC ≤ 20%: bl=0, gl=LOAD_FULL" rule. Avoids ambiguous fallthrough.
        if soc <= cfg.soc_floor:
            return 0.0, C + E, gc
 
        if outlook == "SUNNY_WEEK":
            return C + E, 0.0, gc
 
        if soc >= 0.61:
            return C + E, 0.0, gc
 
        # mid-range SOC (soc_floor < soc < 0.61)
        if outlook == "MIXED_WEEK":
            if forecast_tier == "HIGH":
                return C + E, 0.0, gc
            elif forecast_tier == "MEDIUM":
                return (C + E, 0.0, gc) if soc > 0.35 else (C, E, gc)
            else:
                return (C + E, 0.0, gc) if soc > 0.45 else (C, E, gc)
 
        if outlook == "CLOUDY_WEEK":
            if forecast_tier == "HIGH":
                return C + E, 0.0, gc
            elif forecast_tier == "MEDIUM":
                return (C + E, 0.0, gc) if soc > 0.40 else (C, E, gc)
            else:
                return (C + E, 0.0, gc) if soc > 0.55 else (C, E, gc)
 
        # FIX: explicit fallback — should never be reached with valid inputs,
        # but prevents a silent None return that would crash the simulation loop.
        return 0.0, C + E, gc
 
    # FIX: same safety fallback for any unexpected pv_state value
    return 0.0, C + E, 0.0


def should_grid_charge(outlook, forecast_tier, soc):
    # SUNNY WEEK: solar will handle tomorrow
    if outlook == "SUNNY_WEEK":
        return None
 
    # MIXED WEEK: only charge if tomorrow is LOW
    if outlook == "MIXED_WEEK":
        if forecast_tier != "LOW":
            return None
 
        target_soc = 0.75
 
        # avoid tiny top-ups
        if soc >= target_soc - 0.10:
            return None
 
        return target_soc
 
    # CLOUDY WEEK: charge more aggressively
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
    total_load = battery_demand + grid_demand
 
    # 1. PV serves load first
    pv_to_load = min(pv_kwh, total_load)
    remaining_load = total_load - pv_to_load
    remaining_pv = pv_kwh - pv_to_load
 
    # 2. Battery serves remaining load
    available_battery_kwh = max(0, (soc - cfg.soc_floor) * cfg.battery_capacity)
    battery_to_load = min(remaining_load, available_battery_kwh)
    soc -= battery_to_load / cfg.battery_capacity
 
    # 3. Grid serves remaining load
    grid_to_load = remaining_load - battery_to_load
 
    # 4. Excess PV charges battery
    battery_headroom_kwh = max(0, (cfg.soc_max - soc) * cfg.battery_capacity)
    pv_to_battery = min(remaining_pv * cfg.system_efficiency, battery_headroom_kwh)
    soc += pv_to_battery / cfg.battery_capacity
 
    pv_used_for_battery = (
        pv_to_battery / cfg.system_efficiency
        if cfg.system_efficiency > 0
        else 0
    )
 
    # 5. Remaining PV is exported
    export_kwh = max(0, remaining_pv - pv_used_for_battery)
 
    # 6. Optional grid charging
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
        outlook = check_outlook(current_date, daily_kwh)
 
        if day_index + 1 < len(dates):
            tomorrow_date = dates[day_index + 1]
        else:
            tomorrow_date = current_date
 
        tomorrow_kwh = daily_kwh[tomorrow_date]
        forecast_tier = check_forecast_tier(tomorrow_kwh)
 
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
 
        soc = flow["soc"]
        pv_to_load = flow["pv_to_load"]
        battery_to_load = flow["battery_to_load"]
        grid_to_load = flow["grid_to_load"]
        pv_to_battery = flow["pv_to_battery"]
        grid_to_battery = flow["grid_to_battery"]
        export_kwh = flow["export_kwh"]
 
        rate = cfg.peak_rate if is_peak else cfg.offpeak_rate
 
        # FIX: bill actual grid energy drawn for charging (grid_to_battery /
        # efficiency = raw kWh pulled from grid), not the requested gc amount.
        # gc may exceed what the battery could actually absorb if headroom ran out.
        actual_gc_grid_draw = (
            grid_to_battery / cfg.system_efficiency
            if cfg.system_efficiency > 0
            else 0
        )
        grid_cost = (grid_to_load + actual_gc_grid_draw) * rate
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
 
            # battery + financial results
            "soc": soc,
            "rate": rate,
            "export_kwh": export_kwh,
            "export_credit": export_credit,
            "grid_cost": grid_cost,
            "net_cost": net_cost,
        })
 
    return results