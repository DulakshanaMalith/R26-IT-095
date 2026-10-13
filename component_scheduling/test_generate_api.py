import requests

payload = {
    "project_id": "demo_project_01",
    "description": "test description",
    "team_size": 4,
    "duration_months": 6.0,
    "function_points": 120,
    "start_date": "2026-08-30"
}

try:
    res = requests.post("http://127.0.0.1:8000/api/schedule/generate", json=payload)
    print(res.status_code)
    print(res.json())
except Exception as e:
    print(e)
