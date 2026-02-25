import json


def test_extract_first_json_object_handles_wrapped_json():
    from backend.app.services.ai_common import extract_first_json_object

    raw = "here you go:\n\n{ \"a\": 1, \"b\": {\"c\": 2} }\nthanks"
    obj = extract_first_json_object(raw)
    assert obj["a"] == 1
    assert obj["b"]["c"] == 2


def test_apply_flow_uses_ai_score_and_persists_ai_structured_json(client, db_session, monkeypatch):
    """
    When Gemini is configured, apply should:
    - use AI score/explanation (best-effort)
    - persist Resume.ai_structured_json
    """
    from backend.app.services.ai_client import GeminiMeta
    import backend.app.services.ai_job_match as ajm
    import backend.app.services.ai_resume_structuring as ars
    from backend.app.models.application import Application
    from backend.app.models.resume import Resume

    # Enable AI in the imported service modules (they import config constants at import-time).
    monkeypatch.setattr(ars, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ajm, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ars, "GEMINI_MODEL", "gemini-test")
    monkeypatch.setattr(ajm, "GEMINI_MODEL", "gemini-test")

    async def fake_structured_call(**kwargs):
        payload = {
            "version": 1,
            "sections": {
                "skills": {"text": "Skills\nPython", "items": ["Python"], "primary": ["Python"], "secondary": []},
                "experience": {"text": "Experience", "bullets": ["Built APIs"]},
                "education": {"text": "Education", "items": ["BSc"]},
            },
            "raw": {"warnings": []},
        }
        return json.dumps(payload), GeminiMeta(model="gemini-test", latency_ms=1, status_code=200, retries=0)

    async def fake_match_call(**kwargs):
        payload = {
            "education_summary": {"score": 82, "summary": "CS degree is relevant for backend fundamentals. Solid base for APIs and data work."},
            "projects_summary": {"score": 90, "summary": "Projects show hands-on programming and problem solving. Evidence of shipping features is present."},
            "work_experience_summary": {"score": 70, "summary": "Some experience demonstrating teamwork and responsibility. Limited direct backend role history."},
            "overall_match_score": 88,
        }
        return json.dumps(payload), GeminiMeta(model="gemini-test", latency_ms=1, status_code=200, retries=0)

    monkeypatch.setattr(ars, "gemini_generate_content", fake_structured_call)
    monkeypatch.setattr(ajm, "gemini_generate_content", fake_match_call)

    # recruiter creates job
    r = client.post("/auth/signup", json={"email": "rec_ai@example.com", "password": "Testpass123!", "role": "recruiter", "name": "R"})
    assert r.status_code == 200, r.text
    rec_login = client.post("/auth/login", json={"email": "rec_ai@example.com", "password": "Testpass123!", "role": "recruiter"}).json()
    rec_token = rec_login["access_token"]
    job = client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {rec_token}"},
        json={"title": "Backend Dev", "description": "Need Python APIs", "status": "active"},
    ).json()["job"]

    # candidate applies
    r = client.post("/auth/signup", json={"email": "cand_ai@example.com", "password": "Testpass123!", "role": "candidate", "name": "C"})
    assert r.status_code == 200, r.text
    cand_login = client.post("/auth/login", json={"email": "cand_ai@example.com", "password": "Testpass123!", "role": "candidate"}).json()
    cand_token = cand_login["access_token"]

    pdf_bytes = b"%PDF-1.4\nPython\n"
    resp = client.post(
        f"/jobs/{job['id']}/apply",
        headers={"Authorization": f"Bearer {cand_token}"},
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code in (200, 201), resp.text
    app = resp.json()["application"]

    assert abs(app["match_score"] - 0.88) < 1e-6
    assert app.get("ai_sections") is not None
    assert int(app.get("ai_overall_match_score") or 0) == 88

    # persisted application score
    db_app = db_session.query(Application).filter(Application.id == app["id"]).first()
    assert db_app is not None
    assert abs(float(db_app.match_score) - 0.88) < 1e-6

    # persisted AI structured JSON on resume
    db_resume = db_session.query(Resume).filter(Resume.id == app["resume_id"]).first()
    assert db_resume is not None
    assert db_resume.ai_structured_json and "Python" in db_resume.ai_structured_json


def test_resume_upload_persists_ai_structured_json(client, db_session, monkeypatch):
    from backend.app.services.ai_client import GeminiMeta
    import backend.app.services.ai_resume_structuring as ars
    from backend.app.models.resume import Resume

    monkeypatch.setattr(ars, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ars, "GEMINI_MODEL", "gemini-test")

    async def fake_structured_call(**kwargs):
        payload = {
            "version": 1,
            "sections": {
                "skills": {"text": "Skills", "items": ["SQL"], "primary": ["SQL"], "secondary": []},
                "experience": {"text": "", "bullets": []},
                "education": {"text": "", "items": []},
            },
            "raw": {"warnings": []},
        }
        return json.dumps(payload), GeminiMeta(model="gemini-test", latency_ms=1, status_code=200, retries=0)

    monkeypatch.setattr(ars, "gemini_generate_content", fake_structured_call)

    r = client.post("/auth/signup", json={"email": "cand_up_ai@example.com", "password": "Testpass123!", "role": "candidate", "name": "C"})
    assert r.status_code == 200, r.text
    login = client.post("/auth/login", json={"email": "cand_up_ai@example.com", "password": "Testpass123!", "role": "candidate"}).json()
    token = login["access_token"]

    pdf_bytes = b"%PDF-1.4\nSQL\n"
    resp = client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    resume_id = resp.json()["resume"]["id"]

    db_resume = db_session.query(Resume).filter(Resume.id == resume_id).first()
    assert db_resume is not None
    assert db_resume.ai_structured_json and "SQL" in db_resume.ai_structured_json

