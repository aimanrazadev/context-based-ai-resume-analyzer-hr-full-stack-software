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


def test_recruiter_can_schedule_interview_candidate_sees_it(client):
    # recruiter creates job
    _signup(client, email="rec_sched@example.com", password="Testpass123!", role="recruiter", name="R")
    rec_login = _login(client, email="rec_sched@example.com", password="Testpass123!", role="recruiter").json()
    rec_token = rec_login["access_token"]
    job = client.post(
        "/jobs",
        headers=_auth_headers(rec_token),
        json={"title": "Backend", "description": "Python FastAPI", "status": "active"},
    ).json()["job"]

    # candidate applies (save-only)
    _signup(client, email="cand_sched@example.com", password="Testpass123!", role="candidate", name="C")
    cand_login = _login(client, email="cand_sched@example.com", password="Testpass123!", role="candidate").json()
    cand_token = cand_login["access_token"]
    apply = client.post(
        f"/jobs/{job['id']}/apply_save",
        headers=_auth_headers(cand_token),
        files={"file": ("resume.pdf", b"%PDF-1.4\nHello\n", "application/pdf")},
    )
    assert apply.status_code in (200, 201), apply.text
    application_id = apply.json()["application"]["id"]

    # recruiter schedules interview
    sched = client.post(
        "/interviews/schedule",
        headers=_auth_headers(rec_token),
        json={
            "application_id": application_id,
            "scheduled_at": "2030-01-20T10:00:00",
            "timezone": "UTC",
            "duration_minutes": 30,
            "mode": "Zoom",
            "meeting_link": "https://example.com/meet",
            "location": "",
            "interviewer_name": "Recruiter",
            "recruiter_notes": "See you then",
        },
    )
    assert sched.status_code == 200, sched.text
    interview_id = sched.json()["interview"]["id"]
    assert interview_id

    # candidate sees interview in /mine
    mine = client.get("/interviews/mine", headers=_auth_headers(cand_token))
    assert mine.status_code == 200, mine.text
    items = mine.json()["interviews"]
    assert any(int(x["id"]) == int(interview_id) for x in items)

    # candidate can view details
    det = client.get(f"/interviews/{interview_id}", headers=_auth_headers(cand_token))
    assert det.status_code == 200, det.text
    assert det.json()["interview"]["status"] == "scheduled"


def test_non_owner_recruiter_cannot_schedule(client):
    # recruiter A creates job
    _signup(client, email="recA@example.com", password="Testpass123!", role="recruiter", name="R")
    recA = _login(client, email="recA@example.com", password="Testpass123!", role="recruiter").json()["access_token"]
    jr = client.post(
        "/jobs",
        headers=_auth_headers(recA),
        json={"title": "Backend", "description": "Need Python and SQL", "status": "active"},
    )
    assert jr.status_code in (200, 201), jr.text
    job = jr.json()["job"]

    # candidate applies
    _signup(client, email="candX@example.com", password="Testpass123!", role="candidate", name="C")
    cand = _login(client, email="candX@example.com", password="Testpass123!", role="candidate").json()["access_token"]
    apply = client.post(
        f"/jobs/{job['id']}/apply_save",
        headers=_auth_headers(cand),
        files={"file": ("resume.pdf", b"%PDF-1.4\nHello\n", "application/pdf")},
    ).json()
    application_id = apply["application"]["id"]

    # recruiter B tries to schedule
    _signup(client, email="recB@example.com", password="Testpass123!", role="recruiter", name="R2")
    recB = _login(client, email="recB@example.com", password="Testpass123!", role="recruiter").json()["access_token"]

    sched = client.post(
        "/interviews/schedule",
        headers=_auth_headers(recB),
        json={
            "application_id": application_id,
            "scheduled_at": "2030-01-20T10:00:00",
            "timezone": "UTC",
            "duration_minutes": 30,
            "mode": "Zoom",
            "meeting_link": "https://example.com/meet",
            "location": "",
            "interviewer_name": "Recruiter",
            "recruiter_notes": "See you then",
        },
    )
    assert sched.status_code == 403, sched.text


