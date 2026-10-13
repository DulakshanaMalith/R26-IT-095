with open("src/api/main.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.startswith("def build_report_lines"):
        print(f"Start: {i}")
    if line.startswith("def generate_report"):
        print(f"generate_report: {i}")

# find end of generate_report
start_i = 0
for i, line in enumerate(lines):
    if line.startswith("def generate_report"):
        start_i = i
for i in range(start_i + 1, len(lines)):
    if line.startswith("def ") or line.startswith("@app"):
        print(f"End: {i}")
        break
