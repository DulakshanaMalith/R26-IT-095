import requests
import json
import PyPDF2

pdf_path = "Proposal Reort Merged Final (1) (1).pdf"
with open(pdf_path, "rb") as f:
    reader = PyPDF2.PdfReader(f)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"

payload = {
    "description": text,
    "team_size": 4,
    "duration_months": 6,
    "function_points": 100,
    "start_date": "2026-08-30"
}

resp = requests.post("http://127.0.0.1:8000/api/schedule/generate", json=payload)
data = resp.json()

print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    print(f"Total Tasks: {data.get('total_tasks')}")
    print(f"Schedule Length: {len(data.get('schedule', []))}")
    for i, t in enumerate(data.get('schedule', [])):
        print(f"  {i+1}: {t['task_name']} ({t.get('component_owner', 'N/A')})")
else:
    print(f"Error: {resp.text}")
