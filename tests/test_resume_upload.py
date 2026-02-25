from pathlib import Path


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


def test_candidate_can_upload_pdf_and_list(client):
    _signup(
        client,
        email="cand_upload@example.com",
        password="Testpass123!",
        role="candidate",
        name="Cand Upload",
    )
    login = _login(client, email="cand_upload@example.com", password="Testpass123!", role="candidate").json()
    token = login["access_token"]

    pdf_bytes = b"%PDF-1.4\\n%Fake\\n"
    r = client.post(
        "/resumes/upload",
        headers=_auth_headers(token),
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["success"] is True
    resume = data["resume"]
    assert resume["original_filename"] == "resume.pdf"
    assert resume["stored_filename"].endswith(".pdf")
    assert resume["size_bytes"] == len(pdf_bytes)
    assert resume["file_path"].startswith("resumes/")

    r2 = client.get("/resumes/mine", headers=_auth_headers(token))
    assert r2.status_code == 200, r2.text
    rows = r2.json()["resumes"]
    assert len(rows) == 1
    assert rows[0]["id"] == resume["id"]


def test_upload_rejects_invalid_extension(client):
    _signup(
        client,
        email="cand_upload2@example.com",
        password="Testpass123!",
        role="candidate",
        name="Cand Upload2",
    )
    login = _login(client, email="cand_upload2@example.com", password="Testpass123!", role="candidate").json()
    token = login["access_token"]

    r = client.post(
        "/resumes/upload",
        headers=_auth_headers(token),
        files={"file": ("resume.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400, r.text


def test_upload_rejects_too_large(client):
    _signup(
        client,
        email="cand_upload3@example.com",
        password="Testpass123!",
        role="candidate",
        name="Cand Upload3",
    )
    login = _login(client, email="cand_upload3@example.com", password="Testpass123!", role="candidate").json()
    token = login["access_token"]

    from backend.app.api.resume import MAX_RESUME_BYTES

    big = b"a" * (MAX_RESUME_BYTES + 1)
    r = client.post(
        "/resumes/upload",
        headers=_auth_headers(token),
        files={"file": ("resume.pdf", big, "application/pdf")},
    )
    assert r.status_code == 413, r.text

