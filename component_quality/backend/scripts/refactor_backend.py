import re

with open("src/api/main.py", "r") as f:
    lines = f.readlines()

schemas_start = -1
schemas_end = -1

for i, line in enumerate(lines):
    if line.startswith("class TextRequest(BaseModel):"):
        schemas_start = i
    if line.startswith("class SupervisorAnalyticsResponse(BaseModel):"):
        schemas_end = i + 10 # approximate

# find the actual end of SupervisorAnalyticsResponse
for i in range(schemas_end, len(lines)):
    if not lines[i].startswith(" ") and not lines[i].strip() == "":
        schemas_end = i
        break

schemas_content = "".join(lines[schemas_start:schemas_end])

schemas_file = """from pydantic import BaseModel, Field, model_validator
from typing import Any
from src.reviewer.schemas import ReviewResult

""" + schemas_content

with open("src/api/schemas.py", "w") as f:
    f.write(schemas_file)

# Remove schemas from main and add import
new_main = lines[:schemas_start] + ["from src.api.schemas import *\n"] + lines[schemas_end:]

with open("src/api/main.py", "w") as f:
    f.writelines(new_main)

print("Schemas extracted!")
