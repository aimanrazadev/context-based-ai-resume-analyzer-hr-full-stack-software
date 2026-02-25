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


def test_signup_recruiter_success(client):
    r = _signup(
        client,
        email="recruiter@example.com",
        password="Testpass123!",
        role="recruiter",
        name="Recruiter",
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user"]["role"] == "recruiter"
    assert isinstance(data.get("access_token"), str) and len(data["access_token"]) > 10


def test_signup_candidate_success(client):
    r = _signup(
        client,
        email="candidate@example.com",
        password="Testpass123!",
        role="candidate",
        name="Candidate",
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user"]["role"] == "candidate"


def test_login_role_mismatch_fails(client):
    _signup(
        client,
        email="cand2@example.com",
        password="Testpass123!",
        role="candidate",
        name="Cand2",
    )
    r = _login(client, email="cand2@example.com", password="Testpass123!", role="recruiter")
    assert r.status_code == 403, r.text


def test_login_invalid_credentials_fails(client):
    _signup(
        client,
        email="rec2@example.com",
        password="Testpass123!",
        role="recruiter",
        name="Rec2",
    )
    r = _login(client, email="rec2@example.com", password="wrong", role="recruiter")
    assert r.status_code == 401, r.text


def test_logout_endpoint_exists(client):
    r = client.post("/auth/logout")
    assert r.status_code == 200, r.text
    assert "message" in r.json()


def test_candidate_cannot_create_job(client):
    _signup(
        client,
        email="cand3@example.com",
        password="Testpass123!",
        role="candidate",
        name="Cand3",
    )
    login = _login(client, email="cand3@example.com", password="Testpass123!", role="candidate").json()
    token = login["access_token"]

    r = client.post(
        "/jobs",
        json={"title": "PM", "description": "A" * 20, "status": "active"},
        headers=_auth_headers(token),
    )
    assert r.status_code == 403, r.text


def test_recruiter_can_create_job_and_validation_applies(client):
    _signup(
        client,
        email="rec3@example.com",
        password="Testpass123!",
        role="recruiter",
        name="Rec3",
    )
    login = _login(client, email="rec3@example.com", password="Testpass123!", role="recruiter").json()
    token = login["access_token"]

    # Active job requires title + description (runtime rule).
    r = client.post(
        "/jobs",
        json={"status": "active"},
        headers=_auth_headers(token),
    )
    assert r.status_code in (400, 422), r.text

    r2 = client.post(
        "/jobs",
        json={"title": "Product Manager", "description": "A" * 20, "status": "active"},
        headers=_auth_headers(token),
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["job"]["title"] == "Product Manager"

