import sys
import PyPDF2

pdf_path = "Proposal Reort Merged Final (1) (1).pdf"
try:
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
except Exception as e:
    print(f"Error reading PDF: {e}")
    sys.exit(1)

from main import extract_wbs_tasks
import logging

tasks = extract_wbs_tasks(text)
print(f"PDF EXTRATED TASKS: {len(tasks)}")
