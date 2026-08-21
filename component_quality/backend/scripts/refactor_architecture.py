import re
import os

with open("src/api/main.py", "r") as f:
    lines = f.readlines()

# 1. Create core_logic.py
core_logic_lines = []
for i, line in enumerate(lines):
    if line.startswith("@app.") and "def " in lines[i+1]:
        break
    core_logic_lines.append(line)

# Remove the app = FastAPI(...) from core_logic
final_core = []
for line in core_logic_lines:
    if line.startswith("app = FastAPI"):
        continue
    if line.startswith("app.add_middleware"):
        continue
    if line.startswith("    allow_origins"):
        continue
    if line.startswith("    allow_credentials"):
        continue
    if line.startswith("    allow_methods"):
        continue
    if line.startswith("    allow_headers"):
        continue
    final_core.append(line)

with open("src/api/services/core_logic.py", "w") as f:
    f.writelines(final_core)

print("Created core_logic.py")
