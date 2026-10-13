"""
test_quality.py - Quality acceptance tests for task generation & scheduling.
Tests Priorities 1-6 fixes. Run with: python test_quality.py
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from main import should_accept_task, normalize_tasks, classify_task, estimate_durations, detect_dependencies

class TestActionabilityFilter(unittest.TestCase):
    """Priority 1: Vague/technology-only task rejection"""

    def test_transformers_rejected(self):
        t = {"name": "Transformers", "extraction_method": "GANTT"}
        ok, reason = should_accept_task(t)
        self.assertFalse(ok, f"'Transformers' should be rejected but got: {reason}")

    def test_analysis_component_rejected_from_gantt(self):
        t = {"name": "Analysis Component", "extraction_method": "GANTT"}
        ok, reason = should_accept_task(t)
        self.assertFalse(ok, f"'Analysis Component' (GANTT) should be rejected but got: {reason}")

    def test_machine_learning_rejected(self):
        t = {"name": "Machine Learning", "extraction_method": "NLP_FALLBACK"}
        ok, reason = should_accept_task(t)
        self.assertFalse(ok)

    def test_implement_transformer_model_accepted(self):
        t = {"name": "Implement Transformer-Based Semantic Model", "extraction_method": "METHODOLOGY_ACTION"}
        ok, reason = should_accept_task(t)
        self.assertTrue(ok, f"Should accept but got: {reason}")

    def test_build_sbert_engine_accepted(self):
        t = {"name": "Build The Sbert Student Vector Profiling Engine", "extraction_method": "GANTT"}
        ok, reason = should_accept_task(t)
        self.assertTrue(ok, f"Should accept but got: {reason}")

    def test_literature_review_wbs_accepted(self):
        """Short WBS tasks are valid even without action verbs"""
        t = {"name": "Literature Review", "extraction_method": "WBS_TABLE"}
        ok, reason = should_accept_task(t)
        self.assertTrue(ok, f"WBS 'Literature Review' should be accepted but got: {reason}")

    def test_system_testing_gantt_accepted(self):
        t = {"name": "System Testing", "extraction_method": "GANTT"}
        ok, reason = should_accept_task(t)
        self.assertTrue(ok, f"Should accept 'System Testing' but got: {reason}")

    def test_acronym_inside_task_accepted(self):
        """Acronyms inside real tasks must not be rejected"""
        cases = [
            ("Develop Nlp Module", "METHODOLOGY_ACTION"),
            ("Train Ml Classifier", "NLP_FALLBACK"),
            ("Design Rest Api", "NLP_FALLBACK"),
        ]
        for name, method in cases:
            t = {"name": name, "extraction_method": method}
            ok, reason = should_accept_task(t)
            self.assertTrue(ok, f"'{name}' should be accepted but got: {reason}")


class TestSemanticDuplication(unittest.TestCase):
    """Priority 2: Semantic containment deduplication"""

    def test_contained_task_removed(self):
        """'Develop IPMS Integration API' should be removed when the longer version exists"""
        tasks = [
            {"name": "Develop Ipms Integration Api", "extraction_method": "GANTT", "source_section": "Gantt Chart"},
            {"name": "Develop Ipms Integration Api And Supervisor Dashboard", "extraction_method": "GANTT", "source_section": "Gantt Chart"},
        ]
        result = normalize_tasks(tasks)
        names = [t["name"] for t in result]
        self.assertEqual(len(result), 1, f"Expected 1 task after containment merge, got {len(result)}: {names}")
        self.assertIn("Dashboard", result[0]["name"], "Should keep the longer/more specific task")

    def test_distinct_nlp_tasks_kept_separate(self):
        """NLP Proposal Parsing and NLP Semantic Grading are DISTINCT and must not be merged"""
        tasks = [
            {"name": "Implement Nlp-Based Proposal Parsing Engine", "extraction_method": "GANTT", "source_section": "Gantt Chart"},
            {"name": "Implement Nlp-Based Semantic Grading Engine", "extraction_method": "GANTT", "source_section": "Gantt Chart"},
        ]
        result = normalize_tasks(tasks)
        self.assertEqual(len(result), 2, f"Distinct NLP tasks must remain separate, got {len(result)}")

    def test_exact_duplicates_deduplicated(self):
        """Exact duplicates (after verb-stripping) should still be removed"""
        tasks = [
            {"name": "Build The Schedule Generation Engine", "extraction_method": "GANTT", "source_section": "Gantt Chart"},
            {"name": "Implement The Schedule Generation Engine", "extraction_method": "GANTT", "source_section": "Gantt Chart"},
        ]
        result = normalize_tasks(tasks)
        self.assertEqual(len(result), 1, "Exact semantic duplicates should collapse to 1")


class TestTaskClassification(unittest.TestCase):
    """Priority 3: Task type and complexity classification"""

    def test_nsga_classified_as_optimization_high(self):
        c = classify_task("Implement NSGA-II Multi-Objective Team Optimization")
        self.assertEqual(c["task_type"], "OPTIMIZATION")
        self.assertEqual(c["complexity"], "HIGH")

    def test_sbert_classified_as_ml_high(self):
        c = classify_task("Build The SBERT Student Vector Profiling Engine")
        self.assertIn(c["task_type"], {"ML_MODEL", "DEVELOPMENT"})
        self.assertEqual(c["complexity"], "HIGH")

    def test_literature_review_classified_low(self):
        c = classify_task("Literature Review")
        self.assertEqual(c["task_type"], "LITERATURE_REVIEW")
        self.assertEqual(c["complexity"], "LOW")

    def test_integration_api_classified_integration(self):
        c = classify_task("Develop IPMS Integration API And Supervisor Dashboard")
        self.assertEqual(c["task_type"], "INTEGRATION")

    def test_system_testing_classified_testing(self):
        c = classify_task("System Testing")
        self.assertEqual(c["task_type"], "TESTING")


class TestEffortDistribution(unittest.TestCase):
    """Priority 4: Weighted effort distribution (not uniform)"""

    def test_effort_not_uniform(self):
        tasks = [
            "Literature Review",
            "Implement NSGA-II Optimization",
            "System Testing",
        ]
        efforts = estimate_durations(tasks, team_size=4, duration_months=10, fp=50)
        self.assertEqual(len(efforts), 3)
        # Must NOT all be equal
        self.assertFalse(
            len(set(round(e) for e in efforts)) == 1,
            f"Effort should be differentiated but got: {efforts}"
        )

    def test_effort_conservation(self):
        """Sum of task efforts should approximately equal XGBoost total"""
        import pandas as pd
        import numpy as np
        tasks = [
            "Literature Review",
            "Implement NSGA-II Optimization",
            "Build The SBERT Profiling Engine",
            "Develop Integration API",
            "System Testing",
            "Final Evaluation",
        ]
        from main import models
        fp = 50
        team_size = 4
        duration_months = 10
        df = pd.DataFrame([{"function_points": fp, "log_fp": np.log1p(fp), "source_enc": 0}])
        total_effort = float(np.clip(
            np.expm1(models["xgboost"].predict(df)[0]),
            team_size * duration_months * 4 * 40 * 0.2,
            team_size * duration_months * 4 * 40 * 0.9
        ))
        efforts = estimate_durations(tasks, team_size, duration_months, fp)
        self.assertAlmostEqual(sum(efforts), total_effort, delta=total_effort * 0.05,
            msg=f"Effort conservation failed: sum={sum(efforts):.1f} vs total={total_effort:.1f}")

    def test_high_complexity_gets_more_effort_than_low(self):
        tasks = ["Literature Review", "Implement NSGA-II Multi-Objective Optimization"]
        efforts = estimate_durations(tasks, team_size=4, duration_months=10, fp=50)
        self.assertGreater(efforts[1], efforts[0],
            "NSGA-II optimization should get more effort than Literature Review")


class TestDependencyGraph(unittest.TestCase):
    """Priority 6: Phase-based dependency inference"""

    def test_design_before_development(self):
        tasks = ["System Design", "Develop Backend Module", "System Testing"]
        deps = detect_dependencies(tasks)
        # Task 1 (Development) should depend on Task 0 (Design)
        self.assertIn(0, deps[1], "Development should depend on Design")

    def test_same_phase_tasks_independent(self):
        """Two development tasks in the same phase should NOT depend on each other"""
        tasks = ["Implement NLP Parser", "Implement NSGA-II Optimizer"]
        deps = detect_dependencies(tasks)
        # Neither should depend on the other
        self.assertNotIn(1, deps[0], "Parallel dev tasks should not depend on each other")
        self.assertNotIn(0, deps[1], "Parallel dev tasks should not depend on each other")

    def test_dag_cycle_detection(self):
        """Dependency graph must not contain cycles"""
        tasks = ["System Design", "Implement Backend", "System Testing", "Final Evaluation"]
        deps = detect_dependencies(tasks)
        # Simple reachability check for cycles
        def has_cycle(graph):
            visited, stack = set(), set()
            def dfs(n):
                visited.add(n); stack.add(n)
                for nb in graph.get(n, []):
                    if nb not in visited:
                        if dfs(nb): return True
                    elif nb in stack:
                        return True
                stack.remove(n)
                return False
            return any(dfs(v) for v in graph if v not in visited)
        self.assertFalse(has_cycle(deps), "Dependency graph must be acyclic (DAG)")


class TestRegressionPrevious(unittest.TestCase):
    """Regression tests: previous bugs must NOT return"""

    def test_abbreviation_table_still_rejected(self):
        cases = ["Ai Artificial Intelligence", "Ml Machine Learning", "Nlp Natural Language Processing"]
        for name in cases:
            t = {"name": name, "extraction_method": "GANTT"}
            ok, _ = should_accept_task(t)
            self.assertFalse(ok, f"Abbreviation '{name}' should still be rejected")

    def test_glossary_still_rejected(self):
        cases = ["Rest Representational State Transfer", "Shap Shapley Additive Explanations"]
        for name in cases:
            t = {"name": name, "extraction_method": "GANTT"}
            ok, _ = should_accept_task(t)
            self.assertFalse(ok, f"Glossary '{name}' should still be rejected")

    def test_valid_wbs_short_tasks_still_accepted(self):
        cases = ["Literature Review", "System Testing", "Data Collection", "Final Evaluation"]
        for name in cases:
            t = {"name": name, "extraction_method": "WBS_TABLE"}
            ok, reason = should_accept_task(t)
            self.assertTrue(ok, f"Short WBS task '{name}' should still be accepted, got: {reason}")

    def test_acronym_in_real_task_still_accepted(self):
        cases = [
            ("Develop Nlp Model", "METHODOLOGY_ACTION"),
            ("Train Ml Classifier", "NLP_FALLBACK"),
        ]
        for name, method in cases:
            t = {"name": name, "extraction_method": method}
            ok, reason = should_accept_task(t)
            self.assertTrue(ok, f"Real task with acronym '{name}' must still be accepted, got: {reason}")


if __name__ == "__main__":
    print("=" * 60)
    print("IPMS Quality Acceptance Tests")
    print("=" * 60)
    unittest.main(verbosity=2)
