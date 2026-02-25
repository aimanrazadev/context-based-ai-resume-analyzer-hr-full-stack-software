def _signup(client, *, email: str, password: str, role: str, name: str = "Test User"):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": password, "role": role, "name": name},
    )


def _login(client, *, email: str, password: str, role: str | None):
    body = {"email": email, "password": password}
    if role is not None:
        body["role"] = role
    return client.post("/auth/login", json=body)


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_candidate_apply_uploads_resume_and_returns_score(client):
    # recruiter creates job
    _signup(
        client,
        email="rec_apply@example.com",
        password="Testpass123!",
        role="recruiter",
        name="Recruiter",
    )
    rec_login = _login(client, email="rec_apply@example.com", password="Testpass123!", role="recruiter").json()
    rec_token = rec_login["access_token"]

    job = client.post(
        "/jobs",
        headers=_auth_headers(rec_token),
        json={"title": "React Developer", "description": "Need React JavaScript CSS", "status": "active"},
    ).json()["job"]

    # candidate applies with a (minimal) PDF
    _signup(
        client,
        email="cand_apply@example.com",
        password="Testpass123!",
        role="candidate",
        name="Candidate",
    )
    cand_login = _login(client, email="cand_apply@example.com", password="Testpass123!", role="candidate").json()
    cand_token = cand_login["access_token"]

    pdf_bytes = b"%PDF-1.4\\nReact JavaScript CSS\\n"
    r = client.post(
        f"/jobs/{job['id']}/apply",
        headers=_auth_headers(cand_token),
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 200 or r.status_code == 201, r.text
    data = r.json()
    assert data["success"] is True
    app = data["application"]
    assert app["job_id"] == job["id"]
    assert isinstance(app["resume_id"], int)
    assert isinstance(app["match_score"], float)
    assert 0.0 <= app["match_score"] <= 1.0
    assert isinstance(app["ai_explanation"], str) and len(app["ai_explanation"]) > 5


def test_candidate_apply_rejects_invalid_extension(client):
    _signup(
        client,
        email="rec_apply2@example.com",
        password="Testpass123!",
        role="recruiter",
        name="Recruiter2",
    )
    rec_login = _login(client, email="rec_apply2@example.com", password="Testpass123!", role="recruiter").json()
    rec_token = rec_login["access_token"]
    job = client.post(
        "/jobs",
        headers=_auth_headers(rec_token),
        json={"title": "Backend", "description": "Need Python FastAPI", "status": "active"},
    ).json()["job"]

    _signup(
        client,
        email="cand_apply2@example.com",
        password="Testpass123!",
        role="candidate",
        name="Candidate2",
    )
    cand_login = _login(client, email="cand_apply2@example.com", password="Testpass123!", role="candidate").json()
    cand_token = cand_login["access_token"]

    r = client.post(
        f"/jobs/{job['id']}/apply",
        headers=_auth_headers(cand_token),
        files={"file": ("resume.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400, r.text