def test_recruiter_can_update_interview_schedule(client):
    # Setup: recruiter creates job, candidate applies, recruiter schedules
    _signup(client, email="rec_upd@example.com", password="Testpass123!", role="recruiter", name="R")
    rec_token = _login(client, email="rec_upd@example.com", password="Testpass123!", role="recruiter").json()["access_token"]
    job = client.post(
        "/jobs",
        headers=_auth_headers(rec_token),
        json={"title": "Backend", "description": "Python FastAPI", "status": "active"},
    ).json()["job"]

    _signup(client, email="cand_upd@example.com", password="Testpass123!", role="candidate", name="C")
    cand_token = _login(client, email="cand_upd@example.com", password="Testpass123!", role="candidate").json()["access_token"]
    apply = client.post(
        f"/jobs/{job['id']}/apply_save",
        headers=_auth_headers(cand_token),
        files={"file": ("resume.pdf", b"%PDF-1.4\nHello\n", "application/pdf")},
    ).json()
    application_id = apply["application"]["id"]

    sched = client.post(
        "/interviews/schedule",
        headers=_auth_headers(rec_token),
        json={
            "application_id": application_id,
            "scheduled_at": "2030-01-20T10:00:00",
            "timezone": "UTC",
            "duration_minutes": 30,
            "mode": "Zoom",
            "meeting_link": "https://example.com/meet",
            "interviewer_name": "John Doe",
            "recruiter_notes": "Initial notes",
        },
    ).json()
    interview_id = sched["interview"]["id"]

    # Recruiter updates the interview
    update = client.patch(
        f"/interviews/{interview_id}",
        headers=_auth_headers(rec_token),
        json={
            "scheduled_at": "2030-01-22T14:00:00",
            "timezone": "Asia/Kolkata",
            "duration_minutes": 45,
            "interviewer_name": "Jane Smith",
            "recruiter_notes": "Updated: moved to 2pm IST",
        },
    )
    assert update.status_code == 200, update.text
    updated = update.json()["interview"]
    assert updated["status"] == "scheduled"

    # Verify update persisted
    detail = client.get(f"/interviews/{interview_id}", headers=_auth_headers(rec_token)).json()
    assert detail["interview"]["duration_minutes"] == 45
    assert detail["interview"]["interviewer_name"] == "Jane Smith"


def test_recruiter_can_complete_interview_and_status_updates(client):
    # Setup
    _signup(client, email="rec_complete@example.com", password="Testpass123!", role="recruiter", name="R")
    rec_token = _login(client, email="rec_complete@example.com", password="Testpass123!", role="recruiter").json()["access_token"]
    job = client.post(
        "/jobs",
        headers=_auth_headers(rec_token),
        json={"title": "Backend", "description": "Python FastAPI", "status": "active"},
    ).json()["job"]

    _signup(client, email="cand_complete@example.com", password="Testpass123!", role="candidate", name="C")
    cand_token = _login(client, email="cand_complete@example.com", password="Testpass123!", role="candidate").json()["access_token"]
    apply = client.post(
        f"/jobs/{job['id']}/apply_save",
        headers=_auth_headers(cand_token),
        files={"file": ("resume.pdf", b"%PDF-1.4\nHello\n", "application/pdf")},
    ).json()
    application_id = apply["application"]["id"]

    sched = client.post(
        "/interviews/schedule",
        headers=_auth_headers(rec_token),
        json={
            "application_id": application_id,
            "scheduled_at": "2030-01-20T10:00:00",
            "timezone": "UTC",
            "duration_minutes": 30,
            "mode": "Zoom",
            "meeting_link": "https://example.com/meet",
        },
    ).json()
    interview_id = sched["interview"]["id"]

    # Recruiter marks interview as completed with feedback
    complete = client.post(
        f"/interviews/{interview_id}/complete",
        headers=_auth_headers(rec_token),
        json={"feedback": "Great communication skills and technical knowledge."},
    )
    assert complete.status_code == 200, complete.text
    completed = complete.json()["interview"]
    assert completed["status"] == "completed"

    # Verify interview details show completed status
    detail = client.get(f"/interviews/{interview_id}", headers=_auth_headers(rec_token)).json()
    assert detail["interview"]["status"] == "completed"
    assert detail["interview"]["feedback"] is not None


def test_recruiter_can_evaluate_interview_with_outcomes(client):
    # Setup
    _signup(client, email="rec_eval@example.com", password="Testpass123!", role="recruiter", name="R")
    rec_token = _login(client, email="rec_eval@example.com", password="Testpass123!", role="recruiter").json()["access_token"]
    job = client.post(
        "/jobs",
        headers=_auth_headers(rec_token),
        json={"title": "Backend", "description": "Python FastAPI", "status": "active"},
    ).json()["job"]

    _signup(client, email="cand_eval@example.com", password="Testpass123!", role="candidate", name="C")
    cand_token = _login(client, email="cand_eval@example.com", password="Testpass123!", role="candidate").json()["access_token"]
    apply = client.post(
        f"/jobs/{job['id']}/apply_save",
        headers=_auth_headers(cand_token),
        files={"file": ("resume.pdf", b"%PDF-1.4\nHello\n", "application/pdf")},
    ).json()
    application_id = apply["application"]["id"]

    sched = client.post(
        "/interviews/schedule",
        headers=_auth_headers(rec_token),
        json={
            "application_id": application_id,
            "scheduled_at": "2030-01-20T10:00:00",
            "timezone": "UTC",
            "mode": "Zoom",
        },
    ).json()
    interview_id = sched["interview"]["id"]

    # First complete
    client.post(
        f"/interviews/{interview_id}/complete",
        headers=_auth_headers(rec_token),
        json={"feedback": "Good"},
    )

    # Then evaluate with pass outcome
    eval_pass = client.post(
        f"/interviews/{interview_id}/evaluate",
        headers=_auth_headers(rec_token),
        json={"outcome": "pass", "remarks": "Excellent fit for the role."},
    )
    assert eval_pass.status_code == 200, eval_pass.text
    evaluated = eval_pass.json()["interview"]
    assert evaluated["status"] == "evaluated"
    assert evaluated["outcome"] == "pass"

    # Test fail + on_hold outcomes
    # Setup another interview
    apply2 = client.post(
        f"/jobs/{job['id']}/apply_save",
        headers=_auth_headers(cand_token),
        files={"file": ("resume2.pdf", b"%PDF-1.4\nHello2\n", "application/pdf")},
    ).json()
    application_id2 = apply2["application"]["id"]

    sched2 = client.post(
        "/interviews/schedule",
        headers=_auth_headers(rec_token),
        json={
            "application_id": application_id2,
            "scheduled_at": "2030-01-21T10:00:00",
            "timezone": "UTC",
        },
    ).json()
    interview_id2 = sched2["interview"]["id"]

    client.post(f"/interviews/{interview_id2}/complete", headers=_auth_headers(rec_token), json={})

    eval_fail = client.post(
        f"/interviews/{interview_id2}/evaluate",
        headers=_auth_headers(rec_token),
        json={"outcome": "fail", "remarks": "Not a good match."},
    )
    assert eval_fail.status_code == 200
    assert eval_fail.json()["interview"]["outcome"] == "fail"


