import json


def test_cosine_similarity_basic():
    from backend.app.services.semantic_similarity import cosine_similarity

    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0


def test_hash_normalization_stable():
    from backend.app.services.embeddings import normalize_text, text_hash

    t1 = normalize_text("Hello   world\n\n")
    t2 = normalize_text("Hello world")
    assert t1 == t2
    assert text_hash(text=t1, model="m") == text_hash(text=t2, model="m")


def test_apply_returns_semantic_score_and_stores_embeddings(client, db_session, monkeypatch):
    """
    Integration: monkeypatch embed_text to avoid downloading models.
    """
    import backend.app.services.embeddings as emb
    import backend.app.api.job as job_api
    from backend.app.models.embedding import Embedding

    # Simple deterministic embedding:
    # - job text -> [1,0]
    # - resume text -> [1,0] if contains 'python' else [0,1]
    def fake_embed_text(text: str):
        t = (text or "").lower()
        if "python" in t:
            return [1.0, 0.0]
        return [0.0, 1.0]

    monkeypatch.setattr(emb, "embed_text", fake_embed_text)
    # Ensure resume extraction yields stable text for embeddings (avoid flaky PDF parsing)
    monkeypatch.setattr(
        job_api,
        "extract_and_clean_resume_text",
        lambda **kwargs: {"clean_text": "Python experience building APIs"},
    )

    # recruiter creates job
    r = client.post("/auth/signup", json={"email": "rec_sem@example.com", "password": "Testpass123!", "role": "recruiter", "name": "R"})
    assert r.status_code == 200
    rec_login = client.post("/auth/login", json={"email": "rec_sem@example.com", "password": "Testpass123!", "role": "recruiter"}).json()
    rec_token = rec_login["access_token"]
    job = client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {rec_token}"},
        json={"title": "Python Dev", "description": "Need Python APIs", "status": "active"},
    ).json()["job"]

    # candidate applies
    r = client.post("/auth/signup", json={"email": "cand_sem@example.com", "password": "Testpass123!", "role": "candidate", "name": "C"})
    assert r.status_code == 200
    cand_login = client.post("/auth/login", json={"email": "cand_sem@example.com", "password": "Testpass123!", "role": "candidate"}).json()
    cand_token = cand_login["access_token"]

    pdf_bytes = b"%PDF-1.4\nPython\n"
    resp = client.post(
        f"/jobs/{job['id']}/apply",
        headers={"Authorization": f"Bearer {cand_token}"},
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code in (200, 201), resp.text
    data = resp.json()
    app = data["application"]
    assert "semantic_score" in app
    assert 0.0 <= float(app["semantic_score"]) <= 1.0

    # DB should have at least two embeddings (job + resume)
    rows = db_session.query(Embedding).all()
    assert len(rows) >= 2


def test_semantic_match_endpoint(client, db_session, monkeypatch):
    import backend.app.services.embeddings as emb
    from backend.app.models.embedding import Embedding
    from backend.app.models.resume import Resume

    monkeypatch.setattr(emb, "embed_text", lambda t: [1.0, 0.0])

    # recruiter creates job
    client.post("/auth/signup", json={"email": "rec_sem2@example.com", "password": "Testpass123!", "role": "recruiter", "name": "R"})
    rec_login = client.post("/auth/login", json={"email": "rec_sem2@example.com", "password": "Testpass123!", "role": "recruiter"}).json()
    rec_token = rec_login["access_token"]
    job = client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {rec_token}"},
        json={"title": "Python Dev", "description": "Need Python", "status": "active"},
    ).json()["job"]

    # candidate uploads resume (so we have a resume_id)
    client.post("/auth/signup", json={"email": "cand_sem2@example.com", "password": "Testpass123!", "role": "candidate", "name": "C"})
    cand_login = client.post("/auth/login", json={"email": "cand_sem2@example.com", "password": "Testpass123!", "role": "candidate"}).json()
    cand_token = cand_login["access_token"]

    pdf_bytes = b"%PDF-1.4\nPython\n"
    up = client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {cand_token}"},
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert up.status_code == 201, up.text
    resume_id = up.json()["resume"]["id"]

    # ensure embedding exists (best-effort)
    assert db_session.query(Embedding).count() >= 1
    assert db_session.query(Resume).filter(Resume.id == resume_id).first() is not None

    r = client.get(
        f"/jobs/{job['id']}/semantic_match/{resume_id}",
        headers={"Authorization": f"Bearer {cand_token}"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["success"] is True
    assert 0.0 <= float(payload["semantic_score"]) <= 1.0

