import requests
import pandas as pd
import datetime


HOURLY_VARS = [
    "cloud_cover",
    "shortwave_radiation",
    "precipitation",
    "temperature_2m"
]


def _parse_response(data):
    return pd.DataFrame({
        "time": data["hourly"]["time"],
        "cloud_cover": data["hourly"]["cloud_cover"],
        "shortwave_radiation": data["hourly"]["shortwave_radiation"],
        "precipitation": data["hourly"]["precipitation"],
        "temperature": data["hourly"]["temperature_2m"],
    })


def get_weather_forecast(latitude, longitude, forecast_days=3):
    """Fetch forecast data. forecast_days can be 3 (daily) or 7 (weekly)."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": HOURLY_VARS,
        "forecast_days": forecast_days,
        "timezone": "Asia/Manila"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return _parse_response(response.json())


def get_weather_historical(latitude, longitude, start_date: str, end_date: str):
    """
    Fetch historical weather from Open-Meteo Archive API.
    start_date / end_date: 'YYYY-MM-DD'
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": HOURLY_VARS,
        "timezone": "Asia/Manila"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return _parse_response(response.json())


def get_weather_weekly(latitude, longitude):
    """
    Returns data for the current calendar week (Mon–Sun):
    - Historical data from Monday through yesterday
    - Forecast for today through Sunday
    """
    today = datetime.date.today()
    # Monday of the current week
    monday = today - datetime.timedelta(days=today.weekday())
    yesterday = today - datetime.timedelta(days=1)
    sunday = monday + datetime.timedelta(days=6)

    frames = []

    # Historical: Monday → yesterday (skip if today is Monday)
    if yesterday >= monday:
        hist_df = get_weather_historical(
            latitude, longitude,
            start_date=monday.isoformat(),
            end_date=yesterday.isoformat()
        )
        frames.append(hist_df)

    # Forecast: today → Sunday
    days_remaining = (sunday - today).days + 1  # inclusive
    forecast_df = get_weather_forecast(latitude, longitude, forecast_days=days_remaining)
    frames.append(forecast_df)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset="time").reset_index(drop=True)
    return combined


def get_weather_monthly(latitude, longitude):
    """
    Returns data for the current month:
    - Historical data from the 1st to yesterday
    - Forecast for today onwards
    Combines both into a single DataFrame.
    """
    today = datetime.date.today()
    month_start = today.replace(day=1)
    yesterday = today - datetime.timedelta(days=1)

    frames = []

    # Historical: 1st of month → yesterday (only if month has started > 1 day)
    if yesterday >= month_start:
        hist_df = get_weather_historical(
            latitude, longitude,
            start_date=month_start.isoformat(),
            end_date=yesterday.isoformat()
        )
        frames.append(hist_df)

    # Forecast: today → end of month
    days_remaining = (today.replace(month=today.month % 12 + 1, day=1) - today).days
    days_remaining = max(1, min(days_remaining, 16))  # open-meteo max forecast is 16 days
    forecast_df = get_weather_forecast(latitude, longitude, forecast_days=days_remaining)
    frames.append(forecast_df)

    combined = pd.concat(frames, ignore_index=True)
    # Drop duplicates on time in case of overlap
    combined = combined.drop_duplicates(subset="time").reset_index(drop=True)
    return combined


def get_weather_annual(latitude, longitude):
    """
    Returns historical data for the entire previous calendar year.
    """
    today = datetime.date.today()
    prev_year = today.year - 1
    start_date = f"{prev_year}-01-01"
    end_date = f"{prev_year}-12-31"
    return get_weather_historical(latitude, longitude, start_date=start_date, end_date=end_date)


def calculate_pv_kw(irradiance, cfg):
    return (
        cfg.pv_capacity
        * (irradiance / 1000)
        * cfg.system_efficiency
    )


def prepare_weather_data(forecast_df, cfg):
    forecast_df = forecast_df.copy()
    forecast_df["time"] = pd.to_datetime(forecast_df["time"])

    forecast_df["pv_kw"] = forecast_df["shortwave_radiation"].apply(
        lambda x: calculate_pv_kw(x, cfg)
    )

    forecast_df["date"] = forecast_df["time"].dt.strftime("%Y-%m-%d")
    forecast_df["slot"] = forecast_df["time"].dt.hour * 2

    return forecast_df


def aggregate_daily_pv(forecast_df):
    daily_kwh = (
        forecast_df
        .groupby("date")["pv_kw"]
        .sum()
    )
    return daily_kwh.to_dict()


def classify_forecast(daily_kwh):
    if daily_kwh > 20:
        return "HIGH"
    elif daily_kwh >= 10:
        return "MEDIUM"
    else:
        return "LOW"