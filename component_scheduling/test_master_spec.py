import unittest
import json
import re
from collections import Counter
from pathlib import Path

import main
import postgres_db
import progress_tracking
from auth import AuthenticatedUser, authenticate, issue_token, verify_token


class TestMasterSpecRegressions(unittest.TestCase):
    def test_github_evidence_requires_the_assigned_student(self):
        task = {"assigned_to": "IT22114662", "is_collaborative": False}
        self.assertEqual(
            ("LINKED", "IT22114662"),
            progress_tracking._github_assignment_decision(task, "IT22114662", "IT22114662"),
        )
        self.assertEqual(
            ("UNASSIGNED_AUTHOR", "IT22114662"),
            progress_tracking._github_assignment_decision(task, "IT22114662", "IT22117014"),
        )
        self.assertEqual(
            ("UNMAPPED_AUTHOR", "IT22114662"),
            progress_tracking._github_assignment_decision(task, "IT22114662", None),
        )
        shared = {"assigned_to": "All Members", "is_collaborative": True}
        self.assertEqual(
            ("LINKED", "All Members"),
            progress_tracking._github_assignment_decision(shared, "All Members", "IT22117014"),
        )

    def test_future_task_is_not_reported_as_a_bottleneck(self):
        state, reason = progress_tracking._task_schedule_state(
            start_date="2026-11-30", end_date="2026-12-10", progress_percentage=10,
            status="IN_PROGRESS", today=progress_tracking.date(2026, 8, 31),
        )
        self.assertEqual("EARLY_PROGRESS", state)
        self.assertIsNone(reason)
        state, _ = progress_tracking._task_schedule_state(
            start_date="2026-11-30", end_date="2026-12-10", progress_percentage=0,
            status="NOT_STARTED", today=progress_tracking.date(2026, 8, 31),
        )
        self.assertEqual("UPCOMING", state)

    def test_viva_panel_has_read_only_progress_briefing(self):
        frontend = Path("frontend/academic_scheduler.js").read_text(encoding="utf-8")
        schema = Path("postgres_db.py").read_text(encoding="utf-8")
        self.assertIn("viva-progress-briefing", frontend)
        self.assertIn("/api/progress/viva-summary", frontend)
        self.assertIn("viva_progress_snapshots", schema)

    def test_five_row_wbs_stays_five_tasks(self):
        proposal = """WORK BREAKDOWN STRUCTURE
1. Literature Review
2. Requirements Analysis
3. System Design
4. Backend Development
5. System Testing
GANTT CHART
M1 M2 M3 M4 M5
"""
        tasks = main.extract_wbs_tasks(proposal)
        self.assertEqual(5, len(tasks), [task["name"] for task in tasks])
        self.assertTrue(all(task.get("source_evidence") for task in tasks))
        self.assertTrue(all(task.get("stable_id") for task in tasks))

    def test_toc_dot_leader_is_not_a_gantt_task(self):
        proposal = """TABLE OF CONTENTS
Gantt Chart ................................................................ 21
WORK BREAKDOWN STRUCTURE
1. Literature Review
2. Requirements Analysis
3. System Design
4. Backend Development
5. System Testing
6. Integration Testing
7. Final Evaluation
8. Report Writing
GANTT CHART
M1 M2 M3 M4 M5 M6
"""
        names = [task["name"] for task in main.extract_wbs_tasks(proposal)]
        self.assertFalse(any("..." in name for name in names), names)
        self.assertNotIn("Gantt Chart", names)

    def test_methodology_action_verb_need_not_start_sentence(self):
        proposal = """METHODOLOGY
The system will implement a transformer-based semantic model for proposal parsing.
This research aims to develop an adaptive workload balancing engine.
The evaluation will compare predicted schedules with completed project evidence.
"""
        names = [task["name"].lower() for task in main.extract_wbs_tasks(proposal)]
        self.assertTrue(any(name.startswith("implement") for name in names), names)
        self.assertTrue(any(name.startswith("develop") for name in names), names)
        self.assertTrue(any(name.startswith("compare") for name in names), names)

    def test_lpt_processes_all_tasks_independent_of_team_size(self):
        for task_count, member_count in ((12, 4), (10, 2)):
            efforts = [float(task_count - i) for i in range(task_count)]
            members = [f"Member {i + 1}" for i in range(member_count)]
            assignments, loads = main.cold_start_lpt_assign(efforts, members)
            self.assertEqual(task_count, len(assignments))
            self.assertAlmostEqual(sum(efforts), sum(loads.values()))

    def test_cycle_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            main.validate_dependency_dag({0: [2], 1: [0], 2: [1]}, 3)

    def test_api_routes_are_unique(self):
        keys = [
            (route.path, tuple(sorted(getattr(route, "methods", ()) or ())))
            for route in main.app.routes
            if route.path.startswith("/api/")
        ]
        self.assertFalse([key for key, count in Counter(keys).items() if count > 1])

    def test_application_uses_postgresql_not_sqlite(self):
        source = Path(main.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import sqlite3", source)
        self.assertNotIn("sqlite3.connect", source)
        self.assertNotIn("schedule_drift.db", source)
        self.assertTrue(main.DATABASE_URL.startswith("postgresql://"))

    def test_postgresql_parameter_translation_preserves_literals(self):
        sql = "SELECT * FROM tasks WHERE project_id=? AND note='why?'"
        self.assertEqual(
            "SELECT * FROM tasks WHERE project_id=%s AND note='why?'",
            postgres_db._translate_qmark(sql),
        )

    def test_postgresql_academic_event_returns_id_and_rolls_back(self):
        connection = postgres_db.connect()
        try:
            cursor = connection.cursor()
            cursor.execute(
                """INSERT INTO academic_events
                   (event_type, group_id, status, created_at) VALUES (?, ?, ?, ?)""",
                ("VALIDATION", "codex_pg_event", "Scheduled", "2026-08-30"),
            )
            self.assertIsInstance(cursor.lastrowid, int)
            connection.rollback()
            count = connection.execute(
                "SELECT COUNT(*) FROM academic_events WHERE group_id=?",
                ("codex_pg_event",),
            ).fetchone()[0]
            self.assertEqual(0, count)
        finally:
            connection.rollback()
            connection.close()

    def test_balance_score_does_not_hide_overload(self):
        balance = main.calculate_workload_balance({
            "IT22114662": 256.6,
            "IT22101624": 177.4,
            "IT22117014": 173.4,
            "IT22109576": 173.4,
        })
        self.assertEqual(18.2, balance["cv_percent"])
        self.assertEqual(81.8, balance["balance_score_pct"])
        self.assertAlmostEqual(1.48, balance["max_to_min_ratio"], places=2)
        self.assertTrue(balance["overload_detected"])
        self.assertEqual("GOOD", balance["cv_balance_label"])
        self.assertEqual("OVERLOADED", balance["balance_label"])

    def test_final_guard_moves_only_individual_tasks_and_resolves_ratio(self):
        loads = {"A": 256.6, "B": 177.4, "C": 173.4, "D": 173.4}
        assignments = [{
            "task_id": 1,
            "task_name": "Individual implementation",
            "assigned_to": "A",
            "effort_hours": 40.0,
            "is_collaborative": False,
            "is_parallel": False,
            "assign_method": "XGBoost Completion Classifier",
            "assign_reason": "Initial model choice.",
            "component_name": "Component A",
        }]
        moves = main.rebalance_final_assignments(
            assignments, loads, {member: f"Component {member}" for member in loads}
        )
        final_balance = main.calculate_workload_balance(loads)
        self.assertEqual(1, len(moves))
        self.assertEqual("A", moves[0]["from_member"])
        self.assertFalse(final_balance["overload_detected"])
        self.assertLessEqual(final_balance["max_to_min_ratio"], 1.40)
        self.assertTrue(assignments[0]["final_guard_triggered"])

    def test_frontend_has_no_duplicate_element_ids(self):
        html_path = Path(main.__file__).parent / "frontend" / "index.html"
        element_ids = re.findall(r'\bid=["\']([^"\']+)["\']', html_path.read_text(encoding="utf-8"))
        duplicates = [element_id for element_id, count in Counter(element_ids).items() if count > 1]
        self.assertEqual([], duplicates)

    def test_light_theme_is_scoped_and_available_on_scheduler_pages(self):
        frontend = Path(main.__file__).parent / "frontend"
        theme = (frontend / "theme-toggle.js").read_text(encoding="utf-8")
        self.assertIn(':root[data-theme="light"]', theme)
        self.assertNotIn("p, span, label, li, td, th, div", theme)
        for page_name in ("index.html", "team_portal.html", "progress.html"):
            page = (frontend / page_name).read_text(encoding="utf-8")
            self.assertIn("theme-toggle.js", page, page_name)

    def test_schedule_history_summary_restores_project_and_team(self):
        schedule = [{
            "task_id": 1,
            "task_name": "System Design",
            "assigned_to": "IT22114662",
            "effort_hours": 16.5,
            "duration_days": 4,
            "start_date": "2026-09-01",
            "end_date": "2026-09-04",
        }]
        summary = main._schedule_history_summary(
            (7, "GROUP-01", 3, json.dumps(schedule), "2026-08-30T20:00:00")
        )
        self.assertEqual("GROUP-01", summary["project_id"])
        self.assertEqual("IT22114662", summary["schedule"][0]["assigned_to"])
        self.assertEqual("IT22114662", summary["schedule"][0]["component_owner"])
        self.assertFalse(summary["schedule"][0]["is_collaborative"])
        self.assertFalse(summary["schedule"][0]["is_parallel"])
        self.assertEqual(["IT22114662"], summary["team_members"])
        self.assertEqual(4, summary["total_duration_days"])
        self.assertEqual(16.5, summary["total_effort_hours"])

    def test_fresh_and_history_ownership_use_same_all_members_lane(self):
        task = {
            "task_id": 1,
            "task_name": "Literature Review",
            "assigned_to": "IT22114662",
        }
        normalized = main._normalize_schedule_ownership([task])[0]
        self.assertEqual("All Members", normalized["assigned_to"])
        self.assertEqual("all", normalized["component_owner"])
        self.assertTrue(normalized["is_collaborative"])

    def test_generated_unassigned_task_stays_flat_until_workload_balance(self):
        task = {
            "task_id": 1,
            "task_name": "Literature Review",
            "assigned_to": "Unassigned",
            "assignment_stage": "UNASSIGNED",
            "is_collaborative": True,
        }
        normalized = main._normalize_schedule_ownership([task])[0]
        self.assertEqual("Unassigned", normalized["assigned_to"])
        self.assertEqual("", normalized["component_owner"])
        self.assertEqual("UNASSIGNED", normalized["assignment_stage"])

    def test_workload_assignment_marks_schedule_as_balanced(self):
        schedule = [{
            "task_id": 1,
            "task_name": "Database Migration",
            "assigned_to": "Unassigned",
            "assignment_stage": "UNASSIGNED",
        }]
        assignments = [{
            "task_id": 1,
            "assigned_to": "IT22114662",
            "is_collaborative": False,
            "is_parallel": False,
        }]
        balanced = main._apply_workload_assignments_to_schedule(schedule, assignments)[0]
        self.assertEqual("IT22114662", balanced["assigned_to"])
        self.assertEqual("BALANCED", balanced["assignment_stage"])

    def test_academic_panel_has_required_four_distinct_roles(self):
        staff = [
            (1, "Prof A", "AI", "", "09:00-17:00", "Professor", "a@example.test"),
            (2, "Dr B", "AI", "", "09:00-17:00", "Doctor", "b@example.test"),
            (3, "Lecturer C", "AI", "", "09:00-17:00", "Lecturer", "c@example.test"),
            (4, "Instructor D", "AI", "", "09:00-17:00", "Instructor", "d@example.test"),
            (5, "Prof E", "AI", "", "09:00-17:00", "Professor", "e@example.test"),
        ]
        panel = main.select_academic_panel([(1.0 - index / 10, person) for index, person in enumerate(staff)])
        role_counts = Counter(main._academic_role_key(item[1][5]) for item in panel)
        self.assertEqual({"prof_dr": 2, "lecturer": 1, "instructor": 1}, dict(role_counts))
        self.assertEqual(4, len({item[1][0] for item in panel}))

    def test_academic_panel_rejects_missing_required_role(self):
        staff = [
            (1, "Prof A", "AI", "", "09:00-17:00", "Professor", "a@example.test"),
            (2, "Dr B", "AI", "", "09:00-17:00", "Doctor", "b@example.test"),
            (3, "Lecturer C", "AI", "", "09:00-17:00", "Lecturer", "c@example.test"),
        ]
        with self.assertRaisesRegex(ValueError, "instructor"):
            main.select_academic_panel([(1.0, person) for person in staff])

    def test_academic_event_types_include_viva_and_pp(self):
        self.assertEqual(
            ("Proposal Presentation", "PP1", "PP2", "Viva"),
            main.ACADEMIC_EVENT_TYPES,
        )

    def test_academic_interval_overlap_guard(self):
        bookings = [(540, 600)]
        self.assertFalse(main._interval_free(bookings, 570, 630))
        self.assertTrue(main._interval_free(bookings, 600, 660))

    def test_signed_authentication_does_not_trust_browser_role(self):
        self.assertIsNone(authenticate("staff1", "staff@2026", "supervisor"))
        staff = authenticate("staff1", "staff@2026", "staff")
        self.assertEqual("staff", staff.role)
        token = issue_token(staff, lifetime_seconds=60)
        self.assertEqual(AuthenticatedUser("staff1", "Staff Member 1", "staff"), verify_token(token))

    def test_excel_style_dates_and_time_ranges_are_validated(self):
        parsed = main._parse_dates("2026-09-01 00:00:00;02/09/2026")
        self.assertEqual({"2026-09-01", "2026-09-02"}, {item.isoformat() for item in parsed})
        self.assertEqual(("09:00", "17:00"), main._parse_time_range("09:00:00 - 17:00:00"))
        with self.assertRaises(ValueError):
            main._parse_time_range("morning")

    def test_academic_generation_never_deletes_existing_schedules(self):
        source = Path(main.__file__).read_text(encoding="utf-8")
        academic_section = source[source.index('async def auto_schedule'):source.index('@app.get("/api/academic/events")')]
        self.assertNotIn("DELETE FROM academic_events", academic_section)
        self.assertIn("academic_schedule_batches", academic_section)


if __name__ == "__main__":
    unittest.main(verbosity=2)
