import unittest

from fastapi import HTTPException

from app.modules.applications.status import (
    DEFAULT_APPLICATION_STATUS,
    normalize_application_status,
    validate_application_status,
)
from app.services.job_service import _validate_range_pair
from app.services.scoring_service import compute_final_score, score_application


class ApplicationStatusTests(unittest.TestCase):
    def test_legacy_statuses_normalize_for_existing_rows(self):
        self.assertEqual(normalize_application_status("pending"), DEFAULT_APPLICATION_STATUS)
        self.assertEqual(normalize_application_status("hold"), "on-hold")
        self.assertEqual(normalize_application_status("on_hold"), "on-hold")

    def test_explicit_status_input_rejects_unknown_values(self):
        with self.assertRaises(ValueError):
            validate_application_status("banana")

    def test_explicit_status_input_accepts_canonical_values(self):
        self.assertEqual(validate_application_status("Shortlisted"), "shortlisted")
        self.assertEqual(validate_application_status("on hold"), "on-hold")


class ScoringContractTests(unittest.TestCase):
    def test_unknown_ai_recommendation_uses_review_manually_score(self):
        skills_score, final_score, breakdown = score_application(
            job_title="Backend Engineer",
            job_description="Build Python APIs",
            job_required_skills=["Python"],
            resume_structured_json='{"sections":{"skills":{"items":["Python"]}}}',
            resume_ai_structured_json=None,
            semantic_score=0.0,
            ai_recommendation="Unexpected Label",
        )

        self.assertEqual(skills_score, 100.0)
        self.assertEqual(breakdown["ai_score"], 40.0)
        self.assertEqual(final_score, compute_final_score(
            skills_score=1.0,
            experience_score=0.0,
            semantic_score=0.0,
            ai_evaluation_score=0.4,
        ))


class JobValidationTests(unittest.TestCase):
    def test_range_pair_rejects_inverted_values(self):
        with self.assertRaises(HTTPException):
            _validate_range_pair(20, 10, "Salary")

    def test_range_pair_allows_partial_values(self):
        self.assertIsNone(_validate_range_pair(20, None, "Salary"))
        self.assertIsNone(_validate_range_pair(None, 20, "Salary"))


if __name__ == "__main__":
    unittest.main()
