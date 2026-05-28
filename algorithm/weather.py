import requests
import pandas as pd
import datetime


MINUTELY_15_VARS = [
    "cloud_cover",
    "shortwave_radiation",
    "precipitation",
    "temperature_2m"
]


def _parse_response(data):
    return pd.DataFrame({
        "time": data["minutely_15"]["time"],
        "cloud_cover": data["minutely_15"]["cloud_cover"],
        "shortwave_radiation": data["minutely_15"]["shortwave_radiation"],
        "precipitation": data["minutely_15"]["precipitation"],
        "temperature": data["minutely_15"]["temperature_2m"],
    })


def get_weather_forecast(latitude, longitude, forecast_days=3):
    """Fetch forecast data. forecast_days can be 3 (daily) or 7 (weekly)."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "minutely_15": MINUTELY_15_VARS,  # was "hourly"
        "forecast_days": forecast_days,
        "timezone": "Asia/Manila"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return _parse_response(response.json())


def get_weather_historical(latitude, longitude, start_date: str, end_date: str):
    url = "https://archive-api.open-meteo.com/v1/archive"

    for interval in ["minutely_15", "hourly"]:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            interval: MINUTELY_15_VARS,
            "timezone": "Asia/Manila"
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if interval in data:
                return pd.DataFrame({
                    "time": data[interval]["time"],
                    "cloud_cover": data[interval]["cloud_cover"],
                    "shortwave_radiation": data[interval]["shortwave_radiation"],
                    "precipitation": data[interval]["precipitation"],
                    "temperature": data[interval]["temperature_2m"],
                })

    response.raise_for_status()


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
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    days_remaining = (next_month - today).days
    days_remaining = max(1, min(days_remaining, 16))

    forecast_df = get_weather_forecast(latitude, longitude, forecast_days=days_remaining)
    frames.append(forecast_df)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset="time").reset_index(drop=True)
    return combined


def get_weather_monthly(latitude, longitude, month=None, year=None):
    """
    Returns data for any calendar month:
    - Past months: fully historical
    - Current month: historical up to yesterday + forecast for remainder
    - Future months: not supported
    """
    today = datetime.date.today()
    if month is None:
        month = today.month
    if year is None:
        year = today.year

    month_start = datetime.date(year, month, 1)
    # Last day of the month
    if month == 12:
        month_end = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        month_end = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

    frames = []

    is_current_month = (year == today.year and month == today.month)

    if is_current_month:
        yesterday = today - datetime.timedelta(days=1)

        # Historical: 1st → yesterday
        if yesterday >= month_start:
            hist_df = get_weather_historical(
                latitude, longitude,
                start_date=month_start.isoformat(),
                end_date=yesterday.isoformat(),
            )
            frames.append(hist_df)

        # Forecast: today → end of month
        days_remaining = max(1, min((month_end - today).days + 1, 16))
        forecast_df = get_weather_forecast(latitude, longitude, forecast_days=days_remaining)
        frames.append(forecast_df)

    else:
        # Past month: fully historical
        hist_df = get_weather_historical(
            latitude, longitude,
            start_date=month_start.isoformat(),
            end_date=month_end.isoformat(),
        )
        frames.append(hist_df)

    combined = pd.concat(frames, ignore_index=True)
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
    forecast_df = forecast_df.set_index("time")

    # Detect resolution
    time_diffs = forecast_df.index.to_series().diff().dropna()
    median_minutes = time_diffs.median().total_seconds() / 60

    if median_minutes <= 15:
        # 15-min data → resample to 30-min
        forecast_df = forecast_df.resample("30min").agg({
            "shortwave_radiation": "mean",
            "cloud_cover": "mean",
            "precipitation": "sum",
            "temperature": "mean",
        })
    elif median_minutes <= 60:
        # Hourly data → resample to 30-min with interpolation
        forecast_df = forecast_df.resample("30min").interpolate(method="linear")
    
    forecast_df = forecast_df.reset_index()

    # Fill any remaining NaNs to be safe
    forecast_df["shortwave_radiation"] = forecast_df["shortwave_radiation"].fillna(0)
    forecast_df["cloud_cover"] = forecast_df["cloud_cover"].fillna(0)
    forecast_df["precipitation"] = forecast_df["precipitation"].fillna(0)
    forecast_df["temperature"] = forecast_df["temperature"].ffill().bfill()

    forecast_df["pv_kw"] = forecast_df["shortwave_radiation"].apply(
        lambda x: calculate_pv_kw(x, cfg)
    )

    forecast_df["date"] = forecast_df["time"].dt.strftime("%Y-%m-%d")
    forecast_df["slot"] = forecast_df["time"].dt.hour * 2 + (forecast_df["time"].dt.minute // 30)

    return forecast_df


def aggregate_daily_pv(forecast_df):
    daily_kwh = forecast_df.groupby("date")["pv_kw"].sum() * 0.5

    return daily_kwh.to_dict()