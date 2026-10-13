"""Capture the local post-fix History roster UI on the isolated test database.

Run the scheduling service on 127.0.0.1:8000 with
SCHEDULING_DATABASE_URL pointing to ipms_scheduling_codex_test_20261010
after the focused test suite has created CODEX-HISTORY-20261010.
"""

from pathlib import Path
import json
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from auth import AuthenticatedUser, issue_token


OUTPUT = Path(__file__).resolve().parent
PROJECT = "CODEX-HISTORY-20261010"

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    token = issue_token(AuthenticatedUser("supervisor1", "Supervisor", "supervisor"))
    page.add_init_script(
        "localStorage.setItem('ipms_token', " + json.dumps(token) + ");"
        "localStorage.setItem('ipms_role', 'supervisor');"
        "localStorage.setItem('ipms_user', 'Supervisor');"
    )
    page.goto("http://127.0.0.1:8000/app/index.html", wait_until="domcontentloaded")
    page.locator("#btnViewHistory").click()
    page.locator("#historySearch").fill(PROJECT)
    page.locator("#btnSearchHistory").click()
    page.locator(".schedule-history-item").first.wait_for()
    page.locator("#historyModal .modal-box").screenshot(
        path=str(OUTPUT / "11_history_roster_version.png")
    )
    page.locator(".schedule-history-item").first.click()
    page.locator("#teamNamesDisplay").get_by_text("IT22101624").wait_for()
    page.locator("#teamNamesDisplay").get_by_text("IT22109576").wait_for()
    page.evaluate("""() => {
        for (const id of ['ipmsThemeToggle', 'btnOpenAcademicScheduler']) {
            document.getElementById(id)?.style.setProperty('display', 'none', 'important');
        }
    }""")
    page.locator("#teamNamesDisplay").locator("xpath=../..").screenshot(
        path=str(OUTPUT / "12_history_restored_member_ids.png")
    )
    browser.close()
