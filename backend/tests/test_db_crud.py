from backend.app.models.application import Application
from backend.app.models.candidate import Candidate
from backend.app.models.embedding import Embedding
from backend.app.models.interview import Interview
from backend.app.models.job import Job
from backend.app.models.resume import Resume
from backend.app.models.user import User


def test_db_crud_operations_and_relationships(db_session):
    # Create recruiter user
    recruiter = User(email="crud_recruiter@example.com", password="hashed", role="recruiter", name="Recruiter")
    db_session.add(recruiter)
    db_session.commit()
    db_session.refresh(recruiter)
    assert recruiter.id is not None

    # Create job owned by recruiter
    job = Job(
        user_id=recruiter.id,
        job_title="CRUD Job",
        job_description="A" * 20,
        status="active",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    assert job.user.email == "crud_recruiter@example.com"

    # Create candidate
    candidate = Candidate(name="Cand", email="crud_candidate@example.com")
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)
    assert candidate.id is not None

    # Create resume
    resume = Resume(
        file_path="resumes/1/resume.pdf",
        stored_filename="resume.pdf",
        original_filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=5,
        extracted_text="hello",
        candidate_id=candidate.id,
    )
    db_session.add(resume)
    db_session.commit()
    db_session.refresh(resume)
    assert resume.candidate.id == candidate.id
    assert len(candidate.resumes) == 1

    # Create application
    application = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
        match_score=0.9,
        status="submitted",
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    assert application.job.id == job.id
    assert application.candidate.id == candidate.id

    # Create interview
    interview = Interview(
        application_id=application.id,
        transcript="hello",
        clarity_score=0.8,
        relevance_score=0.7,
        overall_fit=0.75,
    )
    db_session.add(interview)
    db_session.commit()
    db_session.refresh(interview)
    assert interview.application.id == application.id
    assert len(application.interviews) == 1

    # Update application
    application.status = "reviewed"
    db_session.add(application)
    db_session.commit()
    updated = db_session.query(Application).filter(Application.id == application.id).first()
    assert updated.status == "reviewed"

    # Delete interview then application
    db_session.delete(interview)
    db_session.commit()
    assert db_session.query(Interview).filter(Interview.id == interview.id).first() is None

    db_session.delete(application)
    db_session.commit()
    assert db_session.query(Application).filter(Application.id == application.id).first() is None


def test_delete_job_removes_row_and_dependents(client, db_session):
    # Create recruiter + login
    client.post(
        "/auth/signup",
        json={"email": "del_recruiter@example.com", "password": "pw", "role": "recruiter", "name": "R"},
    )
    login = client.post("/auth/login", json={"email": "del_recruiter@example.com", "password": "pw", "role": "recruiter"})
    token = (login.json() or {}).get("access_token")
    assert token

    # Create candidate user + login
    client.post(
        "/auth/signup",
        json={"email": "del_candidate@example.com", "password": "pw", "role": "candidate", "name": "C"},
    )
    login_c = client.post("/auth/login", json={"email": "del_candidate@example.com", "password": "pw", "role": "candidate"})
    token_c = (login_c.json() or {}).get("access_token")
    assert token_c

    # Create job
    r = client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Del Job", "description": "A" * 30, "status": "active"},
    )
    job_id = (r.json() or {}).get("job", {}).get("id")
    assert job_id

    # Create dependent rows directly (application + interview + embeddings) to simulate real usage.
    recruiter_user = db_session.query(User).filter(User.email == "del_recruiter@example.com").first()
    assert recruiter_user
    candidate_user = db_session.query(User).filter(User.email == "del_candidate@example.com").first()
    assert candidate_user

    # Candidate row may not exist yet; create it the same way API does.
    cand = db_session.query(Candidate).filter(Candidate.email == candidate_user.email).first()
    if not cand:
        cand = Candidate(name=candidate_user.name or "C", email=candidate_user.email)
        db_session.add(cand)
        db_session.commit()
        db_session.refresh(cand)

    resume = Resume(
        file_path=f"applications/{job_id}/{cand.id}/x.pdf",
        stored_filename="x.pdf",
        original_filename="x.pdf",
        content_type="application/pdf",
        size_bytes=10,
        extracted_text="hello",
        candidate_id=cand.id,
    )
    db_session.add(resume)
    db_session.commit()
    db_session.refresh(resume)

    app = Application(job_id=int(job_id), candidate_id=cand.id, resume_id=resume.id, match_score=0.1, status="submitted")
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)
    app_id = int(app.id)
    resume_id = int(resume.id)

    it = Interview(application_id=app.id, transcript="t", clarity_score=0.1, relevance_score=0.1, overall_fit=0.1)
    db_session.add(it)
    db_session.add(Embedding(entity_type="job", entity_id=int(job_id), model="m", dim=1, text_hash="h", vector_json="[0.1]"))
    db_session.add(Embedding(entity_type="resume", entity_id=int(resume.id), model="m", dim=1, text_hash="h2", vector_json="[0.2]"))
    db_session.commit()

    # Delete job via API
    d = client.delete(f"/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
    assert d.status_code == 200

    assert db_session.query(Job).filter(Job.id == int(job_id)).first() is None
    assert db_session.query(Application).filter(Application.job_id == int(job_id)).count() == 0
    assert db_session.query(Interview).filter(Interview.application_id == app_id).count() == 0
    assert db_session.query(Resume).filter(Resume.id == resume_id).count() == 0
    assert db_session.query(Embedding).filter(Embedding.entity_type == "job", Embedding.entity_id == int(job_id)).count() == 0
    assert db_session.query(Embedding).filter(Embedding.entity_type == "resume", Embedding.entity_id == resume_id).count() == 0