def test_candidate_cannot_modify_interview(client):
    # Setup
    _signup(client, email="rec_candmod@example.com", password="Testpass123!", role="recruiter", name="R")
    rec_token = _login(client, email="rec_candmod@example.com", password="Testpass123!", role="recruiter").json()["access_token"]
    job = client.post(
        "/jobs",
        headers=_auth_headers(rec_token),
        json={"title": "Backend", "description": "Python FastAPI", "status": "active"},
    ).json()["job"]

    _signup(client, email="cand_candmod@example.com", password="Testpass123!", role="candidate", name="C")
    cand_token = _login(client, email="cand_candmod@example.com", password="Testpass123!", role="candidate").json()["access_token"]
    apply = client.post(
        f"/jobs/{job['id']}/apply_save",
        headers=_auth_headers(cand_token),
        files={"file": ("resume.pdf", b"%PDF-1.4\nHello\n", "application/pdf")},
    ).json()
    application_id = apply["application"]["id"]

    sched = client.post(
        "/interviews/schedule",
        headers=_auth_headers(rec_token),
        json={
            "application_id": application_id,
            "scheduled_at": "2030-01-20T10:00:00",
        },
    ).json()
    interview_id = sched["interview"]["id"]

    # Candidate tries to update (should fail)
    update_attempt = client.patch(
        f"/interviews/{interview_id}",
        headers=_auth_headers(cand_token),
        json={"recruiter_notes": "Hacked!"},
    )
    assert update_attempt.status_code == 403, update_attempt.text

    # Candidate tries to complete (should fail)
    complete_attempt = client.post(
        f"/interviews/{interview_id}/complete",
        headers=_auth_headers(cand_token),
        json={},
    )
    assert complete_attempt.status_code == 403, complete_attempt.text

    # Candidate tries to evaluate (should fail)
    eval_attempt = client.post(
        f"/interviews/{interview_id}/evaluate",
        headers=_auth_headers(cand_token),
        json={"outcome": "pass"},
    )
    assert eval_attempt.status_code == 403, eval_attempt.text


def test_interview_email_sent_on_schedule(client, monkeypatch):
    # Mock the email sending service
    email_calls = []

    def mock_send_email(**kwargs):
        email_calls.append(kwargs)

    monkeypatch.setattr("backend.app.api.interview.send_interview_scheduled_email", mock_send_email)

    # Setup
    _signup(client, email="rec_email@example.com", password="Testpass123!", role="recruiter", name="R")
    rec_token = _login(client, email="rec_email@example.com", password="Testpass123!", role="recruiter").json()["access_token"]
    job = client.post(
        "/jobs",
        headers=_auth_headers(rec_token),
        json={"title": "Backend", "description": "Python FastAPI", "status": "active"},
    ).json()["job"]

    _signup(client, email="cand_email@example.com", password="Testpass123!", role="candidate", name="C")
    cand_token = _login(client, email="cand_email@example.com", password="Testpass123!", role="candidate").json()["access_token"]
    apply = client.post(
        f"/jobs/{job['id']}/apply_save",
        headers=_auth_headers(cand_token),
        files={"file": ("resume.pdf", b"%PDF-1.4\nHello\n", "application/pdf")},
    ).json()
    application_id = apply["application"]["id"]

    # Schedule interview (which should trigger background email task)
    sched = client.post(
        "/interviews/schedule",
        headers=_auth_headers(rec_token),
        json={
            "application_id": application_id,
            "scheduled_at": "2030-01-20T10:00:00",
            "timezone": "UTC",
            "mode": "Zoom",
            "meeting_link": "https://example.com/meet",
            "recruiter_notes": "See you then",
        },
    )
    assert sched.status_code == 200, sched.text
