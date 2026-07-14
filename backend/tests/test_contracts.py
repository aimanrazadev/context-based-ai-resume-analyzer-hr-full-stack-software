import unittest

from app.main import app
from app.modules.applications.status import normalize_application_status
from app.modules.matching.skills import canonical_skill, classify_required_skills


class ApplicationContractTests(unittest.TestCase):
    def test_ranked_candidates_route_is_registered(self):
        paths = {getattr(route, "path", "") for route in app.routes}
        self.assertIn("/jobs/{job_id:int}/ranked_candidates", paths)

    def test_recruiter_aggregate_routes_are_registered(self):
        paths = {getattr(route, "path", "") for route in app.routes}
        self.assertIn("/recruiter/dashboard", paths)
        self.assertIn("/recruiter/jobs", paths)
        self.assertIn("/recruiter/candidates", paths)

    def test_application_status_normalization(self):
        self.assertEqual(normalize_application_status("pending"), "not-reviewed")
        self.assertEqual(normalize_application_status("On Hold"), "on-hold")
        self.assertEqual(normalize_application_status("on_hold"), "on-hold")
        self.assertEqual(normalize_application_status("rejected"), "rejected")
        self.assertEqual(normalize_application_status("unknown"), "not-reviewed")

    def test_skill_aliases_and_classification(self):
        self.assertEqual(canonical_skill("PostgreSQL"), "sql")
        snapshot = classify_required_skills(
            text="Built React and PostgreSQL dashboards with REST APIs.",
            required_skills=["React", "MySQL", "FastAPI"],
        )
        self.assertEqual(snapshot["matched_skills"], ["React", "MySQL"])
        self.assertEqual(snapshot["missing_skills"], ["FastAPI"])


if __name__ == "__main__":
    unittest.main()
