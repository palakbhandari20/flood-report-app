import requests

def get_rainfall_zone(latitude, longitude):

    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&hourly=rain"

    response = requests.get(url)
    data = response.json()

    rain_values = data["hourly"]["rain"]

    max_rain = max(rain_values)

    if max_rain > 20:
        zone = "RED"
    elif max_rain > 5:
        zone = "ORANGE"
    else:
        zone = "GREEN"

    return {
        "rainfall_mm": max_rain,
        "zone": zone
    }