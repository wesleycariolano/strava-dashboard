import requests
from datetime import datetime, timedelta
import os

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")

def refresh_access_token(refresh_token):
    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": STRAVA_CLIENT_ID,
            "client_secret": STRAVA_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
    )
    if response.status_code != 200:
        raise Exception("Erro ao atualizar access_token")
    return response.json()

def get_activities(access_token, after_timestamp=None, before_timestamp=None):
    url = "https://www.strava.com/api/v3/athlete/activities"
    params = {
        "per_page": 200
    }
    if after_timestamp:
        params["after"] = after_timestamp
    if before_timestamp:
        params["before"] = before_timestamp

    activities = []
    page = 1
    while True:
        params["page"] = page
        resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, params=params)
        data = resp.json()
        if not isinstance(data, list) or not data:
            break
        activities.extend(data)
        page += 1
    return activities

def get_month_range(year: int, month: int):
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        end = datetime(year, month + 1, 1) - timedelta(seconds=1)
    return start, end

def get_week_ranges(year: int, month: int):
    start, end = get_month_range(year, month)
    current = start
    weeks = []
    while current < end:
        week_end = current + timedelta(days=6 - current.weekday())
        if week_end > end:
            week_end = end
        weeks.append((current, week_end))
        current = week_end + timedelta(days=1)
    return weeks