import requests

url = "http://localhost:8000/api/schedule/generate"
payload = {
    "project_id": "test_01",
    "description": "WORK BREAKDOWN STRUCTURE\n1. Literature Review\n2. System Design\n3. Backend Implementation\n4. Frontend Implementation\n5. System Testing\n6. Final Evaluation\n",
    "start_date": "2026-09-01",
    "team_size": 4,
    "function_points": 50,
    "team_members": ["IT201", "IT202", "IT203", "IT204"]
}

res = requests.post(url, json=payload)
print("Generate Schedule Status:", res.status_code)
if res.status_code == 200:
    data = res.json()
    tasks = data["schedule"]
    print("Tasks Generated:", len(tasks))
    for task in tasks[:3]:
        print(
            f" - {task['task_name']} | {task.get('source_section', 'N/A')} | "
            f"{task['start_date']} to {task['end_date']}"
        )

    print("\nLPT Assignments:")
    for task in tasks[:3]:
        print(
            f" - {task['task_name']} assigned to {task.get('assigned_to', 'N/A')} "
            f"({task.get('assign_method', 'LPT schedule')})"
        )

print("\n--- Testing Rebalance API ---")
res2 = requests.get("http://localhost:8000/api/schedule/rebalance/recommendations")
print("Rebalance Status:", res2.status_code)
if res2.status_code == 200:
    print("Recommendations:", res2.json()["recommendations"])
