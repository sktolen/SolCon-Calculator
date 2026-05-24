
from dataclasses import dataclass

# import user inputs from calculator (valus are defaults but will be changed when pressing submit)
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
    critical_load=0.200
    essential_load=0.350
    noncritical_load=0.250

    max_grid_charge=2.5


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


# Returns TRUE if current time slot is in peak hours, FALSE otherwise
def check_pop(slot, weekday):
    # weekday: 0-6 (Mon-Sun)
    # slot: 0-47 (30-min intervals of the day)

    # Peak on sunday is 8AM to 9PM (13 hours)
    if weekday == 6:
        return 16 <= slot <= 41

    # Peak on other days is 6PM to 8PM (2 hours)
    return 36 <= slot <= 39


# Check current battery state of charge (SOC)
def check_battery_soc(soc, cfg):
    if soc <= cfg.soc_floor:
        return "LOW"
    elif soc >= 0.61:
        return "HIGH"
    else:
        return "NORMAL"


# Check current day forecast tier based on daily kWh
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


def determine_action(pv_state, is_peak, soc, forecast_tier, outlook, cfg):
    C = cfg.critical_load
    E = cfg.essential_load
    N = cfg.noncritical_load

    # CHARGE: run all loads
    if pv_state == "CHARGE":
        return C + E + N, 0.0, 0.0

    # SUNNY
    if pv_state == "SUNNY":
        if soc >= 0.61:
            return C + E + N, 0.0, 0.0
        else:
            return C + E, 0.0, 0.0

    # CLOUDY
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
    if is_peak:
        if soc > cfg.soc_floor:
            return C + E, 0.0, 0.0
        else:
            return 0.0, C + E, 0.0

    # NIGHT + OFFPEAK
    target_soc = should_grid_charge(outlook, forecast_tier, soc)

    if target_soc is not None:
        gc = calculate_grid_charge(target_soc, soc, cfg)
    else:
        gc = 0.0

    if outlook == "SUNNY_WEEK":
        if soc > cfg.soc_floor:
            return C + E, 0.0, gc
        else:
            return 0.0, C + E, gc

    if soc >= 0.61:
        return C + E, 0.0, gc

    if soc > cfg.soc_floor:
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

    return 0.0, C + E, gc


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


