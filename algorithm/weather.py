import requests
import pandas as pd


def get_weather_forecast(latitude, longitude):

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": [
            "cloud_cover",
            "shortwave_radiation",
            "precipitation",
            "temperature_2m"
        ],
        "forecast_days": 3,
        "timezone": "Asia/Manila"
    }

    response = requests.get(url, params=params)
    response.raise_for_status()

    data = response.json()

    forecast_df = pd.DataFrame({
        "time": data["hourly"]["time"],
        "cloud_cover": data["hourly"]["cloud_cover"],
        "shortwave_radiation": data["hourly"]["shortwave_radiation"],
        "precipitation": data["hourly"]["precipitation"],
        "temperature": data["hourly"]["temperature_2m"],
    })

    return forecast_df

def calculate_pv_kw(irradiance, cfg):

    return (
        cfg.pv_capacity
        * (irradiance / 1000)
        * cfg.system_efficiency
    )

def prepare_weather_data(forecast_df, cfg):

    forecast_df["pv_kw"] = forecast_df[
        "shortwave_radiation"
    ].apply(lambda x: calculate_pv_kw(x, cfg))

    return forecast_df

def aggregate_daily_pv(forecast_df):

    daily_kwh = (
        forecast_df
        .groupby(forecast_df["time"].str[:10])["pv_kw"]
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