import sys
import os
import requests

from dotenv import load_dotenv
load_dotenv('.env')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.api.services.resend_service import send_feedback_email

try:
    send_feedback_email(
        recipient_email="student.one@example.test",
        subject="Test",
        body="This is a test",
        attachments=[]
    )
    print("Success")
except Exception as e:
    print(f"Failed: {e}")
