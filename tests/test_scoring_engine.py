import json


def test_scoring_engine_skills_overlap_and_final_score():
    from backend.app.services.scoring_engine import score_application

    job_title = "Backend Developer"
    job_description = "Need Python FastAPI SQL. Build REST APIs."
    resume_structured = {
        "version": 1,
        "sections": {
            "skills": {"items": ["Python", "FastAPI", "AWS"], "text": "", "primary": [], "secondary": []},
            "experience": {"text": "", "items": []},
            "education": {"text": "", "items": []},
        },
        "raw": {"warnings": []},
    }
    skills_score, final_score, breakdown = score_application(
        job_title=job_title,
        job_description=job_description,
        job_required_skills=None,
        resume_structured_json=json.dumps(resume_structured),
        resume_ai_structured_json=None,
        semantic_score=0.8,
    )
    assert 0.0 <= skills_score <= 1.0
    assert 0 <= final_score <= 100
    assert breakdown["semantic_score"] == 0.8
    assert "matched_skills" in breakdown


def test_apply_persists_final_score_and_breakdown(client, db_session, monkeypatch):
    import backend.app.api.job as job_api
    from backend.app.models.application import Application

    # Make apply deterministic and fast
    monkeypatch.setattr(job_api, "resume_job_similarity", lambda *args, **kwargs: 0.9)
    monkeypatch.setattr(job_api, "extract_and_clean_resume_text", lambda **kwargs: {"clean_text": "Python, FastAPI, SQL"})

    # recruiter creates job
    client.post("/auth/signup", json={"email": "rec_m10@example.com", "password": "Testpass123!", "role": "recruiter", "name": "R"})
    rec_login = client.post("/auth/login", json={"email": "rec_m10@example.com", "password": "Testpass123!", "role": "recruiter"}).json()
    rec_token = rec_login["access_token"]
    job = client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {rec_token}"},
        json={"title": "Backend", "description": "Need Python FastAPI SQL", "status": "active"},
    ).json()["job"]

    # candidate applies
    client.post("/auth/signup", json={"email": "cand_m10@example.com", "password": "Testpass123!", "role": "candidate", "name": "C"})
    cand_login = client.post("/auth/login", json={"email": "cand_m10@example.com", "password": "Testpass123!", "role": "candidate"}).json()
    cand_token = cand_login["access_token"]

    r = client.post(
        f"/jobs/{job['id']}/apply",
        headers={"Authorization": f"Bearer {cand_token}"},
        files={"file": ("resume.pdf", b"%PDF-1.4\\n", "application/pdf")},
    )
    assert r.status_code in (200, 201), r.text
    payload = r.json()["application"]
    assert "final_score" in payload
    assert "score_breakdown" in payload
    assert payload["final_score"] >= 0

    db_app = db_session.query(Application).filter(Application.id == payload["id"]).first()
    assert db_app is not None
    assert db_app.final_score is not None
    assert db_app.score_breakdown_json
    assert db_app.semantic_score is not None
    assert db_app.skills_score is not None


def test_ranked_candidates_endpoint_sorts(client, monkeypatch):
    import backend.app.api.job as job_api

    # recruiter creates job
    client.post("/auth/signup", json={"email": "rec_rank@example.com", "password": "Testpass123!", "role": "recruiter", "name": "R"})
    rec_login = client.post("/auth/login", json={"email": "rec_rank@example.com", "password": "Testpass123!", "role": "recruiter"}).json()
    rec_token = rec_login["access_token"]
    job = client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {rec_token}"},
        json={"title": "Backend", "description": "Need Python FastAPI SQL", "status": "active"},
    ).json()["job"]

    # Two candidates apply; we control semantic score per call
    sem_scores = [0.95, 0.10]

    def fake_sem(*args, **kwargs):
        return sem_scores.pop(0)

    monkeypatch.setattr(job_api, "resume_job_similarity", fake_sem)
    monkeypatch.setattr(job_api, "extract_and_clean_resume_text", lambda **kwargs: {"clean_text": "Python, FastAPI"})

    for i in range(2):
        email = f"cand_rank_{i}@example.com"
        client.post("/auth/signup", json={"email": email, "password": "Testpass123!", "role": "candidate", "name": f"C{i}"})
        cand_login = client.post("/auth/login", json={"email": email, "password": "Testpass123!", "role": "candidate"}).json()
        cand_token = cand_login["access_token"]
        r = client.post(
            f"/jobs/{job['id']}/apply",
            headers={"Authorization": f"Bearer {cand_token}"},
            files={"file": ("resume.pdf", b"%PDF-1.4\\n", "application/pdf")},
        )
        assert r.status_code in (200, 201), r.text

    ranked = client.get(
        f"/jobs/{job['id']}/ranked_candidates",
        headers={"Authorization": f"Bearer {rec_token}"},
    )
    assert ranked.status_code == 200, ranked.text
    rows = ranked.json()["candidates"]
    assert len(rows) == 2
    assert rows[0]["final_score"] >= rows[1]["final_score"]

