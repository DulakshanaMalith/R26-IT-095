import unittest
from main import should_accept_task

class TestTaskAcceptance(unittest.TestCase):
    def test_abbreviation_table(self):
        cases = [
            "Ai Artificial Intelligence",
            "Ml Machine Learning",
            "Nlp Natural Language Processing"
        ]
        for c in cases:
            res, _ = should_accept_task({"name": c, "extraction_method": "GANTT"})
            self.assertFalse(res, f"Should reject {c}")

    def test_glossary(self):
        cases = [
            "Rest Representational State Transfer",
            "Shap Shapley Additive Explanations"
        ]
        for c in cases:
            res, _ = should_accept_task({"name": c, "extraction_method": "GANTT"})
            self.assertFalse(res, f"Should reject {c}")

    def test_front_matter(self):
        cases = [
            "Student Id",
            "Supervisor Name",
            "Bsc Hons Degree",
            "Information Technology",
            "Declaration Of Authorship"
        ]
        for c in cases:
            res, _ = should_accept_task({"name": c, "extraction_method": "GANTT"})
            self.assertFalse(res, f"Should reject {c}")

    def test_valid_wbs(self):
        cases = [
            "Literature Review",
            "System Design",
            "Backend Development",
            "System Testing",
            "Final Evaluation"
        ]
        for c in cases:
            res, _ = should_accept_task({"name": c, "extraction_method": "WBS_TABLE"})
            self.assertTrue(res, f"Should accept {c}")

    def test_acronym_inside_task(self):
        cases = [
            "Develop Nlp Model",
            "Train Ml Classifier",
            "Design Rest Api"
        ]
        for c in cases:
            res, _ = should_accept_task({"name": c, "extraction_method": "METHODOLOGY_ACTION"})
            self.assertTrue(res, f"Should accept {c}")

    def test_weak_actionable(self):
        cases = [
            ("Machine Learning", False),
            ("Evaluate Neural Network", True)
        ]
        for c, exp in cases:
            res, _ = should_accept_task({"name": c, "extraction_method": "NLP_FALLBACK"})
            self.assertEqual(res, exp, f"Expected {exp} for {c}")

if __name__ == '__main__':
    unittest.main()
